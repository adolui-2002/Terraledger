"""
Model / provider abstraction.

Business logic (scoring_service, assistant_service, ...) only ever talks to
`get_ai_provider()`. It never imports an SDK directly. This means:

  - Swapping Mock -> Local (e.g. an on-prem Llama server) -> Cloud is a one
    line config change (AI_PROVIDER env var), not a code change.
  - The default is MockAIProvider: fully deterministic, offline, and safe
    to run against real RESTRICTED data because nothing ever leaves the
    machine.
  - CloudAIProvider is opt-in and is intentionally never invoked from any
    code path that touches RESTRICTED application data directly (see
    assistant_service.py / scoring_service.py for the redaction step that
    happens before it's ever called).
"""
from __future__ import annotations

import textwrap
from abc import ABC, abstractmethod

import requests

from app.config import get_settings

settings = get_settings()


class BaseAIProvider(ABC):
    name: str = "base"

    @abstractmethod
    def summarize(self, text: str, max_sentences: int = 3) -> str: ...

    @abstractmethod
    def explain_score(self, breakdown: dict, positives: list[str], concerns: list[str]) -> str: ...

    @abstractmethod
    def answer_question(self, question: str, context: str) -> str: ...


class MockAIProvider(BaseAIProvider):
    """Deterministic, template-based provider. No network calls, ever.

    This is the default and the only provider that is guaranteed safe for
    RESTRICTED (real citizen/government) data, which is why it's what the
    on-prem / air-gapped deployment target uses.
    """

    name = "mock-local"

    def summarize(self, text: str, max_sentences: int = 3) -> str:
        if not text:
            return "No extractable text was found in the submitted documents."
        # For structured digest text (from summarization_service), surface
        # the most reviewer-relevant lines rather than blindly truncating.
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        # Priority order: score/recommendation, fraud, validation failures, docs
        priority_keywords = ["ai score", "recommendation", "fraud", "failure", "warning", "extracted", "submitted"]
        selected: list[str] = []
        for kw in priority_keywords:
            for line in lines:
                if kw in line.lower() and line not in selected:
                    selected.append(line)
                    if len(selected) >= max_sentences:
                        break
            if len(selected) >= max_sentences:
                break
        # Pad with remaining lines if needed
        for line in lines:
            if line not in selected:
                selected.append(line)
            if len(selected) >= max_sentences:
                break
        return " ".join(selected)

    def explain_score(self, breakdown: dict, positives: list[str], concerns: list[str]) -> str:
        lines = ["Score breakdown:"]
        for category, points in breakdown.items():
            lines.append(f"  - {category.replace('_', ' ').title()}: {points}")
        if positives:
            lines.append("Positive factors: " + "; ".join(positives))
        if concerns:
            lines.append("Concerns: " + "; ".join(concerns))
        lines.append(
            "This is a system-generated recommendation. A human reviewer makes "
            "the final determination."
        )
        return "\n".join(lines)

    def answer_question(self, question: str, context: str) -> str:
        # Simple deterministic retrieval-style answer: surface the most
        # relevant lines of context rather than generating free text.
        q = question.lower()
        relevant = [line for line in context.split("\n") if line.strip()]
        if "why" in q and "score" in q:
            hits = [l for l in relevant if "score" in l.lower() or "reason" in l.lower() or "%" in l]
            body = "\n".join(hits[:6]) or "\n".join(relevant[:6])
        elif "fraud" in q or "risk" in q or "suspicious" in q:
            hits = [l for l in relevant if any(k in l.lower() for k in ("fraud", "duplicate", "risk", "flag"))]
            body = "\n".join(hits[:6]) or "No fraud or risk signals were recorded for this application."
        elif "escalat" in q:
            hits = [l for l in relevant if "escalat" in l.lower() or "review" in l.lower()]
            body = "\n".join(hits[:6]) or "\n".join(relevant[:6])
        else:
            body = "\n".join(relevant[:8])
        return textwrap.dedent(
            f"""Based on the application record:
{body}

Note: I can only recommend and explain — the final decision rests with the assigned reviewer."""
        ).strip()


class CloudAIProvider(BaseAIProvider):
    """Optional cloud LLM adapter (OpenAI-compatible endpoint).

    Only ever called with pre-redacted / synthetic text. See callers for
    the sanitization step. Never used automatically for RESTRICTED data.
    """

    name = "cloud"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    def _chat(self, system: str, user: str) -> str:
        if not self.api_key:
            # Fail safe to the mock provider's behaviour rather than crash
            return MockAIProvider().answer_question(user, system)
        try:
            resp = requests.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": 500,
                },
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:  # network disabled / offline env, etc.
            return f"[cloud provider unavailable: {exc}] " + MockAIProvider().answer_question(user, system)

    def summarize(self, text: str, max_sentences: int = 3) -> str:
        return self._chat(
            "Summarize the following government scheme application text in "
            f"at most {max_sentences} sentences. Be factual, do not invent details.",
            text,
        )

    def explain_score(self, breakdown: dict, positives: list[str], concerns: list[str]) -> str:
        prompt = f"Breakdown: {breakdown}\nPositives: {positives}\nConcerns: {concerns}"
        return self._chat(
            "You explain an application review score to a government reviewer. "
            "Never say the application is approved or rejected — only recommend "
            "and explain. The human reviewer makes the final call.",
            prompt,
        )

    def answer_question(self, question: str, context: str) -> str:
        return self._chat(
            "You are a reviewer assistant for a government scheme review platform. "
            "Answer using only the provided context. Never state a final "
            "approve/reject determination — only explain and recommend.",
            f"Context:\n{context}\n\nQuestion: {question}",
        )


def get_ai_provider() -> BaseAIProvider:
    if settings.ai_provider == "openai" and settings.openai_api_key:
        return CloudAIProvider(settings.openai_api_key, settings.openai_model)
    return MockAIProvider()
