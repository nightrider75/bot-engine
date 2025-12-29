#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Placeholder language detection processor with user language events."""

import re
import string
from typing import List, Optional

from langdetect import DetectorFactory, LangDetectException, detect_langs
from loguru import logger
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

from bot_engine.frames.frames import Frame, TranscriptionFrame
from bot_engine.processors.frame_processor import FrameDirection
from bot_engine.processors.language_detection.base_language_detector import (
    BaseLanguageDetectionProcessor,
)
from bot_engine.transcriptions.language import Language

DetectorFactory.seed = 0
logger = logger.opt(ansi=True)


class StaticLanguageDetectionProcessor(BaseLanguageDetectionProcessor):
    """A processor that detects a user's language using langdetect."""

    class InputParams(BaseLanguageDetectionProcessor.InputParams):
        """Input parameters for StaticLanguageDetectionProcessor.

        Attributes:
        nltk_stopword_languages: List of NLTK stopword language codes to filter out.
        stopwords: List of custom stopwords to filter from transcription text.
        stopwords_case_sensitive: Whether stopword filtering is case-sensitive.
        """

        # TODO: Use a list of Languages instead of list of str
        nltk_stopword_languages: List[str] = []
        stopwords: List[str] = []
        stopwords_case_sensitive: bool = False

    def __init__(self, *args, params: InputParams = InputParams(), **kwargs):
        """Initialize the processor."""
        super().__init__(*args, params=params, **kwargs)
        self._nltk_stopwords = list(string.punctuation)
        for lang in params.nltk_stopword_languages:
            if lang in stopwords.fileids():
                self._nltk_stopwords.extend(stopwords.words(lang))
        self._case_sensitive = params.stopwords_case_sensitive
        if not self._case_sensitive:
            self._stopwords = [i.lower() for i in params.stopwords]
        else:
            self._stopwords = params.stopwords

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Log the frame, detect or reuse language info, and continue the pipeline."""
        await super().process_frame(frame, direction)
        if not isinstance(frame, TranscriptionFrame):
            return

        transcription_text = self._clean_text(frame.text)
        language = self._detect_language(transcription_text)

        if language:
            await self.update_user_language(language)

    def _clean_text(self, text: str) -> str:
        """Cleanup text from stopwords etc."""
        if not self._case_sensitive:
            output = text.lower()
        else:
            output = text
        chunked_words = word_tokenize(output)
        filtered_words = [word for word in chunked_words if word not in self._stopwords]
        nltk_filtered_words = [
            word for word in filtered_words if word.lower() not in self._nltk_stopwords
        ]
        output = " ".join(nltk_filtered_words)
        logger.info(f"Language Detection Cleanup [{text}] => [{output}]")
        return output

    def _detect_language(self, text: str) -> Optional[Language]:
        """Try to detect a language from the transcription text."""
        candidate = text.strip()
        if not candidate:
            return None

        try:
            codes = detect_langs(candidate)
            for code in codes:
                try:
                    if self._params.language_range:
                        if Language(code.lang) in self._params.language_range:
                            return Language(code.lang)
                    else:
                        return Language(code.lang)
                except ValueError as e:
                    logger.error(f"Failed to identify language code: [{code}]: {e}")

        except LangDetectException:
            logger.error(f"langdetect could not classify text: [{text}]")
            return None

        return None
