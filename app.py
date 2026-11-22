"""JanataLens AI — Professional User Experience Redesign.

Evidence-backed public-works disclosure review assistant for social-audit
facilitators, Gram Sabha participants, and community reviewers.

Adheres strictly to the specification:
- Pure workflow orchestration; audit logic remains in src/audit_engine.py
- Responsive civic-tech interface with restrained professional palette
- 5-stage guided stepper workflow (Work Details -> Upload -> Review -> Investigate -> Export)
- Landing page: "Know what was approved. Check what was reported."
- Fully functional offline synthetic demonstration and custom file intake
- Non-accusatory language, evidence-linked findings, and human verification checklists
"""

from __future__ import annotations

import io
import hashlib
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
import streamlit as st
from PIL import Image

from src.audit_engine import run_full_audit
from src.database import get_recent_sessions, save_session_record
from src.document_extractor import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    load_synthetic_bundle,
    parse_bills_csv,
    parse_labour_csv,
    parse_sanction_pdf,
    parse_weekly_disclosure_csv,
    validate_demo_mode_intake,
    validate_file_intake,
    validate_upload_content,
)
from src.gemini_adapter import GeminiAdapter
from src.finding_status import map_finding_display_state as _map_finding_display_state
from src.report_generator import generate_json_report, generate_markdown_report
from src.sample_generator import generate_all_cases
from src.schemas import (
    AuditBundle,
    AuditFinding,
    AuditReport,
    BillVoucherRecord,
    EvidenceCategory,
    EvidenceReference,
    ExtractedField,
    ExtractionStatus,
    FindingStatus,
    JanataBoardData,
    LabourPaymentRecord,
    MaterialEntry,
    SanctionEstimateData,
    Severity,
    StagePhotoEvidence,
    WeeklyDisclosureData,
)
from src.vision_forensics import (
    compute_image_hashes,
    compute_sha256,
    extract_exif_metadata,
    hamming_distance,
    inspect_stage_photo_bytes,
)

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="JanataLens AI — Public-Works Disclosure Review",
    page_icon="JL",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Professional Civic Theme CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Google Fonts & Modern Base Typography */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        color: #1e293b;
    }

    /* Top Brand Navigation Bar */
    .brand-navbar {
        background-color: #0f172a;
        padding: 16px 28px;
        border-radius: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .brand-title {
        color: #ffffff;
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .brand-subtitle {
        color: #94a3b8;
        font-size: 0.88rem;
        font-weight: 400;
    }
    .brand-tag {
        background-color: #1e293b;
        color: #38bdf8;
        font-size: 0.75rem;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 600;
        border: 1px solid #334155;
    }

    /* Hero / Landing Section */
    .hero-container {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 40px 36px;
        margin-bottom: 28px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .hero-headline {
        font-size: 2.2rem;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.25;
        letter-spacing: -0.03em;
        margin-bottom: 12px;
    }
    .hero-lead {
        font-size: 1.15rem;
        color: #475569;
        line-height: 1.6;
        max-width: 820px;
        margin-bottom: 24px;
    }

    /* 4-Stage Process Grid */
    .process-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 20px;
        height: 100%;
        transition: all 0.2s ease;
    }
    .process-step-num {
        display: inline-block;
        width: 28px;
        height: 28px;
        background-color: #0f172a;
        color: #ffffff;
        border-radius: 50%;
        text-align: center;
        line-height: 28px;
        font-size: 0.8rem;
        font-weight: 700;
        margin-bottom: 12px;
    }
    .process-title {
        font-size: 1rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 6px;
    }
    .process-desc {
        font-size: 0.85rem;
        color: #64748b;
        line-height: 1.5;
    }

    /* Visible Progress Stepper */
    .stepper-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px 24px;
        margin-bottom: 28px;
    }
    .stepper-item {
        display: flex;
        align-items: center;
        gap: 10px;
        flex: 1;
        position: relative;
    }
    .stepper-circle {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.85rem;
        font-weight: 700;
    }
    .step-active .stepper-circle {
        background-color: #0f766e;
        color: #ffffff;
        box-shadow: 0 0 0 4px #ccfbf1;
    }
    .step-completed .stepper-circle {
        background-color: #0f172a;
        color: #ffffff;
    }
    .step-upcoming .stepper-circle {
        background-color: #f1f5f9;
        color: #94a3b8;
        border: 1px solid #cbd5e1;
    }
    .step-label {
        font-size: 0.85rem;
        font-weight: 600;
    }
    .step-active .step-label { color: #0f766e; font-weight: 700; }
    .step-completed .step-label { color: #0f172a; }
    .step-upcoming .step-label { color: #94a3b8; }

    /* Watermark & Caution Banners */
    .synthetic-banner {
        background-color: #fff1f2;
        border-left: 5px solid #e11d48;
        padding: 12px 18px;
        border-radius: 6px;
        color: #9f1239;
        font-size: 0.88rem;
        font-weight: 600;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .disclaimer-banner {
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
        border-left: 5px solid #475569;
        padding: 14px 18px;
        border-radius: 6px;
        color: #334155;
        font-size: 0.85rem;
        line-height: 1.5;
        margin-bottom: 24px;
    }

    /* Upload & Evidence Cards */
    .upload-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 18px;
        margin-bottom: 16px;
    }
    .upload-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .upload-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #0f172a;
    }
    .tag-required {
        background-color: #fee2e2;
        color: #991b1b;
        font-size: 0.7rem;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 700;
    }
    .tag-optional {
        background-color: #f1f5f9;
        color: #475569;
        font-size: 0.7rem;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 600;
    }
    .tag-uploaded {
        background-color: #ccfbf1;
        color: #0f766e;
        font-size: 0.7rem;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 700;
    }

    /* Audit Finding Cards */
    .finding-card {
        background-color: #ffffff;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        padding: 20px 24px;
        margin-bottom: 18px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .border-consistent { border-left: 6px solid #0f766e !important; }
    .border-mismatch { border-left: 6px solid #dc2626 !important; }
    .border-missing { border-left: 6px solid #d97706 !important; }
    .border-review { border-left: 6px solid #2563eb !important; }

    .badge-pill {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 16px;
        font-size: 0.78rem;
        font-weight: 700;
    }
    .pill-consistent { background-color: #f0fdfa; color: #0f766e; border: 1px solid #99f6e4; }
    .pill-mismatch { background-color: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
    .pill-missing { background-color: #fffbeb; color: #b45309; border: 1px solid #fde68a; }
    .pill-review { background-color: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }

    .calc-panel {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #0f172a;
        padding: 12px 16px;
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.9rem;
        color: #0f172a;
        margin: 12px 0;
    }
    .verification-box {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 14px 18px;
        margin-top: 12px;
    }

    [data-testid="stSidebar"] {
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
    [data-testid="stHeader"] {
        background: rgba(255,255,255,0.96);
    }
    [data-testid="stAppViewContainer"] {
        background-color: #f6f8fb;
    }
    .block-container {
        max-width: 1180px;
        padding-top: 1.25rem;
        padding-bottom: 2.5rem;
    }
    .mode-chip {
        display: inline-block;
        background: #e0f2fe;
        color: #0369a1;
        border: 1px solid #bae6fd;
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .evidence-state {
        display: inline-block;
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .state-verified { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
    .state-missing { background: #fff7ed; color: #b45309; border: 1px solid #fed7aa; }
    .state-inconsistent { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
    .state-unverified { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------

if "workflow_step" not in st.session_state:
    st.session_state.workflow_step = 1  # 1: Details, 2: Upload, 3: Review, 4: Findings, 5: Export
if "current_page" not in st.session_state:
    st.session_state.current_page = "home"  # "home", "audit", "demos", "methodology"
if "bundle" not in st.session_state:
    st.session_state.bundle = None
if "audit_report" not in st.session_state:
    st.session_state.audit_report = None
if "selected_case_name" not in st.session_state:
    st.session_state.selected_case_name = None
if "gemini_adapter" not in st.session_state:
    st.session_state.gemini_adapter = GeminiAdapter()


def clear_case_associated_outputs():
    """Prevents summaries or report context from one case appearing under another."""
    st.session_state.pop("gemini_en", None)
    st.session_state.pop("gemini_te", None)

# Work metadata fields
if "work_id_input" not in st.session_state:
    st.session_state.work_id_input = "WRK-AP-2026-00101"
if "work_name_input" not in st.session_state:
    st.session_state.work_name_input = "Water Harvesting Bund Construction"
if "gp_input" not in st.session_state:
    st.session_state.gp_input = "Pedda Amberpet GP"
if "district_input" not in st.session_state:
    st.session_state.district_input = "Ranga Reddy, Telangana"
if "agency_input" not in st.session_state:
    st.session_state.agency_input = "Panchayat Raj Engineering Wing"

app_mode = os.getenv("JANATALENS_MODE", "demo")


def map_finding_display_state(
    finding: AuditFinding,
    bundle: Optional[AuditBundle] = None,
) -> tuple[str, str]:
    """Conservative display-only mapping; engine status, evidence, and explanation stay unchanged."""
    state = _map_finding_display_state(finding, bundle=bundle)
    css = {
        "VERIFIED": "state-verified",
        "MISSING": "state-missing",
        "INCONSISTENT": "state-inconsistent",
        "UNVERIFIED": "state-unverified",
    }[state]
    return state, css


# ---------------------------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### JanataLens AI")
    st.caption("Public-Works Disclosure Review")
    st.markdown("---")

    selected_nav = st.radio(
        "Navigation",
        ["Home / Landing", "Audit Stepper", "Demo Cases", "Statutory Framework"],
        index=0 if st.session_state.current_page == "home" else (
            1 if st.session_state.current_page == "audit" else (
                2 if st.session_state.current_page == "demos" else 3
            )
        ),
    )

    if selected_nav == "Home / Landing":
        st.session_state.current_page = "home"
    elif selected_nav == "Audit Stepper":
        st.session_state.current_page = "audit"
    elif selected_nav == "Demo Cases":
        st.session_state.current_page = "demos"
    elif selected_nav == "Statutory Framework":
        st.session_state.current_page = "methodology"

    st.markdown("---")
    st.markdown(
        f"<span class='mode-chip'>{app_mode.upper()} MODE</span>",
        unsafe_allow_html=True,
    )
    gemini_badge = "Ready" if st.session_state.gemini_adapter.is_available() else "Offline (Deterministic)"
    st.markdown(f"**Gemini AI Layer:** {gemini_badge}")

    st.markdown("---")
    if st.session_state.bundle:
        st.caption(f"**Active Work:** `{st.session_state.bundle.work_id}`")
        st.caption(f"**Evidence Files:** {len(st.session_state.bundle.evidence_files)}")
        if st.session_state.audit_report:
            st.caption(f"**Review State:** `{st.session_state.audit_report.overall_review_state}`")

    st.caption("VB–G RAM G Act, 2025 Framework")


# ---------------------------------------------------------------------------
# Top Header Banner
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="brand-navbar">
        <div>
            <div class="brand-title">JanataLens AI</div>
            <div class="brand-subtitle">AI-assisted public-worksite disclosure and social-audit evidence intelligence</div>
        </div>
        <div class="brand-tag">PUBLIC WORKS REVIEW</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# View 1: Home / Landing Experience
# ---------------------------------------------------------------------------

if st.session_state.current_page == "home":
    st.markdown(
        """
        <div class="hero-container">
            <div class="hero-headline">Know what was approved.<br>Check what was reported.</div>
            <div class="hero-lead">
                Examine worksite disclosures against sanction records, weekly reports, bills, wages,
                and stage photographs. The platform highlights evidence gaps, conflicting records,
                and items that need physical or document verification.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Primary Action Buttons
    c_btn1, c_btn2, c_sp = st.columns([1.2, 1.2, 1.6])
    with c_btn1:
        if st.button("Start a New Audit", type="primary", use_container_width=True):
            st.session_state.current_page = "audit"
            st.session_state.workflow_step = 1
            st.rerun()
    with c_btn2:
        if st.button("Explore Demonstration Cases", use_container_width=True):
            st.session_state.current_page = "demos"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # 4-Stage Explanation of the Process
    st.subheader("How JanataLens Reconciles Evidence")
    p1, p2, p3, p4 = st.columns(4)

    with p1:
        st.markdown(
            """
            <div class="process-card">
                <span class="process-step-num">1</span>
                <div class="process-title">Identify Work</div>
                <div class="process-desc">
                    Enter the work code and village metadata to establish a verified baseline for comparison.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with p2:
        st.markdown(
            """
            <div class="process-card">
                <span class="process-step-num">2</span>
                <div class="process-title">Intake Evidence</div>
                <div class="process-desc">
                    Upload worksite Janata Board photo, sanction order PDF, weekly disclosures, and bills.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with p3:
        st.markdown(
            """
            <div class="process-card">
                <span class="process-step-num">3</span>
                <div class="process-title">Review & Confirm</div>
                <div class="process-desc">
                    Review extracted candidate values. Key financial amounts must be confirmed by a human.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with p4:
        st.markdown(
            """
            <div class="process-card">
                <span class="process-step-num">4</span>
                <div class="process-title">Investigate & Verify</div>
                <div class="process-desc">
                    Inspect deterministic calculations, photo forensics, and Gram Sabha verification steps.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Responsible-Use & Product Boundary Disclaimer
    st.markdown(
        """
        <div class="disclaimer-banner">
            <strong>Important Review Notice & Civic Boundary:</strong><br>
            JanataLens AI is an evidence-review assistant created to assist citizens and social auditors. 
            It is <strong>not</strong> a government monitoring portal, an official audit authority, or a fraud detector. 
            Findings highlight documentation discrepancies and missing records that require physical verification at the Gram Sabha. 
            No finding implies wrongdoing or criminal conduct.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# View 2: Demonstration Cases
# ---------------------------------------------------------------------------

elif st.session_state.current_page == "demos":
    st.subheader("Explore Synthetic Demonstration Cases")
    st.markdown(
        "Select a pre-built synthetic demonstration bundle to test the full deterministic audit pipeline without uploading your own files."
    )

    d1, d2, d3 = st.columns(3)

    with d1:
        st.markdown(
            """
            <div class="process-card">
                <span class="badge-pill pill-consistent">Consistent Case</span>
                <h4 style="margin: 10px 0 6px 0; color: #0f172a;">Case 1: Clean & Consistent Work</h4>
                <p style="font-size: 0.85rem; color: #64748b;">
                    <strong>Work:</strong> Water Harvesting Bund<br>
                    <strong>Approved Sanction:</strong> ₹5,00,000.00<br>
                    <strong>Cumulative Bills:</strong> ₹3,50,000.00<br>
                    <strong>Expected:</strong> All statutory checks consistent.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Load Case 1 (Clean)", type="primary", use_container_width=True):
            with st.spinner("Loading Case 1 and executing deterministic audit..."):
                clear_case_associated_outputs()
                samples = generate_all_cases()
                bundle = load_synthetic_bundle(samples["case_1"])
                report = run_full_audit(bundle)
                st.session_state.bundle = bundle
                st.session_state.audit_report = report
                st.session_state.selected_case_name = "Case 1: Clean and Consistent Work"
                st.session_state.current_page = "audit"
                st.session_state.workflow_step = 4  # Jump to findings
                st.rerun()

    with d2:
        st.markdown(
            """
            <div class="process-card">
                <span class="badge-pill pill-mismatch">Cost Discrepancy</span>
                <h4 style="margin: 10px 0 6px 0; color: #0f172a;">Case 2: Cost Difference & Incomplete Board</h4>
                <p style="font-size: 0.85rem; color: #64748b;">
                    <strong>Work:</strong> Community Tank Desiltation<br>
                    <strong>Approved Sanction:</strong> ₹8,00,000.00<br>
                    <strong>Cumulative Bills:</strong> ₹9,20,000.00<br>
                    <strong>Expected:</strong> ₹1,20,000 excess & missing board costs.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Load Case 2 (Cost Mismatch)", type="primary", use_container_width=True):
            with st.spinner("Loading Case 2 and executing deterministic audit..."):
                clear_case_associated_outputs()
                samples = generate_all_cases()
                bundle = load_synthetic_bundle(samples["case_2"])
                report = run_full_audit(bundle)
                st.session_state.bundle = bundle
                st.session_state.audit_report = report
                st.session_state.selected_case_name = "Case 2: Cost Difference and Incomplete Board"
                st.session_state.current_page = "audit"
                st.session_state.workflow_step = 4  # Jump to findings
                st.rerun()

    with d3:
        st.markdown(
            """
            <div class="process-card">
                <span class="badge-pill pill-review">Evidence Anomaly</span>
                <h4 style="margin: 10px 0 6px 0; color: #0f172a;">Case 3: Photo Reuse & Date Anomaly</h4>
                <p style="font-size: 0.85rem; color: #64748b;">
                    <strong>Work:</strong> Check Dam across Vagu<br>
                    <strong>Stage Photos:</strong> Stage 1 & 3 visual near-duplicate<br>
                    <strong>Bills:</strong> Bill dated prior to sanction issuance<br>
                    <strong>Expected:</strong> Flagged for human review.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Load Case 3 (Anomaly)", type="primary", use_container_width=True):
            with st.spinner("Loading Case 3 and executing deterministic audit..."):
                clear_case_associated_outputs()
                samples = generate_all_cases()
                bundle = load_synthetic_bundle(samples["case_3"])
                report = run_full_audit(bundle)
                st.session_state.bundle = bundle
                st.session_state.audit_report = report
                st.session_state.selected_case_name = "Case 3: Photo Similarity and Date Anomaly"
                st.session_state.current_page = "audit"
                st.session_state.workflow_step = 4  # Jump to findings
                st.rerun()


# ---------------------------------------------------------------------------
# View 3: Statutory Framework & Methodology
# ---------------------------------------------------------------------------

elif st.session_state.current_page == "methodology":
    st.subheader("Statutory Framework & Rule-Source Registry")
    st.markdown(
        """
        JanataLens grounds every audit check in published statutory provisions under the 
        **Viksit Bharat—Guarantee for Rozgar and Ajeevika Mission (Gramin): VB–G RAM G Act, 2025** (Act No. 36 of 2025), 
        notified on 11 May 2026 and commenced on 1 July 2026.
        """
    )

    t1, t2, t3 = st.tabs(["Statutory Audit Rules (JL-01 to JL-05)", "Two Separate Legal Clocks", "Historical Audit Context"])

    with t1:
        st.markdown(
            """
            | Rule ID | Title | Legal Section | Calculation / Comparison Basis |
            |---|---|---|---|
            | **JL-01** | Janata Board Completeness | Section 25(2)(b) | Verifies worksite board displays work details, estimated labour days, material quantities, and item-wise costs. |
            | **JL-02** | Financial Reconciliation | Section 25(2)(c) & (d) | Reconciles cumulative bills against administrative and revised sanction orders using Python `Decimal`. |
            | **JL-03** | Labour & Wage Timeline | Section 5(3) & Sched II Para 6 | Separately checks 14-day wage disbursement and 15-day muster closure compensation. |
            | **JL-04** | Chronological Integrity | General Financial Rules | Verifies that bills, muster closures, and stage photos are dated on or after sanction date. |
            | **JL-05** | Photo Reuse Forensics | Digital Audit Guidelines | Pairwise SHA-256 exact match and perceptual hash (pHash / dHash) Hamming distance. |
            """
        )

    with t2:
        st.markdown(
            """
            ### The Two Separate Statutory Clocks for Wages
            JanataLens strictly separates wage disbursement timing from delay compensation:

            1. **Wage Disbursement Clock (Section 5(3)):**
               - Wages must be paid weekly, or in any case not later than a fortnight (14 days) after the date on which work was done.
               - FTO generation or processing is **not** treated as proof of credit.
            
            2. **Delay Compensation Clock (Schedule II, Paragraph 6):**
               - If wages are not paid within 15 days from muster-roll closure, delay compensation is payable at **0.05% of unpaid wages per day of delay** beyond the 16th day of closure.
               - Only calculated when muster closure date, wage due, and confirmed credit date are evidenced.
            """
        )

    with t3:
        st.markdown(
            """
            ### Historical Motivation: CAG Report No. 13 of 2026
            - **Audit Scope:** Performance audit of MGNREGS implementation in Karnataka for the year ended March 2024.
            - **Civic Motivation:** Highlighted systemic issues in worksite signboard omissions, delay compensation calculations, and photo documentation.
            - **Legal Boundary:** Historical findings under the prior MGNREGS framework are cited for methodology motivation, not conflated with VB–G RAM G Act, 2025 implementations.
            """
        )


# ---------------------------------------------------------------------------
# View 4: Guided Audit Stepper Workflow
# ---------------------------------------------------------------------------

elif st.session_state.current_page == "audit":

    # --- Stepper Header ---
    current_step = st.session_state.workflow_step

    def _step_class(step_num: int) -> str:
        if current_step == step_num:
            return "step-active"
        elif current_step > step_num:
            return "step-completed"
        return "step-upcoming"

    st.markdown(
        f"""
        <div class="stepper-container">
            <div class="stepper-item {_step_class(1)}">
                <div class="stepper-circle">1</div>
                <div class="step-label">Work Details</div>
            </div>
            <div style="color: #cbd5e1; font-weight: bold; margin: 0 10px;">→</div>
            <div class="stepper-item {_step_class(2)}">
                <div class="stepper-circle">2</div>
                <div class="step-label">Upload Evidence</div>
            </div>
            <div style="color: #cbd5e1; font-weight: bold; margin: 0 10px;">→</div>
            <div class="stepper-item {_step_class(3)}">
                <div class="stepper-circle">3</div>
                <div class="step-label">Review Extracted Data</div>
            </div>
            <div style="color: #cbd5e1; font-weight: bold; margin: 0 10px;">→</div>
            <div class="stepper-item {_step_class(4)}">
                <div class="stepper-circle">4</div>
                <div class="step-label">Investigate Findings</div>
            </div>
            <div style="color: #cbd5e1; font-weight: bold; margin: 0 10px;">→</div>
            <div class="stepper-item {_step_class(5)}">
                <div class="stepper-circle">5</div>
                <div class="step-label">Export Report</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Show watermark banner if active bundle is synthetic
    if st.session_state.bundle and st.session_state.bundle.synthetic:
        st.markdown(
            """
            <div class="synthetic-banner">
                <strong>SYNTHETIC DEMO DATA — NOT AN OFFICIAL GOVERNMENT RECORD</strong>:
                Currently inspecting a pre-generated demonstration case.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # =========================================================================
    # STEP 1: WORK DETAILS
    # =========================================================================
    if current_step == 1:
        st.subheader("Step 1: Work Identity & Scheme Details")
        st.markdown(
            "Enter the official work code and administrative location details. "
            "These establish the verified baseline for cross-document linkage."
        )

        with st.container():
            c_w1, c_w2 = st.columns(2)
            with c_w1:
                st.session_state.work_id_input = st.text_input(
                    "Work Code / Project ID *",
                    value=st.session_state.work_id_input,
                    help="Unique identifier from the administrative sanction order or NREGAsoft MIS",
                )
                st.session_state.work_name_input = st.text_input(
                    "Work Title / Approved Description *",
                    value=st.session_state.work_name_input,
                )
                st.session_state.agency_input = st.text_input(
                    "Implementing Agency",
                    value=st.session_state.agency_input,
                )
            with c_w2:
                st.session_state.gp_input = st.text_input(
                    "Gram Panchayat",
                    value=st.session_state.gp_input,
                )
                st.session_state.district_input = st.text_input(
                    "Mandal / District / State",
                    value=st.session_state.district_input,
                )

        st.markdown("<br>", unsafe_allow_html=True)
        col_next, col_demo = st.columns([1, 1])
        with col_next:
            if st.button("Save & Continue to Evidence Upload →", type="primary", use_container_width=True):
                if not st.session_state.work_id_input.strip():
                    st.error("Please enter a valid Work Code before proceeding.")
                else:
                    st.session_state.workflow_step = 2
                    st.rerun()
        with col_demo:
            if st.button("Or Load a Pre-configured Demo Case", use_container_width=True):
                st.session_state.current_page = "demos"
                st.rerun()

    # =========================================================================
    # STEP 2: UPLOAD EVIDENCE
    # =========================================================================
    elif current_step == 2:
        demo_allowed, demo_message = validate_demo_mode_intake(app_mode)
        if not demo_allowed:
            st.subheader("Step 2: Synthetic Demo Evidence")
            st.warning(demo_message)
            st.info("Demo mode intentionally accepts no private uploads or persistence. Choose one of the pre-built synthetic cases.")
            if st.button("Open Synthetic Demonstration Cases", type="primary", use_container_width=True):
                st.session_state.current_page = "demos"
                st.rerun()
            st.stop()
        st.subheader("Step 2: Upload Supporting Evidence")
        st.markdown(
            "Upload records for this work. Accepted formats: `.pdf`, `.csv`, `.jpg`, `.jpeg`, `.png`. Max 15 MB per file."
        )

        # 6 Dedicated Upload Areas in a 2-column layout
        u_col1, u_col2 = st.columns(2)

        with u_col1:
            # 1. Janata Board Photo
            st.markdown(
                """
                <div class="upload-card">
                    <div class="upload-header">
                        <span class="upload-title">1. Worksite Janata Board Photo</span>
                        <span class="tag-required">Required (Sec 25(2)(b))</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 8px;">
                        JPG / PNG image of physical worksite board displaying labour days & item costs.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            up_board = st.file_uploader("Upload Janata Board Photo", type=["jpg", "jpeg", "png"], key="step2_board", label_visibility="collapsed")

            # 2. Sanction Order & Estimate PDF
            st.markdown(
                """
                <div class="upload-card">
                    <div class="upload-header">
                        <span class="upload-title">2. Sanction Order & BOQ Estimate</span>
                        <span class="tag-required">Required</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 8px;">
                        PDF file containing administrative approval ceiling and item-wise BOQ estimate.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            up_sanction = st.file_uploader("Upload Sanction PDF", type=["pdf"], key="step2_sanc", label_visibility="collapsed")

            # 3. Weekly Disclosures CSV
            st.markdown(
                """
                <div class="upload-card">
                    <div class="upload-header">
                        <span class="upload-title">3. Weekly Disclosures Table</span>
                        <span class="tag-optional">Recommended (Sec 25(2)(c))</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 8px;">
                        CSV table of weekly public disclosures showing labour days and expenditure.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            up_disc = st.file_uploader("Upload Weekly Disclosure CSV", type=["csv"], key="step2_disc", label_visibility="collapsed")

        with u_col2:
            # 4. Bills & Vouchers CSV
            st.markdown(
                """
                <div class="upload-card">
                    <div class="upload-header">
                        <span class="upload-title">4. Material Bills & Vouchers</span>
                        <span class="tag-required">Required for Reconciliation</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 8px;">
                        CSV table of vendor bills, voucher dates, and expenditure amounts.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            up_bills = st.file_uploader("Upload Bills CSV", type=["csv"], key="step2_bills", label_visibility="collapsed")

            # 5. Muster & Labour Records CSV
            st.markdown(
                """
                <div class="upload-card">
                    <div class="upload-header">
                        <span class="upload-title">5. Muster Roll & Wage Records</span>
                        <span class="tag-optional">Recommended (Sec 5(3))</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 8px;">
                        Pseudonymous CSV of work dates, muster closure dates, and credit timestamps.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            up_labour = st.file_uploader("Upload Labour Records CSV", type=["csv"], key="step2_labour", label_visibility="collapsed")

            # 6. Stage Photographs
            st.markdown(
                """
                <div class="upload-card">
                    <div class="upload-header">
                        <span class="upload-title">6. Stage Progress Photographs</span>
                        <span class="tag-optional">Forensic Analysis</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 8px;">
                        Upload Initial, Intermediate, and Final stage photographs for reuse review.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                up_p1 = st.file_uploader("Stage 1", type=["jpg", "jpeg", "png"], key="step2_p1")
            with col_p2:
                up_p2 = st.file_uploader("Stage 2", type=["jpg", "jpeg", "png"], key="step2_p2")
            with col_p3:
                up_p3 = st.file_uploader("Stage 3", type=["jpg", "jpeg", "png"], key="step2_p3")

        st.markdown("<br>", unsafe_allow_html=True)
        c_b1, c_b2 = st.columns([1, 1])

        with c_b1:
            if st.button("← Back to Work Details", use_container_width=True):
                st.session_state.workflow_step = 1
                st.rerun()

        with c_b2:
            if st.button("Process Evidence & Continue to Review →", type="primary", use_container_width=True):
                demo_allowed, demo_message = validate_demo_mode_intake(app_mode)
                if not demo_allowed:
                    st.error(demo_message)
                    st.stop()
                with st.spinner("Extracting candidate fields and computing file hashes..."):
                    evidence_files: List[EvidenceReference] = []
                    sanction_data = None
                    bills: List[BillVoucherRecord] = []
                    labour_records: List[LabourPaymentRecord] = []
                    disclosures: List[WeeklyDisclosureData] = []
                    stage_photos: List[StagePhotoEvidence] = []
                    board_data = None

                    # If user didn't upload custom files and no bundle exists, suggest demo
                    if not (up_sanction or up_bills or up_labour or up_board or up_disc):
                        st.warning("No files were uploaded. You can load a demonstration bundle or upload at least a sanction PDF or bills CSV.")
                    else:
                        if up_sanction:
                            s_bytes = up_sanction.read()
                            valid, intake_error = validate_file_intake(up_sanction.name, s_bytes)
                            if not valid:
                                st.error(intake_error)
                                st.stop()
                            valid, intake_error = validate_upload_content(up_sanction.name, s_bytes)
                            if not valid:
                                st.error(intake_error)
                                st.stop()
                            try:
                                sanction_data = parse_sanction_pdf(s_bytes, filename=up_sanction.name, synthetic=False)
                            except ValueError as exc:
                                st.error(str(exc))
                                st.stop()
                            evidence_files.extend(sanction_data.evidence_references)

                        if up_bills:
                            b_bytes = up_bills.read()
                            valid, intake_error = validate_file_intake(up_bills.name, b_bytes)
                            if not valid:
                                st.error(intake_error)
                                st.stop()
                            valid, intake_error = validate_upload_content(up_bills.name, b_bytes)
                            if not valid:
                                st.error(intake_error)
                                st.stop()
                            try:
                                bills = parse_bills_csv(b_bytes, filename=up_bills.name, synthetic=False)
                            except ValueError as exc:
                                st.error(f"Could not process bills file: {exc}")
                                st.stop()
                            evidence_files.extend([b.evidence for b in bills if b.evidence])

                        if up_labour:
                            l_bytes = up_labour.read()
                            valid, intake_error = validate_file_intake(up_labour.name, l_bytes)
                            if not valid:
                                st.error(intake_error)
                                st.stop()
                            valid, intake_error = validate_upload_content(up_labour.name, l_bytes)
                            if not valid:
                                st.error(intake_error)
                                st.stop()
                            try:
                                labour_records = parse_labour_csv(l_bytes, filename=up_labour.name, synthetic=False)
                            except ValueError as exc:
                                st.error(f"Could not process labour records: {exc}")
                                st.stop()
                            evidence_files.extend([l.evidence for l in labour_records if l.evidence])

                        if up_disc:
                            d_bytes = up_disc.read()
                            valid, intake_error = validate_file_intake(up_disc.name, d_bytes)
                            if not valid:
                                st.error(intake_error)
                                st.stop()
                            valid, intake_error = validate_upload_content(up_disc.name, d_bytes)
                            if not valid:
                                st.error(intake_error)
                                st.stop()
                            try:
                                disclosures = parse_weekly_disclosure_csv(d_bytes, filename=up_disc.name, synthetic=False)
                            except ValueError as exc:
                                st.error(f"Could not process weekly disclosure: {exc}")
                                st.stop()
                            for d in disclosures:
                                evidence_files.extend(d.evidence_references)

                        if up_board:
                            board_bytes = up_board.read()
                            valid, intake_error = validate_file_intake(up_board.name, board_bytes)
                            if not valid:
                                st.error(intake_error)
                                st.stop()
                            valid, intake_error = validate_upload_content(up_board.name, board_bytes)
                            if not valid:
                                st.error(intake_error)
                                st.stop()
                            board_sha = hashlib.sha256(board_bytes).hexdigest()
                            board_ref = EvidenceReference(
                                evidence_id=f"EV-BOARD-{board_sha[:8]}",
                                filename=up_board.name,
                                evidence_type=EvidenceCategory.JANATA_BOARD_PHOTO,
                                sha256=board_sha,
                                file_size_bytes=len(board_bytes),
                                synthetic=False,
                            )
                            evidence_files.append(board_ref)
                            board_data = JanataBoardData(evidence_references=[board_ref])

                        for uploaded_photo, stage_label, stage_order in (
                            (up_p1, "Stage 1: Initial", 1),
                            (up_p2, "Stage 2: Intermediate", 2),
                            (up_p3, "Stage 3: Final", 3),
                        ):
                            if uploaded_photo:
                                photo_bytes = uploaded_photo.read()
                                valid, intake_error = validate_file_intake(uploaded_photo.name, photo_bytes)
                                if not valid:
                                    st.error(intake_error)
                                    st.stop()
                                valid, intake_error = validate_upload_content(uploaded_photo.name, photo_bytes)
                                if not valid:
                                    st.error(intake_error)
                                    st.stop()
                                stage_photos.append(
                                    inspect_stage_photo_bytes(
                                        photo_bytes,
                                        uploaded_photo.name,
                                        stage_label,
                                        stage_order,
                                        synthetic=False,
                                    )
                                )
                        evidence_files.extend([p.evidence_reference for p in stage_photos])

                        user_bundle = AuditBundle(
                            work_id=st.session_state.work_id_input,
                            work_name=st.session_state.work_name_input,
                            synthetic=False,
                            evidence_files=evidence_files,
                            board_data=board_data,
                            sanction_data=sanction_data,
                            weekly_disclosures=disclosures,
                            bills=bills,
                            labour_records=labour_records,
                            stage_photos=stage_photos,
                        )
                        st.session_state.bundle = user_bundle
                        st.session_state.workflow_step = 3
                        st.rerun()

    # =========================================================================
    # STEP 3: REVIEW EXTRACTED DATA
    # =========================================================================
    elif current_step == 3:
        st.subheader("Step 3: Human Extraction Review Gate")
        st.markdown(
            "Review and confirm extracted candidate values. "
            "Under JanataLens audit principles, **unreviewed or low-confidence numbers cannot silently enter financial calculations**."
        )

        bundle = st.session_state.bundle
        if not bundle:
            st.warning("No active evidence bundle found. Please return to Step 2 to upload files or load a demo case.")
        else:
            # 1. Work Identity Review
            st.markdown("#### 1. Work Identity Verification")
            c_r1, c_r2, c_r3 = st.columns(3)
            with c_r1:
                st.text_input("Declared Work Code", value=bundle.work_id, disabled=True)
            with c_r2:
                st.text_input("Declared Work Title", value=bundle.work_name, disabled=True)
            with c_r3:
                st.text_input("Registered Evidence Files", value=f"{len(bundle.evidence_files)} files", disabled=True)

            # 2. Key Extracted Values Confirmation Table
            st.markdown("#### 2. Key Financial & Sanction Values")
            sanc = bundle.sanction_data

            if sanc:
                s_amt_val = sanc.original_sanction_amount.get_effective_value() if sanc.original_sanction_amount else Decimal("0")
                s_date_val = sanc.original_sanction_date.get_effective_value() if sanc.original_sanction_date else "N/A"
                s_ev = sanc.original_sanction_amount.source.filename if (sanc.original_sanction_amount and sanc.original_sanction_amount.source) else "sanction_order.pdf"

                c_s1, c_s2, c_s3 = st.columns([1.5, 1.2, 1.3])
                with c_s1:
                    st.text_input("Sanctioned Amount Ceiling", value=f"₹{s_amt_val:,.2f}", disabled=True)
                    st.caption(f"Source: `{s_ev}` (Page 1)")
                with c_s2:
                    st.text_input("Sanction Issuance Date", value=str(s_date_val), disabled=True)
                    st.caption("Chronology anchor")
                with c_s3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    sanc_confirmed = st.checkbox("Confirm Sanction Values", value=True, help="Check to approve this value for financial comparison")
            else:
                st.info("No administrative sanction document registered in this bundle.")

            # 3. Bills & Vouchers Summary
            st.markdown("#### 3. Bills & Vouchers Breakdown")
            if bundle.bills:
                total_bills = sum(b.amount for b in bundle.bills)
                st.write(f"**Total Bills Registered:** {len(bundle.bills)} | **Cumulative Sum:** ₹{total_bills:,.2f}")
                bill_rows = []
                for b in bundle.bills:
                    bill_rows.append({
                        "Bill No": b.bill_number,
                        "Date": str(b.bill_date),
                        "Vendor": b.vendor_or_payee,
                        "Category": b.cost_category,
                        "Amount (₹)": f"₹{b.amount:,.2f}",
                        "Source File": b.evidence.filename if b.evidence else "bills.csv",
                        "Row": b.evidence.row_number if b.evidence else "-",
                    })
                st.dataframe(bill_rows, use_container_width=True)
            else:
                st.info("No bills or vouchers uploaded.")

            # 4. Worksite Janata Board Completeness
            st.markdown("#### 4. Janata Board Statutory Disclosures (Section 25(2)(b))")
            board = bundle.board_data
            if board:
                b_ld = board.estimated_labour_days.get_effective_value() if board.estimated_labour_days else "Not Found"
                st.write(f"**Disclosed Estimated Labour Days:** `{b_ld}`")
                if board.material_entries:
                    st.write(f"**Disclosed Material Items:** {len(board.material_entries)}")
                    m_rows = []
                    for m in board.material_entries:
                        cost_str = f"₹{m.item_cost:,.2f}" if m.item_cost is not None else "MISSING / NOT DISPLAYED"
                        m_rows.append({
                            "Local Item Name": m.local_name,
                            "Quantity": str(m.quantity or "-"),
                            "Unit": m.unit or "-",
                            "Item Cost": cost_str,
                        })
                    st.dataframe(m_rows, use_container_width=True)
            else:
                st.warning("Worksite Janata Board record not supplied. Rule JL-01 will report MISSING_EVIDENCE.")

            st.markdown("<br>", unsafe_allow_html=True)
            c_r_back, c_r_run = st.columns([1, 1.5])
            with c_r_back:
                if st.button("← Back to Upload Evidence", use_container_width=True):
                    st.session_state.workflow_step = 2
                    st.rerun()
            with c_r_run:
                if st.button("Run Deterministic Audit Engine →", type="primary", use_container_width=True):
                    with st.spinner("Executing deterministic audit rules (JL-01 to JL-05)..."):
                        report = run_full_audit(bundle)
                        st.session_state.audit_report = report

                        # Save ephemeral local session
                        save_session_record(
                            session_id=report.session_id,
                            work_id=report.work_id or "DEMO",
                            work_name=report.work_name or "Work",
                            synthetic=report.synthetic,
                            overall_state=report.overall_review_state,
                            findings_count=len(report.findings),
                            summary=report.rule_execution_summary,
                            evidence_inventory=[ev.model_dump() for ev in report.evidence_inventory],
                        )
                        st.session_state.workflow_step = 4
                        st.rerun()

    # =========================================================================
    # STEP 4: INVESTIGATE FINDINGS
    # =========================================================================
    elif current_step == 4:
        st.subheader("Step 4: Audit Review Findings & Evidence Reconciliation")

        report = st.session_state.audit_report
        bundle = st.session_state.bundle

        if not report:
            st.warning("No audit report available. Please execute the audit in Step 3 or load a demonstration case.")
        else:
            # Overall Status Metric Banner
            st.markdown("#### Case Summary")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Work ID", report.work_id or "Not specified")
            s2.metric("Rules Executed", len(report.rule_execution_summary.get("rules_executed", [])))
            s3.metric("Findings", len(report.findings))
            s4.metric("Evidence Files", len(report.evidence_inventory))
            st.caption(f"{report.work_name or 'Unnamed work'} · Overall review state: {report.overall_review_state.replace('_', ' ')}")

            # Tabbed Views: Rule-wise Findings, Photo Forensics, Optional Plain-Language Summary
            f_tab1, f_tab2, f_tab3 = st.tabs(["Detailed Findings & Evidence", "Photo Forensics Review", "Plain-Language Explanation"])

            with f_tab1:
                # Filter buttons
                filter_options = ["All Findings", "Discrepancies Only", "Needs Review Only", "Consistent Only"]
                chosen_filter = st.radio("Filter findings by status:", filter_options, horizontal=True, label_visibility="collapsed")

                filtered_findings = report.findings
                if chosen_filter == "Discrepancies Only":
                    filtered_findings = [f for f in report.findings if f.status == FindingStatus.MISMATCH_FOUND]
                elif chosen_filter == "Needs Review Only":
                    filtered_findings = [f for f in report.findings if f.status in (FindingStatus.NEEDS_HUMAN_REVIEW, FindingStatus.MISSING_EVIDENCE)]
                elif chosen_filter == "Consistent Only":
                    filtered_findings = [f for f in report.findings if f.status == FindingStatus.CONSISTENT]

                if not filtered_findings:
                    st.info(f"No findings matching filter '{chosen_filter}'.")

                for idx, finding in enumerate(filtered_findings, start=1):
                    display_state, state_class = map_finding_display_state(finding, bundle)
                    card_border = {
                        "VERIFIED": "border-consistent",
                        "MISSING": "border-missing",
                        "INCONSISTENT": "border-mismatch",
                        "UNVERIFIED": "border-review",
                    }[display_state]

                    st.markdown(
                        f"""
                        <div class="finding-card {card_border}">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                                <div>
                                    <span style="font-size: 0.8rem; font-weight: 700; color: #64748b;">{finding.rule_id}</span>
                                    <h3 style="margin: 2px 0 0 0; color: #0f172a; font-size: 1.15rem; font-weight: 700;">{finding.title}</h3>
                                </div>
                                <span class="evidence-state {state_class}">{display_state}</span>
                            </div>
                            <p style="color: #334155; font-size: 0.95rem; line-height: 1.5; margin-bottom: 8px;">
                                {finding.summary}
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Exact Deterministic Calculation
                    if finding.exact_calculation:
                        st.markdown(
                            f"""
                            <div class="calc-panel">
                                <strong>Deterministic Calculation:</strong><br>
                                {finding.exact_calculation}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    # Expandable Context & Verification Steps
                    with st.expander(f"Investigate Evidence & Verification Steps for Finding #{idx}", expanded=(finding.status != FindingStatus.CONSISTENT)):
                        c_ex1, c_ex2 = st.columns(2)

                        with c_ex1:
                            st.markdown("##### Supporting Evidence")
                            if finding.evidence_references:
                                for ev in finding.evidence_references:
                                    pg_info = f" (Page {ev.page_number})" if ev.page_number else ""
                                    row_info = f" (Row {ev.row_number})" if ev.row_number else ""
                                    st.write(f"- `{ev.filename}`{pg_info}{row_info}")
                                    st.caption(f"  SHA-256: `{ev.sha256[:12]}...`")
                            else:
                                st.caption("No specific file attached.")

                            if finding.rule_source:
                                st.markdown("##### Legal & Policy Source")
                                st.caption(f"**Authority:** {finding.rule_source.issuing_authority}")
                                st.caption(f"**Section:** {finding.rule_source.section_reference}")

                        with c_ex2:
                            st.markdown("##### Actionable Human Verification Steps")
                            if finding.human_verification_steps:
                                for step in finding.human_verification_steps:
                                    st.markdown(f"- [ ] {step}")
                            else:
                                st.caption("No specific follow-up required for consistent findings.")

                            st.markdown(
                                """
                                <div style="font-size: 0.78rem; color: #64748b; margin-top: 10px; font-style: italic;">
                                    Civil Notice: A review exception requires human checking at the Gram Sabha. It does not establish culpability.
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

            with f_tab2:
                # Photo Forensics Layout
                st.markdown("#### Stage Photograph Comparison & Metadata Integrity")
                st.markdown(
                    "Side-by-side inspection of declared stage photographs. "
                    "JanataLens computes binary SHA-256 identity and perceptual hash (pHash / dHash) Hamming distances. "
                    "**No facial recognition or worker tracking is ever performed.**"
                )

                if not bundle or not bundle.stage_photos:
                    st.info("No stage photographs available in this audit bundle.")
                else:
                    # Side by side images
                    p_cols = st.columns(min(len(bundle.stage_photos), 3))
                    case_root = Path("sample_cases")

                    for p_idx, photo in enumerate(bundle.stage_photos):
                        with p_cols[p_idx % 3]:
                            st.markdown(f"**{photo.declared_stage_label}**")
                            # Resolve only within the active synthetic case; never glob across cases.
                            matched_img = None
                            if bundle.synthetic:
                                synthetic_case_dirs = {
                                    "WRK-AP-2026-00101": case_root / "case_1_clean",
                                    "WRK-AP-2026-00204": case_root / "case_2_cost_mismatch",
                                    "WRK-AP-2026-00309": case_root / "case_3_evidence_anomaly",
                                }
                                case_dir = synthetic_case_dirs.get(bundle.work_id)
                                candidate = case_dir / photo.evidence_reference.filename if case_dir else None
                                if candidate and candidate.exists():
                                    candidate_sha = compute_sha256(candidate)
                                    if candidate_sha == photo.evidence_reference.sha256:
                                        matched_img = candidate

                            if matched_img:
                                st.image(str(matched_img), use_container_width=True)
                            else:
                                st.caption(f"Image: `{photo.evidence_reference.filename}`")

                            st.caption(f"**File:** `{photo.evidence_reference.filename}`")
                            st.caption(f"**pHash:** `{photo.phash}` | **dHash:** `{photo.dhash}`")

                    st.markdown("---")
                    st.markdown("##### Pairwise Forensic Hash Results (JL-05)")

                    photos = bundle.stage_photos
                    for i in range(len(photos)):
                        for j in range(i + 1, len(photos)):
                            ph1 = photos[i]
                            ph2 = photos[j]
                            p_dist = hamming_distance(ph1.phash, ph2.phash)
                            d_dist = hamming_distance(ph1.dhash, ph2.dhash)
                            is_exact = (ph1.sha256 == ph2.sha256)

                            st.write(f"**Comparison:** {ph1.declared_stage_label} vs {ph2.declared_stage_label}")
                            res1, res2, res3 = st.columns(3)
                            with res1:
                                st.metric("Exact Binary Match", "Duplicate" if is_exact else "Distinct")
                            with res2:
                                st.metric("pHash Hamming Distance", str(p_dist) if p_dist is not None else "N/A")
                            with res3:
                                st.metric("dHash Hamming Distance", str(d_dist) if d_dist is not None else "N/A")

                            if is_exact or (p_dist is not None and p_dist <= 8) or (d_dist is not None and d_dist <= 8):
                                st.warning(
                                    f"**Potential Image Reuse:** Perceptual similarity between {ph1.declared_stage_label} "
                                    f"and {ph2.declared_stage_label} exceeds forensic threshold (Hamming distance <= 8). "
                                    "Physical verification at worksite is required."
                                )
                            else:
                                st.success("**Distinct Visual Content:** Photographs show distinct physical appearances.")

            with f_tab3:
                # Plain-Language Explanations (AI layer)
                st.markdown("#### Plain-Language Community Explanations")
                st.markdown(
                    "Translate deterministic audit findings into accessible explanations for Gram Sabha participants."
                )

                if st.session_state.gemini_adapter.is_available():
                    col_ai_en, col_ai_te = st.columns(2)
                    with col_ai_en:
                        if st.button("Generate English Review Summary", use_container_width=True):
                            with st.spinner("Generating English summary..."):
                                s_txt = f"Work {report.work_id}: {report.overall_review_state}. Findings: {len(report.findings)}"
                                st.session_state.gemini_en = st.session_state.gemini_adapter.explain_audit_report(s_txt, "en")
                    with col_ai_te:
                        if st.button("Generate Telugu Review Summary (తెలుగు వివరణ)", use_container_width=True):
                            with st.spinner("Generating Telugu summary..."):
                                s_txt = f"Work {report.work_id}: {report.overall_review_state}. Findings: {len(report.findings)}"
                                st.session_state.gemini_te = st.session_state.gemini_adapter.explain_audit_report(s_txt, "te")

                    if "gemini_en" in st.session_state:
                        st.info(f"**English Community Summary:**\n\n{st.session_state.gemini_en}")
                    if "gemini_te" in st.session_state:
                        st.info(f"**తెలుగు సమీక్ష వివరణ (Telugu Summary):**\n\n{st.session_state.gemini_te}")
                else:
                    st.info(
                        "Gemini API key is not configured locally. "
                        "The deterministic audit results above are complete, evidence-backed, and authoritative."
                    )

            st.markdown("<br>", unsafe_allow_html=True)
            c_f_back, c_f_next = st.columns([1, 1.5])
            with c_f_back:
                if st.button("← Back to Extracted Data", use_container_width=True):
                    st.session_state.workflow_step = 3
                    st.rerun()
            with c_f_next:
                if st.button("Continue to Export Report →", type="primary", use_container_width=True):
                    st.session_state.workflow_step = 5
                    st.rerun()

    # =========================================================================
    # STEP 5: EXPORT REPORT
    # =========================================================================
    elif current_step == 5:
        st.subheader("Step 5: Export Evidence-Backed Audit Report")
        st.markdown(
            "Download the complete audit findings, calculation logs, and evidence provenance "
            "in machine-readable JSON or human-readable Markdown format."
        )

        report = st.session_state.audit_report
        if not report:
            st.warning("No audit report to export. Please run an audit first.")
        else:
            json_report_str = generate_json_report(report)
            md_report_str = generate_markdown_report(report)

            st.markdown("#### Case Summary")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Work ID", report.work_id or "Not specified")
            r2.metric("Evidence Files", len(report.evidence_inventory))
            r3.metric("Findings", len(report.findings))
            r4.metric("Overall State", report.overall_review_state.replace("_", " ").title())
            st.caption(f"Work: {report.work_name or 'Unnamed work'}")

            c_exp1, c_exp2 = st.columns(2)
            with c_exp1:
                st.download_button(
                    label="Download JSON Report (Machine-Readable)",
                    data=json_report_str,
                    file_name=f"janatalens_audit_{report.work_id}.json",
                    mime="application/json",
                    type="primary",
                    use_container_width=True,
                )
                st.caption("Standardized JSON export containing full provenance and calculation inputs.")

            with c_exp2:
                st.download_button(
                    label="Download Markdown Report (Gram Sabha Ready)",
                    data=md_report_str,
                    file_name=f"janatalens_audit_{report.work_id}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
                st.caption("Formatted Markdown document ready for printing or Gram Sabha review.")

            st.markdown("---")
            st.markdown("#### Evidence Inventory Summary")
            inv_rows = []
            for ev in report.evidence_inventory:
                inv_rows.append({
                    "Filename": ev.filename,
                    "Category": ev.evidence_type.value,
                    "SHA-256 (Hash)": f"{ev.sha256[:16]}...",
                    "Size": f"{ev.file_size_bytes:,} bytes",
                    "Synthetic Data": "Yes" if ev.synthetic else "No",
                })
            st.dataframe(inv_rows, use_container_width=True)

            st.markdown("---")
            st.markdown("#### Report Document Preview")
            st.text_area("Markdown Report Content", value=md_report_str, height=300)

            st.markdown("<br>", unsafe_allow_html=True)
            c_e_back, c_e_new = st.columns([1, 1])
            with c_e_back:
                if st.button("← Back to Findings Investigation", use_container_width=True):
                    st.session_state.workflow_step = 4
                    st.rerun()
            with c_e_new:
                if st.button("Start Another Audit Review 🔄", use_container_width=True):
                    clear_case_associated_outputs()
                    st.session_state.bundle = None
                    st.session_state.audit_report = None
                    st.session_state.workflow_step = 1
                    st.session_state.current_page = "home"
                    st.rerun()
