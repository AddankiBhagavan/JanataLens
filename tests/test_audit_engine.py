"""Unit tests for deterministic audit engine (JL-01 to JL-05 and linkage gate)."""

from datetime import date, datetime
from decimal import Decimal
import pytest

from src.audit_engine import (
    audit_jl01_board_completeness,
    audit_jl02_financial_reconciliation,
    audit_jl03_labour_timeline,
    audit_jl04_chronological_integrity,
    audit_jl05_photo_reuse,
    run_full_audit,
    validate_work_linkage,
)
from src.schemas import (
    AuditBundle,
    BillVoucherRecord,
    EvidenceCategory,
    EvidenceReference,
    ExtractedField,
    ExtractionStatus,
    FindingStatus,
    JanataBoardData,
    LabourPaymentRecord,
    MaterialEntry,
    RevisedSanction,
    SanctionEstimateData,
    Severity,
    StagePhotoEvidence,
)


@pytest.fixture
def dummy_evidence_ref():
    return EvidenceReference(
        evidence_id="ev_test",
        filename="test_file.pdf",
        evidence_type=EvidenceCategory.SANCTION_ORDER,
        sha256="a" * 64,
        file_size_bytes=1024,
        synthetic=True,
    )


def test_work_linkage_gate_pass(dummy_evidence_ref):
    bundle = AuditBundle(
        work_id="WRK-101",
        work_name="Gram Panchayat Road Concreting",
        synthetic=True,
        board_data=JanataBoardData(
            work_id=ExtractedField(field_name="work_id", raw_value="WRK-101", reviewed_by_user=True),
        ),
        sanction_data=SanctionEstimateData(
            work_id=ExtractedField(field_name="work_id", raw_value="WRK-101", reviewed_by_user=True),
        ),
    )
    is_linked, details = validate_work_linkage(bundle)
    assert is_linked is True
    assert details["status"] == "LINKAGE_VERIFIED"


def test_work_linkage_gate_conflict(dummy_evidence_ref):
    bundle = AuditBundle(
        work_id="WRK-101",
        work_name="Gram Panchayat Road Concreting",
        synthetic=True,
        board_data=JanataBoardData(
            work_id=ExtractedField(field_name="work_id", raw_value="WRK-999", reviewed_by_user=True),
        ),
    )
    is_linked, details = validate_work_linkage(bundle)
    assert is_linked is False
    assert details["status"] == "CONFLICT_DETECTED"

    # Full audit must stop and emit human review gate finding
    report = run_full_audit(bundle)
    assert report.overall_review_state == "NEEDS_HUMAN_REVIEW"
    assert report.findings[0].rule_id == "GATE"
    assert "JL-01" in report.rule_execution_summary["rules_skipped"]


def test_jl01_board_completeness_pass(dummy_evidence_ref):
    board = JanataBoardData(
        work_name=ExtractedField(field_name="work_name", raw_value="Check Dam Construction", reviewed_by_user=True),
        estimated_labour_days=ExtractedField(field_name="labour_days", raw_value=Decimal("450"), reviewed_by_user=True),
        material_entries=[
            MaterialEntry(local_name="Cement (Bags)", quantity=Decimal("100"), item_cost=Decimal("38000.00")),
            MaterialEntry(local_name="Sand (Cu.m)", quantity=Decimal("20"), item_cost=Decimal("15000.00")),
        ],
        evidence_references=[dummy_evidence_ref],
    )
    bundle = AuditBundle(work_id="W-1", work_name="Test", board_data=board, synthetic=True)
    finding = audit_jl01_board_completeness(bundle)
    assert finding.status == FindingStatus.CONSISTENT
    assert finding.rule_id == "JL-01"


def test_jl01_board_completeness_missing_item_cost(dummy_evidence_ref):
    board = JanataBoardData(
        work_name=ExtractedField(field_name="work_name", raw_value="Check Dam Construction", reviewed_by_user=True),
        estimated_labour_days=ExtractedField(field_name="labour_days", raw_value=Decimal("450"), reviewed_by_user=True),
        material_entries=[
            # Missing item_cost
            MaterialEntry(local_name="Cement (Bags)", quantity=Decimal("100"), item_cost=None),
        ],
        evidence_references=[dummy_evidence_ref],
    )
    bundle = AuditBundle(work_id="W-1", work_name="Test", board_data=board, synthetic=True)
    finding = audit_jl01_board_completeness(bundle)
    assert finding.status == FindingStatus.MISSING_EVIDENCE
    assert "Item-wise cost breakdown missing" in finding.summary


