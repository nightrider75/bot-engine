#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""WebSocket client transport implementation for Bot Engine.

This module provides a WebSocket client transport that enables bidirectional
communication over WebSocket connections, with support for audio streaming,
frame serialization, and connection management.
"""

import warnings

from bot_engine.transports.websocket.client import *

with warnings.catch_warnings():
    warnings.simplefilter("always")
    warnings.warn(
        "Module `bot_engine.transports.network.websocket_client` is deprecated, "
        "use `bot_engine.transports.websocket.client` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
