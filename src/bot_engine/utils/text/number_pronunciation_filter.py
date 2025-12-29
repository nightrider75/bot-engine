#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Number pronunciation text filter for converting numbers to words.

This module provides a text filter that converts numeric values to their word
representations using the indic_numtowords library. It supports multiple languages
based on the language parameter provided in the configuration.
"""

import re
from typing import Any, Mapping, Optional

from indic_numtowords import num2words
from loguru import logger
from pydantic import BaseModel

from bot_engine.transcriptions.language import Language
from bot_engine.utils.text.base_text_filter import BaseTextFilter


class NumberPronunciationFilter(BaseTextFilter):
    """Text filter that converts numbers to their word representations.

    This filter identifies numeric values in text and replaces them with their
    word equivalents. The language for number pronunciation must be specified
    through the configuration parameters.
    """

    class InputParams(BaseModel):
        """Configuration parameters for number pronunciation filtering.

        Parameters:
            enable_text_filter: Whether to apply the text filter. Defaults to True.
            language: Language code for number pronunciation (e.g., 'en', 'hi'). Defaults to 'en'.
        """

        enable_text_filter: Optional[bool] = True
        language: Language = Language.EN

    def __init__(self, params: Optional[InputParams] = None, **kwargs):
        """Initialize the number pronunciation filter.

        Args:
            params: Configuration parameters for filtering behavior.
            **kwargs: Additional keyword arguments passed to parent class.
        """
        super().__init__(**kwargs)
        self._settings = params or NumberPronunciationFilter.InputParams()

    async def update_settings(self, settings: Mapping[str, Any]):
        """Update the filter's configuration settings.

        Args:
            settings: Dictionary of setting names to values for configuration.
        """
        for key, value in settings.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)

    async def filter(self, text: str) -> str:
        """Apply number pronunciation transformations to the input text.

        Args:
            text: The input text containing numbers to be converted.

        Returns:
            The filtered text with numbers converted to words.
        """
        if not self._settings.enable_text_filter:
            return text

        # Use the configured language
        language = self._settings.language or Language.EN

        logger.debug(f"Running number pronunciation fixes for language: {language}")

        # Convert numbers to words
        converted_text = self._replace_numbers_with_words(text, language)

        logger.debug(f"Text after number replacement: {converted_text}")
        return converted_text

    def _replace_numbers_with_words(self, text: str, language: str) -> str:
        """Replace numbers in text with their word representations.

        Args:
            text: The input text containing numbers.
            language: Language code for number pronunciation.

        Returns:
            Text with numbers converted to words.
        """

        def replace_match(match):
            """Replace numeric matches with word representations."""
            # TODO: Unify this with the templating utils to provide more exhaustive features
            number = match.group()
            try:
                number = number.replace(",", "")  # Remove commas from numbers
                if float(number) == int(float(number)):
                    return f"{num2words(int(number), lang=language.value)}"
                else:
                    normal = num2words(int(float(number)), lang=language.value)
                    decimal = num2words(round((float(number) % 1) * 100), lang=language.value)
                    if language == Language.EN:
                        return f"{normal} point {decimal}"
                    elif language == Language.HI:
                        return f"{normal} दशमलव {decimal}"
                    else:
                        logger.error(f"Received invalid language: {language}")
                        return f"{normal} point {decimal}"
            except Exception as e:
                logger.warning(f"Failed to convert number '{number}' to words: {e}")
                return number

        # Replace numbers with words
        text = re.sub(r"\b\d+(?:,\d+)*(?:\.\d+)?\b", replace_match, text)

        return text

    async def handle_interruption(self):
        """Handle interruption events in the processing pipeline.

        For number pronunciation filtering, no special state needs to be reset
        as each filter operation is stateless.
        """
        # No state to reset for stateless operations
        return

    async def reset_interruption(self):
        """Reset the filter state after an interruption has been handled.

        For number pronunciation filtering, no special state needs to be reset
        as each filter operation is stateless.
        """
        # No state to reset for stateless operations
        return
