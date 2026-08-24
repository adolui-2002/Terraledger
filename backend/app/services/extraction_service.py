"""
Extraction pipeline: turns raw uploaded bytes into (raw_text, structured
fields). Each document type gets a dedicated extraction path so that a
corrupt or unusual file degrades gracefully instead of crashing the
pipeline (see tests/test_extraction_service.py for the negative-path
tests this is designed to satisfy).
"""
from __future__ import annotations

import hashlib
import io
import re

AMOUNT_PATTERN = re.compile(r"(?:₹|rs\.?|inr)\s?([\d,]+(?:\.\d+)?)\s?(lakh|lac|crore)?", re.IGNORECASE)
DATE_PATTERN = re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b")
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_pdf_text(data: bytes) -> tuple[str, bool]:
    """Returns (text, used_ocr_fallback)."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        if text.strip():
            return text, False
    except Exception:
        pass
    # Fall back to OCR-style handling for scanned/corrupt PDFs. In a full
    # deployment this would rasterize pages (pdf2image) and OCR each one;
    # kept as an explicit, clearly-labelled extension point for the POC.
    return "", True


def extract_image_text(data: bytes) -> tuple[str, float]:
    """OCR an image. Returns (text, confidence 0-1). Never raises."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        words = [w for w in ocr_data.get("text", []) if w.strip()]
        confs = [float(c) for c in ocr_data.get("conf", []) if str(c).replace(".", "", 1).lstrip("-").isdigit()]
        confs = [c for c in confs if c >= 0]
        text = " ".join(words)
        avg_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        return text, avg_conf
    except Exception:
        return "", 0.0


def extract_xlsx_amounts(data: bytes) -> list[float]:
    """Pull numeric totals out of a budget spreadsheet, gracefully."""
    try:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        amounts: list[float] = []
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, (int, float)) and cell.value > 1000:
                        amounts.append(float(cell.value))
        return amounts
    except Exception:
        return []


def _normalize_amount(raw: str, unit: str | None) -> float:
    value = float(raw.replace(",", ""))
    if unit and unit.lower() in ("lakh", "lac"):
        value *= 100_000
    elif unit and unit.lower() == "crore":
        value *= 10_000_000
    return value


def extract_amounts(text: str) -> list[float]:
    if not text:
        return []
    return [_normalize_amount(m.group(1), m.group(2)) for m in AMOUNT_PATTERN.finditer(text)]


def extract_dates(text: str) -> list[str]:
    if not text:
        return []
    return [f"{y}-{m.zfill(2)}-{d.zfill(2)}" for (y, m, d) in DATE_PATTERN.findall(text)]


def detect_language(text: str) -> str:
    if not text or len(text.strip()) < 10:
        return "en"
    try:
        from langdetect import detect

        return detect(text)
    except Exception:
        return "en"


def extract_structured_fields(text: str) -> dict[str, str]:
    """Lightweight heuristic field extraction (no ML model required for
    the POC). Each hit is later stored as an ExtractedField with a
    confidence score so low-confidence extractions can be routed to a
    human for verification.
    """
    fields: dict[str, str] = {}
    amounts = extract_amounts(text)
    if amounts:
        fields["extracted_amount"] = str(max(amounts))
    dates = extract_dates(text)
    if dates:
        fields["extracted_date"] = dates[0]
    duration_match = re.search(r"(\d{1,3})\s*(month|year)s?", text, re.IGNORECASE)
    if duration_match:
        fields["project_duration"] = f"{duration_match.group(1)} {duration_match.group(2)}(s)"
    return fields
