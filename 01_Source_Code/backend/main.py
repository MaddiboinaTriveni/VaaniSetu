"""
VaaniSetu — FastAPI Backend
Main application with all API endpoints.

Endpoints:
  POST /pipeline       — Full pipeline: image → OCR → translate → summarize → TTS
  POST /ocr            — OCR only
  POST /translate      — Translate text
  POST /summarize      — LLM summarize
  POST /tts            — Text to speech
  GET  /audio/{id}     — Serve audio file
  POST /whatsapp       — Twilio WhatsApp webhook
  GET  /health         — Health check
  GET  /languages      — List supported languages
  GET  /               — Demo UI
"""
import logging
import os
import io
import uuid
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import config
from ocr import extract_text
from translate import translate
from summarize import summarize, build_voice_text
from voice import text_to_speech, cleanup_audio
from sms import parse_webhook_form, download_twilio_media, send_whatsapp_summary

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("vaanisetu")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="VaaniSetu API",
    description="AI-Powered Multilingual Legal Aid Interpreter for Rural India",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    import translate as tr
    return {
        "status": "ok",
        "version": "1.0.0",
        "services": {
            "ocr": "tesseract",
            "translation": "mock" if tr.MOCK_MODE else "indictrans2",
            "llm": "groq" if config.GROQ_API_KEY and config.GROQ_API_KEY != "your_groq_api_key_here" else "mock",
            "tts": "gtts",
            "sms": "twilio" if bool(config.TWILIO_ACCOUNT_SID and config.TWILIO_ACCOUNT_SID != "your_twilio_account_sid") else "mock",
        },
        "supported_languages": list(config.SUPPORTED_LANGUAGES.keys()),
    }


@app.get("/languages")
async def languages():
    return {
        lang: {
            "label": info["label"],
            "code": info["code"],
        }
        for lang, info in config.SUPPORTED_LANGUAGES.items()
    }


