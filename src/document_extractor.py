"""Document extraction, file validation, and bundle intake for JanataLens AI.

Parses:
- Text PDFs using PyMuPDF with page provenance
- CSV tabular disclosures (Weekly disclosures, Bills/Vouchers, Labour records)
- JPG/PNG images with SHA-256 and size validation
- Programmatic synthetic bundles
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import pymupdf  # PyMuPDF
from decimal import InvalidOperation

from src.schemas import (
    AuditBundle,
    BillVoucherRecord,
    EvidenceCategory,
    EvidenceReference,
    ExtractedField,
    ExtractionStatus,
    JanataBoardData,
    LabourPaymentRecord,
    MaterialEntry,
    RevisedSanction,
    SanctionEstimateData,
    StagePhotoEvidence,
    WeeklyDisclosureData,
)
from src.vision_forensics import compute_sha256, inspect_stage_photo

# Limits
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_SESSION_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".pdf", ".csv", ".jpg", ".jpeg", ".png"}


def _parse_finite_decimal(value: Any, field_name: str, allow_missing: bool = False) -> Optional[Decimal]:
    """Parses a monetary or numeric CSV value without permitting NaN or infinity."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        if allow_missing:
            return None
        raise ValueError(f"{field_name} is missing or must be a finite numeric value")
    try:
        parsed = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        if allow_missing:
            return None
        raise ValueError(f"{field_name} is not a valid numeric value")
    if not parsed.is_finite():
        if allow_missing:
            return None
        raise ValueError(f"{field_name} must be a finite numeric value")
    return parsed


