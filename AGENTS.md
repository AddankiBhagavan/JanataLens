# JanataLens AI — Agent Guidelines & Instructions

JanataLens AI is an evidence-backed public-works disclosure review assistant for social-audit facilitators, community auditors, and citizens. It is not an official audit authority, fraud detector, or legal decision-maker.

## Core Rules for Agents and Developers

1. **Evidence Before Conclusions:** Every finding must link to supporting evidence (filename, page, row, or visual region).
2. **Deterministic Engine:** All financial calculations, date calculations, identity/linkage checks, and image hashes must be performed in pure Python (`src/audit_engine.py`, `src/vision_forensics.py`). Never use an LLM for calculations or audit decisions.
3. **No Accusations:** Never use defamatory or accusatory terms such as "fraud", "corruption", "theft", "ghost-work", or "culprit". Findings highlight discrepancies requiring human review (`NEEDS_HUMAN_REVIEW`, `MISMATCH_FOUND`, `MISSING_EVIDENCE`, `CONSISTENT`).
4. **Safe Failure & Gemini Isolation:** The core deterministic audit and synthetic demo workflows must run completely offline without Gemini credentials. `src/gemini_adapter.py` is an optional assistant for document extraction and plain-language explanation only.
5. **Strict Data Schemas:** Use Pydantic v2 schemas in `src/schemas.py`. Monetary values must use `Decimal`.
6. **Work Identity Gate:** Records must be verified to refer to the same work before cross-document comparisons are allowed.
7. **Synthetic Data Transparency:** Synthetic demo data must always be clearly watermarked: `SYNTHETIC DEMO DATA — NOT AN OFFICIAL GOVERNMENT RECORD`.
8. **Privacy by Default:** Never collect, request, or persist Aadhaar numbers, bank account numbers, or real worker identities.
9. **Preserve Architecture:** Follow the modular structure specified in `spec.md`. Do not invent new frameworks or microservices.
