import asyncio
import json
import os
import time

import websockets


async def main():
    api_key = os.getenv("VOICING_TTS_API_KEY", "your-api-key-here")
    if not api_key:
        raise SystemExit("VOICING_TTS_API_KEY not set")

    base = os.getenv("VOICING_TTS_ENDPOINT", "")
    uri = f"{base}/tts/stream?api_key={api_key}"

    print(f"Connecting to: {base}")
    print(f"Using API key: {api_key[:20]}..." if len(api_key) > 20 else f"Using API key: {api_key}")

    async with websockets.connect(uri, ping_interval=10, ping_timeout=600) as ws:
        # Fixed request payload to match working test version
        request = {
            "text": "Hello! How are you doing today?",
            "speaker": os.getenv("VOICING_TTS_SPEAKER", "amber"),
            "language": os.getenv("VOICING_TTS_LANGUAGE", "en"),
            "output_format": os.getenv("VOICING_TTS_OUTPUT", "pcm_24000"),
            "speed": float(os.getenv("VOICING_TTS_SPEED", "1.0")),
            "expressiveness": int(os.getenv("VOICING_TTS_EXPRESSIVENESS", "46")),
            "custom_pronunciations": {"words": {}, "phonemes": {}},
            "translate_text": False,
        }

        print(f"Sending request: {json.dumps(request, indent=2)}")
        await ws.send(json.dumps(request))
        t0 = time.time()

        # Wait up to 30s for first binary chunk with longer timeout per recv
        for i in range(30):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)  # Increased timeout
                if isinstance(msg, bytes):
                    print(f"✓ SUCCESS: Received {len(msg)} bytes in {time.time() - t0:.3f}s")
                    return
                else:
                    print(f"Received text message: {msg}")
            except asyncio.TimeoutError:
                print(f"Waiting... ({i + 1}s elapsed)")
                continue

        raise TimeoutError("No audio received within 30s")


if __name__ == "__main__":
    asyncio.run(main())
