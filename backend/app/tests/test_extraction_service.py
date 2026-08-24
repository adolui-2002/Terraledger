from app.services import extraction_service


def test_corrupt_pdf_does_not_raise():
    garbage = b"%PDF-1.4 this is not a real pdf stream" + b"\x00\x01\x02" * 50
    text, needs_ocr = extraction_service.extract_pdf_text(garbage)
    assert isinstance(text, str)
    assert needs_ocr is True  # falls back to manual/OCR review instead of crashing


def test_corrupt_image_does_not_raise():
    garbage = b"not a real image" * 20
    text, confidence = extraction_service.extract_image_text(garbage)
    assert text == ""
    assert confidence == 0.0


def test_corrupt_xlsx_does_not_raise():
    garbage = b"not a real spreadsheet"
    amounts = extraction_service.extract_xlsx_amounts(garbage)
    assert amounts == []


def test_extract_amounts_handles_lakh_and_crore():
    text = "Total is ₹5 lakh for phase 1 and Rs. 1.2 crore overall."
    amounts = extraction_service.extract_amounts(text)
    assert 500000.0 in amounts
    assert 12000000.0 in amounts


def test_extract_amounts_empty_text():
    assert extraction_service.extract_amounts("") == []
    assert extraction_service.extract_amounts(None) == []


def test_detect_language_falls_back_safely_on_short_text():
    assert extraction_service.detect_language("hi") == "en"
