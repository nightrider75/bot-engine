#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Placeholder language detection processor with user language events."""

import string
from collections import defaultdict
from typing import List, Optional

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
from bot_engine.processors.language_detection.google_static_detector import (
    StaticLanguageDetectionProcessor,
)
from bot_engine.transcriptions.language import Language

logger = logger.opt(ansi=True)
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize


class WordBasedLanguageDetectionProcessor(StaticLanguageDetectionProcessor):
    """A processor that will eventually detect a user's language.

    For now it simply logs the frames that pass through and emits a default
    English language event so that consumers can be wired up before the actual
    detection logic is ready.
    """

    class InputParams(StaticLanguageDetectionProcessor.InputParams):
        """Parameters for the WordBasedLanguageDetectionProcessor.

        Attributes:
            min_words (int): The minimum number of words required to perform language detection.
            change_threshold_percent (int): The minimum percentage change required for a detected language
            to be considered valid.
        """

        min_words: int = 0
        change_threshold_percent: int = 50

    def __init__(self, *args, params: InputParams = InputParams(), **kwargs):
        """Initialize the processor."""
        super().__init__(*args, params=params, **kwargs)
        self._min_words = params.min_words
        self._change_thres = params.change_threshold_percent

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Log the frame, emit the initial language event, and continue the pipeline."""
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            filtered_text = self._clean_text(frame.text)
            filtered_words = filtered_text.split()
            if len(filtered_words) < self._min_words:
                logger.info(
                    f"Skipping detection for [{frame.text}] since filtered text len([{filtered_words}]) <{self._min_words}"
                )
                return

            lang_map = defaultdict(int)
            for word in filtered_words:
                lang = self._detect_language(word)
                if lang:
                    lang_map[lang] += 1
            total_elegible_words = sum(lang_map.values())
            detected_language = None
            detected_language_percent = 0
            for lang, words in lang_map.items():
                lang_percent = (words * 100) / total_elegible_words
                if lang_percent > self._change_thres and lang_percent > detected_language_percent:
                    detected_language_percent = lang_percent
                    detected_language = lang
            if detected_language:
                await self.update_user_language(detected_language)
