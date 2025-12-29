#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Time replacement text filter for handling time-like patterns in text.

This module provides a text filter that processes time-like patterns in text,
such as preserving leading zeros or formatting time representations consistently.
"""

import re
from typing import Any, Mapping, Optional

from loguru import logger
from pydantic import BaseModel

from bot_engine.utils.text.base_text_filter import BaseTextFilter


class TimeReplacementFilter(BaseTextFilter):
    """Text filter that handles time-like patterns in text.

    This filter processes numeric patterns that might represent time values,
    ensuring consistent formatting and handling of leading zeros or other
    time-specific formatting requirements.
    """

    class InputParams(BaseModel):
        """Configuration parameters for time replacement filtering.

        Parameters:
            enable_text_filter: Whether to apply the text filter. Defaults to True.
            preserve_leading_zeros: Whether to preserve leading zeros in time patterns. Defaults to False.
            add_spacing: Whether to add spacing around time patterns. Defaults to True.
        """

        enable_text_filter: Optional[bool] = True
        preserve_leading_zeros: Optional[bool] = False
        add_spacing: Optional[bool] = True

    def __init__(self, params: Optional[InputParams] = None, **kwargs):
        """Initialize the time replacement filter.

        Args:
            params: Configuration parameters for filtering behavior.
            **kwargs: Additional keyword arguments passed to parent class.
        """
        super().__init__(**kwargs)
        self._settings = params or TimeReplacementFilter.InputParams()

    async def update_settings(self, settings: Mapping[str, Any]):
        """Update the filter's configuration settings.

        Args:
            settings: Dictionary of setting names to values for configuration.
        """
        for key, value in settings.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)

    async def filter(self, text: str) -> str:
        """Apply time replacement transformations to the input text.

        Args:
            text: The input text containing time patterns to be processed.

        Returns:
            The filtered text with time patterns processed.
        """
        if not self._settings.enable_text_filter:
            return text

        logger.debug("Processing time patterns in text")

        # Process time-like patterns
        processed_text = self._process_time_patterns(text)

        logger.debug(f"Text after time pattern processing: {processed_text}")
        return processed_text

    def _process_time_patterns(self, text: str) -> str:
        """Process time-like patterns in the text.

        Args:
            text: The input text containing time patterns.

        Returns:
            Text with time patterns processed according to settings.
        """

        def replace_time_pattern(match):
            """Handle time-like pattern replacement."""
            matched_str = match.group()

            if self._settings.preserve_leading_zeros:
                # Keep the original format with leading zeros
                processed_str = matched_str
            else:
                # Remove leading zeros
                processed_str = matched_str.lstrip("0")
                # Handle edge case where the entire string is zeros
                if not processed_str:
                    processed_str = "0"

            if self._settings.add_spacing:
                return f" {processed_str} "
            else:
                return processed_str

        # Match time-like patterns: numbers that could represent time
        # This pattern matches numbers with optional commas and decimals
        time_pattern = r"\b\d+(?:,\d+)*(?:\.\d+)?\b"

        processed_text = re.sub(time_pattern, replace_time_pattern, text)

        return processed_text

    async def handle_interruption(self):
        """Handle interruption events in the processing pipeline.

        For time replacement filtering, no special state needs to be reset
        as each filter operation is stateless.
        """
        # No state to reset for stateless operations
        return

    async def reset_interruption(self):
        """Reset the filter state after an interruption has been handled.

        For time replacement filtering, no special state needs to be reset
        as each filter operation is stateless.
        """
        # No state to reset for stateless operations
        return
