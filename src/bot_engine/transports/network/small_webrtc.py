#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Small WebRTC transport implementation for Bot Engine.

This module provides a WebRTC transport implementation using aiortc for
real-time audio and video communication. It supports bidirectional media
streaming, application messaging, and client connection management.
"""

import warnings

from bot_engine.transports.smallwebrtc.transport import *

with warnings.catch_warnings():
    warnings.simplefilter("always")
    warnings.warn(
        "Module `bot_engine.transports.network.small_webrtc` is deprecated, "
        "use `bot_engine.transports.smallwebrtc.transport` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
