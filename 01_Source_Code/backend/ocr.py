"""
VaaniSetu — OCR Pipeline
Reads legal documents from images using Tesseract + OpenCV preprocessing.
Handles Telugu, Hindi, Tamil, Kannada, and English scripts.
"""
import io
import os
import logging
import numpy as np
import pytesseract
import cv2
from PIL import Image
from config import TESSERACT_LANG_MAP, DOCUMENT_TYPES

logger = logging.getLogger(__name__)


def load_image(source) -> np.ndarray:
    """
    Load image from file path, bytes, or PIL Image.
    Returns BGR numpy array.
    """
    if isinstance(source, np.ndarray):
        return source
    if isinstance(source, Image.Image):
        return cv2.cvtColor(np.array(source), cv2.COLOR_RGB2BGR)
    if isinstance(source, (bytes, bytearray)):
        arr = np.frombuffer(source, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if isinstance(source, str) and os.path.exists(source):
        return cv2.imread(source)
    raise ValueError(f"Cannot load image from: {type(source)}")


def deskew(image: np.ndarray) -> np.ndarray:
    """Detect and correct image skew using Hough line transform."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10)
    if lines is None:
        return image
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) < 45:
            angles.append(angle)
    if not angles:
        return image
    median_angle = np.median(angles)
    if abs(median_angle) < 0.5:
        return image
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def preprocess(image: np.ndarray) -> np.ndarray:
    """
    Full preprocessing pipeline for legal document images:
    1. Deskew
    2. Grayscale
    3. Resize to 300 DPI equivalent
    4. Denoise
    5. Adaptive threshold (handles shadows and uneven lighting)
    """
    img = deskew(image)

    # Convert to grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # Upscale if image is small (Tesseract works best at 300+ DPI)
    h, w = gray.shape
    if w < 1200:
        scale = 1200 / w
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    # Adaptive threshold — handles shadows and uneven illumination
    thresh = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2
    )

    # Morphological opening to remove noise specks
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    return cleaned


def compute_confidence(data: dict) -> float:
    """Compute average OCR confidence from Tesseract output data."""
    confidences = [c for c in data.get("conf", []) if isinstance(c, (int, float)) and c > 0]
    if not confidences:
        return 0.0
    return round(float(np.mean(confidences)), 1)


def classify_document(text: str) -> str:
    """Detect document type from extracted text using keyword matching."""
    text_lower = text.lower()
    for doc_type, keywords in DOCUMENT_TYPES.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                return doc_type
    return "legal_document"


def extract_text(image_source, target_language: str = "telugu") -> dict:
    """
    Main OCR function.

    Args:
        image_source: File path, bytes, PIL Image, or numpy array
        target_language: Target translation language (used to pick OCR lang pack)

    Returns:
        dict with keys: text, confidence, doc_type, language_hint, word_count
    """
    try:
        image = load_image(image_source)
    except Exception as e:
        logger.error(f"Image loading failed: {e}")
        return {"error": f"Could not load image: {e}", "text": "", "confidence": 0.0}

    processed = preprocess(image)

    # Choose OCR language pack
    ocr_lang = TESSERACT_LANG_MAP.get(target_language, TESSERACT_LANG_MAP["default"])

    # Tesseract config: PSM 6 = assume uniform text block, OEM 3 = LSTM engine
    tess_config = "--psm 6 --oem 3"

    try:
        raw_text = pytesseract.image_to_string(processed, lang=ocr_lang, config=tess_config)
        data = pytesseract.image_to_data(processed, lang=ocr_lang, config=tess_config,
                                          output_type=pytesseract.Output.DICT)
    except Exception as e:
        logger.error(f"Tesseract OCR failed: {e}")
        # Fallback to English only
        try:
            raw_text = pytesseract.image_to_string(processed, lang="eng", config=tess_config)
            data = pytesseract.image_to_data(processed, lang="eng", config=tess_config,
                                              output_type=pytesseract.Output.DICT)
        except Exception as e2:
            return {"error": f"OCR failed: {e2}", "text": "", "confidence": 0.0}

    text = raw_text.strip()
    confidence = compute_confidence(data)
    doc_type = classify_document(text)
    word_count = len(text.split())

    logger.info(f"OCR complete — confidence: {confidence}%, words: {word_count}, type: {doc_type}")

    return {
        "text": text,
        "confidence": confidence,
        "doc_type": doc_type,
        "word_count": word_count,
        "language_hint": ocr_lang,
        "low_quality": confidence < 60.0,
    }
