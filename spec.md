# JanataLens AI — Product & Technical Specification

**Product:** JanataLens AI  
**Tagline:** Evidence-backed public-works disclosure review  
**Track:** Civic Pulse, Digital Governance & Public Information  
**Platform:** Responsive Streamlit web application  
**Language:** Python 3.11+ (local development currently uses Python 3.14.7)  
**MVP deployment target:** Streamlit Community Cloud  
**Specification status:** Implementation baseline for the hackathon MVP  
**Last policy/source review:** 21 November 2026  

> **Product boundary:** JanataLens is an evidence-review assistant. It is not a government system, an official audit authority, a legal opinion, or a fraud detector. It flags records that need human review.

---

## 1. Executive Summary

JanataLens AI helps a citizen, social-audit facilitator, field inspector, or Gram Sabha participant examine whether public-works information displayed to the community is consistent with supporting records supplied for the same work.

A user can upload a worksite Janata Board photograph, sanction/estimate documents, weekly disclosure records, bills or vouchers, muster/payment records, and optional stage photographs. The application extracts structured fields, preserves their source locations, allows the user to confirm or correct extracted values, runs transparent deterministic checks, compares photographs for potential duplication, and creates an evidence-linked audit-review report.

AI is used for document understanding, extraction assistance, normalisation suggestions, and plain-language explanations. Python performs all financial calculations, date calculations, identity/linkage checks, and image-hash comparisons.

The application must never:

- Accuse a person or organisation of fraud, corruption, theft, or criminal conduct.
- Treat an unexplained discrepancy as proof of wrongdoing.
- Treat an image hash or EXIF field as proof that a photograph is authentic or false.
- Claim official compliance merely because no mismatch was detected.
- Present synthetic demonstration records as real government records.

### Product value

The core value is a repeatable workflow that connects fragmented evidence, identifies inconsistencies, shows the exact source and calculation behind each finding, and helps a human reviewer decide what to check next.

### Differentiation

JanataLens is not another map of rural assets or a generic grievance dashboard. Its narrow focus is **cross-document and photo-evidence reconciliation of public worksite disclosures**. It complements rather than replaces government monitoring platforms and statutory social-audit processes.

---

## 2. Product Principles

1. **Evidence before conclusions:** Every finding must link to the supporting file and, where possible, page, row, text excerpt, or image region.
2. **Human confirmation:** Required extracted values must be reviewed before they influence an audit calculation, except for trusted generated demo fixtures.
3. **Deterministic audit logic:** Python—not an LLM—calculates money, dates, totals, hash distances, and final finding statuses.
4. **Safe uncertainty:** Missing, unreadable, ambiguous, or contradictory evidence must remain visible as uncertainty.
5. **No false certainty:** “No mismatch detected” is not the same as “verified compliant.”
6. **Privacy by default:** Collect the minimum data needed; never request Aadhaar, bank account numbers, or unnecessary worker identities.
7. **Safe failure:** The core synthetic demo and deterministic audit must work without Gemini credentials or an internet connection.
8. **Demo integrity:** Synthetic files and results must be visibly labelled and traceable to their generating fixtures.
9. **Source-aware rules:** Every policy check must have a source, effective date, jurisdiction, and rule version.
10. **Scope discipline:** Deliver one complete, tested workflow before adding optional features.

---

## 3. Problem Statement and Users

### 3.1 Problem

Information about a public work may be distributed across multiple sources:

- A physical Janata Board at the worksite.
- Administrative sanction and technical estimate/BOQ.
- Weekly digital or physical public disclosures.
- Bills, vouchers, and material-payment records.
- Muster rolls, attendance, wage processing, and payment records.
- Optional work-progress or stage photographs.

A reviewer may need to manually align these records, determine whether they refer to the same work and period, compare values and dates, and find missing supporting evidence. This is time-consuming and difficult for a community reviewer who is not a technical auditor.

JanataLens reduces that manual reconciliation burden while retaining human oversight and record-level traceability.

### 3.2 Target users

| User | Need |
|---|---|
| Social-audit facilitator | Prepare a structured evidence review before a Gram Sabha/social audit |
| Community auditor | Understand differences between public disclosures and supporting records |
| Field inspector | Identify records requiring follow-up |
| Civil-society organisation | Review a consistent set of documents across works |
| Journalist/researcher | Examine supplied public-works records responsibly |
| Hackathon judge | See an end-to-end application with real processing and transparent results |

### 3.3 Primary user journey

1. Open JanataLens.
2. Select a synthetic demo case or start a new review.
3. Enter a work name/code and available location/agency details.
4. Upload a Janata Board photograph.
5. Upload the sanction order and estimate/BOQ.
6. Upload weekly disclosure, bills/vouchers, and optional muster/payment records.
7. Upload optional stage photographs.
8. The application validates file types and extracts candidate fields.
9. The user reviews, confirms, or corrects the candidate fields and links records to the same work.
10. The user selects **Run Audit**.
11. The deterministic engine executes each applicable rule and records skipped rules with reasons.
12. The user inspects findings, evidence, calculations, photo comparisons, and next steps.
13. The user exports a JSON or Markdown report.

The synthetic demo and user-upload workflow must use the same extraction/review/audit/report pipeline. Demo fixtures may be pre-confirmed because they are generated and controlled by the application, but their synthetic status must remain visible throughout.

---

## 4. Policy and Evidence Context

This section defines the initial national-level reference framework. It is not a substitute for later Gazette notifications, State Scheme rules, state-specific instructions, or legal review.

### 4.1 Act and commencement

The Viksit Bharat—Guarantee for Rozgar and Ajeevika Mission (Gramin): VB–G RAM G Act, 2025 (Act No. 36 of 2025) received Presidential assent on 20 December 2025 and was published in the Gazette of India on 21 December 2025. The commencement notification S.O. 2382(E), dated 11 May 2026, appointed **1 July 2026** as the date on which the Act came into force across all States and Union Territories.

