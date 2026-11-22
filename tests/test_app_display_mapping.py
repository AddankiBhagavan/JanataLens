"""Focused tests for the presentation-only finding-state mapping."""

from decimal import Decimal

from app import map_finding_display_state
from src.schemas import (
    AuditBundle,
    AuditFinding,
    BillVoucherRecord,
    EvidenceCategory,
    EvidenceReference,
    ExtractedField,
    FindingStatus,
    JanataBoardData,
    LabourPaymentRecord,
    MaterialEntry,
    SanctionEstimateData,
    Severity,
)


def make_ref(category: EvidenceCategory = EvidenceCategory.OTHER_SUPPORTING_EVIDENCE) -> EvidenceReference:
    return EvidenceReference(
        evidence_id="EV-TEST",
        filename="source.pdf",
        evidence_type=category,
        sha256="a" * 64,
        file_size_bytes=1024,
        page_number=1,
        synthetic=True,
    )


def make_finding(status: FindingStatus, rule_id: str = "JL-02", refs=None) -> AuditFinding:
    return AuditFinding(
        finding_id="F-TEST",
        rule_id=rule_id,
        title="Test finding",
        status=status,
        severity=Severity.INFO,
        summary="Original engine explanation",
        exact_calculation="1 - 1 = 0",
        evidence_references=refs or [],
        human_verification_steps=["Inspect the source evidence"],
    )


def test_consistent_without_evidence_maps_to_unverified():
    finding = make_finding(FindingStatus.CONSISTENT)
    state, css = map_finding_display_state(finding, AuditBundle(work_id="W-1", work_name="Test"))
    assert state == "UNVERIFIED"
    assert css == "state-unverified"


def test_consistent_with_sufficient_jl02_evidence_maps_to_verified():
    ref = make_ref(EvidenceCategory.SANCTION_ORDER)
    finding = make_finding(FindingStatus.CONSISTENT, refs=[ref])
    bundle = AuditBundle(
        work_id="W-1",
        work_name="Test",
        sanction_data=SanctionEstimateData(
            original_sanction_amount=ExtractedField(
                field_name="sanction_amount",
                raw_value=Decimal("100"),
                reviewed_by_user=True,
                source=ref,
            ),
            evidence_references=[ref],
        ),
        bills=[
            BillVoucherRecord(
                bill_number="B-1",
                work_id="W-1",
                amount=Decimal("90"),
                evidence=ref,
            )
        ],
    )
    state, css = map_finding_display_state(finding, bundle)
    assert state == "VERIFIED"
    assert css == "state-verified"


def test_missing_never_upgrades_to_verified():
    finding = make_finding(FindingStatus.MISSING_EVIDENCE, refs=[make_ref()])
    before = finding.model_dump()
    assert map_finding_display_state(finding)[0] == "MISSING"
    assert finding.model_dump() == before


def test_inconsistent_never_upgrades_to_verified():
    finding = make_finding(FindingStatus.MISMATCH_FOUND)
    before = finding.model_dump()
    assert map_finding_display_state(finding)[0] == "INCONSISTENT"
    assert finding.model_dump() == before


def test_needs_human_review_maps_to_unverified():
    finding = make_finding(FindingStatus.NEEDS_HUMAN_REVIEW)
    before = finding.model_dump()
    assert map_finding_display_state(finding)[0] == "UNVERIFIED"
    assert finding.model_dump() == before


def test_consistent_jl01_without_complete_board_is_unverified():
    ref = make_ref(EvidenceCategory.JANATA_BOARD_PHOTO)
    finding = make_finding(FindingStatus.CONSISTENT, "JL-01", [ref])
    bundle = AuditBundle(
        work_id="W-1",
        work_name="Test",
        board_data=JanataBoardData(
            work_name=ExtractedField(field_name="work_name", raw_value="Test", reviewed_by_user=True),
            estimated_labour_days=ExtractedField(field_name="labour_days", raw_value=Decimal("10"), reviewed_by_user=True),
            material_entries=[
                MaterialEntry(local_name="Stone", quantity=Decimal("1"), item_cost=None)
            ],
            evidence_references=[ref],
        ),
    )
    assert map_finding_display_state(finding, bundle)[0] == "UNVERIFIED"


def test_original_finding_explanation_refs_and_actions_are_preserved():
    ref = make_ref()
    finding = make_finding(FindingStatus.CONSISTENT, refs=[ref])
    before = finding.model_dump()
    map_finding_display_state(finding)
    after = finding.model_dump()
    assert after == before
    assert after["summary"] == "Original engine explanation"
    assert after["evidence_references"][0]["evidence_id"] == "EV-TEST"
    assert after["human_verification_steps"] == ["Inspect the source evidence"]
