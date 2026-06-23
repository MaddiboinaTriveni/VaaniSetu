# वाणीसेतु — VaaniSetu

> **AI-Powered Multilingual Legal Aid Interpreter for Rural India**

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Flutter](https://img.shields.io/badge/Flutter-3.x-blue)](https://flutter.dev)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-20%2F20%20passing-brightgreen)](#testing)

---

## The Problem

Every year, millions of rural Indians receive court summons, land notices, and legal orders they cannot read. Court documents arrive in English or state official language — but 65%+ of rural citizens can only read their local dialect or mother tongue.

**The result:** They miss hearings. They lose land. They silently accept wrong outcomes — not because they're wrong, but because nobody translated a piece of paper for them.

**40 crore affected. Zero dedicated solutions. Until now.**

---

## The Solution

VaaniSetu is a 4-stage AI pipeline:

```
📷 Photograph notice  →  🔍 OCR extract  →  🧠 AI understand  →  🗣️ Hear in your language
```

1. **OCR** — Tesseract + OpenCV reads any legal document photo (Telugu, Hindi, Tamil, Kannada scripts)
2. **Translation** — IndicTrans2 (IIT Madras / AI4Bharat) translates to 22 Indian languages
3. **LLM Summarization** — Llama 3.3 70B via Groq API (via Groq) explains in plain language: *"what you must do, by when, and what happens if you don't"*
4. **Voice Output** — gTTS speaks the summary in the user's regional language
5. **SMS Fallback** — Twilio WhatsApp bot works on 2G feature phones without the app

---

## Demo

| Screen | Description |
|--------|-------------|
| ![Home](docs/screenshots/home.png) | Language select + camera capture |
| ![Processing](docs/screenshots/processing.png) | Animated pipeline steps |
| ![Result](docs/screenshots/result.png) | Audio player + 4 info cards |

**Live demo:** https://vaanisetu.onrender.com  
**Demo video:** [YouTube link — add after recording]

---

## Quick Start

```bash
# Clone
git clone https://github.com/trivenimaddiboina/vaanisetu
cd vaanisetu

# Install system dependencies (Ubuntu)
sudo apt-get install tesseract-ocr tesseract-ocr-tel tesseract-ocr-hin \
                     tesseract-ocr-tam tesseract-ocr-kan espeak

# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # Add your GROQ_API_KEY
uvicorn main:app --reload

# Open http://localhost:8000
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| OCR | Tesseract 5 + OpenCV | Open source, Indian script support |
| Translation | IndicTrans2 (AI4Bharat) | Indian-made, 22 languages, free |
| LLM | Llama 3 70B via Groq API | Free tier, high quality |
| TTS | gTTS / espeak | Free, offline fallback |
| SMS | Twilio WhatsApp | 2G phone support |
| Backend | FastAPI (Python) | Async, auto-docs |
| Mobile | Flutter | Android + iOS |

---

## Project Structure

```
vaanisetu/
├── backend/
│   ├── main.py          # FastAPI app + demo UI
│   ├── ocr.py           # Tesseract + OpenCV pipeline
│   ├── translate.py     # IndicTrans2 translation
│   ├── summarize.py     # Groq LLM summarization
│   ├── voice.py         # gTTS + espeak TTS
│   ├── sms.py           # Twilio WhatsApp bot
│   ├── config.py        # Environment + language config
│   └── requirements.txt
├── mobile/              # Flutter app (3 screens)
│   └── lib/
│       ├── main.dart
│       ├── screens/
│       └── services/
├── tests/
│   └── test_backend.py  # 20 tests, all passing
├── docs/
│   └── TECHNICAL_DOC.md
└── .env.example
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/pipeline` | Full pipeline: image → audio summary |
| `POST` | `/ocr` | OCR text extraction only |
| `POST` | `/translate` | Text translation |
| `POST` | `/summarize` | LLM summarization |
| `POST` | `/tts` | Text to speech |
| `GET` | `/audio/{id}` | Serve audio file |
| `POST` | `/whatsapp` | Twilio webhook |
| `GET` | `/health` | Service status |
| `GET` | `/languages` | Supported languages |
| `GET` | `/` | Demo web UI |

Full API docs: http://localhost:8000/docs

---

## Testing

```bash
python tests/test_backend.py
```

```
Results: 20/20 tests passed 🎉
```

Tests cover: OCR extraction, confidence scoring, document classification, translation chunking, LLM summarization, voice generation, SMS formatting, and the full end-to-end pipeline.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
GROQ_API_KEY=your_key          # Free at groq.com
TWILIO_ACCOUNT_SID=...         # Free trial at twilio.com
TWILIO_AUTH_TOKEN=...
```

All services have mock fallbacks — the app runs without any API keys for development.

---

## Supported Languages

Telugu · Hindi · Tamil · Kannada · Malayalam · Marathi · Bengali · Gujarati  
*(22 languages with full IndicTrans2 model)*

---

## Impact

- **40 crore+** Indians who cannot access legal documents in their language
- **6,000+** district courts handling cases where notices go ununderstood
- **₹0.15** cost per SMS summary — accessible to BPL households
- Plugs into **eCourts MMP** infrastructure — scales nationally without rebuilding

---

## Team

**Triveni** — Solo participant  
B.Tech Computer Science, St. Ann's College of Engineering & Technology (2027)  
CGPA: 8.53 | AI Engineering Intern @ Madblocks Technologies | Published: ICRAIICE-2025

---

## License

MIT License — see [LICENSE](LICENSE)

---

*"Every Indian deserves to understand the law that governs them."*
