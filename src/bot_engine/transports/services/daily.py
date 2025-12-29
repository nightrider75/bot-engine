#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Daily transport implementation for Bot Engine.

This module provides comprehensive Daily video conferencing integration including
audio/video streaming, transcription, recording, dial-in/out functionality, and
real-time communication features.
"""

import warnings

from bot_engine.transports.daily.transport import *

with warnings.catch_warnings():
    warnings.simplefilter("always")
    warnings.warn(
        "Module `bot_engine.transports.services.daily` is deprecated, "
        "use `bot_engine.transports.daily.transport` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
