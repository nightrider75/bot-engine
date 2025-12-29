#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Tavus transport implementation for Bot Engine.

This module provides integration with the Tavus platform for creating conversational
AI applications with avatars. It manages conversation sessions and provides real-time
audio/video streaming capabilities through the Tavus API.
"""

import warnings

from bot_engine.transports.tavus.transport import *

with warnings.catch_warnings():
    warnings.simplefilter("always")
    warnings.warn(
        "Module `bot_engine.transports.services.tavus` is deprecated, "
        "use `bot_engine.transports.tavus.transport` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