The Act provides a statutory guarantee of 125 days of unskilled wage employment per eligible rural household in each financial year, subject to the Act and applicable Scheme provisions.

### 4.2 Janata Board and public disclosure anchor

Schedule I, paragraph 25(2)(b) requires a Janata Board at every worksite showing:

- Details of the work.
- Estimated labour days.
- Material quantities in local terminology.
- Item-wise costs.

Schedule I, paragraph 14 addresses administrative and financial sanction. Section 23(1)-(2) addresses proper fund utilisation and maintenance of labour and expenditure accounts. These sources support documentary reconciliation and account review; they do not by themselves establish a legal violation.

The application must implement a **versioned completeness checklist** based on the applicable requirement and source. Do not treat optional fields, local formatting conventions, or fields not established by the applicable rule as mandatory.

### 4.3 Wage timing — two separate legal clocks

The wage logic must not merge payment timing and delay compensation.

| Rule | Legal reference/date basis | Initial implementation treatment |
|---|---|---|
| Wage disbursement timing | Act section 5(3): weekly, or in any case not later than a fortnight after the date on which the work was done, subject to applicable provisions | Record the work date/period and payment evidence. Do not substitute the muster closure date for this statutory wording without an applicable rule/source establishing that basis. |
| Delay compensation | Schedule II, paragraph 6: where wages are not paid within fifteen days from muster-roll closure, compensation is payable at 0.05% of unpaid wages per day of delay beyond the sixteenth day of closure | Use the muster-roll closure date and actual deposit/credit evidence. Keep this calculation separate from the section 5(3) wage-payment timing check. |

Important controls:

- The official PIB FAQ also describes weekly payment or payment not later than a fortnight after muster-roll closure and explains the compensation trigger. Where an FAQ summary and the enacted text use different date wording, preserve both citations and do not silently combine them. For the legal rule engine, retain the exact statutory provision and the applicable notified rules/Scheme; unresolved interpretation must result in `NEEDS_HUMAN_REVIEW`.
- The wage-payment notification/rules and any State-specific rules must be checked before enabling a production legal calculation.
- Do not treat FTO generation, FTO upload, or payment processing as proof that money reached a worker's bank/post-office account.
- Only calculate delay compensation when the muster closure date, unpaid amount, and actual deposit/credit date are supported by evidence for the same wage event.
- The demo may use synthetic pseudonymous worker references. Never request Aadhaar or bank-account numbers.

### 4.4 Historical audit motivation

CAG Report No. 13 of 2026 concerns historical MGNREGS implementation in Karnataka for the year ended March 2024 and was tabled on 24 March 2026. It is historical motivation for stronger financial, execution, photographic, and social-audit evidence practices.

Do not describe historical findings under the previous MGNREGS framework as findings under VB–G RAM G after 1 July 2026. Cite exact report pages when quoting any finding in the UI or presentation.

### 4.5 Rule-source registry

Every executable policy rule must record:

- Rule ID and version.
- Source title and issuing authority.
- URL and retrieval/verification date.
- Section, paragraph, or page reference where known.
- Effective date and end date, if applicable.
- Jurisdiction: national, state, district, or scheme-specific.
- Required input fields and calculation basis.
- Known limitations/interpretation notes.

Do not invent clause numbers, monetary thresholds, deadlines, or State rules. If a State-specific rule is required but not configured and verified, do not run that check as a legal conclusion; return `NEEDS_HUMAN_REVIEW`.

### 4.6 Primary reference sources

| Source | URL | Use |
|---|---|---|
| Gazette of India — VB–G RAM G Act, 2025 | https://egazette.gov.in/WriteReadData/2025/268696.pdf | Primary Act text |
| Commencement notification S.O. 2382(E), 11 May 2026 | https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/may/doc2026511867901.pdf | Effective date across States/UTs |
| PIB FAQ — VB–G RAM G Act, 2025 | https://www.pib.gov.in/PressNoteDetails.aspx?ModuleId=4&NoteId=158511 | Public explanation and wage FAQ |
| Gazette notification G.S.R. 402(E), Wage Payment and Unemployment Allowance Rules, 2026 | https://egazette.gov.in/WriteReadData/2026/272829.pdf | Wage-rule context; validate applicable text |
| CAG Report No. 13 of 2026 | https://www.cag.gov.in/en/audit-report/details/123873 | Historical audit motivation |
| Google Gemini API model documentation | https://ai.google.dev/gemini-api/docs/models | Runtime model configuration |
| Google Gen AI Python SDK | https://googleapis.github.io/python-genai/ | Gemini integration |
| Streamlit Community Cloud deployment documentation | https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy | Deployment configuration |

---

## 5. Scope and Priorities

### 5.1 In scope

- Single-user, no-login hackathon demonstration.
- One audit session per selected work/case.
- JPG/JPEG/PNG images, PDF documents, and CSV tables.
- Three generated synthetic demonstration bundles.
- Local text-PDF and CSV extraction.
- Optional Gemini multimodal extraction for scanned documents/photos.
- Manual field confirmation/correction.
- Pre-audit work-record linkage validation.
- Five deterministic audit check groups.
- SHA-256, pHash, dHash, EXIF metadata, and Hamming-distance photo review.
- Evidence-linked findings and JSON/Markdown export.
- Optional SQLite metadata persistence for local development.
- English interface and optional Telugu explanations.
- Public demo mode and local review mode.

### 5.2 Out of scope

