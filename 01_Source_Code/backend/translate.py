"""
VaaniSetu — Translation Pipeline
Uses IndicTrans2 (AI4Bharat/IIT Madras) for Indian language translation.
Falls back to a rule-based mock when the model is not downloaded yet,
so the rest of the app runs during development.
"""
import logging
import os
from config import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

# ── Try to load IndicTrans2 ──────────────────────────────────────────────────
# The model is ~4GB. First-run download takes time.
# If not available, MOCK_MODE = True and we return a placeholder translation.

MOCK_MODE = True
_model = None
_tokenizer = None


def _try_load_model():
    global MOCK_MODE, _model, _tokenizer
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        import torch

        model_name = "ai4bharat/indictrans2-en-indic-1B"
        logger.info(f"Loading IndicTrans2 model: {model_name}")
        _tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        _model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype=torch.float32,
        )
        _model.eval()
        MOCK_MODE = False
        logger.info("IndicTrans2 loaded successfully — real translation active")
    except Exception as e:
        logger.warning(f"IndicTrans2 not available ({e}). Running in MOCK_MODE.")
        MOCK_MODE = True


def _translate_real(text: str, target_lang: str) -> str:
    """Run actual IndicTrans2 inference."""
    import torch
    lang_info = SUPPORTED_LANGUAGES.get(target_lang, SUPPORTED_LANGUAGES["telugu"])
    tgt_code = lang_info["indic"]

    inputs = _tokenizer(
        text,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512,
    )

    with torch.no_grad():
        outputs = _model.generate(
            **inputs,
            forced_bos_token_id=_tokenizer.convert_tokens_to_ids(tgt_code),
            max_length=512,
            num_beams=4,
            early_stopping=True,
        )

    return _tokenizer.decode(outputs[0], skip_special_tokens=True)


def _translate_mock(text: str, target_lang: str) -> str:
    """
    Mock translation — returns a clearly labelled placeholder so the
    full pipeline can be tested without the 4GB model downloaded.
    Replace with _translate_real() once model is available.
    """
    lang_info = SUPPORTED_LANGUAGES.get(target_lang, {})
    label = lang_info.get("label", target_lang)

    # Show first 200 chars of original + language label so the demo still makes sense
    preview = text[:200].strip()
    return (
        f"[{label} translation — IndicTrans2 model not yet downloaded]\n\n"
        f"Original document excerpt:\n{preview}...\n\n"
        f"To enable real translation, download the IndicTrans2 model:\n"
        f"  pip install transformers torch\n"
        f"  python -c \"from transformers import AutoTokenizer; "
        f"AutoTokenizer.from_pretrained('ai4bharat/indictrans2-en-indic-1B', trust_remote_code=True)\""
    )


def translate(text: str, target_lang: str = "telugu") -> dict:
    """
    Translate document text into the target Indian language.

    Args:
        text: Source text (English or mixed)
        target_lang: Language key from SUPPORTED_LANGUAGES

    Returns:
        dict with: translated_text, target_lang, mock_mode
    """
    if not text or not text.strip():
        return {"translated_text": "", "target_lang": target_lang, "mock_mode": MOCK_MODE}

    if target_lang not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unknown language: {target_lang}, falling back to telugu")
        target_lang = "telugu"

    # Chunk long texts (model max is 512 tokens ≈ ~350 words)
    words = text.split()
    chunk_size = 300
    chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

    translated_chunks = []
    for chunk in chunks:
        if MOCK_MODE:
            translated_chunks.append(_translate_mock(chunk, target_lang))
        else:
            try:
                translated_chunks.append(_translate_real(chunk, target_lang))
            except Exception as e:
                logger.error(f"Translation chunk failed: {e}")
                translated_chunks.append(_translate_mock(chunk, target_lang))

    translated = "\n".join(translated_chunks)
    logger.info(f"Translation complete — lang: {target_lang}, mock: {MOCK_MODE}")

    return {
        "translated_text": translated,
        "target_lang": target_lang,
        "mock_mode": MOCK_MODE,
    }


# Attempt model load at import time (non-blocking — MOCK_MODE stays True if it fails)
_try_load_model()
