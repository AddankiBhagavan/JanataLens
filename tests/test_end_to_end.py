"""End-to-end audit pipeline tests for Case 1, Case 2, and Case 3."""

from decimal import Decimal
from pathlib import Path
import pytest

from src.audit_engine import run_full_audit
from src.document_extractor import load_synthetic_bundle
from src.report_generator import generate_json_report, generate_markdown_report
from src.sample_generator import generate_all_cases
from src.schemas import FindingStatus


@pytest.fixture(scope="session")
def samples():
    return generate_all_cases()


def test_case_1_clean_audit_pipeline(samples):
    """Case 1 must execute all applicable rules and be CONSISTENT across checks."""
    bundle = load_synthetic_bundle(samples["case_1"])
    report = run_full_audit(bundle)

    assert report.synthetic is True
    assert report.work_id == "WRK-AP-2026-00101"
    assert report.work_linkage_result["status"] == "LINKAGE_VERIFIED"
    assert "JL-01" in report.rule_execution_summary["rules_executed"]
    assert "JL-02" in report.rule_execution_summary["rules_executed"]
    assert "JL-03" in report.rule_execution_summary["rules_executed"]
    assert "JL-04" in report.rule_execution_summary["rules_executed"]
    assert "JL-05" in report.rule_execution_summary["rules_executed"]

    # All primary findings in Case 1 should be CONSISTENT
    for f in report.findings:
        assert f.status == FindingStatus.CONSISTENT

    assert report.overall_review_state == "CONSISTENT"

    # Export generation
    json_rep = generate_json_report(report)
    md_rep = generate_markdown_report(report)
    assert "WRK-AP-2026-00101" in json_rep
    assert "SYNTHETIC DEMO DATA" in md_rep


def test_case_reports_include_conservative_display_states(samples):
    import json

    bundle = load_synthetic_bundle(samples["case_1"])
    report = run_full_audit(bundle)
    json_rep = json.loads(generate_json_report(report))
    md_rep = generate_markdown_report(report)

    assert "display_statuses" in json_rep
    assert all(
        display_state in {"VERIFIED", "MISSING", "INCONSISTENT", "UNVERIFIED"}
        for display_state in json_rep["display_statuses"].values()
    )
    assert "**Display State:**" in md_rep
    assert "**Engine Status:**" in md_rep


def test_missing_and_inconsistent_reports_never_claim_verified(samples):
    bundle = load_synthetic_bundle(samples["case_2"])
    report = run_full_audit(bundle)
    import json

    json_rep = json.loads(generate_json_report(report))
    display_states = json_rep["display_statuses"]
    assert all(
        display_states[finding.finding_id] != "VERIFIED"
        for finding in report.findings
        if finding.status in (
            FindingStatus.MISSING_EVIDENCE,
            FindingStatus.MISMATCH_FOUND,
            FindingStatus.NEEDS_HUMAN_REVIEW,
        )
    )


def test_case_2_cost_mismatch_and_incomplete_board(samples):
    """Case 2 must find ₹1,20,000 cost excess and missing board item-wise costs."""
    bundle = load_synthetic_bundle(samples["case_2"])
    report = run_full_audit(bundle)

    assert report.synthetic is True
    assert report.work_id == "WRK-AP-2026-00204"

    # 1. JL-01: Board missing item-wise costs
    jl01_finding = next(f for f in report.findings if f.rule_id == "JL-01")
    assert jl01_finding.status == FindingStatus.MISSING_EVIDENCE
    assert "Item-wise cost breakdown missing" in jl01_finding.summary

    # 2. JL-02: Sanction ₹8,00,000 vs Bills ₹9,20,000 -> Diff ₹1,20,000
    jl02_finding = next(f for f in report.findings if f.rule_id == "JL-02")
    assert jl02_finding.status == FindingStatus.MISMATCH_FOUND
    assert jl02_finding.observed_values["difference"] == "120000.00"
    assert "₹920,000.00 - ₹800,000.00 = ₹120,000.00" in (jl02_finding.exact_calculation or "")

    assert report.overall_review_state == "MISMATCH_FOUND"

    # Report outputs must include calculation
    md_rep = generate_markdown_report(report)
    assert "₹120,000.00" in md_rep
    assert "Cumulative Expenditure Exceeds Sanctioned Amount" in md_rep


