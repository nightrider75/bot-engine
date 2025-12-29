#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import warnings

from bot_engine.services.azure.realtime.llm import AzureRealtimeLLMService
from bot_engine.services.openai.realtime.events import (
    InputAudioNoiseReduction,
    InputAudioTranscription,
    SemanticTurnDetection,
    SessionProperties,
    TurnDetection,
)
from bot_engine.services.openai.realtime.llm import OpenAIRealtimeLLMService

with warnings.catch_warnings():
    warnings.simplefilter("always")
    warnings.warn(
        "Types in bot_engine.services.openai_realtime are deprecated. "
        "Please use the equivalent types from "
        "bot_engine.services.openai.realtime instead.",
        DeprecationWarning,
        stacklevel=2,
    )
