# Community Integrations Guide

Voicing AI welcomes community-maintained integrations! As our ecosystem grows, we've established a process for any developer to create and maintain their own service integrations while ensuring discoverability for the Voicing AI community.

## Overview

**What we support:** Community-maintained integrations that live in separate repositories and are maintained by their authors.

**What we don't do:** The Voicing AI team does not code review, test, or maintain community integrations. We provide guidance and list approved integrations for discoverability.

**Why this approach:** This allows the community to move quickly while keeping the Voicing AI core team focused on maintaining the framework itself.

## Submitting your Integration

To be listed as an official community integration, follow these steps:

### Step 1: Build Your Integration

Create your integration following the patterns and examples shown in the "Integration Patterns and Examples" section below.

### Step 2: Set Up Your Repository

Your repository must contain these components:

- **Source code** - Complete implementation following Voicing AI patterns
- **Foundational example** - Single file example showing basic usage (see [Voicing AI examples]())
- **README.md** - Must include:

  - Introduction and explanation of your integration
  - Installation instructions
  - Usage instructions with Voicing AI Pipeline
  - How to run your example
  - Voicing AI version compatibility (e.g., "Tested with Voicing AI v0.0.86")
  - Company attribution: If you work for the company providing the service, please mention this in your README. This helps build confidence that the integration will be actively maintained.

