"""
Multilingual normalization pipeline.

    document -> detect_language -> (translate if needed) -> normalized text

Architecture:
  - Language detection: langdetect (local, no network)
  - Translation: TranslationAdapter abstraction
      mock  (default) — labels the text as untranslated, safe for RESTRICTED
      live  (opt-in)  — calls a configured translation API

Setting TRANSLATION_ADAPTER=live in .env enables real translation.
For on-prem deployments, a local model (LibreTranslate, Argos Translate)
can be pointed to via TRANSLATION_BASE_URL.

Supported languages (detection + labelling):
  en  English      hi  Hindi        bn  Bengali
  ta  Tamil        te  Telugu       mr  Marathi
  gu  Gujarati     kn  Kannada      ml  Malayalam
  pa  Punjabi      ur  Urdu         or  Odia
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.config import get_settings
from app.services.extraction_service import detect_language

logger = logging.getLogger(__name__)

settings = get_settings()

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
    "or": "Odia",
}

# Languages that use Devanagari / Indic scripts — extraction patterns
# need to account for these explicitly.
INDIC_LANGUAGES = {"hi", "mr", "ne", "kok"}  # Devanagari script
LATIN_EQUIVALENT_LANGS = {"en"}

# Amount words in various languages that map to multipliers
AMOUNT_WORDS: dict[str, dict[str, float]] = {
    "hi": {"लाख": 100_000, "करोड़": 10_000_000, "हजार": 1_000},
    "bn": {"লাখ": 100_000, "কোটি": 10_000_000, "হাজার": 1_000},
    "ta": {"லட்சம்": 100_000, "கோடி": 10_000_000},
    "te": {"లక్ష": 100_000, "కోటి": 10_000_000},
    "mr": {"लाख": 100_000, "कोटी": 10_000_000},
    "gu": {"લાખ": 100_000, "કરોડ": 10_000_000},
}


# ---------------------------------------------------------------------------
# Translation adapter abstraction
# ---------------------------------------------------------------------------

class BaseTranslationAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def translate_to_english(self, text: str, source_language: str) -> tuple[str, bool]:
        """Returns (translated_text, translation_was_applied)."""
        ...

    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Return list of language codes this adapter can translate."""
        ...


class MockTranslationAdapter(BaseTranslationAdapter):
    """Pass-through adapter. Marks non-English text as untranslated so
    reviewers can see the language was detected but not translated.
    Zero network calls. Safe for RESTRICTED data.
    """
    name = "mock-translation"

    def translate_to_english(self, text: str, source_language: str) -> tuple[str, bool]:
        if source_language == "en" or not text:
            return text, False
        lang_name = LANGUAGE_NAMES.get(source_language, source_language)
        logger.info(
            "Non-English document detected (mock adapter — not translated)",
            extra={"detected_language": source_language, "language_name": lang_name},
        )
        return text, False  # Return original — mock doesn't translate

    def supported_languages(self) -> list[str]:
        return list(LANGUAGE_NAMES.keys())


