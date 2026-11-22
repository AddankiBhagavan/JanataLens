# JanataLens AI — Evidence-Backed Public-Works Disclosure Review

**Tagline:** Evidence-backed public-works disclosure review  
**Track:** Civic Pulse, Digital Governance & Public Information  

JanataLens AI assists community reviewers, social-audit facilitators, and citizens in reconciling worksite Janata Boards, sanction orders, weekly disclosures, vouchers/bills, and stage photographs under the Viksit Bharat—Guarantee for Rozgar and Ajeevika Mission (Gramin) (VB–G RAM G Act, 2025) and historical public-works frameworks.

> **Important Disclaimer:** JanataLens is an evidence-review assistant. It is not a government portal, an official audit authority, a legal opinion, or a fraud detector. It flags discrepancies and missing evidence requiring human review.

---

## Architecture Overview

- `app.py`: Streamlit responsive web application & workflow orchestration
- `src/schemas.py`: Pydantic v2 data models, validation, and strict audit enums
- `src/audit_engine.py`: Pure deterministic audit rules (JL-01 to JL-05) using Python `Decimal` and standard logic
- `src/document_extractor.py`: PDF, CSV, and image intake, provenance tracking, and extraction review
- `src/vision_forensics.py`: Perceptual hashing (pHash, dHash), SHA-256, and EXIF metadata comparison
- `src/sample_generator.py`: Synthetic test bundle generation (Case 1, Case 2, Case 3)
- `src/report_generator.py`: Evidence-backed JSON and Markdown report export
- `src/gemini_adapter.py`: Optional Google GenAI (Gemini) extraction and plain-language explanation layer
- `src/database.py`: Ephemeral local session and metadata storage via SQLite

---

## Quickstart

### 1. Environment & Setup

JanataLens runs on Python 3.11+.

```powershell
# Activate existing virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Run Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### 3. Launch Application

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

---

## Modes of Operation

- `JANATALENS_MODE=demo`: Default mode for public deployment. Uses synthetic demo cases only, disables persistent uploads, and protects user privacy.
- `JANATALENS_MODE=local`: Local development and audit mode with local file upload and optional Gemini integration.

## Demo Walkthrough

1. Run `.\.venv\Scripts\python.exe -m streamlit run app.py`.
2. Open the demo page and select one of the three synthetic cases.
3. Show the synthetic-data watermark, selected work identity, findings, provenance, and stage-photo review.
4. Continue to the export screen to download JSON or Markdown reports.
5. Case 1 demonstrates consistent records, Case 2 demonstrates a cost and disclosure mismatch, and Case 3 demonstrates a chronology/photo-review anomaly.

Demo mode disables private uploads. Gemini is optional and the deterministic audit remains available offline.

## Evidence and responsible use

JanataLens reconciles work identity, public-board disclosures, sanction records, bills, wages, chronology, and stage photographs. A determination is not a legal or official finding. Mismatches and anomalies require human investigation at the Gram Sabha or through the relevant public authority.

The application distinguishes:

- Verified evidence: source-backed and rule-complete.
- Missing evidence: a required source was not supplied.
- Inconsistent evidence: supplied sources conflict.
- Unverified evidence: available evidence is incomplete or inconclusive.

The core audit and synthetic cases operate offline. Gemini is optional and does not perform deterministic calculations or audit decisions.

OCR is not a guaranteed fallback: scanned or image-only PDFs may require human confirmation or alternative document processing.

## Five-minute demonstration

1. Open the landing page and explain the responsible-use boundary.
2. Select DEMO MODE and open the synthetic case gallery.
3. Load Case 1 and show verified and traceable consistent evidence.
4. Load Case 2 and distinguish missing board disclosures from the financial mismatch.
5. Load Case 3 and show the chronology/photo-forensics review.
6. Open the provenance and evidence sections.
7. Continue to JSON or Markdown export.
8. State that Gemini is optional and the demo remains deterministic offline.

## Difficult judge questions

1. **Does it detect fraud?** No. It reports evidence gaps and review exceptions, not guilt or fraud.
2. **Can a consistent status be shown as verified?** Only when supporting evidence and rule-specific criteria pass.
3. **Are stage-photo matches proof of reuse or misconduct?** No. They indicate possible similarity requiring human inspection.
4. **Does FTO processing prove wage credit?** No. JanataLens requires an actual credit date for confirmed payment.
5. **Can missing bills prove overpayment or misuse?** No. Missing evidence is reported as missing.
6. **Does it replace a government audit?** No. It is an evidence-review assistant.
7. **Does Gemini calculate the audit?** No. It only provides optional explanation/support.
8. **Does the demo use real people or records?** No. All demonstration data is synthetic and pseudonymous.
9. **Is OCR included?** Text PDF extraction is included; guaranteed OCR for scanned PDFs is not.
10. **Can reports preserve provenance?** Yes. JSON and Markdown include source filenames and hashes, with limitations and review actions.

## Submission Checklist

- Run `.\.venv\Scripts\python.exe -m pytest -q`.
- Run `.\.venv\Scripts\python.exe -m compileall -q app.py src tests`.
- Verify the Streamlit health endpoint.
- Confirm `.env`, databases, uploads, and private evidence are excluded from Git.
- Do not commit real worker, Aadhaar, bank-account, or uploaded evidence data.
