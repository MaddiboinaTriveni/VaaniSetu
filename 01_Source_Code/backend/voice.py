"""
VaaniSetu — Voice Output Module
Converts legal document summaries to regional language audio using gTTS.
Supports Telugu, Hindi, Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati.
"""
import logging
import os
import uuid
from pathlib import Path
from config import AUDIO_DIR, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


def _gtts_generate(text: str, lang_code: str, output_path: str) -> bool:
    """Generate MP3 using Google Text-to-Speech (gTTS)."""
    from gtts import gTTS
    tts = gTTS(text=text, lang=lang_code, slow=False)
    tts.save(output_path)
    return True


def _pyttsx3_fallback(text: str, output_path: str) -> bool:
    """Offline TTS fallback using pyttsx3 (English only when gTTS fails)."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 150)
        engine.save_to_file(text, output_path.replace(".mp3", ".wav"))
        engine.runAndWait()
        return True
    except Exception as e:
        logger.error(f"pyttsx3 fallback failed: {e}")
        return False


def _espeak_fallback(text: str, output_path: str, lang_code: str = "en") -> bool:
    """Offline TTS using espeak — available on Linux without internet."""
    import subprocess, shutil
    if not shutil.which("espeak"):
        return False
    wav_path = output_path.replace(".mp3", ".wav")
    # espeak language mapping (basic)
    espeak_lang = {
        "te": "te", "hi": "hi", "ta": "ta",
        "kn": "kn", "ml": "ml", "mr": "mr",
    }.get(lang_code, "en")
    try:
        result = subprocess.run(
            ["espeak", "-v", espeak_lang, "-w", wav_path, text[:500]],
            capture_output=True, timeout=30
        )
        return result.returncode == 0 and os.path.exists(wav_path)
    except Exception as e:
        logger.error(f"espeak fallback failed: {e}")
        return False


def text_to_speech(text: str, target_lang: str = "telugu") -> dict:
    """
    Convert summary text to speech audio.

    Args:
        text: Text to convert to speech
        target_lang: Language key from SUPPORTED_LANGUAGES

    Returns:
        dict with: audio_path, audio_filename, duration_estimate, lang_code, success
    """
    if not text or not text.strip():
        return {"success": False, "error": "No text provided"}

    lang_info = SUPPORTED_LANGUAGES.get(target_lang, SUPPORTED_LANGUAGES["telugu"])
    gtts_code = lang_info["gtts"]
    audio_id = uuid.uuid4().hex
    filename = f"vaanisetu_{audio_id}.mp3"
    output_path = os.path.join(AUDIO_DIR, filename)

    # Estimate duration: ~150 words/min for Indian languages
    word_count = len(text.split())
    duration_estimate = max(5, int(word_count / 2.5))

    # Try gTTS (requires internet)
    try:
        success = _gtts_generate(text, gtts_code, output_path)
        if success and os.path.exists(output_path):
            size_kb = os.path.getsize(output_path) // 1024
            logger.info(f"Audio generated: {filename} ({size_kb} KB)")
            return {
                "success": True,
                "audio_path": output_path,
                "audio_filename": filename,
                "audio_id": audio_id,
                "duration_estimate": duration_estimate,
                "lang_code": gtts_code,
                "engine": "gTTS",
            }
    except Exception as e:
        logger.warning(f"gTTS failed ({e}), trying fallback")

    # Fallback 1: pyttsx3
    try:
        wav_path = output_path.replace(".mp3", ".wav")
        if _pyttsx3_fallback(text, wav_path) and os.path.exists(wav_path):
            return {
                "success": True,
                "audio_path": wav_path,
                "audio_filename": filename.replace(".mp3", ".wav"),
                "audio_id": audio_id,
                "duration_estimate": duration_estimate,
                "lang_code": "en",
                "engine": "pyttsx3_fallback",
            }
    except Exception:
        pass

    # Fallback 2: espeak (offline, Linux)
    try:
        wav_path = output_path.replace(".mp3", ".wav")
        if _espeak_fallback(text, wav_path, gtts_code) and os.path.exists(wav_path):
            return {
                "success": True,
                "audio_path": wav_path,
                "audio_filename": filename.replace(".mp3", ".wav"),
                "audio_id": audio_id,
                "duration_estimate": duration_estimate,
                "lang_code": gtts_code,
                "engine": "espeak_offline",
            }
    except Exception as e:
        logger.error(f"All TTS engines failed: {e}")

    return {
        "success": False,
        "error": "Text-to-speech generation failed. Check internet connection.",
        "audio_id": audio_id,
    }


def cleanup_audio(audio_id: str):
    """Remove audio file after it's been served."""
    for ext in [".mp3", ".wav"]:
        path = os.path.join(AUDIO_DIR, f"vaanisetu_{audio_id}{ext}")
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Cleaned up audio: {path}")
            except Exception as e:
                logger.warning(f"Could not remove {path}: {e}")


def list_audio_files() -> list:
    """List all audio files in the audio directory."""
    files = []
    for f in Path(AUDIO_DIR).glob("vaanisetu_*.mp3"):
        files.append({"filename": f.name, "size_kb": f.stat().st_size // 1024})
    for f in Path(AUDIO_DIR).glob("vaanisetu_*.wav"):
        files.append({"filename": f.name, "size_kb": f.stat().st_size // 1024})
    return files
