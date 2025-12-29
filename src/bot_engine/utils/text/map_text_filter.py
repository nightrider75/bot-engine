#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Mapping-based text filter for replacing text content using a dictionary mapping.

This module provides a text filter that performs simple text replacements based on
a provided mapping dictionary. It can be used for text normalization, abbreviation
expansion, or any other text transformation that can be expressed as key-value pairs.
"""

import re
from typing import Any, Dict, Mapping, Optional

from pydantic import BaseModel

from bot_engine.utils.text.base_text_filter import BaseTextFilter


class MapTextFilter(BaseTextFilter):
    """Text filter that performs mapping-based text replacements.

    This filter applies text replacements based on a provided mapping dictionary.
    Each key in the mapping will be replaced with its corresponding value in the
    input text. Replacements are performed in the order they appear in the mapping.
    """

    class InputParams(BaseModel):
        """Configuration parameters for mapping-based text filtering.

        Parameters:
            enable_text_filter: Whether to apply the text filter. Defaults to True.
            mappings: Dictionary mapping source text to replacement text.
            case_sensitive: Whether replacements should be case-sensitive. Defaults to True.
        """

        enable_text_filter: Optional[bool] = True
        mappings: Dict[str, str] = {}
        case_sensitive: Optional[bool] = True

    def __init__(self, params: Optional[InputParams] = None, **kwargs):
        """Initialize the mapping text filter.

        Args:
            params: Configuration parameters for filtering behavior.
            **kwargs: Additional keyword arguments passed to parent class.
        """
        super().__init__(**kwargs)
        self._settings = params or MapTextFilter.InputParams()

    async def update_settings(self, settings: Mapping[str, Any]):
        """Update the filter's configuration settings.

        Args:
            settings: Dictionary of setting names to values for configuration.
        """
        for key, value in settings.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)

    async def filter(self, text: str) -> str:
        """Apply mapping-based text replacements to the input text.

        Replacements are performed only on word boundaries to ensure that
        partial matches within words are not replaced.

        Args:
            text: The input text to be filtered.

        Returns:
            The filtered text with mappings applied.
        """
        if not self._settings.enable_text_filter or not self._settings.mappings:
            return text

        filtered_text = text

        # Apply each mapping replacement with word boundaries
        for source, target in self._settings.mappings.items():
            # Escape the source text for regex and add word boundaries
            escaped_source = re.escape(source)
            pattern = rf"\b{escaped_source}\b"

            if self._settings.case_sensitive:
                filtered_text = re.sub(pattern, target, filtered_text)
            else:
                # Case-insensitive replacement with word boundaries
                filtered_text = re.sub(pattern, target, filtered_text, flags=re.IGNORECASE)

        return filtered_text

    async def handle_interruption(self):
        """Handle interruption events in the processing pipeline.

        For mapping-based filtering, no special state needs to be reset
        as each filter operation is stateless.
        """
        # No state to reset for stateless mapping operations
        return

    async def reset_interruption(self):
        """Reset the filter state after an interruption has been handled.

        For mapping-based filtering, no special state needs to be reset
        as each filter operation is stateless.
        """
        # No state to reset for stateless mapping operations
        return