def test_jl02_financial_reconciliation_case2_cost_mismatch(dummy_evidence_ref):
    """Case 2 requirement: Sanction = ₹8,00,000, Bills = ₹9,20,000 -> ₹1,20,000 difference."""
    sanction = SanctionEstimateData(
        work_id=ExtractedField(field_name="work_id", raw_value="CASE-2", reviewed_by_user=True),
        original_sanction_amount=ExtractedField(
            field_name="sanction_amt", raw_value=Decimal("800000.00"), reviewed_by_user=True
        ),
        evidence_references=[dummy_evidence_ref],
    )
    bills = [
        BillVoucherRecord(
            bill_number="BILL-001",
            work_id="CASE-2",
            bill_date=date(2026, 8, 10),
            amount=Decimal("500000.00"),
            evidence=dummy_evidence_ref,
        ),
        BillVoucherRecord(
            bill_number="BILL-002",
            work_id="CASE-2",
            bill_date=date(2026, 8, 20),
            amount=Decimal("420000.00"),
            evidence=dummy_evidence_ref,
        ),
    ]
    bundle = AuditBundle(
        work_id="CASE-2",
        work_name="Community Tank Desiltation",
        sanction_data=sanction,
        bills=bills,
        synthetic=True,
    )
    findings = audit_jl02_financial_reconciliation(bundle)
    assert len(findings) >= 1
    f = findings[0]
    assert f.status == FindingStatus.MISMATCH_FOUND
    assert f.severity == Severity.HIGH
    assert f.observed_values["difference"] == "120000.00"
    assert "₹920,000.00 - ₹800,000.00 = ₹120,000.00" in (f.exact_calculation or "")


def test_jl02_financial_reconciliation_with_revised_sanction(dummy_evidence_ref):
    """When a revised sanction of ₹9,50,000 is present, ₹9,20,000 expenditure is consistent."""
    sanction = SanctionEstimateData(
        work_id=ExtractedField(field_name="work_id", raw_value="W-REV", reviewed_by_user=True),
        original_sanction_amount=ExtractedField(
            field_name="sanction_amt", raw_value=Decimal("800000.00"), reviewed_by_user=True
        ),
        revised_sanctions=[
            RevisedSanction(
                revised_order_number="REV-01",
                revised_date=date(2026, 8, 15),
                revised_amount=Decimal("950000.00"),
                scope_change="Additional canal lining",
                evidence=dummy_evidence_ref,
            )
        ],
        evidence_references=[dummy_evidence_ref],
    )
    bills = [
        BillVoucherRecord(
            bill_number="BILL-01",
            work_id="W-REV",
            amount=Decimal("920000.00"),
            evidence=dummy_evidence_ref,
        ),
    ]
    bundle = AuditBundle(work_id="W-REV", work_name="Canal Work", sanction_data=sanction, bills=bills, synthetic=True)
    findings = audit_jl02_financial_reconciliation(bundle)
    assert findings[0].status == FindingStatus.CONSISTENT


def test_jl03_labour_and_delay_compensation(dummy_evidence_ref):
    # Worker 1: Paid within 10 days of work end and 10 days of muster closure -> CONSISTENT
    rec1 = LabourPaymentRecord(
        work_id="W-LAB",
        worker_ref="WRK-001",
        work_start_date=date(2026, 7, 1),
        work_end_date=date(2026, 7, 7),
        muster_closure_date=date(2026, 7, 8),
        wage_amount_due=Decimal("2800.00"),
        actual_credit_date=date(2026, 7, 15),
        evidence=dummy_evidence_ref,
    )
    # Worker 2: Paid 25 days after muster closure (10 days delay beyond 15-day limit)
    # Delay comp: 2800 * 0.05% * 10 = 2800 * 0.0005 * 10 = ₹14.00
    rec2 = LabourPaymentRecord(
        work_id="W-LAB",
        worker_ref="WRK-002",
        work_start_date=date(2026, 7, 1),
        work_end_date=date(2026, 7, 7),
        muster_closure_date=date(2026, 7, 8),
        wage_amount_due=Decimal("2800.00"),
        actual_credit_date=date(2026, 8, 2),  # 25 days after closure
        evidence=dummy_evidence_ref,
    )
    bundle = AuditBundle(work_id="W-LAB", work_name="Test", labour_records=[rec1, rec2], synthetic=True)
    findings = audit_jl03_labour_timeline(bundle)

    # Worker 1 checks
    assert any(f.status == FindingStatus.CONSISTENT and "WRK-001" in f.title for f in findings)

    # Worker 2 delay comp check
    comp_finding = next(f for f in findings if "Delay Compensation" in f.title and "WRK-002" in f.title)
    assert comp_finding.status == FindingStatus.NEEDS_HUMAN_REVIEW
    assert comp_finding.observed_values["calculated_compensation"] == "14.00"
    assert "₹14.00" in comp_finding.summary