- Government portal submission or automatic grievance filing.
- Official/certified/legal audit decisions.
- Automatic fraud, corruption, ghost-work, or culprit detection.
- Nationwide scraping or an assumed universal village-level API.
- Satellite imagery, GPS tracking, or asset-map ranking.
- Face recognition or worker identification.
- Bank-account access or direct bank verification.
- Automatic publication of uploaded records or reports.
- Blockchain, IoT hardware, multi-agent swarms, or microservices.
- User accounts, roles, or multi-tenant administration in the MVP.

### 5.3 Priority order

| Priority | Requirements |
|---|---|
| P0 — must work | Synthetic cases, file validation, manual extraction/review fallback, work-record linkage, deterministic audit, findings UI, report export, tests, local launch |
| P1 — high value | Gemini extraction, Telugu explanations, photo metadata/near-duplicate analysis, SQLite local history |
| P2 — optional polish | More advanced PDF table extraction, refined image comparisons, additional sample cases, UI animations |

P0 must be completed and tested before P1/P2. No fake buttons, fake API responses, or hardcoded audit outcomes.

---

## 6. Technical Environment and Dependencies

### 6.1 Runtime

- Python requirement: `>=3.11`.
- Current local environment: Python 3.14.7 in the existing `.venv`.
- Do not reinstall Python or recreate the existing virtual environment.
- Develop and test using the same Python minor version selected for deployment whenever practical.
- Streamlit Community Cloud requires an explicit deployment Python selection if not using its default; test the chosen version against all dependencies.

### 6.2 Required dependencies

Use a lean `requirements.txt`. Initial candidates:

- `streamlit`
- `google-genai`
- `pydantic>=2`
- `opencv-python-headless`
- `ImageHash`
- `Pillow`
- `PyMuPDF`
- `pandas`
- `python-dotenv` (only if local `.env` loading is implemented)
- `pytest`

Add a dependency only when a concrete module requires it. Prefer standard-library functionality where sufficient. Use compatible pinned/minimum versions only after successfully installing and testing them in the existing environment.

Use `google-genai`, not the deprecated `google-generativeai` package. Use `opencv-python-headless`, not `opencv-python`, for Streamlit Cloud compatibility. Install only one OpenCV wheel distribution in the environment.

### 6.3 Required commands

```powershell
# Activate existing environment if needed
.\.venv\Scripts\Activate.ps1

# Install project dependencies
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Run tests
.\.venv\Scripts\python.exe -m pytest -q

# Run application
.\.venv\Scripts\python.exe -m streamlit run app.py
```

---

## 7. Input Evidence and File Handling

### 7.1 Supported formats

| Evidence | Formats |
|---|---|
| Photos/board | `.jpg`, `.jpeg`, `.png` |
| Documents | `.pdf` |
| Tabular disclosures | `.csv` |

Reject unsupported formats clearly. Enforce configurable file and total-session size limits (initial default: 15 MB per file and 50 MB per session; keep configurable). Validate extension, byte signature where feasible, and actual parser readability. Never trust a filename or MIME type alone.

### 7.2 Evidence categories

- `JANATA_BOARD_PHOTO`
- `SANCTION_ORDER`
- `ESTIMATE_OR_BOQ`
- `WEEKLY_DISCLOSURE`
- `MUSTER_OR_ATTENDANCE_RECORD`
- `BILL_OR_VOUCHER`
- `WAGE_PAYMENT_RECORD`
- `STAGE_PHOTO`
- `OTHER_SUPPORTING_EVIDENCE`

### 7.3 Extraction strategy

1. Use PyMuPDF for text-based PDF extraction and page provenance.
2. Use local table parsing only where the structure can be interpreted reliably; preserve row and column provenance.
3. For scanned PDFs, render relevant pages to images before optional multimodal extraction.
4. Use Gemini only when an API key and selected model are available.
5. Use Pandas for CSV parsing, header checks, and row provenance.
6. Retain the original raw text/value alongside any normalised value.
7. Record source filename, SHA-256, page number, CSV row, and image bounding box where available.
8. Missing and unreadable data must remain distinct states.

### 7.4 Extraction status

Each field uses one of:

- `EXTRACTED_UNREVIEWED`
- `USER_CONFIRMED`
- `USER_CORRECTED`
- `LOW_CONFIDENCE`
- `UNREADABLE`
- `NOT_PRESENT`

A low-confidence or unreviewed value must not silently enter a financial or legal calculation. The user must confirm it, correct it, or the related audit rule must report that it cannot run.

Synthetic fixtures may be marked as controlled/pre-confirmed test data; the UI must still display the synthetic warning.

### 7.5 Work identity/linkage gate

Before comparing records, verify that the board, sanction, estimate, disclosure, bills, muster records, and photographs refer to the same work and relevant period.

Use, in order:

1. Exact work/project identifier where present.
2. Sanction/order/work code.
3. Gram Panchayat/village/block/district and work name.
4. Relevant period and implementing agency.

Fuzzy name similarity may suggest a possible match but must not silently establish identity. If records may refer to different works or cannot be matched reliably, stop dependent comparisons and return `NEEDS_HUMAN_REVIEW`.

### 7.6 Document prompt-injection safety

Uploaded text and document content are untrusted data. Instructions embedded in a PDF, image, CSV, or extracted text must never override application instructions, trigger tools, alter rules, or cause external actions. Treat all extracted content as evidence only.

---

## 8. Data Models and Validation

Implement Pydantic v2 models in `src/schemas.py`. Use strict enums, `Decimal` for money, ISO 8601 dates/timestamps, and `Field(default_factory=list)` for list defaults. Avoid mutable literal defaults.

### 8.1 Core models

- `EvidenceReference`
- `ExtractedField`
- `JanataBoardData`
- `SanctionEstimateData`
- `RevisedSanction`
- `EstimateLineItem`
- `WeeklyDisclosureData`
- `LabourPaymentRecord`
- `StagePhotoEvidence`
- `RuleSource`
- `AuditFinding`
- `AuditReport`