class LiveTranslationAdapter(BaseTranslationAdapter):
    """Calls a LibreTranslate-compatible REST API for translation.

    Configure via:
      TRANSLATION_ADAPTER=live
      TRANSLATION_BASE_URL=http://localhost:5000   (local LibreTranslate)
      TRANSLATION_API_KEY=                         (optional, leave blank for LibreTranslate)

    LibreTranslate can be self-hosted for full on-prem operation:
      docker run -p 5000:5000 libretranslate/libretranslate
    """
    name = "live-translation"

    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def translate_to_english(self, text: str, source_language: str) -> tuple[str, bool]:
        if source_language == "en" or not text:
            return text, False
        try:
            import requests
            payload = {
                "q": text[:5000],  # cap to avoid huge API calls
                "source": source_language,
                "target": "en",
                "format": "text",
            }
            if self.api_key:
                payload["api_key"] = self.api_key

            resp = requests.post(
                f"{self.base_url}/translate",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            translated = resp.json().get("translatedText", text)
            logger.info(
                "Document translated",
                extra={"source_language": source_language, "chars_translated": len(text)},
            )
            return translated, True
        except Exception as exc:
            logger.warning(
                "Translation failed — using original text",
                extra={"source_language": source_language, "error": str(exc)},
            )
            return text, False  # Degrade gracefully

    def supported_languages(self) -> list[str]:
        try:
            import requests
            resp = requests.get(f"{self.base_url}/languages", timeout=5)
            resp.raise_for_status()
            return [lang["code"] for lang in resp.json()]
        except Exception:
            return list(LANGUAGE_NAMES.keys())


def get_translation_adapter() -> BaseTranslationAdapter:
    adapter_type = getattr(settings, "translation_adapter", "mock")
    if adapter_type == "live":
        base_url = getattr(settings, "translation_base_url", "http://localhost:5000")
        api_key = getattr(settings, "translation_api_key", "")
        return LiveTranslationAdapter(base_url=base_url, api_key=api_key)
    return MockTranslationAdapter()


# ---------------------------------------------------------------------------
# Multilingual amount extraction
# ---------------------------------------------------------------------------

def extract_indic_amounts(text: str, language: str) -> list[float]:
    """Extract monetary amounts from text in Indic scripts.
    Falls back gracefully if no Indic patterns found.
    """
    import re
    amounts: list[float] = []
    multipliers = AMOUNT_WORDS.get(language, {})

    # Devanagari/Indic digit pattern: ₹\d+ followed by amount word
    devanagari_digits = re.compile(r"[₹रु]\s*([\d,]+(?:\.\d+)?)\s*(" +
                                    "|".join(re.escape(k) for k in multipliers) + r")?", re.UNICODE)
    for match in devanagari_digits.finditer(text):
        try:
            value = float(match.group(1).replace(",", ""))
            word = match.group(2)
            if word and word in multipliers:
                value *= multipliers[word]
            amounts.append(value)
        except (ValueError, TypeError):
            continue

    return amounts


# ---------------------------------------------------------------------------
# Main normalization entry point
# ---------------------------------------------------------------------------

def normalize_document_language(text: str) -> dict:
    """Detect language, attempt translation, return enriched metadata dict."""
    lang = detect_language(text)
    lang_name = LANGUAGE_NAMES.get(lang, lang)
    is_indic = lang in INDIC_LANGUAGES or lang in AMOUNT_WORDS

    adapter = get_translation_adapter()
    normalized_text, translation_applied = adapter.translate_to_english(text, lang)

    result = {
        "detected_language": lang,
        "detected_language_name": lang_name,
        "normalized_text": normalized_text,
        "translation_applied": translation_applied,
        "is_indic_script": is_indic,
        "translation_adapter": adapter.name,
    }

    # If the language is Indic and translation wasn't applied, try to
    # extract Indic amounts directly so they aren't silently missed.
    if is_indic and not translation_applied:
        indic_amounts = extract_indic_amounts(text, lang)
        if indic_amounts:
            result["indic_amounts_extracted"] = indic_amounts
            logger.info(
                "Indic amounts extracted from non-translated document",
                extra={"language": lang, "amounts_found": len(indic_amounts)},
            )

    return result


# ---------------------------------------------------------------------------
# Language metadata helpers
# ---------------------------------------------------------------------------

def get_supported_languages() -> list[dict]:
    """Return all languages the platform can detect and label."""
    adapter = get_translation_adapter()
    supported_for_translation = set(adapter.supported_languages())
    return [
        {
            "code": code,
            "name": name,
            "detection_supported": True,
            "translation_supported": code in supported_for_translation,
            "adapter": adapter.name,
        }
        for code, name in sorted(LANGUAGE_NAMES.items(), key=lambda x: x[1])
    ]
