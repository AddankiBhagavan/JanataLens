"""Unit tests for Pydantic v2 schemas and validation logic."""

from datetime import date, datetime
from decimal import Decimal
import pytest
from pydantic import ValidationError

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
    RevisedSanction,
    RuleSource,
    SanctionEstimateData,
    Severity,
    StagePhotoEvidence,
    WeeklyDisclosureData,
)


def test_strict_finding_statuses():
    """Verify that only the exact 4 statuses are allowed."""
    assert FindingStatus.CONSISTENT.value == "CONSISTENT"
    assert FindingStatus.MISMATCH_FOUND.value == "MISMATCH_FOUND"
    assert FindingStatus.MISSING_EVIDENCE.value == "MISSING_EVIDENCE"
    assert FindingStatus.NEEDS_HUMAN_REVIEW.value == "NEEDS_HUMAN_REVIEW"

    # Attempting to assign an unsupported status must fail
    with pytest.raises(ValueError):
        FindingStatus("COMPLIANT")
    with pytest.raises(ValueError):
        FindingStatus("MISMATCH FOUND")


def test_evidence_reference_provenance():
    ref = EvidenceReference(
        evidence_id="ev_001",
        filename="sanction_order.pdf",
        evidence_type=EvidenceCategory.SANCTION_ORDER,
        sha256="a" * 64,
        file_size_bytes=1024,
        page_number=1,
        synthetic=True,
    )
    assert ref.evidence_id == "ev_001"
    assert ref.page_number == 1
    assert ref.synthetic is True


def test_evidence_reference_rejects_invalid_sha256():
    with pytest.raises(ValidationError):
        EvidenceReference(
            evidence_id="ev_invalid",
            filename="document.pdf",
            evidence_type=EvidenceCategory.SANCTION_ORDER,
            sha256="not-a-real-sha256",
            file_size_bytes=1024,
        )

    with pytest.raises(ValidationError):
        EvidenceReference(
            evidence_id="ev_short",
            filename="document.pdf",
            evidence_type=EvidenceCategory.SANCTION_ORDER,
            sha256="a" * 63,
            file_size_bytes=1024,
        )


def test_stage_photo_rejects_invalid_sha_and_perceptual_hash():
    with pytest.raises(ValidationError):
        StagePhotoEvidence(
            photo_id="PHOTO-INVALID",
            evidence_reference=EvidenceReference(
                evidence_id="ev_photo",
                filename="photo.jpg",
                evidence_type=EvidenceCategory.STAGE_PHOTO,
                sha256="a" * 64,
                file_size_bytes=100,
            ),
            declared_stage_label="Stage 1",
            declared_order=1,
            sha256="b" * 63,
        )

    with pytest.raises(ValidationError):
        StagePhotoEvidence(
            photo_id="PHOTO-INVALID-HASH",
            evidence_reference=EvidenceReference(
                evidence_id="ev_photo",
                filename="photo.jpg",
                evidence_type=EvidenceCategory.STAGE_PHOTO,
                sha256="a" * 64,
                file_size_bytes=100,
            ),
            declared_stage_label="Stage 1",
            declared_order=1,
            sha256="a" * 64,
            phash="not-hex",
        )


def test_extracted_field_calculation_eligibility():
    """Unreviewed or low-confidence fields cannot enter calculations unless confirmed or synthetic."""
    ref_real = EvidenceReference(
        evidence_id="ev_real",
        filename="board.jpg",
        evidence_type=EvidenceCategory.JANATA_BOARD_PHOTO,
        sha256="b" * 64,
        file_size_bytes=2048,
        synthetic=False,
    )
    
    # 1. Unreviewed real field -> Not eligible
    unreviewed = ExtractedField(
        field_name="total_cost",
        raw_value=Decimal("800000"),
        source=ref_real,
        extraction_status=ExtractionStatus.EXTRACTED_UNREVIEWED,
        reviewed_by_user=False,
    )
    assert unreviewed.is_eligible_for_calculation() is False

    # 2. Confirmed by user -> Eligible
    confirmed = ExtractedField(
        field_name="total_cost",
        raw_value=Decimal("800000"),
        source=ref_real,
        extraction_status=ExtractionStatus.USER_CONFIRMED,
        reviewed_by_user=True,
    )
    assert confirmed.is_eligible_for_calculation() is True

    # 3. User corrected -> Eligible and gets effective value
    corrected = ExtractedField(
        field_name="total_cost",
        raw_value=Decimal("800000"),
        normalised_value=Decimal("850000"),
        source=ref_real,
        extraction_status=ExtractionStatus.USER_CORRECTED,
        reviewed_by_user=True,
    )
    assert corrected.is_eligible_for_calculation() is True
    assert corrected.get_effective_value() == Decimal("850000")


def test_confidence_validation():
    ref = EvidenceReference(
        evidence_id="ev_01",
        filename="doc.pdf",
        evidence_type=EvidenceCategory.ESTIMATE_OR_BOQ,
        sha256="c" * 64,
        file_size_bytes=100,
    )
    # Valid confidence
    f = ExtractedField(field_name="test", source=ref, confidence=0.85)
    assert f.confidence == 0.85

    # Out of range confidence must fail
    with pytest.raises(ValidationError):
        ExtractedField(field_name="test", source=ref, confidence=1.5)
    with pytest.raises(ValidationError):
        ExtractedField(field_name="test", source=ref, confidence=-0.1)


def test_decimal_monetary_accuracy():
    """Verify that calculations preserve Decimal precision without floating point inaccuracies."""
    sanction_amt = Decimal("800000.00")
    bill_amt = Decimal("920000.00")
    diff = bill_amt - sanction_amt
    assert diff == Decimal("120000.00")
    assert str(diff) == "120000.00"


def test_audit_finding_model():
    finding = AuditFinding(
        finding_id="F-001",
        rule_id="JL-02",
        title="Sanction versus Expenditure Comparison",
        status=FindingStatus.MISMATCH_FOUND,
        severity=Severity.HIGH,
        summary="Cumulative bills exceed sanctioned amount by ₹1,20,000.00.",
        observed_values={"sanction_amount": "800000.00", "bill_total": "920000.00"},
        exact_calculation="920000.00 - 800000.00 = 120000.00",
        human_verification_steps=[
            "Check whether a revised sanction order exists for this work.",
            "Verify whether any bills belong to a different phase or separate sanction.",
        ],
    )
    assert finding.status == FindingStatus.MISMATCH_FOUND
    assert finding.severity == Severity.HIGH
    assert finding.exact_calculation == "920000.00 - 800000.00 = 120000.00"