### 8.2 EvidenceReference

Fields:

- `evidence_id`
- `filename`
- `evidence_type`
- `sha256`
- `file_size_bytes`
- `page_number` (optional)
- `row_number` (optional)
- `text_excerpt` (optional)
- `bounding_box` (optional, image/page coordinates)
- `synthetic` (boolean)

### 8.3 ExtractedField

Fields:

- `field_name`
- `raw_value` and/or `raw_text`
- `normalised_value` (optional)
- `source` (`EvidenceReference`)
- `extraction_method`
- `confidence` (optional model estimate, 0–1 only if supplied)
- `extraction_status`
- `reviewed_by_user`

Confidence is not a calibrated probability of truth. Never use it as a fraud probability or legal confidence score.

### 8.4 JanataBoardData

Support fields where displayed/applicable:

- Work name and identifier.
- Implementing agency/Gram Panchayat.
- Village, block, district, state.
- Worksite location description.
- Estimated labour days.
- Material entries: local name, optional normalised name, quantity, unit, item-wise cost.
- Board photograph metadata.
- Field-level evidence references.

Completeness requirements must be versioned. Do not require an element not established by the applicable official format/rule.

### 8.5 SanctionEstimateData

Fields:

- Work identifier/name.
- Sanction order number and authority.
- Original sanction date and amount.
- Revised sanctions with date, amount, scope, and evidence.
- Estimate/BOQ line items with description, specification, quantity, unit, rate, amount, and source.
- Scope and relevant period.
- Evidence references.

### 8.6 WeeklyDisclosureData

Fields:

- Work identifier/name.
- Disclosure period start/end.
- Publication date, if available.
- Employment/person-days aggregate.
- Wage amount aggregate.
- Material amount/quantities.
- Physical progress description/percentage.
- Item-wise data where available.
- Evidence references.

### 8.7 LabourPaymentRecord

Use pseudonymous worker references only. Do not request/store full names, Aadhaar numbers, or bank-account numbers.

Fields:

- Work identifier.
- Pseudonymous worker reference or aggregate group reference.
- Work dates/period.
- Muster-roll reference and closure date.
- Wage amount due.
- Wage processing/FTO date (separate field).
- Actual payment/deposit/credit date, if evidenced.
- Payment source/status.
- Evidence references.

### 8.8 StagePhotoEvidence

Fields:

- Evidence reference.
- Declared stage label/order.
- Capture timestamp if present.
- GPS latitude/longitude if present.
- Image dimensions.
- SHA-256.
- pHash and dHash.
- Metadata warnings.

EXIF must be labelled unverified metadata because it can be absent or edited.

### 8.9 AuditFinding

Every finding contains:

- Finding ID and rule ID/version.
- Title and status.
- Severity (`INFO`, `LOW`, `MEDIUM`, `HIGH`).
- Neutral summary.
- Observed values and comparison values.
- Exact calculation where applicable.
- Evidence references.
- Rule source/jurisdiction where applicable.
- Human-verification steps.
- Creation timestamp.

Severity means review priority, not guilt or likelihood of fraud.

### 8.10 AuditReport

Include:

- Session ID and work identity.
- Creation timestamp and application/spec version.
- Synthetic-data indicator.
- Evidence inventory.
- Extraction/review status summary.
- Work-linkage result.
- Rule execution summary (passed, flagged, skipped, and why).
- Findings grouped by status and rule.
- Overall review state, not a fraud score.
- English explanation and optional Telugu explanation.
- Rule/source references and limitations.

### 8.11 Strict finding statuses

Use exactly these enum values throughout code, UI, tests, and exports:

- `CONSISTENT`
- `MISMATCH_FOUND`
- `MISSING_EVIDENCE`
- `NEEDS_HUMAN_REVIEW`

Do not use alternative spellings such as `MISMATCH FOUND` in JSON. The UI may display friendly labels with spaces.

---

## 9. Deterministic Audit Engine

Implement in `src/audit_engine.py`. It must not import Streamlit or call Gemini. Each rule must be independently callable, deterministic, and unit-tested.

Before executing rules, run the work-identity/linkage gate and extraction-review gate. Rules with insufficient or unconfirmed inputs must be explicitly marked skipped/not assessable with a reason; they must not be silently omitted.

### JL-01 — Janata Board Completeness

Check the applicable required fields:

- Work details.
- Estimated labour days.
- Material quantities in local terminology.
- Item-wise costs.

| Condition | Status |
|---|---|
| All applicable fields present, readable, and confirmed | `CONSISTENT` |
| Applicable required field absent | `MISSING_EVIDENCE` |
| Field unreadable, format ambiguous, or applicability uncertain | `NEEDS_HUMAN_REVIEW` |

Do not flag fields not required by the selected rule version.

### JL-02 — Financial Reconciliation

Compare only records compatible in:

- Work identity and scope.
- Accounting period.
- Currency.
- Cost category.
- Units/quantities.
- Original/revised sanction basis.
- Inclusion/exclusion of taxes and other charges where material.

Possible comparisons:

- Approved estimate versus relevant bills/vouchers.
- Latest applicable revised sanction versus compatible cumulative expenditure.
- Board item-wise cost versus corresponding estimate/disclosed item.
- Disclosed wage/material totals versus source records for the same period.

Rules:

- Use `Decimal`, never binary floating-point for rupee calculations.
- Make rounding/tolerance explicit and configurable.
- Do not compare a cumulative amount with a single-period bill as if they were equivalent.
- Do not sum overlapping bills or duplicate rows.
- Keep raw and normalised values visible.
- An unexplained excess is a review exception, not proof of misappropriation.
- If scope/revision/period/tax basis is uncertain, return `NEEDS_HUMAN_REVIEW` instead of a definitive mismatch.

### JL-03 — Labour, Wage, and Delay Timeline

