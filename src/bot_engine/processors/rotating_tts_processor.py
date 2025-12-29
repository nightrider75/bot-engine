"""Rotating TTS processor that handles API key rotation with pre-warmed service pool."""

from typing import Any, Dict, List, Optional, Type

from loguru import logger

from bot_engine.frames.frames import (
    CancelFrame,
    EndFrame,
    ErrorFrame,
    Frame,
    StartFrame,
    TextFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from bot_engine.processors.frame_processor import FrameDirection, FrameProcessor
from bot_engine.services.tts_service import TTSService
from bot_engine.utils.api_key_manager import APIKeyManager
from bot_engine.utils.auth_error_detector import is_auth_error


class RotatingTTSProcessor(FrameProcessor):
    """A processor that wraps TTS services with API key rotation.

    This processor uses a pre-warmed pool strategy for TTS services:
    - All TTS services are initialized at startup (warm pool)
    - On auth error, instantly switch to next service
    - Silent retry for stateless TTS (HTTP-based like OpenAI)
    - For WebSocket TTS (like ElevenLabs), maintains multiple connections

    Key features:
    - Works with ANY TTS service (ElevenLabs, OpenAI, Cartesia, etc.)
    - Per-key voice ID mapping (each API key can have different voice)
    - Instant failover with pre-warmed services
    - Automatic health tracking and recovery
    """

    def __init__(
        self,
        *,
        tts_service_class: Type[TTSService],
        tts_config: Dict[str, Any],
        api_keys: List[str],
        voice_mappings: Optional[Dict[str, str]] = None,
        default_voice_id: Optional[str] = None,
        cooldown_seconds: int = 300,
        max_failures: int = 3,
        **kwargs,
    ):
        """Initialize the rotating TTS processor.

        Args:
            tts_service_class: The TTS service class to instantiate (e.g., ElevenLabsTTSService)
            tts_config: Configuration dict for the TTS service (excluding api_key and voice_id)
            api_keys: List of API keys to rotate through
            voice_mappings: Dict mapping API key to voice ID (optional)
                           e.g., {"api_key_1": "voice_id_1", "api_key_2": "voice_id_2"}
            default_voice_id: Default voice ID if not in voice_mappings
            cooldown_seconds: Cooldown period for failed keys (default: 5 minutes)
            max_failures: Max failures before marking key as exhausted (default: 3)
            **kwargs: Additional arguments for FrameProcessor

        Example:
            >>> rotating_tts = RotatingTTSProcessor(
            ...     tts_service_class=ElevenLabsTTSService,
            ...     tts_config={"model": "eleven_turbo_v2_5"},
            ...     api_keys=["key1", "key2"],
            ...     voice_mappings={
            ...         "key1": "voice_alice",
            ...         "key2": "voice_bob"
            ...     },
            ...     default_voice_id="voice_default"
            ... )
        """
        super().__init__(**kwargs)

        self._tts_service_class = tts_service_class
        self._tts_config = tts_config
        self._voice_mappings = voice_mappings or {}
        self._default_voice_id = default_voice_id
        self._api_keys = api_keys

        # Initialize key manager
        self._key_manager = APIKeyManager(
            api_keys=api_keys,
            cooldown_seconds=cooldown_seconds,
            max_failures=max_failures,
        )

        # Pre-create ALL TTS services (warm pool) with correct voice per key
        self._tts_pool: List[TTSService] = []
        for api_key in api_keys:
            # Get voice ID for this key (from mapping or use default)
            voice_id = self._voice_mappings.get(api_key, self._default_voice_id)

            # Create TTS service with api_key and voice_id
            tts_service = tts_service_class(api_key=api_key, voice_id=voice_id, **tts_config)
            self._tts_pool.append(tts_service)

        # Track current service
        self._current_index = 0
        self._start_frame: Optional[StartFrame] = None

        # Statistics
        self._rotation_count = 0
        self._retry_count = 0

        logger.info(
            f"Initialized RotatingTTSProcessor with {len(api_keys)} pre-warmed "
            f"{tts_service_class.__name__} instances"
        )
        for i, (key, tts) in enumerate(zip(api_keys, self._tts_pool)):
            voice = getattr(tts, "_voice_id", "unknown")
            logger.debug(f"  TTS #{i}: key={key[:12]}... voice={voice}")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames, handling lifecycle and intercepting TTS text frames."""
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
        # Intercept TextFrame for TTS (but not transcription frames)
        elif isinstance(frame, TextFrame) and direction == FrameDirection.DOWNSTREAM:
            # Skip if this is a transcription frame (has user attribute)
            if hasattr(frame, "user") and frame.user:
                await self.push_frame(frame, direction)
            else:
                # This is TTS text - handle with rotation
                await self._handle_tts_request(frame, direction)
        # Intercept error frames from TTS service
        elif isinstance(frame, ErrorFrame) and direction == FrameDirection.UPSTREAM:
            if is_auth_error(frame.error):
                await self._handle_auth_error(frame.error, direction)
                return  # Don't propagate auth errors upstream
            else:
                await self.push_frame(frame, direction)
        # Forward other frames (including audio frames)
        else:
            await self.push_frame(frame, direction)

    async def _start(self, frame: StartFrame):
        """Start the processor and all TTS services in the pool."""
        self._start_frame = frame

        # Start ALL TTS services (warm them up)
        for i, tts in enumerate(self._tts_pool):
            try:
                await tts.start(frame)
                logger.debug(f"Started TTS service #{i} in pool")
            except Exception as e:
                logger.warning(f"Failed to start TTS service #{i}: {e}")

        logger.info(f"All {len(self._tts_pool)} TTS services pre-warmed and ready")

    async def _stop(self, frame: EndFrame):
        """Stop the processor and all TTS services in the pool."""
        for tts in self._tts_pool:
            try:
                await tts.stop(frame)
            except Exception as e:
                logger.warning(f"Error stopping TTS service: {e}")

    async def _cancel(self, frame: CancelFrame):
        """Cancel the processor and all TTS services in the pool."""
        for tts in self._tts_pool:
            try:
                await tts.cancel(frame)
            except Exception as e:
                logger.warning(f"Error cancelling TTS service: {e}")

    async def _handle_tts_request(self, frame: TextFrame, direction: FrameDirection):
        """Handle TTS text frame with automatic failover.

        Args:
            frame: TextFrame containing text to synthesize
            direction: Frame direction
        """
        current_tts = self._tts_pool[self._current_index]
        current_key = self._api_keys[self._current_index]
        text = frame.text

        try:
            # Try with current TTS (already warm!)
            logger.debug(f"Sending TTS request to service #{self._current_index}")

            # Process the TTS request
            audio_received = False
            async for tts_frame in current_tts.run_tts(text):
                # Check for errors
                if isinstance(tts_frame, ErrorFrame):
                    if is_auth_error(tts_frame.error):
                        logger.warning(
                            f"Auth error from TTS service #{self._current_index}: {tts_frame.error}"
                        )
                        # Try to rotate and retry
                        await self._rotate_and_retry_tts(text, direction)
                        return
                    else:
                        # Non-auth error, push it upstream
                        await self.push_frame(tts_frame, FrameDirection.UPSTREAM)
                        return
                else:
                    # Audio frame or other TTS frames - push downstream
                    if isinstance(tts_frame, TTSAudioRawFrame):
                        audio_received = True
                    await self.push_frame(tts_frame, direction)

            # Mark success if we got audio
            if audio_received:
                self._key_manager.mark_success(current_key)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"TTS service #{self._current_index} exception: {error_msg}")

            # Check if it's an auth error
            if is_auth_error(error_msg):
                await self._rotate_and_retry_tts(text, direction)
            else:
                # Non-auth error, push error frame
                await self.push_error(ErrorFrame(error=f"TTS error: {error_msg}"))

    async def _rotate_and_retry_tts(self, text: str, direction: FrameDirection):
        """Rotate to next key and retry TTS request.

        Args:
            text: Text to synthesize
            direction: Frame direction
        """
        # Mark current key as failed
        current_key = self._api_keys[self._current_index]
        self._key_manager.mark_failure(current_key, "TTS auth error")

        # Try to rotate
        next_key = self._key_manager.rotate_key("TTS auth error")

        if not next_key:
            # All keys exhausted
            logger.error("All TTS API keys exhausted")
            await self.push_error(ErrorFrame(error="All TTS API keys have failed or are exhausted"))
            return

        # Find the index for the next key
        self._current_index = self._api_keys.index(next_key)
        self._rotation_count += 1

        logger.info(
            f"TTS key rotation #{self._rotation_count}: "
            f"{current_key[:12]}... → {next_key[:12]}... "
            f"(voice: {self._tts_pool[self._current_index]._voice_id})"
        )

        # Retry with next TTS service (instant - already warmed!)
        self._retry_count += 1
        next_tts = self._tts_pool[self._current_index]

        try:
            logger.debug(f"Retrying TTS with service #{self._current_index}")

            # Retry the same text
            async for tts_frame in next_tts.run_tts(text):
                if isinstance(tts_frame, ErrorFrame):
                    if is_auth_error(tts_frame.error):
                        # This key also failed - try next
                        logger.warning(f"Backup TTS key also failed: {tts_frame.error}")
                        await self._rotate_and_retry_tts(text, direction)
                        return
                    else:
                        await self.push_frame(tts_frame, FrameDirection.UPSTREAM)
                        return
                else:
                    await self.push_frame(tts_frame, direction)

            # Mark success
            self._key_manager.mark_success(next_key)
            logger.info(f"TTS failover successful on retry #{self._retry_count}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"TTS retry failed: {error_msg}")

            if is_auth_error(error_msg):
                # Recursive retry with next key
                await self._rotate_and_retry_tts(text, direction)
            else:
                await self.push_error(ErrorFrame(error=f"TTS retry error: {error_msg}"))

    async def _handle_auth_error(self, error_msg: str, direction: FrameDirection):
        """Handle authentication error by marking key as failed.

        This is called when an ErrorFrame with auth error comes upstream.
        """
        current_key = self._api_keys[self._current_index]
        self._key_manager.mark_failure(current_key, error_msg)
        logger.warning(f"Marked TTS key {current_key[:12]}... as failed due to: {error_msg}")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the rotating TTS processor.

        Returns:
            Dictionary containing rotation statistics
        """
        current_key = self._api_keys[self._current_index]
        key_stats = self._key_manager.get_stats()

        return {
            **key_stats,
            "rotation_count": self._rotation_count,
            "retry_count": self._retry_count,
            "current_key": current_key,
            "current_voice": self._tts_pool[self._current_index]._voice_id,
            "tts_service": self._tts_service_class.__name__,
            "pool_size": len(self._tts_pool),
            "current_index": self._current_index,
        }
