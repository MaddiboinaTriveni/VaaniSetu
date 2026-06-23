"""
VaaniSetu — Legal Document Summarizer
Uses Groq API (free tier, Llama 3 70B) to extract structured plain-language
summaries from legal documents. Designed for zero-literacy rural users.
"""
import logging
import json
import re
from config import GROQ_API_KEY, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are VaaniSetu, a legal document translator helping rural Indians understand court documents.

Your job: Read the legal document text and extract 4 key pieces of information in PLAIN, SIMPLE language.
Write as if explaining to a farmer who has never been to school.

RULES:
- Use ONLY simple everyday words. NO legal jargon.
- Each answer must be ONE clear sentence.
- If information is not found, write "Not mentioned in this document."
- Respond ONLY with valid JSON. No extra text before or after.

Return this exact JSON structure:
{
  "document_type": "What type of document this is (summons/court notice/order/etc.)",
  "parties": "Who sent this and to whom",
  "action_required": "What the person MUST DO and by WHEN (most important!)",
  "consequence": "What will happen if they ignore this",
  "urgency": "high/medium/low",
  "key_date": "The most important date mentioned, or null if none"
}"""

# ── Mock fallback ─────────────────────────────────────────────────────────────
MOCK_SUMMARY = {
    "document_type": "Court Summons",
    "parties": "Sent by the District Court to the document holder",
    "action_required": "You must appear before the court on the date mentioned in this document",
    "consequence": "If you do not appear, the court may issue a warrant against you",
    "urgency": "high",
    "key_date": "Check the original document for the exact date",
    "mock_mode": True,
    "note": "Add your GROQ_API_KEY in .env to enable real AI summarization",
}

# Language-specific explanation templates for voice output
VOICE_TEMPLATES = {
    "telugu": (
        "ఈ పత్రం గురించి ముఖ్యమైన విషయాలు:\n"
        "పత్రం రకం: {document_type}\n"
        "ఏమి చేయాలి: {action_required}\n"
        "చేయకపోతే: {consequence}"
    ),
    "hindi": (
        "इस दस्तावेज़ के बारे में महत्वपूर्ण जानकारी:\n"
        "दस्तावेज़ का प्रकार: {document_type}\n"
        "आपको क्या करना है: {action_required}\n"
        "न करने पर: {consequence}"
    ),
    "tamil": (
        "இந்த ஆவணம் பற்றி முக்கியமான தகவல்கள்:\n"
        "ஆவண வகை: {document_type}\n"
        "நீங்கள் என்ன செய்ய வேண்டும்: {action_required}\n"
        "செய்யாவிட்டால்: {consequence}"
    ),
    "kannada": (
        "ಈ ದಾಖಲೆಯ ಬಗ್ಗೆ ಮುಖ್ಯ ವಿಷಯಗಳು:\n"
        "ದಾಖಲೆಯ ವಿಧ: {document_type}\n"
        "ನೀವು ಏನು ಮಾಡಬೇಕು: {action_required}\n"
        "ಮಾಡದಿದ್ದರೆ: {consequence}"
    ),
    "default": (
        "Important information about this document:\n"
        "Document type: {document_type}\n"
        "What you must do: {action_required}\n"
        "If you don't: {consequence}"
    ),
}


def _call_groq(text: str, target_lang: str) -> dict:
    """Call Groq API to summarize the legal document."""
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)

    lang_label = SUPPORTED_LANGUAGES.get(target_lang, {}).get("label", target_lang)

    user_message = (
        f"Legal document text:\n\n{text[:3000]}\n\n"
        f"Extract the summary in English first (for the JSON fields), "
        f"then for the 'action_required' and 'consequence' fields also provide "
        f"a simple version in {lang_label} language."
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=600,
        temperature=0.1,
    )

    raw = response.choices[0].message.content.strip()

    # Extract JSON from response (handle cases where model adds extra text)
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        result = json.loads(json_match.group())
    else:
        result = json.loads(raw)

    result["mock_mode"] = False
    return result


def build_voice_text(summary: dict, target_lang: str) -> str:
    """Build the text that will be converted to speech."""
    template = VOICE_TEMPLATES.get(target_lang, VOICE_TEMPLATES["default"])
    return template.format(
        document_type=summary.get("document_type", "Legal document"),
        action_required=summary.get("action_required", "Please check this document carefully"),
        consequence=summary.get("consequence", "There may be legal consequences"),
    )


def summarize(text: str, target_lang: str = "telugu", doc_type: str = "legal_document") -> dict:
    """
    Generate a structured plain-language summary of a legal document.

    Args:
        text: Extracted OCR text from the document
        target_lang: Target language for voice output
        doc_type: Pre-classified document type (from OCR module)

    Returns:
        dict with: document_type, parties, action_required, consequence,
                   urgency, key_date, voice_text, mock_mode
    """
    if not text or not text.strip():
        return {**MOCK_SUMMARY, "voice_text": build_voice_text(MOCK_SUMMARY, target_lang)}

    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        logger.warning("GROQ_API_KEY not set — returning mock summary")
        result = {**MOCK_SUMMARY}
        result["voice_text"] = build_voice_text(result, target_lang)
        return result

    try:
        result = _call_groq(text, target_lang)
        result["voice_text"] = build_voice_text(result, target_lang)
        logger.info(f"Groq summarization complete — urgency: {result.get('urgency')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error from Groq: {e}")
        result = {**MOCK_SUMMARY, "error_detail": "JSON parse error"}
        result["voice_text"] = build_voice_text(result, target_lang)
        return result

    except Exception as e:
        logger.error(f"Groq API call failed: {e}")
        result = {**MOCK_SUMMARY, "error_detail": str(e)}
        result["voice_text"] = build_voice_text(result, target_lang)
        return result