Keep these checks separate:

A. Wage disbursement timing under Act section 5(3): weekly or not later than a fortnight after the date on which work was done, subject to applicable provisions.

B. Delay compensation under Schedule II paragraph 6: assess payment within fifteen days from muster-roll closure and the 0.05% per-day compensation basis beyond the sixteenth day of closure, using the actual deposit/credit date and applicable notified rules.

Required evidence depends on the specific check. Do not calculate if the relevant event dates, wage amount, or actual credit evidence are missing.

Do not treat FTO generation/upload as proof of bank/post-office credit. If the payment record only shows processing, classify the check as `MISSING_EVIDENCE` or `NEEDS_HUMAN_REVIEW`.

Record the legal source, date basis, calculation inputs, rate, day count, result, and rule version. If the date interpretation or State-specific rule is not verified, do not produce a legal conclusion.

### JL-04 — Chronological Integrity

Compare where supported:

- Sanction date.
- Work commencement/progress dates.
- Stage-photo capture timestamps.
- Bill/voucher dates.
- Disclosure period/publication dates.
- Muster closure and wage payment dates.

Flag impossible or inconsistent sequences. A bill or photo dated before sanction is an anomaly requiring review, not automatic proof of an illegal act. Missing or editable EXIF must be treated as uncertain.

### JL-05 — Photo Reuse and Metadata Consistency

Compare stage images using:

- SHA-256 for exact file identity.
- pHash and dHash for visual similarity.
- Hamming distance.
- EXIF timestamps/GPS if present.
- Declared stage labels and order.

Thresholds must be configurable and empirically tested. Do not claim visual identity from a hash threshold alone. Resizing, compression, cropping, lighting, and rotation can change hashes; unrelated images can also be similar.

Display both images, declared stages, exact-hash result, pHash/dHash distances, metadata availability, and limitations. Flag potential reuse as `NEEDS_HUMAN_REVIEW`, never as proof of reuse or fraud. Missing EXIF is not wrongdoing.

### Engine-wide requirements

- Every rule returns a structured result, including when it cannot run.
- Every finding has at least one evidence reference or explicitly states that required evidence is missing.
- Do not issue `CONSISTENT` when the relevant check was skipped.
- “No mismatch detected” must not be rephrased as “compliant”, “genuine”, or “verified correct”.
- The report must show checks executed, checks skipped, and why.

---

## 10. Gemini AI Layer

Implement in `src/gemini_adapter.py`, isolated from the deterministic engine.

### 10.1 SDK and model configuration

Use:

```python
from google import genai
```

Use the current `google-genai` SDK and its currently documented structured-output configuration. Validate returned JSON with Pydantic. Do not mix examples from incompatible SDK/API generations.

Environment variables:

```env
GEMINI_API_KEY=
GEMINI_EXTRACTION_MODEL=gemini-3.5-flash-lite
GEMINI_EXPLANATION_MODEL=gemini-3.5-flash-lite
GEMINI_FALLBACK_MODEL=
```

`gemini-4-hydrogen` may be configured as an optional explanation model only after verifying that the user's API project can call it. Do not assume model access or free-tier availability based solely on model existence.

At startup or first use, verify the configured model using the available model-list/API mechanism or a bounded test call. Do not make continuous model-discovery calls.

### 10.2 Permitted AI tasks

- Read Janata Board images and scanned document pages.
- Extract candidate fields into a schema.
- Interpret English/Telugu text while preserving original text.
- Suggest normalised descriptions/units without replacing raw content.
- Explain already-created deterministic findings.
- Translate confirmed explanations into Telugu.

### 10.3 Prohibited AI tasks

- Make the final audit decision.
- Calculate money, dates, percentages, or hash distances.
- Invent missing values, citations, provisions, or page references.
- Treat an LLM confidence estimate as proof.
- Infer worker identity or guilt.
- State that a legal violation or fraud occurred.

### 10.4 Structured extraction

- Request structured JSON matching the field schema.
- Validate every response with Pydantic.
- Preserve raw model output for debugging only when it contains no sensitive data; otherwise do not log it.
- Require provenance fields; if exact page/region cannot be established, mark provenance unavailable rather than inventing it.
- Keep `raw_value` separate from `normalised_value`.
- Require user confirmation for critical financial, date, quantity, and identity values.

### 10.5 Failure handling

Handle missing API key, quota/rate limit, unsupported model, network timeout, malformed JSON, schema validation failure, and provider errors.

The app must continue to support synthetic cases, manual data entry/correction, deterministic calculations, photo hashing, and report export without Gemini. Show a clear “AI extraction unavailable” or “AI explanation unavailable” state. Never fake a model response.

### 10.6 Privacy

Use synthetic or properly redacted data for API demonstrations. The user must be told before any uploaded real record is sent to an external model provider. Do not transmit worker identity, Aadhaar, bank information, or unnecessary personal data.

---

## 11. Image Forensics

Implement in `src/vision_forensics.py` using Pillow, ImageHash, and OpenCV headless where useful.

### 11.1 Metadata

Extract capture time and GPS only where available. Store the raw metadata value and a parse result. Record absence, invalid values, or unsupported EXIF explicitly. Do not treat EXIF as cryptographic proof; it can be absent or edited.

### 11.2 Similarity

Compute:

- SHA-256.
- pHash.
- dHash.
- Hamming distances.

Use configurable thresholds. Test exact duplicates, resized/compressed/near-duplicate images, and unrelated images. Do not hardcode a threshold without documenting why it is appropriate for the test set.

### 11.3 UI evidence

For each possible match show:

- Side-by-side original images.
- Filenames and declared stage labels.
- Exact SHA-256 match indicator.
- pHash/dHash values and distances.
- EXIF timestamp/GPS availability.
- Short explanation of the potential match.
- Human-review warning and known limitations.

