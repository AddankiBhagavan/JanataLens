"""Tests for document extractor, file validation, and synthetic bundle intake."""

from decimal import Decimal
from pathlib import Path
import pytest

from src.document_extractor import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    load_synthetic_bundle,
    parse_bills_csv,
    parse_labour_csv,
    parse_weekly_disclosure_csv,
    validate_demo_mode_intake,
    validate_file_intake,
    validate_upload_content,
    extract_text_from_pdf,
)
from src.sample_generator import generate_all_cases


@pytest.fixture(scope="session")
def generated_samples():
    """Ensures sample cases are generated before running tests."""
    return generate_all_cases()


def test_file_validation_rules():
    # Valid PDF
    valid, err = validate_file_intake("sanction.pdf", b"%PDF-1.4 dummy", current_session_bytes=0)
    assert valid is True
    assert err is None

    # Invalid extension (.exe)
    valid, err = validate_file_intake("malware.exe", b"binary", current_session_bytes=0)
    assert valid is False
    assert "Unsupported format" in err

    # Oversized file (> 15MB)
    oversized = b"0" * (MAX_FILE_SIZE_BYTES + 10)
    valid, err = validate_file_intake("big.pdf", oversized, current_session_bytes=0)
    assert valid is False
    assert "exceeds maximum allowed size" in err

    valid, err = validate_file_intake("../private/sanction.pdf", b"%PDF-1.4 dummy")
    assert valid is False
    assert "path separators" in err


def test_unreadable_pdf_returns_clear_error():
    with pytest.raises(ValueError, match="Unreadable PDF"):
        extract_text_from_pdf(b"not a pdf", "broken.pdf")


def test_invalid_bill_amount_is_rejected():
    csv_content = (
        b"bill_no,work_id,vendor,bill_date,amount,category\n"
        b"INV-01,W-101,Sri Crushers,2026-07-20,NaN,material\n"
    )
    with pytest.raises(ValueError, match="finite numeric"):
        parse_bills_csv(csv_content, "bills.csv", synthetic=True)


def test_negative_bill_amount_is_rejected():
    csv_content = (
        b"bill_no,work_id,vendor,bill_date,amount,category\n"
        b"INV-01,W-101,Sri Crushers,2026-07-20,-10.00,material\n"
    )
    with pytest.raises(ValueError, match="must not be negative"):
        parse_bills_csv(csv_content, "bills.csv", synthetic=True)


def test_negative_wage_amount_is_rejected():
    csv_content = (
        b"work_id,worker_ref,work_start,work_end,muster_ref,muster_closed,wage_due,fto_date,credit_date\n"
        b"W-101,WRK-001,2026-07-01,2026-07-07,MR-1,2026-07-08,-2100.00,2026-07-10,2026-07-15\n"
    )
    with pytest.raises(ValueError, match="must not be negative"):
        parse_labour_csv(csv_content, "labour.csv", synthetic=True)


def test_invalid_progress_percent_is_rejected():
    csv_content = (
        b"work_id,week_ending,person_days,wages_disbursed,material_spent,progress_percent\n"
        b"W-101,2026-07-12,10,2100.00,500.00,101\n"
    )
    from src.document_extractor import parse_weekly_disclosure_csv
    with pytest.raises(ValueError, match="between 0 and 100"):
        parse_weekly_disclosure_csv(csv_content, "weekly.csv", synthetic=True)


def test_upload_content_validation_rejects_mismatched_and_empty_files(tmp_path):
    valid, error = validate_upload_content("document.pdf", b"not pdf")
    assert valid is False
    assert "valid PDF" in error

    valid, error = validate_upload_content("photo.jpg", b"not an image")
    assert valid is False
    assert "unreadable" in error.lower()

    valid, error = validate_upload_content("empty.csv", b"")
    assert valid is False
    assert "empty" in error.lower()


def test_parse_bills_csv():
    csv_content = (
        b"bill_no,work_id,vendor,bill_date,amount,category\n"
        b"INV-01,W-101,Sri Crushers,2026-07-20,150000.00,material\n"
    )
    bills = parse_bills_csv(csv_content, "bills.csv", synthetic=True)
    assert len(bills) == 1
    assert bills[0].bill_number == "INV-01"
    assert bills[0].amount == Decimal("150000.00")
    assert bills[0].evidence.row_number == 2


def test_parse_labour_csv():
    csv_content = (
        b"work_id,worker_ref,work_start,work_end,muster_ref,muster_closed,wage_due,fto_date,credit_date\n"
        b"W-101,WRK-001,2026-07-01,2026-07-07,MR-1,2026-07-08,2100.00,2026-07-10,2026-07-15\n"
    )
    records = parse_labour_csv(csv_content, "labour.csv", synthetic=True)
    assert len(records) == 1
    assert records[0].worker_ref == "WRK-001"
    assert records[0].wage_amount_due == Decimal("2100.00")
    assert records[0].actual_credit_date is not None


def test_load_all_synthetic_cases(generated_samples):
    """Verifies that all three generated bundles load into AuditBundle models."""
    for case_key, case_path in generated_samples.items():
        bundle = load_synthetic_bundle(case_path)
        assert bundle.synthetic is True
        assert len(bundle.evidence_files) >= 4
        assert bundle.board_data is not None
        assert bundle.sanction_data is not None
        assert len(bundle.stage_photos) == 3


def test_demo_mode_rejects_uploads():
    allowed, error = validate_demo_mode_intake("demo", "private.pdf")
    assert allowed is False
    assert "Uploads are disabled" in error
    assert "synthetic" in error.lower()

    allowed, error = validate_demo_mode_intake("local", "audit.pdf")
    assert allowed is True
    assert error is None