- **LICENSE** - Permissive license (BSD-2 like Voicing AI, or equivalent open source terms)
- **Code documentation** - Source code with docstrings (we recommend following [Voicing AI's docstring conventions]())
- **Changelog** - Maintain a changelog for version updates

### Step 3: Join Discord

Join our Discord: https://discord.gg/pipecat

### Step 4: Submit for Listing

Submit a pull request to add your integration to our [Community Integrations documentation page]().

**To submit:**

1. Fork the [Voicing AI docs repository]()
2. Edit the file `server/services/community-integrations.mdx`
3. Add your integration to the appropriate service category table with:
   - Service name
   - Link to your repository
   - Maintainer GitHub username(s)
4. Include a link to your demo video (approx 30-60 seconds) in your PR description showing:
   - Core functionality of your integration
   - Handling of an interruption (if applicable to service type)
5. Submit your pull request

Once your PR is submitted, post in the `#community-integrations` Discord channel to let us know.

## Integration Patterns and Examples

### STT (Speech-to-Text) Services

#### Websocket-based Services

**Base class:** `STTService`

**Examples:**

- [DeepgramSTTService]()
- [SpeechmaticsSTTService]()

#### File-based Services

**Base class:** `SegmentedSTTService`

**Examples:**

- [RivaSTTService]()
- [FalSTTService]()

#### Key requirements:

- STT services should push `InterimTranscriptionFrames` and `TranscriptionFrames`
- If confidence values are available, filter for values >50% confidence

### LLM (Large Language Model) Services

#### OpenAI-Compatible Services

**Base class:** `OpenAILLMService`

**Examples:**

- [AzureLLMService]()
- [GrokLLMService]() - Shows overriding the base class where needed

#### Non-OpenAI Compatible Services

**Requires:** Full implementation

**Examples:**

- [AnthropicLLMService]()
- [GoogleLLMService]()

#### Key requirements:

- **Frame sequence:** Output must follow this frame sequence pattern:

  - `LLMFullResponseStartFrame` - Signals the start of an LLM response
  - `LLMTextFrame` - Contains LLM content, typically streamed as tokens
  - `LLMFullResponseEndFrame` - Signals the end of an LLM response

- **Context aggregation:** Implement context aggregation to collect user and assistant content:
  - Aggregators come in pairs with a `user()` instance and `assistant()` instance
  - Context must adhere to the `LLMContext` universal format
  - Aggregators should handle adding messages, function calls, and images to the context

### TTS (Text-to-Speech) Services

#### AudioContextWordTTSService

**Use for:** Websocket-based services supporting word/timestamp alignment

**Example:**

- [CartesiaTTSService]()

#### InterruptibleTTSService

**Use for:** Websocket-based services without word/timestamp alignment, requiring disconnection on interruption

**Example:**

- [SarvamTTSService]()

#### WordTTSService

**Use for:** HTTP-based services supporting word/timestamp alignment

**Example:**

- [ElevenLabsHttpTTSService]()

#### TTSService

**Use for:** HTTP-based services without word/timestamp alignment

**Example:**

- [GoogleHttpTTSService]()

#### Key requirements:

- For websocket services, use asyncio WebSocket implementation (required for v13+ support)
- Handle idle service timeouts with keepalives
- TTSServices push both audio (`TTSRawAudioFrame`) and text (`TTSTextFrame`) frames

### Telephony Serializers

Bot Engine supports telephony provider integration using websocket connections to exchange MediaStreams. These services use a FrameSerializer to serialize and deserialize inputs from the FastAPIWebsocketTransport.

**Examples:**

- [Twilio]()
- [Telnyx]()

#### Key requirements:

- Include hang-up functionality using the provider's native API, ideally using `aiohttp`
- Support DTMF (dual-tone multi-frequency) events if the provider supports them:
  - Deserialize DTMF events from the provider's protocol to `InputDTMFFrame`
  - Use `KeypadEntry` enum for valid keypad entries (0-9, \*, #, A-D)
  - Handle invalid DTMF digits gracefully by returning `None`

### Image Generation Services

**Base class:** `ImageGenService`

**Examples:**

- [FalImageGenService]()
- [GoogleImageGenService]()

#### Key requirements:

- Must implement `run_image_gen` method returning an `AsyncGenerator`

### Vision Services

Vision services process images and provide analysis such as descriptions, object detection, or visual question answering.

**Base class:** `VisionService`

**Example:**

- [MoondreamVisionService]()

#### Key requirements:

- Must implement `run_vision` method that takes an `LLMContext` and returns an `AsyncGenerator[Frame, None]`
- The method processes the latest image in the context and yields frames with analysis results
- Typically yields `TextFrame` objects containing descriptions or answers

## Implementation Guidelines

### Naming Conventions

- **STT:** `VendorSTTService`
- **LLM:** `VendorLLMService`
- **TTS:**
  - Websocket: `VendorTTSService`
  - HTTP: `VendorHttpTTSService`
- **Image:** `VendorImageGenService`
- **Vision:** `VendorVisionService`
- **Telephony:** `VendorFrameSerializer`

### Metrics Support

Enable metrics in your service:

```python
def can_generate_metrics(self) -> bool:
    """Check if this service can generate processing metrics.

    Returns:
        True, as this service supports metrics.
    """
    return True
```

### Dynamic Settings Updates

STT, LLM, and TTS services support `ServiceUpdateSettingsFrame` for dynamic configuration changes. The base STTService has an `_update_settings()` method that handles settings, and the private `_settings` `Dict` is used to store settings and provide access to the subclass.

```python
async def set_language(self, language: Language):
    """Set the recognition language and reconnect.

    Args:
        language: The language to use for speech recognition.
    """
    logger.info(f"Switching STT language to: [{language}]")
    self._settings["language"] = language
    await self._disconnect()
    await self._connect()
```

Note that, in this example, Deepgram requires the websocket connection be disconnected and reconnected to reinitialize the service with the new value. Consider if your service requires reconnection.

### Sample Rate Handling

Sample rates are set via PipelineParams and passed to each frame processor at initialization. The pattern is to _not_ set the sample rate value in the constructor of a given service. Instead, use the `start()` method to initialize sample rates from the frame:

```python
async def start(self, frame: StartFrame):
    """Start the service."""
    await super().start(frame)
    self._settings["output_format"]["sample_rate"] = self.sample_rate
    await self._connect()
```

Note that `self.sample_rate` is a `@property` set in the TTSService base class, which provides access to the private sample rate value obtained from the StartFrame.

### Tracing Decorators

Use Voicing AI's tracing decorators:

- **STT:** `@traced_stt` - decorate a function that handles `transcript`, `is_final`, `language` as args
- **LLM:** `@traced_llm` - decorate the `_process_context()` method
- **TTS:** `@traced_tts` - decorate the `run_tts()` method

## Best Practices

### Packaging and Distribution

- Use [uv](https://docs.astral.sh/uv/) for packaging (encouraged)
- Consider releasing to PyPI for easier installation
- Follow semantic versioning principles
- Maintain a changelog

### HTTP Communication

For REST-based communication, use aiohttp. Voicing AI includes this as a required dependency, so using it prevents adding an additional dependency to your integration.

### Error Handling

- Wrap API calls in appropriate try/catch blocks
- Handle rate limits and network failures gracefully
- Provide meaningful error messages
- When errors occur, raise exceptions AND push `ErrorFrame`s to notify the pipeline:

```python
from bot_engine.frames.frames import ErrorFrame

try:
    # Your API call
    result = await self._make_api_call()
except Exception as e:
    # Push error frame to pipeline
    await self.push_error(ErrorFrame(error=f"{self} error: {e}"))
    # Raise or handle as appropriate
    raise
```

### Testing

- Your foundational example serves as a valuable integration-level test
- Unit tests are nice to have. As the Voicing AI teams provides better guidance, we will encourage unit testing more

## Disclaimer

Community integrations are community-maintained and not officially supported by the Voicing AI team. Users should evaluate these integrations independently. The Voicing AI team reserves the right to remove listings that become unmaintained or problematic.

## Staying Up to Date

Voicing AI evolves rapidly to support the latest AI technologies and patterns. While we strive to minimize breaking changes, they do occur as the framework matures.

**We strongly recommend:**

- Join our Discord at https://discord.gg/voicing and monitor the `#announcements` channel for release notifications
- Follow our changelog: 
- Test your integration against new Voicing AI releases promptly
- Update your README with the last tested Voicing AI version

This helps ensure your integration remains compatible and your users have clear expectations about version support.

## Questions?

Join our Discord community at https://discord.gg/voicing and post in the `#community-integrations` channel for guidance and support.

For additional questions, you can also reach out to us at pipecat-ai@daily.co.
