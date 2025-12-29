#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import sys

from bot_engine.services import DeprecatedModuleProxy

from .stt import *
from .tts import *

sys.modules[__name__] = DeprecatedModuleProxy(globals(), "elevenlabs", "elevenlabs.[stt,tts]")
