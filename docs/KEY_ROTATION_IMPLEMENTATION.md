# API Key Rotation Implementation - Complete

## ✅ Implementation Complete

This document summarizes the API key rotation system for STT services with proactive user communication.

## 📦 What Was Built

### Step 1: Auth Error Detector
**File:** `src/bot_engine/utils/auth_error_detector.py`

- Detects authentication errors (401, 403, expired, invalid_api_key, etc.)
- Returns error type for logging
- Simple pattern matching on error messages

**Test:** `test_auth_detector.py` ✅

### Step 2: API Key Manager  
**File:** `src/bot_engine/utils/api_key_manager.py`

- Manages pool of API keys with health tracking
- Key states: ACTIVE, FAILED, EXHAUSTED
- Cooldown system (default: 5 minutes)
- Exhaustion after max failures (default: 3)
- Success resets failure count
- Rotation statistics

**Test:** `test_key_manager.py` ✅

### Step 3: Rotating STT Processor
**File:** `src/bot_engine/processors/rotating_stt_processor.py`

- Wraps any STT service class (Deepgram, Azure, Google, etc.)
- Intercepts authentication errors
- Notifies user via TTS: "Sorry, I missed that. Could you please repeat?"
- Rotates to next available API key
- Creates new STT service instance with new key
- Seamless failover with transparent communication

**Test:** `test_rotating_stt_simple.py` ✅

## 🚀 How to Use

### Basic Usage

```python
from bot_engine.processors.rotating_stt_processor import RotatingSTTProcessor
from bot_engine.services.deepgram.stt import DeepgramSTTService
from bot_engine.services.elevenlabs.tts import ElevenLabsTTSService

# Create TTS service for user notifications
tts_service = ElevenLabsTTSService(...)

# Create rotating STT with multiple Deepgram keys
rotating_stt = RotatingSTTProcessor(
    stt_service_class=DeepgramSTTService,
    stt_config={
        "live_options": LiveOptions(
            model="nova-3-general",
            language=Language.EN,
            interim_results=True
        )
    },
    api_keys=[
        os.getenv("DEEPGRAM_KEY_1"),
        os.getenv("DEEPGRAM_KEY_2"),
        os.getenv("DEEPGRAM_KEY_3")
    ],
    tts_service=tts_service,
    cooldown_seconds=300,  # 5 minutes
    max_failures=3
)

# Use in pipeline
pipeline = Pipeline([
    transport.input(),
    rotating_stt,  # Handles rotation automatically
    LLMService(),
    tts_service,
    transport.output()
])
```

### Custom Recovery Messages

```python
rotating_stt = RotatingSTTProcessor(
    ...
    recovery_phrases=[
        "Pardon me, could you repeat that?",
        "I didn't catch that, please say again",
        "Sorry, there was a connection issue. What did you say?"
    ]
)
```

### Azure Speech with Different Endpoints (NEW!)

```python
# Different Azure Speech resources with different endpoints per key
rotating_azure_stt = RotatingSTTProcessor(
    stt_service_class=AzureSTTService,
    stt_config={
        "language": "en-US"  # Base config
    },
    api_keys=["azure_key_eastus", "azure_key_westeurope"],
    config_mappings={
        "azure_key_eastus": {
            "endpoint": "https://eastus.api.cognitive.microsoft.com/",
            "region": "eastus"
        },
        "azure_key_westeurope": {
            "endpoint": "https://westeurope.api.cognitive.microsoft.com/",
            "region": "westeurope"
        }
    },
    tts_service=tts_service
)
```

### Get Statistics

```python
stats = rotating_stt.get_stats()
# {
#     'total_keys': 3,
#     'active_keys': 2,
#     'failed_keys': 1,
#     'exhausted_keys': 0,
#     'rotation_count': 1,
#     'current_key': 'deep...key2',
#     'stt_service': 'DeepgramSTTService'
# }
```

## 🎯 How It Works

### Normal Operation
```
User speaks → STT processes → Transcription → Continue
```

### When API Key Fails
```
User speaks → STT fails (401) → Detect auth error
                              ↓
                    Notify user: "Sorry, could you repeat?"
                              ↓
                    Stop old service
                              ↓
                    Rotate to next key
                              ↓
                    Start new service with new key
                              ↓
                    Ready to listen
                              ↓
User repeats → New STT processes → Transcription → Continue
```

## 🔑 Key Features

### ✅ Implemented
- ✅ Auth error detection (401, 403, expired, etc.)
- ✅ Key health tracking (ACTIVE, FAILED, EXHAUSTED)
- ✅ Automatic key rotation
- ✅ Cooldown system (failed keys wait before retry)
- ✅ User notification via TTS
- ✅ New service instance creation
- ✅ Statistics tracking
- ✅ Supports any STT service class

### 🎯 Design Decisions

**Why notify user instead of buffering audio?**
- Simpler implementation
- Better UX (user knows what happened)
- No context loss issues
- Natural conversation flow
- User feels informed, not confused

**Why create new service instance?**
- API keys are set in constructor
- Can't change key on existing WebSocket
- Clean separation of concerns
- ~100-200ms overhead is acceptable

**Why cooldown period?**
- Prevents hammering failed keys
- Allows temporary issues to resolve
- Default 5 minutes is reasonable

## 📊 Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cooldown_seconds` | 300 (5 min) | How long failed keys wait |
| `max_failures` | 3 | Failures before key exhaustion |
| `recovery_phrases` | Built-in list | TTS messages to user |
| `tts_service` | None | Optional TTS for notifications |

## 🧪 Testing

All components are tested:

```bash
# Test auth detection
python test_auth_detector.py

# Test key management
python test_key_manager.py

# Test rotating processor
python test_rotating_stt_simple.py
```

## 🚧 Future Enhancements

Possible improvements:
- [ ] Multi-provider cascading (Deepgram → Azure → Google)
- [ ] Health check monitoring
- [ ] Hot-reload of keys
- [ ] Metrics export (Prometheus, etc.)
- [ ] Context-aware recovery messages
- [ ] Audio buffering option (advanced)

## 📝 Files Created

```
src/bot_engine/utils/
├── auth_error_detector.py    # Step 1: Error detection
└── api_key_manager.py         # Step 2: Key management

src/bot_engine/processors/
└── rotating_stt_processor.py  # Step 3: Main wrapper

Tests:
├── test_auth_detector.py
├── test_key_manager.py
└── test_rotating_stt_simple.py
```

## ✅ Status: COMPLETE

All steps implemented and tested. Ready for production use with any STT service.