# ── OCR endpoint ──────────────────────────────────────────────────────────────
@app.post("/ocr")
async def ocr_endpoint(
    file: UploadFile = File(...),
    language: str = Form("telugu"),
):
    """Extract text from a legal document image."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image (JPEG, PNG, etc.)")

    image_bytes = await file.read()
    result = extract_text(image_bytes, language)

    if result.get("low_quality"):
        result["warning"] = (
            "Low OCR confidence. Try photographing the document in better lighting "
            "and ensure the text is in focus."
        )

    return result


# ── Translate endpoint ────────────────────────────────────────────────────────
@app.post("/translate")
async def translate_endpoint(
    text: str = Form(...),
    target_language: str = Form("telugu"),
):
    """Translate text to the specified Indian language."""
    result = translate(text, target_language)
    return result


# ── Summarize endpoint ────────────────────────────────────────────────────────
@app.post("/summarize")
async def summarize_endpoint(
    text: str = Form(...),
    language: str = Form("telugu"),
    doc_type: str = Form("legal_document"),
):
    """Generate structured plain-language summary using LLM."""
    result = summarize(text, language, doc_type)
    return result


# ── TTS endpoint ──────────────────────────────────────────────────────────────
@app.post("/tts")
async def tts_endpoint(
    text: str = Form(...),
    language: str = Form("telugu"),
):
    """Convert text to speech audio file."""
    result = text_to_speech(text, language)
    if not result.get("success"):
        raise HTTPException(500, result.get("error", "TTS failed"))
    return result


# ── Serve audio ────────────────────────────────────────────────────────────────
@app.get("/audio/{audio_id}")
async def serve_audio(audio_id: str, cleanup: bool = False):
    """Stream audio file to client."""
    # Security: only allow our generated audio IDs (hex strings)
    if not all(c in "0123456789abcdef" for c in audio_id) or len(audio_id) != 32:
        raise HTTPException(400, "Invalid audio ID")

    for ext in [".mp3", ".wav"]:
        path = os.path.join(config.AUDIO_DIR, f"vaanisetu_{audio_id}{ext}")
        if os.path.exists(path):
            media_type = "audio/mpeg" if ext == ".mp3" else "audio/wav"
            return FileResponse(
                path,
                media_type=media_type,
                headers={"Content-Disposition": f"inline; filename=vaanisetu_{audio_id}{ext}"},
            )

    raise HTTPException(404, "Audio file not found or expired")


# ── Full pipeline endpoint ─────────────────────────────────────────────────────
@app.post("/pipeline")
async def full_pipeline(
    file: UploadFile = File(...),
    language: str = Form("telugu"),
    send_whatsapp: bool = Form(False),
    whatsapp_number: Optional[str] = Form(None),
):
    """
    Full VaaniSetu pipeline:
    Image → OCR → Translate → LLM Summarize → TTS → (optional WhatsApp)

    Returns complete result with audio URL and structured summary.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image")

    logger.info(f"Pipeline started — language: {language}, file: {file.filename}")
    image_bytes = await file.read()

    # ── Step 1: OCR ────────────────────────────────────────────────────────
    logger.info("Step 1/4: OCR extraction")
    ocr_result = extract_text(image_bytes, language)

    if not ocr_result.get("text"):
        return JSONResponse(status_code=422, content={
            "error": "Could not read text from this image. "
                     "Please photograph the document clearly with good lighting.",
            "step_failed": "ocr",
        })

    raw_text = ocr_result["text"]
    doc_type = ocr_result.get("doc_type", "legal_document")

    # ── Step 2: LLM Summarize (from original text) ─────────────────────────
    logger.info("Step 2/4: LLM summarization")
    summary = summarize(raw_text, language, doc_type)

    # ── Step 3: Build voice text & TTS ────────────────────────────────────
    logger.info("Step 3/4: Text-to-speech generation")
    voice_text = summary.get("voice_text") or build_voice_text(summary, language)
    audio_result = text_to_speech(voice_text, language)

    # ── Step 4: Optional WhatsApp send ───────────────────────────────────
    whatsapp_result = None
    if send_whatsapp and whatsapp_number:
        logger.info("Step 4/4: Sending WhatsApp summary")
        whatsapp_result = send_whatsapp_summary(whatsapp_number, summary, language)

    logger.info("Pipeline complete")

    return {
        "success": True,
        "language": language,
        "ocr": {
            "confidence": ocr_result.get("confidence"),
            "word_count": ocr_result.get("word_count"),
            "doc_type": doc_type,
            "low_quality": ocr_result.get("low_quality", False),
            "text_preview": raw_text[:300] + "..." if len(raw_text) > 300 else raw_text,
        },
        "summary": {
            "document_type": summary.get("document_type"),
            "parties": summary.get("parties"),
            "action_required": summary.get("action_required"),
            "consequence": summary.get("consequence"),
            "urgency": summary.get("urgency"),
            "key_date": summary.get("key_date"),
            "mock_mode": summary.get("mock_mode", False),
        },
        "audio": {
            "audio_id": audio_result.get("audio_id"),
            "audio_url": f"/audio/{audio_result.get('audio_id')}" if audio_result.get("audio_id") else None,
            "duration_estimate": audio_result.get("duration_estimate"),
            "engine": audio_result.get("engine"),
            "success": audio_result.get("success"),
        },
        "whatsapp": whatsapp_result,
    }