No face recognition or worker identification.

---

## 12. Synthetic Demonstration Data

Implement `src/sample_generator.py` and generate files in `sample_cases/`.

Every generated file and every relevant UI panel must clearly show:

`SYNTHETIC DEMO DATA — NOT AN OFFICIAL GOVERNMENT RECORD`

Generate real image/PDF/CSV files programmatically. Use Pillow for board and illustrative scene images, PyMuPDF for PDFs, and Pandas/CSV for structured records. Do not copy real workers' personal information or imply a generated image is a real field photograph.

### Case 1 — Clean and Consistent Work

Generate:

- Janata Board image.
- Sanction/estimate PDF.
- Weekly disclosure CSV/PDF.
- Three distinct stage illustrations/photos.

Values and dates should agree within the declared scope. Expected applicable rules: `CONSISTENT`.

### Case 2 — Cost Difference and Incomplete Board

Generate:

- Original sanction: ₹8,00,000.
- Comparable bill total: ₹9,20,000.
- No revised sanction in the supplied bundle.
- Janata Board with missing item-wise material cost breakdown.

Expected:

- `MISMATCH_FOUND` for the ₹1,20,000 unexplained difference, with a visible caveat that a valid revised sanction or scope/tax difference could change the assessment.
- `MISSING_EVIDENCE` for the incomplete board.

Ensure the synthetic records explicitly establish that the compared figures share scope, period, currency, cost categories, and tax basis; otherwise the test would be invalid.

### Case 3 — Photo Similarity and Date Anomaly

Generate:

- Three stage images.
- Stage 1 and Stage 3 identical or near-identical after a documented image transformation.
- A bill dated before the stated sanction date.
- Supporting sanction/disclosure records.

Expected:

- `NEEDS_HUMAN_REVIEW` for potential image reuse.
- `NEEDS_HUMAN_REVIEW` for chronology.
- Optionally add a separate planted numerical mismatch to test `MISMATCH_FOUND`.

A pre-sanction bill or similar image is not presented as proof of fraud.

### Synthetic-data integrity

- Include machine-readable fixture source values.
- Derive the UI findings by executing the actual pipeline; never hardcode the displayed result.
- Keep the same extraction/review/audit interfaces for demo and user-uploaded records.
- Do not mark a synthetic fixture as an official record in any export.

---

## 13. Streamlit Application

Entry point: `app.py`.

Build a polished, responsive, professional public-accountability dashboard—not a generic chatbot.

### 13.1 UI principles

- Clear JanataLens identity and purpose.
- Restrained civic/professional palette.
- Strong readable hierarchy and accessible contrast.
- Consistent spacing and typography.
- Friendly labels for technical statuses.
- Loading, empty, success, and error states.
- Desktop-first and usable on smaller screens.
- No decorative charts without meaningful data.

### 13.2 Sections

| Section | Purpose |
|---|---|
| Overview | Product purpose, mode, session, evidence count, finding count, workflow state |
| Demo Cases | Three one-click synthetic cases |
| New Audit | Work identity and uploads |
| Extraction Review | Candidate fields, provenance, confidence/status, user corrections |
| Audit Results | Findings, calculations, evidence, skipped rules, next steps |
| Photo Forensics | Side-by-side images, hash distances, EXIF warnings |
| Report Export | JSON and Markdown downloads |
| Methodology & Sources | Rule definitions, source references, limitations |

### 13.3 Workflow controls

- Do not enable **Run Audit** until the work-linkage and required-field review gates are satisfied, or clearly show which rules will be skipped.
- Allow a user to correct an extracted value and preserve both original and corrected values.
- Display the source that supports each critical value.
- Clearly distinguish AI-extracted, text-extracted, manually entered, and synthetic fixture data.

### 13.4 Demo loader

One-click selection for:

1. Clean and Consistent Work.
2. Cost Difference and Incomplete Board.
3. Photo Similarity and Date Anomaly.

Loading a demo must populate the same application data structures as uploads and invoke the real processing pipeline.

### 13.5 Upload interface

Separate upload groups:

- Janata Board photo.
- Sanction order and estimate/BOQ PDF.
- Weekly disclosure, muster, bills/vouchers, and wage/payment PDF/CSV.
- Stage 1/2/3 photographs.

Show supported extensions, limits, filenames, remove/reset actions, and useful validation errors.

### 13.6 Findings

Every finding shows title, status, rule ID, severity, observed/comparison values, calculation, source filename/page/row/region, evidence excerpt, human verification steps, and a non-accusatory caveat.

### 13.7 Language

English is the default interface language. Telugu explanations are optional and generated only when the configured AI feature is available. If unavailable, show an explicit unavailable state or use a reviewed static translation for fixed UI labels. Never fabricate a Telugu explanation.

### 13.8 Export

JSON must include session/work identity, synthetic indicator, extraction states, evidence references, checks executed/skipped, finding statuses, calculation inputs, rule versions, timestamps, and limitations.

Markdown must include a readable summary, evidence inventory, extraction-review state, rule results, calculations, source references, limitations, and synthetic-data warning.

Exports must be generated from the actual `AuditReport` object, not from a separate hardcoded template of expected outcomes.

---

## 14. Persistence, Privacy, and Deployment Modes

### 14.1 Local mode

- SQLite may store session metadata, evidence metadata, and report metadata.
- Raw uploads should be processed in memory or in a temporary directory and deleted according to a simple cleanup policy.
- Do not store unnecessary personal data.
- Do not store Aadhaar, full bank-account numbers, or worker names.
- Use pseudonymous references for synthetic or redacted worker records.

### 14.2 Public demo mode

The publicly deployed hackathon demo must default to synthetic cases only. Do not invite visitors to upload sensitive real-world worker, bank, or identity records to an unauthenticated public app.