def validate_demo_mode_intake(
    mode: str,
    filename: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Rejects user-upload intake in demo/public mode at the application boundary."""
    if str(mode).strip().lower() == "demo":
        name = f" '{filename}'" if filename else ""
        return False, (
            f"Uploads are disabled in demo mode{name}. "
            "Load a synthetic demonstration case instead. "
            "SYNTHETIC DEMO DATA — NOT AN OFFICIAL GOVERNMENT RECORD."
        )
    return True, None


def validate_file_intake(
    filename: str,
    file_bytes: bytes,
    current_session_bytes: int = 0,
) -> Tuple[bool, Optional[str]]:
    """Validates file extension, individual size limit, and total session size limit."""
    if not filename or "\x00" in filename or "/" in filename or "\\" in filename:
        return False, "Invalid filename. Upload a plain file name without path separators."
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"

    size = len(file_bytes)
    if size > MAX_FILE_SIZE_BYTES:
        return False, f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB."

    if current_session_bytes + size > MAX_SESSION_SIZE_BYTES:
        return False, f"Upload exceeds total session storage limit of {MAX_SESSION_SIZE_BYTES // (1024*1024)} MB."

    return True, None


def validate_upload_content(filename: str, file_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """Performs lightweight content validation in addition to extension checks."""
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        if not file_bytes.startswith(b"%PDF-"):
            return False, "The selected file is not a valid PDF document."
        try:
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            doc.close()
        except Exception:
            return False, "The selected PDF is unreadable or corrupted."
        return True, None

    if ext in {".jpg", ".jpeg", ".png"}:
        try:
            from PIL import Image
            with Image.open(io.BytesIO(file_bytes)) as image:
                image.verify()
        except Exception:
            return False, "The selected image is unreadable or corrupted."
        return True, None

    if ext == ".csv":
        try:
            text = file_bytes.decode("utf-8-sig")
            if not text.strip():
                return False, "The selected CSV is empty."
            if "," not in text and "\t" not in text:
                return False, "The selected CSV does not contain recognizable column data."
        except UnicodeDecodeError:
            return False, "The selected CSV is not valid UTF-8 text."
        return True, None

    return False, f"Unsupported format '{ext}'."


def extract_text_from_pdf(pdf_bytes: bytes, filename: str = "document.pdf") -> List[Dict[str, Any]]:
    """Extracts text per page from a PDF with provenance tracking."""
    pages_data = []
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError(f"Unreadable PDF document '{filename}'") from exc
    sha256_hash = hashlib.sha256(pdf_bytes).hexdigest()

    try:
        for idx, page in enumerate(doc, start=1):
            text = page.get_text()
            pages_data.append({
                "page_number": idx,
                "text": text,
                "char_count": len(text),
                "filename": filename,
                "sha256": sha256_hash,
                "file_size_bytes": len(pdf_bytes),
            })
    except Exception as exc:
        raise ValueError(f"Could not extract text from PDF '{filename}'") from exc
    finally:
        doc.close()
    return pages_data


def parse_sanction_pdf(pdf_bytes: bytes, filename: str = "sanction_order.pdf", synthetic: bool = False) -> SanctionEstimateData:
    """Parses candidate fields from administrative sanction order PDF."""
    pages = extract_text_from_pdf(pdf_bytes, filename)
    full_text = "\n".join(p["text"] for p in pages)
    sha256_hash = hashlib.sha256(pdf_bytes).hexdigest()

    ev_ref = EvidenceReference(
        evidence_id=f"EV-SANC-{sha256_hash[:8]}",
        filename=filename,
        evidence_type=EvidenceCategory.SANCTION_ORDER,
        sha256=sha256_hash,
        file_size_bytes=len(pdf_bytes),
        page_number=1,
        synthetic=synthetic,
    )

    # Regex extraction heuristics
    work_id_m = re.search(r"Work Identity / Project Code:\s*([^\n\r]+)", full_text, re.IGNORECASE)
    order_no_m = re.search(r"Order Reference:\s*([^\n\r]+)", full_text, re.IGNORECASE)
    date_m = re.search(r"Date of Sanction:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", full_text, re.IGNORECASE)
    amount_m = re.search(r"Total Sanctioned Monetary Ceiling:\s*[^\d]*([0-9,]+(?:\.[0-9]{2})?)", full_text, re.IGNORECASE)
    work_title_m = re.search(r"Approved Scheme Work:\s*([^\n\r]+)", full_text, re.IGNORECASE)

    work_id_val = work_id_m.group(1).strip() if work_id_m else None
    order_no_val = order_no_m.group(1).strip() if order_no_m else None
    title_val = work_title_m.group(1).strip() if work_title_m else None

    sanc_date = None
    if date_m:
        try:
            sanc_date = datetime.strptime(date_m.group(1), "%Y-%m-%d").date()
        except Exception:
            pass

    sanc_amount = None
    if amount_m:
        clean_amt = amount_m.group(1).replace(",", "")
        try:
            sanc_amount = Decimal(clean_amt)
        except Exception:
            pass

    # Status: Pre-confirmed if synthetic fixture, otherwise unreviewed
    status = ExtractionStatus.USER_CONFIRMED if synthetic else ExtractionStatus.EXTRACTED_UNREVIEWED

    return SanctionEstimateData(
        work_id=ExtractedField(
            field_name="work_id",
            raw_value=work_id_val,
            source=ev_ref,
            extraction_method="pymupdf_text",
            extraction_status=status,
            reviewed_by_user=synthetic,
        ) if work_id_val else None,
        work_name=ExtractedField(
            field_name="work_name",
            raw_value=title_val,
            source=ev_ref,
            extraction_method="pymupdf_text",
            extraction_status=status,
            reviewed_by_user=synthetic,
        ) if title_val else None,
        sanction_order_number=ExtractedField(
            field_name="order_no",
            raw_value=order_no_val,
            source=ev_ref,
            extraction_method="pymupdf_text",
            extraction_status=status,
            reviewed_by_user=synthetic,
        ) if order_no_val else None,
        original_sanction_date=ExtractedField(
            field_name="sanction_date",
            raw_value=sanc_date,
            source=ev_ref,
            extraction_method="pymupdf_text",
            extraction_status=status,
            reviewed_by_user=synthetic,
        ) if sanc_date else None,
        original_sanction_amount=ExtractedField(
            field_name="sanction_amount",
            raw_value=sanc_amount,
            source=ev_ref,
            extraction_method="pymupdf_text",
            extraction_status=status,
            reviewed_by_user=synthetic,
        ) if sanc_amount else None,
        evidence_references=[ev_ref],
    )


def parse_bills_csv(csv_bytes: bytes, filename: str = "bills.csv", synthetic: bool = False) -> List[BillVoucherRecord]:
    """Parses a bills and vouchers CSV."""
    df = pd.read_csv(io.BytesIO(csv_bytes))
    sha256_hash = hashlib.sha256(csv_bytes).hexdigest()
    records = []

    for idx, row in df.iterrows():
        b_no = str(row.get("bill_no", f"BILL-{idx+1}")).strip()
        w_id = str(row.get("work_id", "")).strip() or None
        vendor = str(row.get("vendor", "")).strip() or None
        cat = str(row.get("category", "material")).strip() or "material"

        b_date = None
        raw_date = row.get("bill_date")
        if pd.notna(raw_date):
            try:
                b_date = datetime.strptime(str(raw_date).strip(), "%Y-%m-%d").date()
            except Exception:
                pass

        amt_val = _parse_finite_decimal(row.get("amount"), "Bill amount")
        if amt_val is not None and amt_val < Decimal("0"):
            raise ValueError("Bill amount must not be negative")

        ev_ref = EvidenceReference(
            evidence_id=f"EV-BILL-{sha256_hash[:6]}-{idx+1}",
            filename=filename,
            evidence_type=EvidenceCategory.BILL_OR_VOUCHER,
            sha256=sha256_hash,
            file_size_bytes=len(csv_bytes),
            row_number=int(idx) + 2,  # 1-indexed, skipping header
            text_excerpt=f"Bill {b_no}, Vendor: {vendor}, Amount: ₹{amt_val}",
            synthetic=synthetic,
        )

        records.append(
            BillVoucherRecord(
                bill_number=b_no,
                work_id=w_id,
                vendor_or_payee=vendor,
                bill_date=b_date,
                amount=amt_val,
                cost_category=cat,
                evidence=ev_ref,
            )
        )
    return records


def parse_labour_csv(csv_bytes: bytes, filename: str = "labour.csv", synthetic: bool = False) -> List[LabourPaymentRecord]:
    """Parses pseudonymous labour payment CSV records."""
    df = pd.read_csv(io.BytesIO(csv_bytes))
    sha256_hash = hashlib.sha256(csv_bytes).hexdigest()
    records = []

    for idx, row in df.iterrows():
        w_id = str(row.get("work_id", "")).strip()
        w_ref = str(row.get("worker_ref", f"WRK-{idx+1}")).strip()
        m_ref = str(row.get("muster_ref", "")).strip() or None
        wage_due = _parse_finite_decimal(row.get("wage_due"), "Wage amount due")
        if wage_due is not None and wage_due < Decimal("0"):
            raise ValueError("Wage amount due must not be negative")

        def _parse_d(col_name: str) -> Optional[date]:
            val = row.get(col_name)
            if pd.notna(val):
                try:
                    return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
                except Exception:
                    pass
            return None

        w_start = _parse_d("work_start")
        w_end = _parse_d("work_end")
        m_closed = _parse_d("muster_closed")
        fto_d = _parse_d("fto_date")
        cred_d = _parse_d("credit_date")

        ev_ref = EvidenceReference(
            evidence_id=f"EV-LAB-{sha256_hash[:6]}-{idx+1}",
            filename=filename,
            evidence_type=EvidenceCategory.WAGE_PAYMENT_RECORD,
            sha256=sha256_hash,
            file_size_bytes=len(csv_bytes),
            row_number=int(idx) + 2,
            text_excerpt=f"Worker {w_ref}, Wage: ₹{wage_due}, Credit: {cred_d}",
            synthetic=synthetic,
        )

        records.append(
            LabourPaymentRecord(
                work_id=w_id,
                worker_ref=w_ref,
                work_start_date=w_start,
                work_end_date=w_end,
                muster_roll_ref=m_ref,
                muster_closure_date=m_closed,
                wage_amount_due=wage_due,
                fto_processing_date=fto_d,
                actual_credit_date=cred_d,
                evidence=ev_ref,
            )
        )
    return records


def parse_weekly_disclosure_csv(
    csv_bytes: bytes, filename: str = "weekly_disclosure.csv", synthetic: bool = False
) -> List[WeeklyDisclosureData]:
    """Parses weekly disclosure CSV table."""
    df = pd.read_csv(io.BytesIO(csv_bytes))
    sha256_hash = hashlib.sha256(csv_bytes).hexdigest()
    records = []

    for idx, row in df.iterrows():
        w_id = str(row.get("work_id", "")).strip()
        raw_end = row.get("week_ending")
        p_end = None
        if pd.notna(raw_end):
            try:
                p_end = datetime.strptime(str(raw_end).strip(), "%Y-%m-%d").date()
            except Exception:
                pass

        p_days = _parse_finite_decimal(row.get("person_days"), "Person-days", allow_missing=True)
        wage_tot = _parse_finite_decimal(row.get("wages_disbursed"), "Wages disbursed", allow_missing=True)
        mat_tot = _parse_finite_decimal(row.get("material_spent"), "Material spend", allow_missing=True)
        prog_pct = _parse_finite_decimal(row.get("progress_percent"), "Progress percent", allow_missing=True)
        if p_days is not None and p_days < Decimal("0"):
            raise ValueError("Person-days must not be negative")
        if wage_tot is not None and wage_tot < Decimal("0"):
            raise ValueError("Wages disbursed must not be negative")
        if mat_tot is not None and mat_tot < Decimal("0"):
            raise ValueError("Material spend must not be negative")
        if prog_pct is not None and not (Decimal("0") <= prog_pct <= Decimal("100")):
            raise ValueError("Progress percent must be between 0 and 100")

        ev_ref = EvidenceReference(
            evidence_id=f"EV-DISC-{sha256_hash[:6]}-{idx+1}",
            filename=filename,
            evidence_type=EvidenceCategory.WEEKLY_DISCLOSURE,
            sha256=sha256_hash,
            file_size_bytes=len(csv_bytes),
            row_number=int(idx) + 2,
            synthetic=synthetic,
        )

        records.append(
            WeeklyDisclosureData(
                work_id=ExtractedField(
                    field_name="work_id",
                    raw_value=w_id,
                    source=ev_ref,
                    extraction_method="csv_parser",
                    extraction_status=ExtractionStatus.USER_CONFIRMED if synthetic else ExtractionStatus.EXTRACTED_UNREVIEWED,
                    reviewed_by_user=synthetic,
                ),
                period_end=p_end,
                person_days_aggregate=p_days,
                wage_amount_aggregate=wage_tot,
                material_amount_aggregate=mat_tot,
                physical_progress_percent=prog_pct,
                evidence_references=[ev_ref],
            )
        )
    return records


# ---------------------------------------------------------------------------
# Synthetic Case Loader
# ---------------------------------------------------------------------------

def load_synthetic_bundle(case_dir_path: Path | str) -> AuditBundle:
    """Loads a generated synthetic case directory into a verified AuditBundle."""
    case_path = Path(case_dir_path)
    if not case_path.exists():
        raise FileNotFoundError(f"Case directory {case_dir_path} does not exist.")

    case_name = case_path.name
    files_in_dir = list(case_path.iterdir())
    evidence_files: List[EvidenceReference] = []

    # 1. Sanction PDF
    sanc_file = case_path / "sanction_order.pdf"
    sanction_data = None
    if sanc_file.exists():
        with open(sanc_file, "rb") as f:
            pdf_bytes = f.read()
        sanction_data = parse_sanction_pdf(pdf_bytes, filename=sanc_file.name, synthetic=True)
        evidence_files.extend(sanction_data.evidence_references)

    # 2. Janata Board Photo
    board_file = case_path / "janata_board.jpg"
    board_data = None
    if board_file.exists():
        b_sha = compute_sha256(board_file)
        b_size = board_file.stat().st_size
        ev_board = EvidenceReference(
            evidence_id=f"EV-BOARD-{b_sha[:8]}",
            filename=board_file.name,
            evidence_type=EvidenceCategory.JANATA_BOARD_PHOTO,
            sha256=b_sha,
            file_size_bytes=b_size,
            synthetic=True,
        )
        evidence_files.append(ev_board)

        # Populate case-specific synthetic board fields
        if "case_1" in case_name:
            board_data = JanataBoardData(
                work_id=ExtractedField(field_name="work_id", raw_value="WRK-AP-2026-00101", source=ev_board, reviewed_by_user=True),
                work_name=ExtractedField(field_name="work_name", raw_value="Water Harvesting Bund Construction", source=ev_board, reviewed_by_user=True),
                implementing_agency=ExtractedField(field_name="agency", raw_value="Pedda Amberpet GP", source=ev_board, reviewed_by_user=True),
                estimated_labour_days=ExtractedField(field_name="labour_days", raw_value=Decimal("500"), source=ev_board, reviewed_by_user=True),
                material_entries=[
                    MaterialEntry(local_name="Granular Stone Boulders", quantity=Decimal("120"), unit="Cu.m", item_cost=Decimal("180000.00"), source=ev_board),
                    MaterialEntry(local_name="Compacted Red Soil", quantity=Decimal("350"), unit="Cu.m", item_cost=Decimal("120000.00"), source=ev_board),
                    MaterialEntry(local_name="RCC Drainage Pipe (300mm)", quantity=Decimal("25"), unit="Metres", item_cost=Decimal("50000.00"), source=ev_board),
                ],
                total_cost=ExtractedField(field_name="total_cost", raw_value=Decimal("500000.00"), source=ev_board, reviewed_by_user=True),
                evidence_references=[ev_board],
            )
        elif "case_2" in case_name:
            # Planted omission: item_cost is None for items!
            board_data = JanataBoardData(
                work_id=ExtractedField(field_name="work_id", raw_value="WRK-AP-2026-00204", source=ev_board, reviewed_by_user=True),
                work_name=ExtractedField(field_name="work_name", raw_value="Community Tank Desiltation & Feeder Channel", source=ev_board, reviewed_by_user=True),
                implementing_agency=ExtractedField(field_name="agency", raw_value="Amberpet GP", source=ev_board, reviewed_by_user=True),
                estimated_labour_days=ExtractedField(field_name="labour_days", raw_value=Decimal("600"), source=ev_board, reviewed_by_user=True),
                material_entries=[
                    MaterialEntry(local_name="Excavator Machine Rental", quantity=Decimal("120"), unit="Hours", item_cost=None, source=ev_board),
                    MaterialEntry(local_name="Silt Transport Tractor Trips", quantity=Decimal("350"), unit="Trips", item_cost=None, source=ev_board),
                    MaterialEntry(local_name="Feeder Channel Stone Revetment", quantity=Decimal("80"), unit="Cu.m", item_cost=None, source=ev_board),
                ],
                total_cost=ExtractedField(field_name="total_cost", raw_value=Decimal("800000.00"), source=ev_board, reviewed_by_user=True),
                evidence_references=[ev_board],
            )
        else:
            board_data = JanataBoardData(
                work_id=ExtractedField(field_name="work_id", raw_value="WRK-AP-2026-00309", source=ev_board, reviewed_by_user=True),
                work_name=ExtractedField(field_name="work_name", raw_value="Check Dam Construction across Vagu Stream", source=ev_board, reviewed_by_user=True),
                implementing_agency=ExtractedField(field_name="agency", raw_value="Amberpet GP", source=ev_board, reviewed_by_user=True),
                estimated_labour_days=ExtractedField(field_name="labour_days", raw_value=Decimal("450"), source=ev_board, reviewed_by_user=True),
                material_entries=[
                    MaterialEntry(local_name="Cement 43 Grade (Bags)", quantity=Decimal("250"), unit="Bags", item_cost=Decimal("95000.00"), source=ev_board),
                    MaterialEntry(local_name="Coarse Sand (Cu.m)", quantity=Decimal("45"), unit="Cu.m", item_cost=Decimal("36000.00"), source=ev_board),
                    MaterialEntry(local_name="Granite Rubble (Cu.m)", quantity=Decimal("90"), unit="Cu.m", item_cost=Decimal("108000.00"), source=ev_board),
                ],
                total_cost=ExtractedField(field_name="total_cost", raw_value=Decimal("400000.00"), source=ev_board, reviewed_by_user=True),
                evidence_references=[ev_board],
            )

    # 3. Bills CSV
    bills_file = case_path / "bills_vouchers.csv"
    bills: List[BillVoucherRecord] = []
    if bills_file.exists():
        with open(bills_file, "rb") as f:
            bills = parse_bills_csv(f.read(), filename=bills_file.name, synthetic=True)
            evidence_files.extend([b.evidence for b in bills if b.evidence])

    # 4. Labour records CSV
    labour_file = case_path / "labour_records.csv"
    labour_records: List[LabourPaymentRecord] = []
    if labour_file.exists():
        with open(labour_file, "rb") as f:
            labour_records = parse_labour_csv(f.read(), filename=labour_file.name, synthetic=True)
            evidence_files.extend([l.evidence for l in labour_records if l.evidence])

    # 5. Weekly disclosure CSV
    disc_file = case_path / "weekly_disclosure.csv"
    disclosures: List[WeeklyDisclosureData] = []
    if disc_file.exists():
        with open(disc_file, "rb") as f:
            disclosures = parse_weekly_disclosure_csv(f.read(), filename=disc_file.name, synthetic=True)
            for d in disclosures:
                evidence_files.extend(d.evidence_references)

    # 6. Stage Photos
    stage_photos: List[StagePhotoEvidence] = []
    p1 = case_path / "stage_1_initial.jpg"
    p2 = case_path / "stage_2_intermediate.jpg"
    p3 = case_path / "stage_3_final.jpg"

    if p1.exists():
        ev1 = inspect_stage_photo(p1, "Stage 1: Initial", 1, synthetic=True)
        stage_photos.append(ev1)
        evidence_files.append(ev1.evidence_reference)
    if p2.exists():
        ev2 = inspect_stage_photo(p2, "Stage 2: Intermediate", 2, synthetic=True)
        stage_photos.append(ev2)
        evidence_files.append(ev2.evidence_reference)
    if p3.exists():
        ev3 = inspect_stage_photo(p3, "Stage 3: Final", 3, synthetic=True)
        stage_photos.append(ev3)
        evidence_files.append(ev3.evidence_reference)

    # Derive work_id and work_name
    w_id = ""
    w_name = ""
    if sanction_data and sanction_data.work_id:
        w_id = str(sanction_data.work_id.get_effective_value() or "")
    elif board_data and board_data.work_id:
        w_id = str(board_data.work_id.get_effective_value() or "")

    if sanction_data and sanction_data.work_name:
        w_name = str(sanction_data.work_name.get_effective_value() or "")
    elif board_data and board_data.work_name:
        w_name = str(board_data.work_name.get_effective_value() or "")

    # Deduplicate evidence inventory
    seen_ids = set()
    deduped_inventory = []
    for ev in evidence_files:
        if ev.evidence_id not in seen_ids:
            seen_ids.add(ev.evidence_id)
            deduped_inventory.append(ev)

    return AuditBundle(
        work_id=w_id or "DEMO-WORK",
        work_name=w_name or "Public Works Project",
        synthetic=True,
        evidence_files=deduped_inventory,
        board_data=board_data,
        sanction_data=sanction_data,
        weekly_disclosures=disclosures,
        bills=bills,
        labour_records=labour_records,
        stage_photos=stage_photos,
    )
