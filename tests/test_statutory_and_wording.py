"""Focused tests for statutory citations and conservative evidence wording."""

from src.audit_engine import RULE_SOURCES, run_full_audit
from src.display_messages import GEMINI_OFFLINE_MESSAGE, PHOTO_NO_SIGNAL_MESSAGE
from src.document_extractor import load_synthetic_bundle
from src.report_generator import generate_markdown_report
from src.sample_generator import generate_all_cases


def test_jl01_cites_schedule_i_not_main_act_section():
    citation = RULE_SOURCES["JL-01"].section_reference
    assert "Schedule I, paragraph 25(2)(b)" in citation
    assert "Section 25(2)(b)" not in citation


def test_jl02_cites_sanctions_and_accountability_sources():
    citation = RULE_SOURCES["JL-02"].section_reference
    assert "Schedule I, paragraph 14" in citation
    assert "Section 23(1)-(2)" in citation
    assert "Financial Sanction Rules" not in citation
    assert "legally defined violation" in RULE_SOURCES["JL-02"].limitations


def test_jl03_separates_fortnight_and_operational_delay_checks():
    citation = RULE_SOURCES["JL-03"].section_reference
    calculation = RULE_SOURCES["JL-03"].calculation_basis
    assert "Section 5(3)" in citation
    assert "Schedule I, paragraph 16" in citation
    assert "Schedule II, paragraph 6" in citation
    assert "operational" in calculation
    assert "not proof of credit" in RULE_SOURCES["JL-03"].limitations


def test_photo_messages_do_not_claim_hashes_prove_attributes():
    message = PHOTO_NO_SIGNAL_MESSAGE.lower()
    assert "exact or near-duplicate" in message
    assert "authenticity" in message
    assert "location" in message
    assert "capture date" in message
    assert "chronology" in message
    assert "work progress" in message


def test_gemini_offline_message_is_deployment_and_human_review_accurate():
    message = GEMINI_OFFLINE_MESSAGE
    assert "not configured for this deployment" in message
    assert "configured locally" not in message
    assert "Deterministic audit checks remain available offline" in message
    assert "Gemini-powered" in message
    assert "require human verification" in message
    assert "authoritative" not in message


def test_case_2_report_preserves_calculation_and_accurate_disclaimer():
    cases = generate_all_cases()
    report = run_full_audit(load_synthetic_bundle(cases["case_2"]))
    markdown = generate_markdown_report(report)

    jl02 = next(finding for finding in report.findings if finding.rule_id == "JL-02")
    assert "920,000.00" in jl02.exact_calculation
    assert "800,000.00" in jl02.exact_calculation
    assert "120,000.00" in jl02.exact_calculation
    assert "Schedule I, paragraph 14" in jl02.rule_source.section_reference
    assert "requires human review" in jl02.summary
    assert "Source-file SHA-256" in markdown
    assert "individual CSV rows" in markdown
