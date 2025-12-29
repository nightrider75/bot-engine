"""Rotating LLM processor that handles API key rotation with pre-warmed service pool."""

from typing import Any, Dict, List, Optional, Type

from loguru import logger

from bot_engine.frames.frames import (
    CancelFrame,
    EndFrame,
    ErrorFrame,
    Frame,
    LLMContextFrame,
    StartFrame,
)
from bot_engine.processors.aggregators.openai_llm_context import (
    OpenAILLMContextFrame,
)
from bot_engine.processors.frame_processor import FrameDirection, FrameProcessor
from bot_engine.services.llm_service import LLMService
from bot_engine.utils.api_key_manager import APIKeyManager
from bot_engine.utils.auth_error_detector import is_auth_error


class RotatingLLMProcessor(FrameProcessor):
    """A processor that wraps LLM services with API key rotation.

    Unlike STT rotation, LLM rotation uses a pre-warmed pool strategy:
    - All LLM services are initialized at startup (warm pool)
    - On auth error, instantly switch to next service (0ms delay)
    - Silent retry (user doesn't need to repeat - we have the full prompt)
    - No TTS notification needed (seamless failover)

    This provides instant failover with no user-visible delay.
    """

    def __init__(
        self,
        *,
        llm_service_class: Type[LLMService],
        llm_config: Dict[str, Any],
        api_keys: List[str],
        config_mappings: Optional[Dict[str, Dict[str, Any]]] = None,
        cooldown_seconds: int = 300,
        max_failures: int = 3,
        **kwargs,
    ):
        """Initialize the rotating LLM processor.

        Args:
            llm_service_class: The LLM service class to instantiate (e.g., OpenAILLMService)
            llm_config: Base configuration dict for the LLM service (excluding api_key)
            api_keys: List of API keys to rotate through
            config_mappings: Optional dict mapping api_key -> config overrides
                           (e.g., for different Azure endpoints per key)
            cooldown_seconds: Cooldown period for failed keys (default: 5 minutes)
            max_failures: Max failures before marking key as exhausted (default: 3)
            **kwargs: Additional arguments for FrameProcessor
        """
        super().__init__(**kwargs)

        self._llm_service_class = llm_service_class
        self._llm_config = llm_config
        self._config_mappings = config_mappings or {}

        # Initialize key manager
        self._key_manager = APIKeyManager(
            api_keys=api_keys,
            cooldown_seconds=cooldown_seconds,
            max_failures=max_failures,
        )

        # Pre-create ALL LLM services (warm pool)
        self._llm_pool: List[LLMService] = []
        for api_key in api_keys:
            # Merge base config with per-key config (if provided)
            service_config = {**llm_config}
            if api_key in self._config_mappings:
                service_config.update(self._config_mappings[api_key])
                logger.debug(f"Applied config mapping for key {api_key[:12]}...")

            llm_service = llm_service_class(api_key=api_key, **service_config)
            self._llm_pool.append(llm_service)

        # Track current service
        self._current_index = 0
        self._start_frame: Optional[StartFrame] = None

        logger.info(
            f"Initialized RotatingLLMProcessor with {len(api_keys)} pre-warmed "
            f"{llm_service_class.__name__} instances"
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames, handling lifecycle and intercepting LLM requests."""
        await super().process_frame(frame, direction)

        # Handle lifecycle frames
        if isinstance(frame, StartFrame):
            await self.push_frame(frame, direction)
            await self._start(frame)
        elif isinstance(frame, EndFrame):
            await self.push_frame(frame, direction)
            await self._stop(frame)
        elif isinstance(frame, CancelFrame):
            await self._cancel(frame)
            await self.push_frame(frame, direction)
        # Intercept LLM context frames
        elif isinstance(frame, (LLMContextFrame, OpenAILLMContextFrame)):
            await self._handle_llm_request(frame, direction)
        # Intercept error frames from LLM service
        elif isinstance(frame, ErrorFrame) and direction == FrameDirection.UPSTREAM:
            if is_auth_error(frame.error):
                await self._handle_auth_error(frame.error, direction)
                return  # Don't propagate auth errors upstream
            else:
                await self.push_frame(frame, direction)
        # Forward other frames
        else:
            await self.push_frame(frame, direction)

    async def _start(self, frame: StartFrame):
        """Start the processor and all LLM services in the pool."""
        self._start_frame = frame

        # Start ALL LLM services (warm them up)
        for i, llm in enumerate(self._llm_pool):
            try:
                await llm.start(frame)
                logger.debug(f"Started LLM service #{i} in pool")
            except Exception as e:
                logger.warning(f"Failed to start LLM service #{i}: {e}")

        logger.info(f"All {len(self._llm_pool)} LLM services pre-warmed and ready")

    async def _stop(self, frame: EndFrame):
        """Stop the processor and all LLM services in the pool."""
        for llm in self._llm_pool:
            try:
                await llm.stop(frame)
            except Exception as e:
                logger.warning(f"Error stopping LLM service: {e}")

    async def _cancel(self, frame: CancelFrame):
        """Cancel the processor and all LLM services in the pool."""
        for llm in self._llm_pool:
            try:
                await llm.cancel(frame)
            except Exception as e:
                logger.warning(f"Error cancelling LLM service: {e}")

    async def _handle_llm_request(self, frame: Frame, direction: FrameDirection):
        """Handle LLM context frame with automatic failover.

        Args:
            frame: LLMContextFrame or OpenAILLMContextFrame
            direction: Frame direction
        """
        current_llm = self._llm_pool[self._current_index]
        current_key = list(self._key_manager.keys.keys())[self._current_index]

        try:
            # Try with current LLM (already warm!)
            await current_llm.process_frame(frame, direction)

            # Success - mark key as working
            self._key_manager.mark_success(current_key)

        except Exception as e:
            error_msg = str(e)

            # Check if it's an auth error
            if is_auth_error(error_msg):
                logger.warning(
                    f"Auth error with LLM key {self._key_manager.keys[current_key].mask_key()}: {error_msg}"
                )

                # Mark current key as failed
                self._key_manager.mark_failure(current_key, error_msg)

                # Get next healthy service
                next_index = self._get_next_healthy_index()

                if next_index is not None:
                    # Instant switch to next service (already warm!)
                    old_index = self._current_index
                    self._current_index = next_index
                    self._key_manager.rotation_count += 1

                    logger.info(
                        f"Rotated LLM service: #{old_index} → #{next_index} "
                        f"(rotation #{self._key_manager.rotation_count})"
                    )

                    # Retry with next LLM (instant - no initialization delay!)
                    next_llm = self._llm_pool[next_index]
                    await next_llm.process_frame(frame, direction)

                    logger.info("✅ LLM failover successful (silent retry)")
                else:
                    # All keys exhausted
                    error_msg = "All LLM API keys exhausted"
                    logger.error(error_msg)
                    await self.push_error(ErrorFrame(error_msg, fatal=True))
            else:
                # Non-auth error, just propagate
                await self.push_error(ErrorFrame(error_msg, fatal=False))

    async def _handle_auth_error(self, error_msg: str, direction: FrameDirection):
        """Handle auth error from downstream LLM service.

        This is a backup handler in case the error comes as an ErrorFrame.

        Args:
            error_msg: The error message
            direction: Frame direction
        """
        current_key = list(self._key_manager.keys.keys())[self._current_index]

        logger.warning(f"Auth error detected from LLM service: {error_msg}")

        # Mark current key as failed
        self._key_manager.mark_failure(current_key, error_msg)

        # Get next healthy service
        next_index = self._get_next_healthy_index()

        if next_index is not None:
            self._current_index = next_index
            self._key_manager.rotation_count += 1
            logger.info(f"Switched to LLM service #{next_index}")
        else:
            error_msg = "All LLM API keys exhausted"
            logger.error(error_msg)
            await self.push_error(ErrorFrame(error_msg, fatal=True))

    def _get_next_healthy_index(self) -> Optional[int]:
        """Get the index of the next healthy LLM service.

        Returns:
            Index of next healthy service, or None if all exhausted
        """
        # Try to get next key from manager
        next_key = self._key_manager.get_next_key()

        if next_key is None:
            return None

        # Find the index of this key in our pool
        keys_list = list(self._key_manager.keys.keys())
        try:
            return keys_list.index(next_key)
        except ValueError:
            logger.error(f"Key {next_key} not found in pool")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about LLM key rotation.

        Returns:
            Dictionary with rotation statistics
        """
        stats = self._key_manager.get_stats()
        stats["llm_service"] = self._llm_service_class.__name__
        stats["pool_size"] = len(self._llm_pool)
        stats["current_index"] = self._current_index
        return stats
