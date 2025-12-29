#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Placeholder language detection processor with user language events."""

from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel

from bot_engine.frames.frames import (
    Frame,
    LLMUpdateSettingsFrame,
    TTSUpdateSettingsFrame,
)
from bot_engine.processors.frame_processor import FrameDirection, FrameProcessor
from bot_engine.transcriptions.language import Language

logger = logger.opt(ansi=True)


class BaseLanguageDetectionProcessor(FrameProcessor):
    """A processor that will eventually detect a user's language.

    For now it simply logs the frames that pass through and emits a default
    English language event so that consumers can be wired up before the actual
    detection logic is ready.
    """

    class InputParams(BaseModel):
        """Input parameters for Language detector.

        Parameters:
            start_language: Starting language for the detector.
            language_range: The available languages to choose from if empty all languages will be allowed.
            update_tts: Whether to generate a TTSUpdateSettingsFrame.
            update_text_filter: Whether to generate a TTSUpdateSettingsFrame for updating text normalization filters.
            update_llm: Whether to generate a LLMUpdateSettingsFrame.
        """

        start_language: Optional[Language] = None
        language_range: List[Language] = []
        update_tts: bool = False
        update_text_filter: bool = False
        update_llm: bool = False

    def __init__(self, *, params: InputParams = InputParams(), **kwargs):
        """Initialize the processor."""
        super().__init__(**kwargs)
        self._params = params
        self._current_user_language = params.start_language

        self._register_event_handler("user_language_changed")

    @property
    def current_user_language(self) -> Language:
        """Return the currently detected (or default) language for the user."""
        return self._current_user_language

    async def update_user_language(self, language: Language):
        """Update the property and emit the change event when the language changes."""
        if language == self._current_user_language:
            return
        if self._params.language_range and language not in self._params.language_range:
            return

        previous_language = self._current_user_language
        self._current_user_language = language
        await self._emit_user_language_changed(previous_language)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Log the frame, emit the initial language event, and continue the pipeline."""
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)

    async def _emit_user_language_changed(self, previous_language: Optional[Language]):
        await self._call_event_handler(
            "user_language_changed", self._current_user_language, previous_language
        )
        await self._push_language_update_frames(self._current_user_language)

    async def _push_language_update_frames(self, language: Language):
        """Emit downstream frames to keep services in sync with the detected language."""
        tts_settings = self._build_tts_settings(language)
        if tts_settings:
            await self.push_frame(
                TTSUpdateSettingsFrame(settings=tts_settings), FrameDirection.DOWNSTREAM
            )
        if self._params.update_llm:
            await self.push_frame(
                LLMUpdateSettingsFrame(settings={"language": language}),
                FrameDirection.DOWNSTREAM,
            )

    def _build_tts_settings(self, language: Language) -> Optional[Dict[str, Any]]:
        """Build the TTS settings payload for the detected language."""
        if not (self._params.update_tts or self._params.update_text_filter):
            return None

        settings: Dict[str, Any] = {}

        if self._params.update_tts:
            settings["language"] = language

        if self._params.update_text_filter:
            settings["text_filter"] = {"language": language}

        return settings
