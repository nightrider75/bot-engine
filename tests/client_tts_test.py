import os

import pytest

# Skip this integration test in CI (requires audio hardware and live API)
if os.getenv("RUN_INTEGRATION_TESTS", "0") != "1":
    pytest.skip(
        "Skipping integration test: requires audio device and external server. Set RUN_INTEGRATION_TESTS=1 to enable.",
        allow_module_level=True,
    )

import asyncio
import audioop
import base64
import json
import os
import time
import wave
from io import BytesIO

import pyaudio
import websockets
from pydub import AudioSegment

# Get API key from environment
API_KEY = os.getenv("TTS_API_KEY", "your-api-key-here")
SERVER_URI = os.getenv("TTS_ENDPOINT", "") + f"/tts/stream?api_key={API_KEY}"


# Initialize PyAudio for real-time playback
p = pyaudio.PyAudio()


async def receive_data(uri):
    try:
        async with websockets.connect(SERVER_URI, ping_interval=10, ping_timeout=600) as websocket:
            request = {
                "text": "Hello! How are you doing today?",
                "speaker": "amber",
                "language": "en",
                "output_format": "pcm_24000",
                "speed": 1,
                "expressiveness": 46,
                "custom_pronunciations": {"words": {}, "phonemes": {}},
                "translate_text": False,
            }
            await websocket.send(json.dumps(request))
            s = time.time()
            print(f"Message sent :: {request}")

            output_format = "pcm_24000"
            media_type = output_format.split("_")[0]
            frame_rate = int(output_format.split("_")[1])
            print(f"Frame Rate: {frame_rate}, Media Type: {media_type}")

            if media_type in ["pcm", "ulaw"]:
                stream = p.open(format=pyaudio.paInt16, channels=1, rate=frame_rate, output=True)
                frst_chunk = True
                while True:
                    message = await websocket.recv()
                    if frst_chunk:
                        print(time.time())
                        print(time.time() - s)
                        print(len(message))
                        frst_chunk = False

                    if isinstance(message, bytes):
                        if media_type == "ulaw":
                            message = audioop.ulaw2lin(message, 2)  # Convert ULAW to PCM 16-bit

                        stream.write(message)  # Play audio chunk

                    elif isinstance(message, str):  # End of stream signal
                        print(message)

            elif media_type == "mp3":
                audio_data = bytearray()

                while True:
                    message = await websocket.recv()

                    if isinstance(message, bytes):
                        audio_data.extend(message)  # Append bytes to buffer
                        print(f"Receiving MP3 chunk of {len(message)} bytes.")

                    elif isinstance(message, str):  # End of stream signal
                        print(message)
                        break

                # Convert MP3 data to WAV and play it
                audio_segment = AudioSegment.from_mp3(BytesIO(audio_data))
                playback = p.open(
                    format=p.get_format_from_width(audio_segment.sample_width),
                    channels=audio_segment.channels,
                    rate=audio_segment.frame_rate,
                    output=True,
                )
                playback.write(audio_segment.raw_data)
                playback.stop_stream()
                playback.close()
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"WebSocket connection closed: {e}")
    finally:
        print("Audio stream closed.")


async def main():
    uri = SERVER_URI
    # send_task = asyncio.create_task(send_data(uri))
    receive_task = asyncio.create_task(receive_data(uri))

    await asyncio.gather(receive_task)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        p.terminate()
