#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""LiveKit transport implementation for Bot Engine.

This module provides comprehensive LiveKit real-time communication integration
including audio streaming, data messaging, participant management, and room
event handling for conversational AI applications.
"""

import warnings

from bot_engine.transports.livekit.transport import *

with warnings.catch_warnings():
    warnings.simplefilter("always")
    warnings.warn(
        "Module `bot_engine.transports.services.livekit` is deprecated, "
        "use `bot_engine.transports.livekit.transport` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
