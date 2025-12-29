"""Rotating STT processor that handles API key rotation with user notification."""

import random
from typing import Any, Dict, List, Optional, Type

from loguru import logger

from bot_engine.frames.frames import (
    CancelFrame,
    EndFrame,
    ErrorFrame,
    Frame,
    StartFrame,
    TextFrame,
)
from bot_engine.processors.frame_processor import FrameDirection, FrameProcessor
from bot_engine.services.stt_service import STTService
from bot_engine.services.tts_service import TTSService
from bot_engine.utils.api_key_manager import APIKeyManager
from bot_engine.utils.auth_error_detector import is_auth_error

# Recovery phrases to tell user when rotation happens
RECOVERY_PHRASES = [
    "Sorry, I missed that. Could you please repeat?",
    "I didn't catch that. Could you say that again?",
    "Pardon me, could you please repeat?",
    "Sorry, there was a brief interruption. What did you say?",
    "I'm having trouble hearing. Could you say that again?",
]


class RotatingSTTProcessor(FrameProcessor):
    """A processor that wraps an STT service with API key rotation.

    When authentication errors occur, this processor:
    1. Detects the auth error
    2. Notifies the user via TTS
    3. Rotates to the next available API key
    4. Creates a new STT service instance with the new key
    5. Resumes listening

    This provides seamless failover with transparent user communication.
    """

    def __init__(
        self,
        *,
        stt_service_class: Type[STTService],
        stt_config: Dict[str, Any],
        api_keys: List[str],
        config_mappings: Optional[Dict[str, Dict[str, Any]]] = None,
        tts_service: Optional[TTSService] = None,
        recovery_phrases: Optional[List[str]] = None,
        cooldown_seconds: int = 300,
        max_failures: int = 3,
        **kwargs,
    ):
        """Initialize the rotating STT processor.

        Args:
            stt_service_class: The STT service class to instantiate (e.g., DeepgramSTTService)
            stt_config: Base configuration dict for the STT service (excluding api_key)
            api_keys: List of API keys to rotate through
            config_mappings: Optional dict mapping api_key -> config overrides
                           (e.g., for different Azure endpoints per key)
            tts_service: Optional TTS service to notify user of rotation
            recovery_phrases: Custom phrases to use when notifying user
            cooldown_seconds: Cooldown period for failed keys (default: 5 minutes)
            max_failures: Max failures before marking key as exhausted (default: 3)
            **kwargs: Additional arguments for FrameProcessor
        """
        super().__init__(**kwargs)

        self._stt_service_class = stt_service_class
        self._stt_config = stt_config
        self._config_mappings = config_mappings or {}
        self._tts_service = tts_service
        self._recovery_phrases = recovery_phrases or RECOVERY_PHRASES

        # Initialize key manager
        self._key_manager = APIKeyManager(
            api_keys=api_keys,
            cooldown_seconds=cooldown_seconds,
            max_failures=max_failures,
        )

        # Current STT service instance
        self._current_stt: Optional[STTService] = None
        self._start_frame: Optional[StartFrame] = None
        self._is_rotating = False

        logger.info(
            f"Initialized RotatingSTTProcessor with {len(api_keys)} keys for {stt_service_class.__name__}"
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames, handling lifecycle and intercepting errors."""
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
        # Intercept error frames from STT service
        elif isinstance(frame, ErrorFrame) and direction == FrameDirection.UPSTREAM:
            if is_auth_error(frame.error):
                await self._handle_auth_error(frame.error)
                return  # Don't propagate auth errors upstream
            else:
                await self.push_frame(frame, direction)
        # Forward other frames to/from current STT service
        else:
            if self._current_stt:
                await self._current_stt.process_frame(frame, direction)
            else:
                await self.push_frame(frame, direction)

    async def _start(self, frame: StartFrame):
        """Start the processor and initialize the first STT service."""
        self._start_frame = frame
        await self._initialize_stt_service()

    async def _stop(self, frame: EndFrame):
        """Stop the processor and current STT service."""
        if self._current_stt:
            await self._current_stt.stop(frame)

    async def _cancel(self, frame: CancelFrame):
        """Cancel the processor and current STT service."""
        if self._current_stt:
            await self._current_stt.cancel(frame)

    async def _initialize_stt_service(self):
        """Create STT service instance with current API key."""
        api_key = self._key_manager.get_current_key()

        if not api_key:
            error_msg = "No available API keys for STT service"
            logger.error(error_msg)
            await self.push_error(ErrorFrame(error_msg, fatal=True))
            return

        # Merge base config with per-key config (if provided)
        service_config = {**self._stt_config}
        if api_key in self._config_mappings:
            service_config.update(self._config_mappings[api_key])
            logger.debug(f"Applied config mapping for STT key {api_key[:12]}...")

        # Create new STT service instance with current key
        self._current_stt = self._stt_service_class(api_key=api_key, **service_config)

        # Wire up the STT service in the pipeline
        # Set this processor as the source for STT
        self._current_stt.link(self._next)

        # Start the STT service if we have a start frame
        if self._start_frame:
            await self._current_stt.start(self._start_frame)

        masked_key = self._key_manager.keys[api_key].mask_key()
        logger.info(f"Initialized STT service with key: {masked_key}")

    async def _handle_auth_error(self, error_msg: str):
        """Handle authentication error by rotating keys and notifying user.

        Args:
            error_msg: The authentication error message
        """
        if self._is_rotating:
            logger.warning("Already rotating, ignoring duplicate auth error")
            return

        self._is_rotating = True

        try:
            current_key = self._key_manager.current_key
            logger.error(f"Auth error detected: {error_msg}")

            # Mark current key as failed
            if current_key:
                self._key_manager.mark_failure(current_key, error_msg)

            # Notify user BEFORE rotating
            await self._notify_user_of_rotation()

            # Stop current STT service
            if self._current_stt:
                try:
                    await self._current_stt.stop(EndFrame())
                except Exception as e:
                    logger.warning(f"Error stopping STT service: {e}")

            # Rotate to next key
            next_key = self._key_manager.rotate_key(f"auth_error: {error_msg}")

            if next_key:
                # Create new STT service with new key
                await self._initialize_stt_service()
                logger.info("✅ Key rotation successful, ready to listen again")
            else:
                # All keys exhausted
                error_msg = "All API keys exhausted for STT service"
                logger.error(error_msg)

                if self._tts_service:
                    await self._tts_service.push_frame(
                        TextFrame("I'm experiencing technical difficulties. Please hold on.")
                    )

                await self.push_error(ErrorFrame(error_msg, fatal=True))

        finally:
            self._is_rotating = False

    async def _notify_user_of_rotation(self):
        """Notify user that we missed their input and need them to repeat."""
        if not self._tts_service:
            logger.debug("No TTS service configured, skipping user notification")
            return

        # Pick a random recovery phrase for natural variation
        message = random.choice(self._recovery_phrases)

        logger.info(f"Notifying user: '{message}'")

        # Push text frame to TTS service
        await self._tts_service.push_frame(TextFrame(message))

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about key rotation.

        Returns:
            Dictionary with rotation statistics
        """
        stats = self._key_manager.get_stats()
        stats["stt_service"] = self._stt_service_class.__name__
        return stats
