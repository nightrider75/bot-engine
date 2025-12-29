#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Custom frame types for OpenAI Realtime API integration."""

import warnings

from bot_engine.services.openai.realtime.frames import *

with warnings.catch_warnings():
    warnings.simplefilter("always")
    warnings.warn(
        "Types in bot_engine.services.openai_realtime.frames are deprecated. "
        "Please use the equivalent types from "
        "bot_engine.services.openai.realtime.frames instead.",
        DeprecationWarning,
        stacklevel=2,
    )
