#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Placeholder language detection processor with user language events."""

from typing import Optional

from loguru import logger

from bot_engine.frames.frames import (
    Frame,
    StartFrame,
    TranscriptionFrame,
)
from bot_engine.processors.frame_processor import FrameDirection, FrameProcessor
from bot_engine.processors.language_detection.base_language_detector import (
    BaseLanguageDetectionProcessor,
)
from bot_engine.transcriptions.language import Language

logger = logger.opt(ansi=True)


class TranscriberLanguageDetectionProcessor(BaseLanguageDetectionProcessor):
    """A processor that will eventually detect a user's language.

    For now it simply logs the frames that pass through and emits a default
    English language event so that consumers can be wired up before the actual
    detection logic is ready.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the processor."""
        super().__init__(*args, **kwargs)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Log the frame, emit the initial language event, and continue the pipeline."""
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            if frame.language:
                await self.update_user_language(frame.language)
