# VaaniSetu — Technical Documentation

**Version:** 1.0.0  
**Author:** Triveni  
**Stack:** FastAPI · Tesseract OCR · IndicTrans2 · Groq/Llama3 · gTTS · Flutter

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Design](#component-design)
3. [API Reference](#api-reference)
4. [Running Locally](#running-locally)
5. [Configuration](#configuration)
6. [Model Details](#model-details)
7. [Offline Mode](#offline-mode)
8. [SMS / WhatsApp Fallback](#sms--whatsapp-fallback)
9. [Flutter Mobile App](#flutter-mobile-app)
10. [Deployment](#deployment)
11. [Trade-offs & Design Decisions](#trade-offs--design-decisions)

---

## Architecture Overview

```
User photographs legal document
        │
        ▼
┌─────────────────────────────────────────────────────┐
│                  Flutter Mobile App                  │
│  Camera → Image → POST /pipeline → Display result   │
└───────────────────────┬─────────────────────────────┘
                        │  HTTPS multipart/form-data
                        ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI Backend  (Python 3.11)          │
│                                                      │
│  ┌──────────┐  ┌───────────┐  ┌─────────────────┐  │
│  │ OCR      │→ │ LLM       │→ │ TTS             │  │
│  │Tesseract │  │Summarize  │  │gTTS / espeak    │  │
│  │+OpenCV   │  │Groq API   │  │                 │  │
│  └──────────┘  └───────────┘  └─────────────────┘  │
│        │                                            │
│        ▼                                            │
│  ┌──────────┐                                       │
│  │Translate │  IndicTrans2 (AI4Bharat/IIT Madras)   │
│  └──────────┘                                       │
└─────────────────────────────────────────────────────┘
                        │
                        ▼  (optional)
┌─────────────────────────────────────────────────────┐
│       Twilio WhatsApp SMS Fallback                  │
│  Works on 2G feature phones, no app needed          │
└─────────────────────────────────────────────────────┘
```

---

## Component Design

### 1. OCR Module (`ocr.py`)

**Purpose:** Extract raw text from legal document images.

**Pipeline:**
```
Image bytes
    → load_image()         # supports bytes, PIL, numpy, file path
    → deskew()             # Hough line transform to correct rotation
    → preprocess()         # grayscale → upscale to 300 DPI → denoise → adaptive threshold
    → pytesseract()        # PSM 6 (uniform text block) + OEM 3 (LSTM engine)
    → classify_document()  # keyword matching for doc type
    → return {text, confidence, doc_type, word_count, low_quality}
```

**Key design decisions:**
- Adaptive thresholding (not global) handles shadows and uneven lighting from phone cameras
- Deskew corrects documents photographed at an angle
- Confidence score < 60% triggers a user-facing warning to retake the photo
- Tesseract language pack selection matches the user's chosen language

**Supported scripts:** Telugu (`tel`), Hindi/Marathi (`hin`), Tamil (`tam`), Kannada (`kan`), English (`eng`)

---

### 2. Translation Module (`translate.py`)
**Prototype Note:**
- The architecture supports IndicTrans2 multilingual translation.
- During prototype evaluation, the application may operate in fallback mode if the IndicTrans2 model is unavailable locally.


**Purpose:** Translate extracted text into the user's regional language.

**Model:** [IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) by AI4Bharat / IIT Madras
- 1B parameter seq2seq model
- Supports all 22 official Indian languages
- Completely open-source, no API key required
- Runs locally — user data never leaves the device

**Chunking strategy:**
- Model max input: 512 tokens ≈ 350 words
- Texts longer than 300 words are chunked and rejoined

**Mock mode:** When the model is not downloaded, returns a clearly labelled placeholder so the rest of the pipeline can be developed and tested.

**Download (first run, ~4GB):**
```bash
python -c "from transformers import AutoTokenizer; \
AutoTokenizer.from_pretrained('ai4bharat/indictrans2-en-indic-1B', trust_remote_code=True)"
```

---

### 3. Summarization Module (`summarize.py`)

**Purpose:** Convert raw legal text into a structured 4-field plain-language summary.

**Model:** Llama 3.3 70B via Groq API [Groq API](https://groq.com) (free tier: 30 req/min)

**Output schema:**
```json
{
  "document_type": "string — type of legal document",
  "parties":       "string — sender and recipient",
  "action_required": "string — what the person must do and by when",
  "consequence":   "string — what happens if ignored",
  "urgency":       "high | medium | low",
  "key_date":      "string | null"
}
```

**Prompt design:**
- System prompt instructs LLM to use "language a farmer with no legal education would understand"
- Output constrained to JSON only (temperature = 0.1 for consistency)
- JSON extraction with regex fallback handles edge cases where model adds preamble

**Mock fallback:** Returns a sensible default summary when `GROQ_API_KEY` is not set.

---

### 4. Voice Module (`voice.py`)

**Purpose:** Convert the plain-language summary to audio in the user's regional language.

**Engine chain (in priority order):**
1. **gTTS** (Google Text-to-Speech) — best quality, requires internet
2. **pyttsx3** — offline, English only
3. **espeak** — offline, supports Indian scripts, available on all Linux systems

**Language codes:** `te` (Telugu), `hi` (Hindi), `ta` (Tamil), `kn` (Kannada), `ml` (Malayalam), `mr` (Marathi)

**Audio files:**
- Stored in `AUDIO_DIR` (default: `/tmp/vaanisetu_audio/`)
- Named: `vaanisetu_{uuid4_hex}.mp3`
- Served via `GET /audio/{audio_id}`
- Auto-cleanup available

---

### 5. SMS Module (`sms.py`)

**Purpose:** WhatsApp bot that accepts document photos and replies with summaries.

**Flow:**
```
User sends photo to WhatsApp bot number
    → Twilio webhook fires POST /whatsapp
    → Download media from Twilio CDN
    → Run OCR → Summarize pipeline
    → Format WhatsApp message (≤1600 chars)
    → Send reply via Twilio
```

**Message format includes:**
- Document type + urgency emoji
- Parties involved
- Action required
- Consequence if ignored
- Key date if found
- NALSA helpline number

---

## API Reference

### `POST /pipeline` — Full pipeline

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | image/* | ✅ | Document photograph |
| `language` | string | ✅ | Target language key (e.g. `telugu`) |
| `send_whatsapp` | bool | ❌ | Send summary via WhatsApp |
| `whatsapp_number` | string | ❌ | WhatsApp number with country code |

**Response:**
```json
{
  "success": true,
  "language": "telugu",
  "ocr": {
    "confidence": 84.4,
    "word_count": 52,
    "doc_type": "summons",
    "low_quality": false,
    "text_preview": "DISTRICT COURT SUMMONS..."
  },
  "summary": {
    "document_type": "Court Summons",
    "parties": "District Court → Ramu Naidu",
    "action_required": "Appear in court on 20th March 2024 at 10:00 AM",
    "consequence": "Ex-parte proceedings will be initiated",
    "urgency": "high",
    "key_date": "20th March 2024",
    "mock_mode": false
  },
  "audio": {
    "audio_id": "4070dcc76eff4bce84a9614c72766426",
    "audio_url": "/audio/4070dcc76eff4bce84a9614c72766426",
    "duration_estimate": 18,
    "engine": "gTTS",
    "success": true
  }
}
```

---

### `POST /ocr` — OCR only

**Request:** `multipart/form-data` — `file` (image), `language` (string)  
**Response:** `{text, confidence, doc_type, word_count, low_quality}`

---

### `POST /translate` — Translate text

**Request:** `form` — `text`, `target_language`  
**Response:** `{translated_text, target_lang, mock_mode}`

---

### `POST /summarize` — LLM summarize

**Request:** `form` — `text`, `language`, `doc_type`  
**Response:** Summary schema (see above)

---

### `POST /tts` — Text to speech

**Request:** `form` — `text`, `language`  
**Response:** `{success, audio_id, audio_url, duration_estimate, engine}`

---

### `GET /audio/{audio_id}` — Serve audio

**Response:** MP3 or WAV audio stream

---

### `POST /whatsapp` — Twilio webhook

Configured in Twilio console. Receives incoming WhatsApp messages.  
**Response:** TwiML XML

---

### `GET /health` — Service status

```json
{
  "status": "ok",
  "services": {
    "ocr": "tesseract",
    "translation": "indictrans2",
    "llm": "groq",
    "tts": "gtts",
    "sms": "twilio"
  }
}
```

---

### `GET /languages` — Supported languages

Returns map of language key → `{label, code}`

---

## Running Locally

### Prerequisites
- Python 3.10+
- Tesseract OCR with Indian language packs
- 8GB RAM recommended (for IndicTrans2 model)

### Backend setup

```bash
# 1. Clone repository
git clone https://github.com/your-username/vaanisetu
cd vaanisetu

# 2. Install Tesseract (Ubuntu/Debian)
sudo apt-get install tesseract-ocr tesseract-ocr-tel tesseract-ocr-hin \
                     tesseract-ocr-tam tesseract-ocr-kan

# 3. Create virtual environment
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Configure environment
cp ../.env.example .env
# Edit .env and add:
#   GROQ_API_KEY=your_key_from_groq.com
#   TWILIO_ACCOUNT_SID=... (optional)
#   TWILIO_AUTH_TOKEN=...  (optional)

# 6. Start server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000 for the demo UI.  
API docs: http://localhost:8000/docs

### Download IndicTrans2 model (optional, ~4GB)

```bash
python -c "
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
model_name = 'ai4bharat/indictrans2-en-indic-1B'
AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True)
print('IndicTrans2 ready')
"
```

### Run tests

```bash
cd vaanisetu
python tests/test_backend.py
```

### Flutter app setup

```bash
cd mobile
flutter pub get
flutter run   # Connect Android device or start emulator first
```

For physical device testing, update `ApiService.baseUrl` in `lib/services/api_service.dart` to your computer's local IP.

---

## Configuration

All config in `.env` (copy from `.env.example`):

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | For AI summarization | Free at groq.com |
| `TWILIO_ACCOUNT_SID` | For WhatsApp bot | Free trial at twilio.com |
| `TWILIO_AUTH_TOKEN` | For WhatsApp bot | From Twilio console |
| `TWILIO_WHATSAPP_FROM` | Optional | Default: Twilio sandbox number |
| `APP_PORT` | Optional | Default: 8000 |
| `AUDIO_DIR` | Optional | Default: /tmp/vaanisetu_audio |
| `DEBUG` | Optional | Default: true |

---

## Model Details

| Component | Model | Size | License | Notes |
|-----------|-------|------|---------|-------|
| OCR | Tesseract 5 (LSTM) | ~40MB/lang | Apache 2.0 | Indian language packs |
| Translation | IndicTrans2-1B | ~4GB | MIT | AI4Bharat / IIT Madras |
| Summarization | Llama 3 70B (via Groq) | Cloud API | Meta Llama 3 | Free 30 req/min |
| TTS | gTTS (Google) | API call | Free | Requires internet |
| TTS fallback | espeak | ~10MB | GPL | Fully offline |

---

## Offline Mode

VaaniSetu is designed for rural India where connectivity is unreliable.

**What works offline (after first setup):**
- OCR (Tesseract runs locally)
- Translation (IndicTrans2 runs locally after download)
- TTS via espeak (installed locally)
- All summarization logic except LLM call

**What requires internet:**
- Groq API (LLM summarization) — falls back to mock summary offline
- gTTS (best quality audio) — falls back to espeak offline
- IndicTrans2 model download (one-time, ~4GB)

**For fully offline deployment:**
1. Download IndicTrans2 model once with internet
2. Use `OFFLINE_LLM=true` flag to use Ollama + Llama 3 locally (8GB RAM needed)
3. espeak handles audio without internet

---

## SMS / WhatsApp Fallback

Setup for judges to test the WhatsApp flow:

1. Create Twilio account at twilio.com (free $15 trial credit)
2. Enable WhatsApp sandbox: Twilio Console → Messaging → Try WhatsApp
3. Set webhook URL to your deployed backend: `https://your-app.onrender.com/whatsapp`
4. Add credentials to `.env`

User flow:
- User saves the Twilio sandbox number to their contacts
- Sends "join [sandbox-phrase]" once to activate
- After that: sends any document photo → receives plain-language summary in reply

---

## Flutter Mobile App

### Screen flow
```
HomeScreen (language select + camera)
    → ProcessingScreen (animated steps, API call)
        → ResultScreen (audio player + 4 info cards + share)
```

### Key files
| File | Purpose |
|------|---------|
| `lib/main.dart` | App entry, theme config |
| `lib/screens/home_screen.dart` | Language select + image capture |
| `lib/screens/processing_screen.dart` | Animated progress + API call |
| `lib/screens/result_screen.dart` | Audio player + summary cards |
| `lib/services/api_service.dart` | All HTTP calls to backend |

### Change backend URL
In `lib/services/api_service.dart`:
```dart
static const String baseUrl = 'https://your-backend.onrender.com';
```

---

## Deployment

### Backend — Render.com (free tier)

1. Push code to GitHub
2. Create new Web Service on render.com
3. Set Build Command: `pip install -r backend/requirements.txt`
4. Set Start Command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables from `.env`

### Backend — Docker

```bash
docker build -t vaanisetu-backend ./backend
docker run -p 8000:8000 --env-file .env vaanisetu-backend
```

### Flutter APK build

```bash
cd mobile
flutter build apk --release
# APK at: build/app/outputs/flutter-apk/app-release.apk
```

---

## Trade-offs & Design Decisions

| Decision | Alternative Considered | Reason Chosen |
|----------|----------------------|---------------|
| Groq + Llama 3 for summarization | OpenAI GPT-4 | Groq is free; Llama 3 70B is comparable quality |
| IndicTrans2 for translation | Google Translate API | No API cost; runs locally; Indian-made model |
| gTTS + espeak chain | AWS Polly | No cost; espeak works offline |
| FastAPI over Django/Flask | Django, Flask | Async support; auto-generated docs; fastest Python API framework |
| Mock mode for all services | Hard fail if no credentials | Allows full development without API keys |
| Document chunking at 300 words | Single pass | IndicTrans2 max is 512 tokens; chunking prevents truncation |
| Adaptive threshold for OCR | Global threshold | Phone camera photos have uneven lighting; adaptive is more robust |
| Flutter for mobile | React Native | Single codebase; better camera plugin ecosystem; JIT compilation |

---

*VaaniSetu — Built for the 40 crore Indians whose legal rights are silenced by a language barrier.*