def test_jl04_chronological_integrity_pre_sanction_bill(dummy_evidence_ref):
    """Case 3 requirement: Bill dated prior to sanction order date."""
    sanction = SanctionEstimateData(
        work_id=ExtractedField(field_name="work_id", raw_value="CASE-3", reviewed_by_user=True),
        original_sanction_date=ExtractedField(
            field_name="sanction_date", raw_value=date(2026, 7, 15), reviewed_by_user=True
        ),
        original_sanction_amount=ExtractedField(
            field_name="amount", raw_value=Decimal("500000.00"), reviewed_by_user=True
        ),
        evidence_references=[dummy_evidence_ref],
    )
    # Pre-sanction bill dated 2026-06-20
    bills = [
        BillVoucherRecord(
            bill_number="BILL-PRE",
            work_id="CASE-3",
            bill_date=date(2026, 6, 20),
            amount=Decimal("50000.00"),
            evidence=dummy_evidence_ref,
        )
    ]
    bundle = AuditBundle(work_id="CASE-3", work_name="Pond", sanction_data=sanction, bills=bills, synthetic=True)
    findings = audit_jl04_chronological_integrity(bundle)
    assert len(findings) >= 1
    assert findings[0].status == FindingStatus.NEEDS_HUMAN_REVIEW
    assert "Bills Dated Prior to Administrative Sanction Date" in findings[0].title


def test_jl05_photo_reuse_detection(dummy_evidence_ref):
    """Case 3 requirement: Potential image reuse across stages."""
    p1 = StagePhotoEvidence(
        photo_id="PH-1",
        evidence_reference=dummy_evidence_ref,
        declared_stage_label="Stage 1: Excavation",
        declared_order=1,
        sha256="b" * 64,
        phash="ffff0000ffff0000",
        dhash="aaaa0000aaaa0000",
    )
    # P3 has close perceptual hash to P1 (Hamming dist <= 8)
    p3 = StagePhotoEvidence(
        photo_id="PH-3",
        evidence_reference=dummy_evidence_ref,
        declared_stage_label="Stage 3: Completion",
        declared_order=3,
        sha256="c" * 64,
        phash="ffff0000ffff0001",  # 1 bit difference
        dhash="aaaa0000aaaa0000",  # 0 bit difference
    )
    bundle = AuditBundle(work_id="CASE-3", work_name="Test", stage_photos=[p1, p3], synthetic=True)
    findings = audit_jl05_photo_reuse(bundle)
    assert len(findings) >= 1
    assert findings[0].status == FindingStatus.NEEDS_HUMAN_REVIEW
    assert "Potential Stage Photograph Reuse" in findings[0].title


def test_stage_photo_reference_must_belong_to_bundle(dummy_evidence_ref):
    foreign_ref = EvidenceReference(
        evidence_id="EV-FOREIGN",
        filename="stage_1_initial.jpg",
        evidence_type=EvidenceCategory.STAGE_PHOTO,
        sha256="d" * 64,
        file_size_bytes=100,
        synthetic=True,
    )
    photo = StagePhotoEvidence(
        photo_id="PHOTO-FOREIGN",
        evidence_reference=foreign_ref,
        declared_stage_label="Stage 1: Initial",
        declared_order=1,
        sha256="d" * 64,
    )
    bundle = AuditBundle(
        work_id="WRK-CASE-A",
        work_name="Case A",
        evidence_files=[dummy_evidence_ref],
        stage_photos=[photo],
        synthetic=True,
    )
    linked, details = validate_work_linkage(bundle)
    assert linked is False
    assert "not owned or referenced" in " ".join(details["conflicts"])


def test_missing_and_conflicting_financial_evidence_stays_unverified(dummy_evidence_ref):
    sanction = SanctionEstimateData(
        work_id=ExtractedField(field_name="work_id", raw_value="CASE-X", reviewed_by_user=True),
        original_sanction_amount=ExtractedField(
            field_name="sanction_amount",
            raw_value=Decimal("800000"),
            extraction_status=ExtractionStatus.EXTRACTED_UNREVIEWED,
            source=dummy_evidence_ref,
        ),
        evidence_references=[dummy_evidence_ref],
    )
    bundle = AuditBundle(
        work_id="CASE-X",
        work_name="Incomplete Case",
        sanction_data=sanction,
        bills=[
            BillVoucherRecord(
                bill_number="BILL-NO-SOURCE",
                work_id="OTHER-WORK",
                amount=Decimal("900000"),
            )
        ],
        synthetic=False,
    )
    findings = audit_jl02_financial_reconciliation(bundle)
    assert findings[0].status == FindingStatus.MISSING_EVIDENCE
    assert "not been confirmed" in findings[0].summary