def test_case_3_evidence_anomaly_pipeline(samples):
    """Case 3 must flag potential photo reuse (JL-05) and pre-sanction bill (JL-04)."""
    bundle = load_synthetic_bundle(samples["case_3"])
    report = run_full_audit(bundle)

    assert report.synthetic is True
    assert report.work_id == "WRK-AP-2026-00309"

    # 1. JL-04: Pre-sanction bill anomaly
    jl04_finding = next(f for f in report.findings if f.rule_id == "JL-04")
    assert jl04_finding.status == FindingStatus.NEEDS_HUMAN_REVIEW
    assert "Prior to Administrative Sanction Date" in jl04_finding.title

    # 2. JL-05: Potential stage photograph reuse
    jl05_finding = next(f for f in report.findings if f.rule_id == "JL-05")
    assert jl05_finding.status == FindingStatus.NEEDS_HUMAN_REVIEW
    assert "Potential Stage Photograph Reuse" in jl05_finding.title

    assert report.overall_review_state == "NEEDS_HUMAN_REVIEW"

    # Reports
    json_rep = generate_json_report(report)
    md_rep = generate_markdown_report(report)
    assert "Potential Stage Photograph Reuse" in md_rep
    assert "Bills Dated Prior to Administrative Sanction Date" in md_rep


def test_gemini_adapter_safe_offline_fallback(monkeypatch):
    """Gemini adapter must fail safely and return clear deterministic explanations when offline."""
    from src.gemini_adapter import GeminiAdapter
    monkeypatch.setenv("GEMINI_API_KEY", "must-not-leak-from-env")
    adapter = GeminiAdapter(api_key=None)
    assert adapter.is_available() is False

    exp_en = adapter.explain_finding(
        title="Excess Expenditure",
        rule_id="JL-02",
        status="MISMATCH_FOUND",
        summary="Bills exceed sanction by Rs. 1,20,000",
        language="en",
    )
    assert "Deterministic finding" in exp_en

    exp_te = adapter.explain_finding(
        title="Excess Expenditure",
        rule_id="JL-02",
        status="MISMATCH_FOUND",
        summary="Bills exceed sanction",
        language="te",
    )
    assert "అందుబాటులో లేదు" in exp_te


def test_same_stage_filename_in_separate_cases_remains_isolated(samples):
    bundle_1 = load_synthetic_bundle(samples["case_1"])
    bundle_3 = load_synthetic_bundle(samples["case_3"])

    photo_1 = next(p for p in bundle_1.stage_photos if p.declared_order == 1)
    photo_3 = next(p for p in bundle_3.stage_photos if p.declared_order == 1)

    assert photo_1.evidence_reference.filename == photo_3.evidence_reference.filename
    assert photo_1.evidence_reference.sha256 != photo_3.evidence_reference.sha256
    assert bundle_1.work_id != bundle_3.work_id
    assert all(
        photo.evidence_reference.sha256
        == next(ev.sha256 for ev in bundle_1.evidence_files if ev.evidence_id == photo.evidence_reference.evidence_id)
        for photo in bundle_1.stage_photos
    )


def test_database_ephemeral_persistence(tmp_path):
    """Database saves and retrieves audit sessions in SQLite."""
    from src.database import get_recent_sessions, save_session_record
    db_file = tmp_path / "test_janatalens.db"

    save_session_record(
        session_id="SESS-TEST-01",
        work_id="WRK-TEST",
        work_name="Test Bund",
        synthetic=True,
        overall_state="CONSISTENT",
        findings_count=5,
        summary={"rules_executed": ["JL-01", "JL-02"]},
        evidence_inventory=[{"evidence_id": "ev1", "filename": "doc.pdf", "sha256": "123", "file_size_bytes": 100}],
        db_path=db_file,
    )

    recent = get_recent_sessions(limit=5, db_path=db_file)
    assert len(recent) == 1
    assert recent[0]["work_id"] == "WRK-TEST"
    assert recent[0]["overall_state"] == "CONSISTENT"