Use a configuration flag such as:

```env
JANATALENS_MODE=demo
```

In `demo` mode:

- Enable synthetic demo bundles.
- Disable real-document upload, or clearly restrict it to non-sensitive test files with a prominent warning.
- Do not persist user uploads.
- Do not send user data to Gemini.

In `local` mode, enable user uploads after showing privacy/consent notice. External model transmission must require explicit user action/consent.

### 14.3 Streamlit Community Cloud storage caveat

Community Cloud does not guarantee persistence of files written to local storage. SQLite on Community Cloud must be treated as ephemeral demo/session storage only. Do not promise durable history. If durable multi-user storage is later required, design and configure a separate managed database after the MVP; do not add it now.

### 14.4 Secrets and `.gitignore`

Secrets belong in environment variables or Streamlit Secrets. For local `.env` loading, use `python-dotenv` or explicitly set the environment variable in the shell; Streamlit does not automatically load a plain `.env` file. Never commit `.env` or `.streamlit/secrets.toml`.

Required `.gitignore` entries:

```gitignore
.venv/
.env
.env.*
.streamlit/secrets.toml
__pycache__/
*.py[cod]
*.db
*.sqlite
*.sqlite3
.pytest_cache/
.coverage
sample_cases/generated_user_data/
data/uploads/
```

### 14.5 Security

- Validate file extension, signature where feasible, and size.
- Use safe temporary filenames.
- Protect against malformed/oversized PDFs, images, and CSVs.
- Treat uploaded document content as untrusted.
- Do not expose/log API keys.
- Minimise data retention.
- Do not deploy public upload functionality without authentication, limits, privacy notice, and abuse controls.

---

## 15. Architecture and Project Structure

### 15.1 Responsibilities

| Module | Responsibility |
|---|---|
| `app.py` | Streamlit UI and workflow orchestration only |
| `src/schemas.py` | Pydantic schemas, enums, validation |
| `src/gemini_adapter.py` | Gemini client, extraction/explanation, model/error handling |
| `src/document_extractor.py` | PDF/CSV/image intake, extraction, provenance |
| `src/vision_forensics.py` | EXIF, hashes, image comparisons |
| `src/audit_engine.py` | Pure deterministic audit rules |
| `src/database.py` | SQLite metadata persistence |
| `src/sample_generator.py` | Synthetic bundle generation |
| `src/report_generator.py` | JSON/Markdown export |

Dependency rules:

- `app.py` calls the module/service layer; it should not contain audit calculations.
- `document_extractor.py` may call `gemini_adapter.py`.
- `audit_engine.py` must not import Gemini or Streamlit.
- `vision_forensics.py` must be independently testable.
- `report_generator.py` serialises the actual `AuditReport`.
- `database.py` must not contain audit rules.
- No module may bypass evidence provenance for critical fields.

### 15.2 Required structure

```text
JanataLens/
├── app.py
├── requirements.txt
├── AGENTS.md
├── spec.md
├── README.md
├── .gitignore
├── .env.example
├── src/
│   ├── __init__.py
│   ├── schemas.py
│   ├── gemini_adapter.py
│   ├── document_extractor.py
│   ├── vision_forensics.py
│   ├── audit_engine.py
│   ├── database.py
│   ├── sample_generator.py
│   └── report_generator.py
├── tests/
│   ├── test_schemas.py
│   ├── test_document_extractor.py
│   ├── test_audit_engine.py
│   ├── test_vision_forensics.py
│   └── test_end_to_end.py
└── sample_cases/
    ├── case_1_clean/
    ├── case_2_cost_mismatch/
    └── case_3_evidence_anomaly/
```

Create exactly four core documentation/configuration files at the project root: `AGENTS.md`, `spec.md`, `README.md`, and `.gitignore`. `requirements.txt` and `.env.example` are required operational files, not additional product documentation. Create only the application/test/sample directories listed above unless a concrete technical need is documented.

---

## 16. Testing and Acceptance Criteria

Use `pytest`. Tests must run without a Gemini API key or network access.

### 16.1 Schema tests

- Valid records parse.
- Invalid amounts, dates, statuses, and ranges are rejected.
- Missing values remain `None`.
- List fields use safe default factories.
- Evidence provenance is validated.

### 16.2 Work-linkage and extraction tests

- Exact work IDs link correctly.
- Conflicting work IDs block dependent checks.
- Fuzzy name similarity alone does not auto-confirm identity.
- Low-confidence/unreviewed values cannot enter financial/date calculations.
- User corrections preserve the original extracted value.
- CSV/PDF/image parser failures produce explicit statuses, not silent blanks.

### 16.3 Audit tests

- Each required Janata Board field can be independently marked missing.
- Case 2 computes ₹1,20,000 exactly using `Decimal`.
- Revised sanction and compatible accounting period are considered.
- Incompatible scope/period/tax basis results in human review, not a false mismatch.
- Wage-payment and delay-compensation date bases remain separate.
- Missing muster closure or actual credit date does not create a false delay finding.
- FTO processing date is not treated as bank credit.
- Chronology anomalies are flagged for human review.
- No rule can emit an unsupported status.
- Skipped rules are recorded with reasons.

### 16.4 Image tests

- Exact duplicate files are detected by SHA-256.
- Near-duplicate pHash/dHash cases are tested with documented transformations/thresholds.
- Unrelated images are not automatically treated as duplicates.
- Missing/invalid EXIF is handled.
- Malformed images return clear errors.
- Hash distances are calculated correctly.

### 16.5 End-to-end tests

- Case 1 produces consistent results for applicable checks.
- Case 2 produces the planted cost and board findings through the real engine.
- Case 3 produces photo/date review findings through the real pipeline.
- Synthetic labels remain in UI and exports.
- Gemini absence/quota failure does not break synthetic audits.
- JSON/Markdown exports contain actual results and evidence references.

