"""Google GenAI (Gemini) adapter for JanataLens AI.

Isolated extraction and plain-language explanation assistant.
- Uses google-genai SDK
- Never performs financial calculations or audit decisions
- Fails safely when API key is missing or quota is exceeded
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


_KEY_NOT_PROVIDED = object()


class GeminiAdapter:
    """Handles optional multimodal extraction and plain-language explanations."""

    def __init__(
        self,
        api_key: Optional[str] | object = _KEY_NOT_PROVIDED,
        extraction_model: Optional[str] = None,
        explanation_model: Optional[str] = None,
    ):
        # Omitted api_key means "use an explicitly configured environment key".
        # Passing api_key=None explicitly forces offline mode, even when .env is present.
        if api_key is _KEY_NOT_PROVIDED:
            self.api_key = os.getenv("GEMINI_API_KEY")
        else:
            self.api_key = api_key if isinstance(api_key, str) and api_key.strip() else None
        self.extraction_model = extraction_model or os.getenv("GEMINI_EXTRACTION_MODEL", "gemini-3.5-flash-lite")
        self.explanation_model = explanation_model or os.getenv("GEMINI_EXPLANATION_MODEL", "gemini-3.5-flash-lite")
        self._client = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception:
                self._client = None

    def is_available(self) -> bool:
        """Returns True only if client is initialized with an API key."""
        return self._client is not None

    def explain_finding(
        self,
        title: str,
        rule_id: str,
        status: str,
        summary: str,
        exact_calculation: Optional[str] = None,
        language: str = "en",
    ) -> str:
        """Generates a plain-language explanation for an already-computed deterministic finding.

        Language: 'en' for English, 'te' for Telugu.
        """
        if not self.is_available():
            if language == "te":
                return "AI వివరణ అందుబాటులో లేదు (Gemini API కీ కాన్ఫిగర్ చేయబడలేదు)."
            return f"[{status}] {summary} (Deterministic finding. AI explanation unavailable without GEMINI_API_KEY)."

        lang_instruction = "in simple, neutral English" if language == "en" else "in clear, respectful Telugu (తెలుగు)"
        prompt = (
            f"You are a public-works social audit assistant for community reviewers.\n"
            f"Explain the following deterministic audit finding {lang_instruction}.\n"
            f"Do NOT accuse anyone of fraud, corruption, or theft. Keep the tone neutral, clear, and objective.\n"
            f"Explain what the finding means and what physical check a citizen or auditor should perform next.\n\n"
            f"Rule ID: {rule_id}\n"
            f"Finding: {title}\n"
            f"Status: {status}\n"
            f"Summary: {summary}\n"
            f"Calculation: {exact_calculation or 'None'}\n"
        )

        try:
            response = self._client.models.generate_content(
                model=self.explanation_model,
                contents=prompt,
                config={"http_options": {"timeout": 15000}},
            )
            if response and response.text:
                return response.text.strip()
            return summary
        except Exception as e:
            if language == "te":
                return f"AI వివరణ అందుబాటులో లేదు: {str(e)}"
            return f"{summary} (AI explanation failed: {str(e)})"

    def explain_audit_report(self, report_summary: str, language: str = "en") -> str:
        """Explains an overall audit report in English or Telugu."""
        if not self.is_available():
            if language == "te":
                return "AI సమీక్ష వివరణ అందుబాటులో లేదు."
            return "Audit summary generated deterministically. AI explanation requires GEMINI_API_KEY."

        lang_instruction = "in accessible English" if language == "en" else "in Telugu (తెలుగు)"
        prompt = (
            f"Summarize this public-works disclosure review report for a Gram Sabha {lang_instruction}.\n"
            f"Do NOT make accusations of crime or corruption. Highlight transparency and human verification.\n\n"
            f"{report_summary}"
        )
        try:
            response = self._client.models.generate_content(
                model=self.explanation_model,
                contents=prompt,
                config={"http_options": {"timeout": 15000}},
            )
            return response.text.strip() if response and response.text else "Summary unavailable."
        except Exception as e:
            return f"Summary unavailable: {str(e)}"
