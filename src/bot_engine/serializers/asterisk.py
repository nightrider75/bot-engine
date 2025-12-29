#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Asterisk Media Streams WebSocket protocol serializer for Bot Engine."""

from typing import Optional

from loguru import logger
from pydantic import BaseModel

from bot_engine.audio.utils import (
    create_file_resampler,
    pcm_to_ulaw,
    ulaw_to_pcm,
)
from bot_engine.frames.frames import (
    AudioRawFrame,
    CancelFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    InterruptionFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
    StartFrame,
)
from bot_engine.serializers.base_serializer import (
    FrameSerializer,
    FrameSerializerType,
)


class AsteriskFrameSerializer(FrameSerializer):
    """Serializer for Asterisk Media Streams WebSocket protocol.

    This serializer handles converting between Bot Engine frames and Asterisk's WebSocket
    media streams protocol. It supports audio conversion, DTMF events, and automatic
    call termination.

    When auto_hang_up is enabled (default), the serializer will automatically terminate
    the Asterisk call when an EndFrame or CancelFrame is processed, but requires Asterisk
    credentials to be provided.
    """

    class InputParams(BaseModel):
        """Configuration parameters for AsteriskFrameSerializer.

        Parameters:
            asterisk_sample_rate: Sample rate used by Asterisk, defaults to 8000 Hz.
            sample_rate: Optional override for pipeline input sample rate.
            auto_hang_up: Whether to automatically terminate call on EndFrame.
        """

        asterisk_sample_rate: int = 8000
        sample_rate: Optional[int] = None
        auto_hang_up: bool = True

    def __init__(
        self,
        stream_sid: str,
        params: Optional[InputParams] = None,
    ):
        """Initialize the AsteriskFrameSerializer.

        Args:
            stream_sid: The Asterisk Media Stream SID.
            params: Configuration parameters.
        """
        self._params = params or AsteriskFrameSerializer.InputParams()

        # Validate hangup-related parameters if auto_hang_up is enabled
        self._stream_sid = stream_sid

        self._asterisk_sample_rate = self._params.asterisk_sample_rate
        self._sample_rate = self._params.sample_rate or 16000  # Pipeline input rate

        self._input_resampler = create_file_resampler()
        self._output_resampler = create_file_resampler()
        self._hangup_attempted = False

    @property
    def type(self) -> FrameSerializerType:
        """Gets the serializer type.

        Returns:
            The serializer type, either TEXT or BINARY.
        """
        return FrameSerializerType.BINARY

    async def setup(self, frame: StartFrame):
        """Sets up the serializer with pipeline configuration.

        Args:
            frame: The StartFrame containing pipeline configuration.
        """
        self._sample_rate = self._params.sample_rate or frame.audio_in_sample_rate

    async def serialize(self, frame: Frame) -> str | bytes | None:
        """Serializes a Bot Engine frame to Asterisk WebSocket format.

        Handles conversion of various frame types to Asterisk WebSocket messages.
        For EndFrames, initiates call termination if auto_hang_up is enabled.

        Args:
            frame: The Bot Engine frame to serialize.

        Returns:
            Serialized data as string or bytes, or None if the frame isn't handled.
        """
        if (
            self._params.auto_hang_up
            and not self._hangup_attempted
            and isinstance(frame, (EndFrame, CancelFrame))
        ):
            self._hangup_attempted = True
            await self._hang_up_call()
            return None
        elif isinstance(frame, InterruptionFrame):
            return "FLUSH_MEDIA"
        elif isinstance(frame, AudioRawFrame):
            data = frame.audio

            # Output: Convert PCM at frame's rate to 8kHz μ-law for Asterisk
            serialized_data = await pcm_to_ulaw(
                data,
                frame.sample_rate,
                self._asterisk_sample_rate,
                self._output_resampler,
            )
            if serialized_data is None or len(serialized_data) == 0:
                # Ignoring in case we don't have audio
                return None

            return serialized_data
        elif isinstance(frame, (OutputTransportMessageFrame, OutputTransportMessageUrgentFrame)):
            # Transport messages not enabled rn
            return None

        # Return None for unhandled frames
        return None

    async def _hang_up_call(self):
        """Hang up the Asterisk call using Asterisk's REST API."""
        try:
            # TODO: Implement hangup for ARI
            pass
        except Exception as e:
            logger.exception(f"Failed to hang up Asterisk call: {e}")

    async def deserialize(self, data: str | bytes) -> Frame | None:
        """Deserializes Asterisk WebSocket data to Bot Engine frames.

        Handles conversion of Asterisk media events to appropriate Bot Engine frames.

        Args:
            data: The raw WebSocket data from Asterisk.

        Returns:
            A Bot Engine frame corresponding to the Asterisk event, or None if unhandled.
        """
        try:
            pcm_data = await ulaw_to_pcm(
                data, self._asterisk_sample_rate, self._sample_rate, self._input_resampler
            )
            return InputAudioRawFrame(
                audio=pcm_data,
                num_channels=1,  # u-law is typically mono
                sample_rate=self._sample_rate,
            )
        except Exception as e:
            logger.error(f"Failed to decode Asterisk packet: {str(e)}")
            return None
