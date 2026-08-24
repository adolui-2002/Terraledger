"""
Multilingual normalization pipeline:

    document -> detect_language -> (translate if needed) -> normalized text

`TranslationAdapter` is an explicit extension point: for the POC it is a
pass-through / labelling stub (translation quality is out of scope), but
swapping in a real on-prem translation model or approved external
service is a one-class change, matching the "model/provider abstraction"
requirement.
"""
from __future__ import annotations

from app.services.extraction_service import detect_language

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
}


class TranslationAdapter:
    def translate_to_english(self, text: str, source_language: str) -> str:
        if source_language == "en" or not text:
            return text
        # Extension point: plug in a local/offline translation model here.
        return f"[UNTRANSLATED:{source_language}] {text}"


def normalize_document_language(text: str) -> dict:
    lang = detect_language(text)
    adapter = TranslationAdapter()
    normalized = adapter.translate_to_english(text, lang)
    return {
        "detected_language": lang,
        "detected_language_name": LANGUAGE_NAMES.get(lang, lang),
        "normalized_text": normalized,
        "translation_applied": lang != "en",
    }