# ── WhatsApp webhook ───────────────────────────────────────────────────────────
@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Twilio WhatsApp webhook.
    User sends a document photo → bot replies with plain-language summary.
    """
    form_data = await request.form()
    parsed = parse_webhook_form(dict(form_data))

    logger.info(f"WhatsApp incoming — from: {parsed['from_number']}, has_media: {parsed['has_media']}")

    if not parsed["has_media"]:
        # User sent a text message — send instructions
        reply = (
            "🙏 VaaniSetu here!\n\n"
            "Send me a clear PHOTO of your legal document (court notice, summons, order) "
            "and I will explain it to you in simple language.\n\n"
            "📞 NALSA Legal Aid: 15100 (free)"
        )
        return _twilio_twiml_response(reply)

    # Download the image
    try:
        image_bytes = await download_twilio_media(parsed["media_url"])
    except Exception as e:
        logger.error(f"Media download failed: {e}")
        return _twilio_twiml_response("Sorry, I could not download your image. Please try again.")

    # Detect language from message body (e.g. "telugu" or "hindi")
    body_lower = parsed["body"].lower()
    detected_lang = "telugu"
    for lang in config.SUPPORTED_LANGUAGES:
        if lang in body_lower:
            detected_lang = lang
            break

    # Run pipeline
    try:
        ocr_result = extract_text(image_bytes, detected_lang)
        if not ocr_result.get("text"):
            return _twilio_twiml_response(
                "I could not read your document clearly. "
                "Please send a sharper, well-lit photo."
            )

        summary = summarize(ocr_result["text"], detected_lang, ocr_result.get("doc_type", ""))
        whatsapp_result = send_whatsapp_summary(parsed["from_number"], summary, detected_lang)
        logger.info(f"WhatsApp reply sent: {whatsapp_result}")
    except Exception as e:
        logger.error(f"WhatsApp pipeline error: {e}")
        return _twilio_twiml_response(
            "Sorry, I had trouble processing your document. Please try again."
        )

    # Twilio expects an empty 200 response when we send the reply separately
    return HTMLResponse("<Response/>", media_type="application/xml")


def _twilio_twiml_response(message: str) -> HTMLResponse:
    """Build a TwiML response for Twilio."""
    safe_msg = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    xml = f"<Response><Message>{safe_msg}</Message></Response>"
    return HTMLResponse(content=xml, media_type="application/xml")


# ── Demo Web UI ───────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def demo_ui():
    """Interactive demo UI for judges and testing."""
    return HTMLResponse(content=DEMO_HTML)


DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VaaniSetu | AI Legal Aid Interpreter</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f8fafc;
    color: #1e293b;
    min-height: 100vh;

    display: flex;
    flex-direction: column;
}
  .header { background: #0f766e; color: white; padding: 1.5rem 2rem;
            display: flex; align-items: center; gap: 1rem; }
  .header h1 { font-size: 1.5rem; }
  .header .hindi { font-size: 1.8rem; font-weight: 700; }
  .header p { opacity: 0.85; font-size: 0.875rem; margin-top: 2px; }
  .container{
    max-width: 800px;
    margin: 2rem auto;
    padding: 0 1rem;
    flex: 1;
}
  .card { background: white; border: 1px solid #e2e8f0; border-radius: 12px;
          padding: 1.5rem; margin-bottom: 1.5rem; }
  .card h2 { font-size: 1rem; font-weight: 600; color: #475569; margin-bottom: 1rem;
              text-transform: uppercase; letter-spacing: 0.05em; }
  label { display: block; font-size: 0.875rem; font-weight: 500; color: #374151; margin-bottom: 6px; }
  select, input[type=text] { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db;
    border-radius: 8px; font-size: 0.9rem; background: white; outline: none; }
  select:focus, input:focus { border-color: #0f766e; box-shadow: 0 0 0 3px rgba(15,118,110,0.1); }
  .upload-area { border: 2px dashed #cbd5e1; border-radius: 10px; padding: 2rem;
    text-align: center; cursor: pointer; transition: all 0.2s; background: #f8fafc; }
  .upload-area:hover, .upload-area.dragover { border-color: #0f766e; background: #f0fdfa; }
  .upload-area p { color: #64748b; font-size: 0.9rem; margin-top: 0.5rem; }
  #preview { max-width: 100%; max-height: 300px; border-radius: 8px;
             margin-top: 1rem; display: none; border: 1px solid #e2e8f0; }
  .btn { display: inline-flex; align-items: center; gap: 8px; padding: 12px 24px;
    border: none; border-radius: 8px; font-size: 1rem; font-weight: 600;
    cursor: pointer; transition: all 0.2s; }
  .btn-primary { background: #0f766e; color: white; width: 100%; justify-content: center; }
  .btn-primary:hover { background: #0d6460; }
  .btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }
  .btn-audio { background: #1d4ed8; color: white; margin-top: 1rem; }
  .btn-audio:hover { background: #1e40af; }
  .progress { display: none; margin: 1rem 0; }
  .progress-bar { height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden; }
  .progress-fill { height: 100%; background: #0f766e; border-radius: 3px;
                   animation: prog 2s ease-in-out infinite; }
  @keyframes prog { 0%{width:0%} 50%{width:70%} 100%{width:100%} }
  .step-label { font-size: 0.8rem; color: #64748b; margin-top: 6px; text-align: center; }
  .result-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .result-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; }
  .result-card.high { border-left: 3px solid #dc2626; background: #fef2f2; }
  .result-card.medium { border-left: 3px solid #d97706; background: #fffbeb; }
  .result-card.low { border-left: 3px solid #16a34a; background: #f0fdf4; }
  .result-label { font-size: 0.75rem; font-weight: 600; color: #64748b;
                  text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
  .result-value { font-size: 0.9rem; color: #1e293b; line-height: 1.5; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;
           font-weight: 600; text-transform: uppercase; }
  .badge-high { background: #fee2e2; color: #dc2626; }
  .badge-medium { background: #fef3c7; color: #d97706; }
  .badge-low { background: #dcfce7; color: #16a34a; }
  .mock-notice { background: #fef9c3; border: 1px solid #fde047; border-radius: 8px;
                 padding: 0.75rem; font-size: 0.8rem; color: #713f12; margin-top: 1rem; }
  .results-section { display: none; }
  .ocr-preview { background: #f1f5f9; border-radius: 8px; padding: 0.75rem; font-size: 0.8rem;
                 font-family: monospace; max-height: 120px; overflow-y: auto; color: #475569; }
  .conf-bar { height: 4px; background: #e2e8f0; border-radius: 2px; margin-top: 6px; }
  .conf-fill { height: 100%; border-radius: 2px; background: #0f766e; }
  audio { width: 100%; margin-top: 1rem; border-radius: 8px; }
  .nalsa { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px;
           padding: 0.75rem; text-align: center; font-size: 0.875rem; color: #1d4ed8; }
  @media (max-width: 600px) { .result-grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>

<div class="header">
  <div>
    <div class="hindi">वाणीसेतु</div>
    <h1>VaaniSetu</h1>
    <p>AI-Powered Multilingual Legal Aid Interpreter for Rural India</p>
  </div>
</div>

<div class="container">

  <!-- Upload Card -->
  <div class="card">
    <h2>Upload Court Notice / Legal Document</h2>
    <div style="margin-bottom: 1rem;">
      <label>Select your language</label>
      <select id="language">
        <option value="telugu">తెలుగు — Telugu</option>
        <option value="hindi">हिन्दी — Hindi</option>
        <option value="tamil">தமிழ் — Tamil</option>
        <option value="kannada">ಕನ್ನಡ — Kannada</option>
        <option value="malayalam">മലയാളം — Malayalam</option>
        <option value="marathi">मराठी — Marathi</option>
        <option value="bengali">বাংলা — Bengali</option>
        <option value="gujarati">ગુજરાતી — Gujarati</option>
      </select>
    </div>

    <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
      <div style="font-size: 2.5rem;">📄</div>
      <strong>Click to upload or drag & drop</strong>
      <p>Court notice, summons, legal order — any document photo</p>
      <input type="file" id="fileInput" accept="image/*" style="display:none" onchange="onFileSelect(event)">
    </div>
    <img id="preview" alt="Document preview">

    <div class="progress" id="progress">
      <div class="progress-bar"><div class="progress-fill"></div></div>
      <div class="step-label" id="stepLabel">Reading document...</div>
    </div>

    <button class="btn btn-primary" id="analyzeBtn" onclick="analyze()" disabled style="margin-top: 1rem;">
      🔍 Translate & Explain
    </button>
  </div>

  <!-- Results -->
  <div class="results-section" id="results">
    <div class="card">
      <h2>Document Analysis</h2>

      <div class="result-grid" id="summaryGrid">
        <!-- filled by JS -->
      </div>

      <div style="margin-top: 1rem;">
        <div class="result-label">OCR Text Extracted</div>
        <div class="ocr-preview" id="ocrPreview"></div>
        <div style="display:flex; align-items:center; gap:8px; margin-top: 6px;">
          <span style="font-size:0.75rem; color:#64748b;">Confidence</span>
          <div class="conf-bar" style="flex:1"><div class="conf-fill" id="confFill"></div></div>
          <span style="font-size:0.75rem; color:#0f766e; font-weight:600;" id="confLabel"></span>
        </div>
      </div>

      <div id="mockNotice" class="mock-notice" style="display:none">
        ⚡ Running in demo mode — add GROQ_API_KEY in .env for full AI summarization,
        and download IndicTrans2 model for real translation.
      </div>
    </div>

    <div class="card">
      <h2>🔊 Voice Summary</h2>
      <p style="font-size:0.875rem; color:#64748b; margin-bottom:1rem;">
        Hear the document summary in your language
      </p>
      <div id="audioSection">Loading audio...</div>
    </div>

    <div class="nalsa">
      📞 <strong>Need legal help?</strong> Call NALSA Free Legal Aid: <strong>15100</strong>
    </div>
  </div>

</div>

<script>
let selectedFile = null;
let currentAudioId = null;

const uploadArea = document.getElementById('uploadArea');
uploadArea.addEventListener('dragover', e => { e.preventDefault(); uploadArea.classList.add('dragover'); });
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
uploadArea.addEventListener('drop', e => {
  e.preventDefault();
  uploadArea.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f && f.type.startsWith('image/')) setFile(f);
});

function onFileSelect(e) {
  const f = e.target.files[0];
  if (f) setFile(f);
}

function setFile(f) {
  selectedFile = f;
  const reader = new FileReader();
  reader.onload = ev => {
    const img = document.getElementById('preview');
    img.src = ev.target.result;
    img.style.display = 'block';
  };
  reader.readAsDataURL(f);
  document.getElementById('analyzeBtn').disabled = false;
}

const steps = [
  'Reading document with OCR...',
  'Understanding legal content...',
  'Generating voice summary...',
  'Almost ready...'
];
let stepIdx = 0;
let stepInterval = null;

function startSteps() {
  stepIdx = 0;
  document.getElementById('stepLabel').textContent = steps[0];
  stepInterval = setInterval(() => {
    stepIdx = (stepIdx + 1) % steps.length;
    document.getElementById('stepLabel').textContent = steps[stepIdx];
  }, 2500);
}

async function analyze() {
  if (!selectedFile) return;

  const btn = document.getElementById('analyzeBtn');
  btn.disabled = true;
  btn.textContent = 'Analyzing...';
  document.getElementById('progress').style.display = 'block';
  document.getElementById('results').style.display = 'none';
  startSteps();

  const lang = document.getElementById('language').value;
  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('language', lang);

  try {
    const resp = await fetch('/pipeline', { method: 'POST', body: formData });
    const data = await resp.json();
    clearInterval(stepInterval);
    document.getElementById('progress').style.display = 'none';

    if (!resp.ok || data.error) {
      alert(data.error || 'Analysis failed. Please try again.');
      btn.disabled = false;
      btn.textContent = '🔍 Translate & Explain';
      return;
    }

    renderResults(data);
    document.getElementById('results').style.display = 'block';
    document.getElementById('results').scrollIntoView({ behavior: 'smooth' });

  } catch(e) {
    clearInterval(stepInterval);
    document.getElementById('progress').style.display = 'none';
    alert('Network error. Is the server running?');
  }

  btn.disabled = false;
  btn.textContent = '🔍 Translate & Explain';
}

function renderResults(data) {
  const s = data.summary;
  const urgency = s.urgency || 'medium';

  const cards = [
    { label: 'Document type', value: s.document_type || '—', class: '' },
    { label: 'Parties involved', value: s.parties || '—', class: '' },
    { label: '⚠️ What you must do', value: s.action_required || '—', class: urgency },
    { label: '❗ If ignored', value: s.consequence || '—', class: '' },
  ];

  if (s.key_date) {
    cards.push({ label: '📅 Important date', value: s.key_date, class: '' });
  }

  const grid = document.getElementById('summaryGrid');
  grid.innerHTML = cards.map(c => `
    <div class="result-card ${c.class}">
      <div class="result-label">${c.label}</div>
      <div class="result-value">${c.value}</div>
      ${c.class === 'high' ? '<span class="badge badge-high">URGENT</span>' :
        c.class === 'medium' ? '<span class="badge badge-medium">IMPORTANT</span>' : ''}
    </div>
  `).join('');

  // OCR section
  document.getElementById('ocrPreview').textContent = data.ocr.text_preview || 'No text extracted';
  const conf = data.ocr.confidence || 0;
  document.getElementById('confFill').style.width = conf + '%';
  document.getElementById('confLabel').textContent = conf + '%';

  // Mock notice
  document.getElementById('mockNotice').style.display = s.mock_mode ? 'block' : 'none';

  // Audio section
  const audioEl = document.getElementById('audioSection');
  if (data.audio && data.audio.audio_url) {
    currentAudioId = data.audio.audio_id;
    audioEl.innerHTML = `
      <audio controls autoplay src="${data.audio.audio_url}">
        Your browser does not support audio playback.
      </audio>
      <p style="font-size:0.8rem; color:#64748b; margin-top:6px;">
        Estimated duration: ~${data.audio.duration_estimate} seconds
        &nbsp;|&nbsp; Engine: ${data.audio.engine}
      </p>
    `;
  } else {
    audioEl.innerHTML = '<p style="color:#dc2626; font-size:0.875rem;">Audio generation failed. Check server logs.</p>';
  }
}
</script>

<footer style="
    margin-top: 40px;
    padding: 24px;
    text-align: center;
    background: #f8fafc;
    border-top: 1px solid #e5e7eb;
">
    <div style="font-size:18px;font-weight:600;color:#0f766e;">
        VaaniSetu
    </div>

    <div style="margin-top:6px;color:#475569;">
        AI-Powered Multilingual Legal Aid Interpreter for Rural India
    </div>

    <div style="margin-top:10px;font-size:13px;color:#64748b;">
        Bharat Academix CodeQuest 2026 • Social Impact & AI
    </div>

    <div style="margin-top:6px;font-size:13px;color:#64748b;">
        Built by Maddiboina Triveni
    </div>
</footer>

</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.APP_HOST,
        port=config.APP_PORT,
        reload=config.DEBUG,
        log_level="info",
    )