### 16.6 UI smoke tests

- App starts without traceback.
- All three synthetic cases load.
- Upload validation works in local mode.
- Extraction-review step appears before audit.
- Results and skipped checks render correctly.
- Photo comparison renders.
- Downloads work.
- Missing credentials show clear status.
- Demo mode does not expose real-document upload or sensitive data collection.

### 16.7 Quality reporting

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Report actual passed, failed, skipped, and deselected counts. Do not claim 100% test coverage unless coverage has been measured. Fix all P0/critical test failures before calling the MVP complete. Record any remaining non-critical failures honestly.

---

## 17. Deployment Readiness

Target: Streamlit Community Cloud.

Before deployment:

- Verify clean dependency installation from `requirements.txt`.
- Select a supported Python version and test dependencies with it.
- Ensure no machine-specific absolute paths are required.
- Ensure `JANATALENS_MODE=demo` is the public default.
- Ensure sample bundles can be generated/loaded on the hosted instance.
- Ensure the app works without Gemini credentials.
- Add Gemini credentials only through Streamlit Secrets if required.
- Do not commit databases, uploads, generated private files, or secrets.
- Verify report download and image rendering.
- Verify app limits and resource use.
- Obtain owner approval before public GitHub publication or deployment.

Community Cloud local file storage is not durable. SQLite should be described as local/ephemeral demo metadata storage only.

---

## 18. Development Sequence

Build in this order and keep the application runnable after each phase.

### Phase A — Foundation

- Inspect workspace and existing `.venv`.
- Create required root files and folders.
- Install only required dependencies.
- Implement schemas and configuration.

### Phase B — Synthetic data and deterministic engine

- Generate three actual synthetic bundles.
- Implement work-linkage gate.
- Implement JL-01 through JL-05.
- Write unit tests before UI polish.

### Phase C — Document extraction and review

- PDF/CSV/image extraction.
- Evidence provenance.
- Manual correction/confirmation UI.
- Optional Gemini adapter and fallback.

### Phase D — Vision and reporting

- EXIF parsing and hash comparison.
- Side-by-side review.
- JSON/Markdown report generation.

### Phase E — Streamlit workflow

- Demo loader.
- Upload workflow.
- Extraction review.
- Audit results.
- Methodology/sources.

### Phase F — Verification and deployment

- Full tests.
- Run all demo cases.
- Fix P0 defects.
- Browser/UI smoke test.
- Deployment configuration.
- Demo walkthrough and recording.

Do not spend time on advanced optional features while the P0 end-to-end flow is incomplete.

---

## 19. Definition of Done

The MVP is complete only when:

- The application runs using the documented command and existing `.venv`.
- Required modules exist with clear responsibilities.
- Three genuine synthetic bundles are generated as files and clearly watermarked.
- Synthetic and uploaded data use the same application data structures and audit pipeline.
- Work identity/linkage is validated before comparisons.
- Five audit-check groups return structured, evidence-linked findings or explicit skip reasons.
- Low-confidence/unreviewed critical values cannot silently influence calculations.
- Financial calculations use `Decimal` and compare compatible scope/period data.
- Wage timing and compensation checks are not conflated.
- Photo similarity is presented as a review indicator, not proof.
- Gemini is optional; missing credentials do not break the core demo.
- Critical tests pass and actual results are reported.
- The app runs locally without unhandled exceptions.
- JSON and Markdown exports work.
- Demo/public mode uses synthetic data only.
- README setup and limitations match the actual implementation.
- No secrets or private uploaded documents are committed.

---

## 20. Agent Execution Rules

- Inspect the workspace before editing; preserve any existing working files.
- Follow `AGENTS.md` and this specification.
- Use the existing `.venv`; do not reinstall Python or create another environment.
- Perform safe file creation, dependency installation, test execution, and local run commands without repeatedly asking for approval.
- Ask before destructive operations, paid services, sending private data to external providers, or publishing/deploying publicly.
- Do not add technologies or features outside the MVP without stating the reason and trade-off.
- Do not create fake buttons, fake integrations, fake API responses, or hardcoded findings.
- Do not claim that a feature works because files were generated; execute the workflow and tests.
- Keep the code modular and understandable to the project owner.
- If time is constrained, finish the P0 vertical slice before optional P1/P2 features.
- Record blockers and assumptions explicitly.

### Required final implementation report

At completion, report:

1. Files created and modified.
2. Features actually implemented.
3. Actual pytest passed/failed/skipped counts.
4. Exact application launch command.
5. Gemini model/API availability and fallback behaviour.
6. Sources/data actually tested and sources not verified.
7. Known limitations and outstanding risks.
8. Deployment readiness.
9. The next three highest-priority tasks.

---

## 21. Hackathon Demonstration Script

Target a clear 2–3 minute demonstration:

1. Open the deployed/public demo and show the responsible-use notice.
2. Select **Case 2 — Cost Difference and Incomplete Board**.
3. Show the source documents and extracted fields.
4. Show that the work identity and key values are reviewed/confirmed.
5. Run the audit.
6. Display the ₹1,20,000 comparison with source values and exact calculation.
7. Display the missing item-wise board breakdown as `MISSING_EVIDENCE`.
8. Select **Case 3 — Photo Similarity and Date Anomaly**.
9. Show side-by-side photographs, hash distances, EXIF availability, and the review warning.
10. Show the date anomaly as `NEEDS_HUMAN_REVIEW`, not fraud.
11. Export and open the Markdown evidence report.
12. Demonstrate that the deterministic audit still works when Gemini is unavailable.

### Primary engineering principle

Build a small, trustworthy, evidence-backed audit workflow that works end to end. Reliability, traceability, clear uncertainty, and honest limitations matter more than a large collection of unfinished AI features.
