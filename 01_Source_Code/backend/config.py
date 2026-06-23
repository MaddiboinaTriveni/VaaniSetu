"""
VaaniSetu — Configuration
Loads environment variables from .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

AUDIO_DIR = os.getenv("AUDIO_DIR", "/tmp/vaanisetu_audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# Supported languages
SUPPORTED_LANGUAGES = {
    "telugu":    {"code": "tel", "gtts": "te", "indic": "tel_Telu", "label": "తెలుగు"},
    "hindi":     {"code": "hin", "gtts": "hi", "indic": "hin_Deva", "label": "हिन्दी"},
    "tamil":     {"code": "tam", "gtts": "ta", "indic": "tam_Taml", "label": "தமிழ்"},
    "kannada":   {"code": "kan", "gtts": "kn", "indic": "kan_Knda", "label": "ಕನ್ನಡ"},
    "malayalam": {"code": "mal", "gtts": "ml", "indic": "mal_Mlym", "label": "മലയാളം"},
    "marathi":   {"code": "mar", "gtts": "mr", "indic": "mar_Deva", "label": "मराठी"},
    "bengali":   {"code": "ben", "gtts": "bn", "indic": "ben_Beng", "label": "বাংলা"},
    "gujarati":  {"code": "guj", "gtts": "gu", "indic": "guj_Gujr", "label": "ગુજરાતી"},
}

# OCR language strings for Tesseract
TESSERACT_LANG_MAP = {
    "telugu":  "tel+eng",
    "hindi":   "hin+eng",
    "tamil":   "tam+eng",
    "kannada": "kan+eng",
    "marathi": "hin+eng",  # Devanagari
    "default": "eng",
}

# Document type keywords for classification
DOCUMENT_TYPES = {
    "summons":    ["summons", "आदेशिका", "సమన్లు", "சம்மன்"],
    "notice":     ["notice", "नोटिस", "నోటీసు", "அறிவிப்பு"],
    "order":      ["order", "आदेश", "ఆదేశం", "உத்தரவு"],
    "warrant":    ["warrant", "वारंट", "వారెంట్", "வாரண்ட்"],
    "judgment":   ["judgment", "judgement", "निर्णय", "తీర్పు", "தீர்ப்பு"],
    "petition":   ["petition", "याचिका", "పిటిషన్", "மனு"],
}
