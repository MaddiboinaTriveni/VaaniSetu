"""
VaaniSetu — Backend Test Suite
Run with: python -m pytest tests/ -v
or:       python tests/test_backend.py
"""
import sys
import os
import io
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_test_image(text: str = "COURT SUMMONS\nCase No: 1234/2024\nYou are hereby summoned") -> bytes:
    """Generate a synthetic legal document image for OCR testing."""
    img = Image.new("RGB", (800, 400), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def print_result(name: str, result: dict, passed: bool):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}  {name}")
    if not passed:
        print(f"       Result: {result}")


# ─────────────────────────────────────────────────────────────────────────────
# OCR tests
# ─────────────────────────────────────────────────────────────────────────────

def test_ocr_basic():
    from ocr import extract_text
    img_bytes = make_test_image("COURT SUMMONS Case Number 1234")
    result = extract_text(img_bytes, "telugu")
    passed = (
        isinstance(result, dict)
        and "text" in result
        and "confidence" in result
        and len(result["text"]) > 0
    )
    print_result("OCR — basic text extraction", result, passed)
    return passed


def test_ocr_document_classification():
    from ocr import extract_text
    img_bytes = make_test_image("COURT SUMMONS\nYou are hereby ordered to appear")
    result = extract_text(img_bytes, "telugu")
    passed = result.get("doc_type") in ["summons", "legal_document", "order", "notice"]
    print_result("OCR — document type classification", result, passed)
    return passed


def test_ocr_confidence_score():
    from ocr import extract_text
    img_bytes = make_test_image("Hello World Legal Notice")
    result = extract_text(img_bytes, "telugu")
    passed = isinstance(result.get("confidence"), float) and 0 <= result["confidence"] <= 100
    print_result("OCR — confidence score range 0–100", result, passed)
    return passed


def test_ocr_empty_input():
    from ocr import extract_text
    # Completely black image
    img = Image.new("RGB", (100, 100), color="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result = extract_text(buf.getvalue(), "telugu")
    passed = isinstance(result, dict) and "text" in result
    print_result("OCR — handles empty/blank image gracefully", result, passed)
    return passed


# ─────────────────────────────────────────────────────────────────────────────
# Translation tests
# ─────────────────────────────────────────────────────────────────────────────

def test_translate_returns_dict():
    from translate import translate
    result = translate("You must appear in court on Monday.", "telugu")
    passed = (
        isinstance(result, dict)
        and "translated_text" in result
        and len(result["translated_text"]) > 0
    )
    print_result("Translate — returns dict with translated_text", result, passed)
    return passed


def test_translate_empty_text():
    from translate import translate
    result = translate("", "telugu")
    passed = result.get("translated_text") == ""
    print_result("Translate — handles empty string", result, passed)
    return passed


def test_translate_unknown_language():
    from translate import translate
    result = translate("Hello world", "klingon")
    # Should fall back to telugu, not crash
    passed = isinstance(result, dict) and "translated_text" in result
    print_result("Translate — unknown language falls back gracefully", result, passed)
    return passed


def test_translate_long_text():
    from translate import translate
    long_text = "This is a legal notice. " * 200  # ~800 words
    result = translate(long_text, "hindi")
    passed = isinstance(result, dict) and len(result.get("translated_text", "")) > 0
    print_result("Translate — handles long text (chunking)", result, passed)
    return passed


# ─────────────────────────────────────────────────────────────────────────────
# Summarize tests
# ─────────────────────────────────────────────────────────────────────────────

def test_summarize_returns_all_fields():
    from summarize import summarize
    text = "Court Summons No. 456/2024. You must appear before the District Court on 15th March 2024."
    result = summarize(text, "telugu")
    required_fields = ["document_type", "parties", "action_required", "consequence", "urgency"]
    passed = all(f in result for f in required_fields)
    print_result("Summarize — all required fields present", result, passed)
    return passed


def test_summarize_urgency_values():
    from summarize import summarize
    result = summarize("Court summons urgent hearing.", "telugu")
    passed = result.get("urgency") in ["high", "medium", "low"]
    print_result("Summarize — urgency has valid value", result, passed)
    return passed


def test_summarize_voice_text_built():
    from summarize import summarize
    result = summarize("Legal notice for property dispute.", "telugu")
    passed = "voice_text" in result and len(result.get("voice_text", "")) > 10
    print_result("Summarize — voice_text field built", result, passed)
    return passed


def test_summarize_empty_text():
    from summarize import summarize
    result = summarize("", "telugu")
    passed = isinstance(result, dict) and "document_type" in result
    print_result("Summarize — handles empty text", result, passed)
    return passed


# ─────────────────────────────────────────────────────────────────────────────
# TTS tests
# ─────────────────────────────────────────────────────────────────────────────

def test_tts_generates_file():
    from voice import text_to_speech
    result = text_to_speech("You must appear in court.", "telugu")
    passed = (
        isinstance(result, dict)
        and result.get("success") is True
        and result.get("audio_id") is not None
    )
    print_result("TTS — generates audio file", result, passed)
    return passed


def test_tts_file_exists_on_disk():
    from voice import text_to_speech
    import os, config
    result = text_to_speech("Court notice test.", "hindi")
    if result.get("success"):
        path = result.get("audio_path", "")
        passed = os.path.exists(path) and os.path.getsize(path) > 0
    else:
        passed = False
    print_result("TTS — audio file actually written to disk", result, passed)
    return passed


def test_tts_empty_text():
    from voice import text_to_speech
    result = text_to_speech("", "telugu")
    passed = result.get("success") is False
    print_result("TTS — handles empty text gracefully", result, passed)
    return passed


# ─────────────────────────────────────────────────────────────────────────────
# SMS / WhatsApp tests
# ─────────────────────────────────────────────────────────────────────────────

def test_sms_mock_mode():
    from sms import send_whatsapp_summary
    summary = {
        "document_type": "Court Summons",
        "parties": "District Court → Ramu",
        "action_required": "Appear in court by March 15",
        "consequence": "Warrant may be issued",
        "urgency": "high",
        "key_date": "March 15, 2024",
    }
    result = send_whatsapp_summary("+919876543210", summary, "telugu")
    # In mock mode (no Twilio creds), should return success=False with mock=True
    passed = isinstance(result, dict) and "formatted_message" in result
    print_result("SMS — mock mode returns formatted message", result, passed)
    return passed


def test_sms_format_message():
    from sms import _format_sms_message
    summary = {
        "document_type": "Court Notice",
        "parties": "Revenue Court",
        "action_required": "Attend hearing",
        "consequence": "Ex-parte order",
        "urgency": "high",
        "key_date": "2024-03-20",
    }
    msg = _format_sms_message(summary)
    passed = len(msg) <= 1600 and "VaaniSetu" in msg and "NALSA" in msg
    print_result("SMS — formatted message length ≤ 1600 chars", {"length": len(msg)}, passed)
    return passed


# ─────────────────────────────────────────────────────────────────────────────
# Config tests
# ─────────────────────────────────────────────────────────────────────────────

def test_config_languages_loaded():
    from config import SUPPORTED_LANGUAGES
    passed = len(SUPPORTED_LANGUAGES) >= 6 and "telugu" in SUPPORTED_LANGUAGES
    print_result("Config — supported languages loaded correctly", SUPPORTED_LANGUAGES, passed)
    return passed


def test_config_audio_dir_created():
    from config import AUDIO_DIR
    import os
    passed = os.path.isdir(AUDIO_DIR)
    print_result("Config — audio directory exists", {"path": AUDIO_DIR}, passed)
    return passed


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end pipeline test
# ─────────────────────────────────────────────────────────────────────────────

def test_e2e_pipeline():
    """Full pipeline: image → OCR → summarize → TTS → result"""
    from ocr import extract_text
    from summarize import summarize
    from voice import text_to_speech

    print("\n  Running E2E pipeline test...")
    img_bytes = make_test_image(
        "DISTRICT COURT SUMMONS\n"
        "Case No. 789/2024\n"
        "To: Ramu Naidu, Village Kondapalli\n"
        "You are hereby summoned to appear before this court\n"
        "on 20th March 2024 at 10:00 AM\n"
        "regarding the land dispute case filed by Raju Reddy.\n"
        "Failure to appear will result in ex-parte proceedings."
    )

    # Step 1 — OCR
    ocr = extract_text(img_bytes, "telugu")
    assert ocr.get("text"), "OCR produced no text"
    print(f"  OCR: {ocr['word_count']} words, confidence {ocr['confidence']}%")

    # Step 2 — Summarize
    summ = summarize(ocr["text"], "telugu", ocr.get("doc_type", ""))
    assert "action_required" in summ, "Summary missing action_required"
    print(f"  Summary: doc_type={summ['document_type']}, urgency={summ['urgency']}")

    # Step 3 — TTS
    voice = text_to_speech(summ.get("voice_text", "Test audio"), "telugu")
    print(f"  TTS: success={voice['success']}, engine={voice.get('engine')}")

    passed = ocr.get("word_count", 0) > 0 and "action_required" in summ
    print_result("E2E — full pipeline (OCR → Summarize → TTS)", {}, passed)
    return passed


# ─────────────────────────────────────────────────────────────────────────────
# Run all tests
# ─────────────────────────────────────────────────────────────────────────────

def run_all():
    print("\n" + "="*60)
    print("  VaaniSetu — Backend Test Suite")
    print("="*60 + "\n")

    tests = [
        ("OCR",        [test_ocr_basic, test_ocr_document_classification,
                        test_ocr_confidence_score, test_ocr_empty_input]),
        ("Translation",[test_translate_returns_dict, test_translate_empty_text,
                        test_translate_unknown_language, test_translate_long_text]),
        ("Summarize",  [test_summarize_returns_all_fields, test_summarize_urgency_values,
                        test_summarize_voice_text_built, test_summarize_empty_text]),
        ("TTS",        [test_tts_generates_file, test_tts_file_exists_on_disk,
                        test_tts_empty_text]),
        ("SMS",        [test_sms_mock_mode, test_sms_format_message]),
        ("Config",     [test_config_languages_loaded, test_config_audio_dir_created]),
        ("E2E",        [test_e2e_pipeline]),
    ]

    total = passed = 0
    for group, fns in tests:
        print(f"\n── {group} ──")
        for fn in fns:
            total += 1
            try:
                if fn():
                    passed += 1
            except Exception as e:
                print(f"❌ FAIL  {fn.__name__} — Exception: {e}")

    print("\n" + "="*60)
    print(f"  Results: {passed}/{total} tests passed")
    if passed == total:
        print("  🎉 All tests passed!")
    else:
        print(f"  ⚠️  {total - passed} test(s) failed")
    print("="*60 + "\n")
    return passed == total


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
