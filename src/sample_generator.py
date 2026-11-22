"""Synthetic demonstration bundle generator for JanataLens AI.

Generates programmatically:
- Case 1: Clean and Consistent Work (Water Harvesting Bund)
- Case 2: Cost Difference and Incomplete Board (Community Tank Desiltation)
- Case 3: Photo Similarity and Date Anomaly (Check Dam Construction)

Every generated file includes the clear watermark:
SYNTHETIC DEMO DATA — NOT AN OFFICIAL GOVERNMENT RECORD
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont
import pymupdf as fitz
import pandas as pd

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
    SanctionEstimateData,
    StagePhotoEvidence,
    WeeklyDisclosureData,
)
from src.vision_forensics import inspect_stage_photo

WATERMARK = "SYNTHETIC DEMO DATA — NOT AN OFFICIAL GOVERNMENT RECORD"


def _draw_synthetic_watermark(draw: ImageDraw.Draw, width: int, height: int):
    """Draws a prominent synthetic warning banner across the image."""
    banner_height = 36
    draw.rectangle([0, 0, width, banner_height], fill=(180, 0, 0))
    draw.text((15, 8), WATERMARK, fill=(255, 255, 255))


def create_board_image(
    output_path: Path,
    title: str,
    work_id: str,
    agency: str,
    labour_days: str,
    items: List[Tuple[str, str, str]],  # (name, qty, cost)
    total_cost: str,
    include_item_costs: bool = True,
):
    """Creates a synthetic Janata Board signboard image with clear text."""
    width, height = 900, 650
    img = Image.new("RGB", (width, height), color=(245, 245, 235))
    draw = ImageDraw.Draw(img)

    # Frame
    draw.rectangle([10, 10, width - 10, height - 10], outline=(40, 40, 40), width=4)
    _draw_synthetic_watermark(draw, width, height)

    # Signboard header
    draw.rectangle([20, 50, width - 20, 120], fill=(20, 50, 90))
    draw.text((30, 60), "JANATA INFORMATION BOARD (SECTION 25(2)(b))", fill=(255, 255, 255))
    draw.text((30, 88), f"Work: {title}", fill=(230, 240, 255))

    # Details
    y = 135
    details = [
        ("Work Code / ID:", work_id),
        ("Implementing Agency:", agency),
        ("Location / Gram Panchayat:", "Pedda Amberpet GP, Hayathnagar Mandal, Ranga Reddy"),
        ("Estimated Labour Days:", labour_days),
        ("Sanctioned Amount:", f"Rs. {total_cost.replace('₹', '')}"),
    ]
    for label, val in details:
        draw.text((30, y), label, fill=(10, 10, 10))
        draw.text((260, y), str(val), fill=(0, 20, 120))
        y += 26

    # Material & Cost table header
    y += 10
    draw.rectangle([30, y, width - 30, y + 30], fill=(220, 225, 230), outline=(100, 100, 100))
    draw.text((40, y + 6), "Item Description (Local Terminology)", fill=(0, 0, 0))
    draw.text((450, y + 6), "Quantity / Units", fill=(0, 0, 0))
    draw.text((680, y + 6), "Item-wise Cost (₹)", fill=(0, 0, 0))
    y += 35

    for name, qty, cost in items:
        draw.text((40, y), name, fill=(20, 20, 20))
        draw.text((450, y), qty, fill=(20, 20, 20))
        cost_display = cost if include_item_costs else "[MISSING / NOT DISPLAYED]"
        cost_color = (20, 20, 20) if include_item_costs else (180, 0, 0)
        draw.text((680, y), cost_display, fill=cost_color)
        y += 26

    y += 20
    draw.line([(30, y), (width - 30, y)], fill=(100, 100, 100), width=2)
    y += 10
    draw.text((30, y), f"Total Disclosed Cost: {total_cost}", fill=(0, 0, 0))
    draw.text((30, y + 30), "Statutory Social Audit Notice: Open to inspection by any resident / Gram Sabha.", fill=(60, 60, 60))

    img.save(output_path, "JPEG", quality=90)


def create_sanction_pdf(
    output_path: Path,
    title: str,
    work_id: str,
    order_no: str,
    sanc_date: str,
    sanc_amount: str,
    line_items: List[Tuple[str, str, str, str]],  # (desc, qty, rate, amount)
):
    """Creates a PDF sanction order with technical estimate using PyMuPDF."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size

    # Header banner with watermark
    page.draw_rect(fitz.Rect(0, 0, 595, 30), color=(0.7, 0, 0), fill=(0.7, 0, 0))
    page.insert_text(fitz.Point(30, 20), WATERMARK, color=(1, 1, 1), fontsize=10)

    # Document Title
    page.insert_text(fitz.Point(30, 60), "OFFICE OF THE DISTRICT PROGRAMME COORDINATOR", color=(0.1, 0.2, 0.4), fontsize=14)
    page.insert_text(fitz.Point(30, 80), "ADMINISTRATIVE & TECHNICAL SANCTION ORDER", color=(0.1, 0.2, 0.4), fontsize=12)

    # Metadata table
    text_lines = [
        f"Order Reference: {order_no}",
        f"Date of Sanction: {sanc_date}",
        f"Work Identity / Project Code: {work_id}",
        f"Approved Scheme Work: {title}",
        f"Total Sanctioned Monetary Ceiling: Rs. {sanc_amount.replace('₹', '')}",
        "Funding Head: National Public Works Scheme (VB-G RAM G / MGNREGS)",
    ]
    y = 110
    for line in text_lines:
        page.insert_text(fitz.Point(30, y), line, color=(0, 0, 0), fontsize=9)
        y += 18

    # Estimate / BOQ Breakdown
    y += 15
    page.insert_text(fitz.Point(30, y), "SCHEDULE OF APPROVED ESTIMATE / BILL OF QUANTITIES (BOQ):", color=(0.1, 0.2, 0.4), fontsize=10)
    y += 15

    # Table headers
    page.draw_rect(fitz.Rect(30, y - 10, 565, y + 10), fill=(0.9, 0.9, 0.9))
    page.insert_text(fitz.Point(35, y), "Item Description", fontsize=8, color=(0, 0, 0))
    page.insert_text(fitz.Point(260, y), "Quantity", fontsize=8, color=(0, 0, 0))
    page.insert_text(fitz.Point(360, y), "Rate (₹)", fontsize=8, color=(0, 0, 0))
    page.insert_text(fitz.Point(460, y), "Amount (₹)", fontsize=8, color=(0, 0, 0))
    y += 18

    for desc, qty, rate, amt in line_items:
        page.insert_text(fitz.Point(35, y), desc, fontsize=8, color=(0.1, 0.1, 0.1))
        page.insert_text(fitz.Point(260, y), qty, fontsize=8, color=(0.1, 0.1, 0.1))
        page.insert_text(fitz.Point(360, y), rate, fontsize=8, color=(0.1, 0.1, 0.1))
        page.insert_text(fitz.Point(460, y), amt, fontsize=8, color=(0.1, 0.1, 0.1))
        y += 16

    y += 30
    page.insert_text(fitz.Point(30, y), f"Total Estimated Cost: Rs. {sanc_amount.replace('₹', '')}", fontsize=9, color=(0, 0, 0))
    page.insert_text(fitz.Point(30, y + 25), "Executive Engineer / Sanctioning Authority Signature: [Signed]", fontsize=8, color=(0.3, 0.3, 0.3))

    doc.save(output_path)
    doc.close()


def create_stage_illustration(
    output_path: Path,
    stage_name: str,
    color_theme: Tuple[int, int, int],
    pattern: str = "foundation",
    near_dup_of: Optional[Path] = None,
):
    """Generates an illustrative stage photograph."""
    width, height = 800, 600

    if near_dup_of and near_dup_of.exists():
        # Near duplicate: copy existing image and apply very subtle modification (1 tiny line)
        with Image.open(near_dup_of) as orig:
            img = orig.copy()
            draw = ImageDraw.Draw(img)
            # Re-draw stage banner at bottom
            draw.rectangle([0, height - 40, width, height], fill=(0, 0, 0))
            draw.text((20, height - 30), f"Stage Evidence: {stage_name}", fill=(255, 255, 255))
            img.save(output_path, "JPEG", quality=90)
            return

    img = Image.new("RGB", (width, height), color=(220, 230, 240))
    draw = ImageDraw.Draw(img)

    _draw_synthetic_watermark(draw, width, height)

    # Draw simulated worksite view
    # Ground
    draw.rectangle([0, 300, width, height], fill=(110, 80, 50))

    if pattern == "foundation":
        # Excavation trench
        draw.polygon([(100, 350), (700, 350), (650, 520), (150, 520)], fill=(60, 40, 25), outline=(30, 20, 10))
        draw.text((250, 420), "[Simulated Works Excavation Trench]", fill=(200, 200, 200))
    elif pattern == "structure":
        # Stone masonry / concrete bund
        draw.rectangle([150, 260, 650, 480], fill=color_theme, outline=(50, 50, 50), width=3)
        draw.text((280, 360), "[Simulated Masonry Bund / Plinth]", fill=(255, 255, 255))
    else:
        # Completed check dam with impounded water
        draw.rectangle([100, 240, 700, 450], fill=color_theme, outline=(40, 40, 40), width=4)
        draw.rectangle([150, 450, 650, 550], fill=(30, 120, 180))  # Water pool
        draw.text((260, 320), "[Simulated Completed Check Dam Structure]", fill=(255, 255, 255))
        draw.text((320, 480), "[Impounded Water Storage]", fill=(255, 255, 255))

    # Stage Label banner
    draw.rectangle([0, height - 45, width, height], fill=(20, 30, 40))
    draw.text((20, height - 35), f"Stage Evidence: {stage_name}", fill=(255, 255, 255))

    img.save(output_path, "JPEG", quality=90)


# ---------------------------------------------------------------------------
# Generators for the 3 Cases
# ---------------------------------------------------------------------------

def generate_case_1(base_dir: Path) -> Path:
    """Case 1: Clean and Consistent Work (Water Harvesting Bund)."""
    case_dir = base_dir / "case_1_clean"
    case_dir.mkdir(parents=True, exist_ok=True)

    title = "Water Harvesting Bund Construction"
    work_id = "WRK-AP-2026-00101"
    agency = "Pedda Amberpet Gram Panchayat"

    # 1. Janata Board Image
    items = [
        ("Granular Stone Boulders", "120 Cu.m", "1,80,000.00"),
        ("Compacted Red Soil", "350 Cu.m", "1,20,000.00"),
        ("RCC Drainage Pipe (300mm)", "25 Metres", "50,000.00"),
    ]
    create_board_image(
        case_dir / "janata_board.jpg",
        title=title,
        work_id=work_id,
        agency=agency,
        labour_days="500 Person-Days",
        items=items,
        total_cost="₹5,00,000.00",
        include_item_costs=True,
    )

    # 2. Sanction PDF
    boq = [
        ("Earthwork excavation & bund formation", "350 Cu.m", "342.85", "1,20,000.00"),
        ("Stone pitching with boulders", "120 Cu.m", "1500.00", "1,80,000.00"),
        ("RCC drainage conduit piping", "25 Metres", "2000.00", "50,000.00"),
        ("Unskilled labour wage component", "500 Person-days", "300.00", "1,50,000.00"),
    ]
    create_sanction_pdf(
        case_dir / "sanction_order.pdf",
        title=title,
        work_id=work_id,
        order_no="EE/PR/SAN/2026/0412",
        sanc_date="2026-07-05",
        sanc_amount="₹5,00,000.00",
        line_items=boq,
    )

    # 3. Weekly Disclosure CSV
    disc_data = [
        {"work_id": work_id, "week_ending": "2026-07-19", "person_days": 180, "wages_disbursed": 54000.00, "material_spent": 120000.00, "progress_percent": 35.0},
        {"work_id": work_id, "week_ending": "2026-07-26", "person_days": 170, "wages_disbursed": 51000.00, "material_spent": 150000.00, "progress_percent": 70.0},
        {"work_id": work_id, "week_ending": "2026-08-02", "person_days": 150, "wages_disbursed": 45000.00, "material_spent": 80000.00, "progress_percent": 100.0},
    ]
    pd.DataFrame(disc_data).to_csv(case_dir / "weekly_disclosure.csv", index=False)

    # 4. Bills CSV
    bills_data = [
        {"bill_no": "INV-2026-01", "work_id": work_id, "vendor": "Sri Sai Stone Crushers", "bill_date": "2026-07-18", "amount": 180000.00, "category": "material"},
        {"bill_no": "INV-2026-02", "work_id": work_id, "vendor": "Amberpet Earthworks", "bill_date": "2026-07-22", "amount": 120000.00, "category": "material"},
        {"bill_no": "INV-2026-03", "work_id": work_id, "vendor": "Ranga Reddy Hume Pipes", "bill_date": "2026-07-29", "amount": 50000.00, "category": "material"},
    ]
    pd.DataFrame(bills_data).to_csv(case_dir / "bills_vouchers.csv", index=False)

    # 5. Labour muster records CSV (pseudonymous)
    labour_data = [
        {"work_id": work_id, "worker_ref": "WRK-001", "work_start": "2026-07-07", "work_end": "2026-07-13", "muster_ref": "MR-101", "muster_closed": "2026-07-14", "wage_due": 2100.00, "fto_date": "2026-07-17", "credit_date": "2026-07-20"},
        {"work_id": work_id, "worker_ref": "WRK-002", "work_start": "2026-07-07", "work_end": "2026-07-13", "muster_ref": "MR-101", "muster_closed": "2026-07-14", "wage_due": 2100.00, "fto_date": "2026-07-17", "credit_date": "2026-07-20"},
        {"work_id": work_id, "worker_ref": "WRK-003", "work_start": "2026-07-14", "work_end": "2026-07-20", "muster_ref": "MR-102", "muster_closed": "2026-07-21", "wage_due": 2100.00, "fto_date": "2026-07-24", "credit_date": "2026-07-27"},
    ]
    pd.DataFrame(labour_data).to_csv(case_dir / "labour_records.csv", index=False)

    # 6. Three distinct stage photographs
    create_stage_illustration(case_dir / "stage_1_initial.jpg", "Stage 1: Trench Excavation", (120, 100, 80), "foundation")
    create_stage_illustration(case_dir / "stage_2_intermediate.jpg", "Stage 2: Stone Pitching", (140, 140, 140), "structure")
    create_stage_illustration(case_dir / "stage_3_final.jpg", "Stage 3: Completed Bund", (100, 130, 90), "completed")

    return case_dir


def generate_case_2(base_dir: Path) -> Path:
    """Case 2: Cost Difference and Incomplete Board (Community Tank Desiltation).
    Sanction: ₹8,00,000.
    Bills: ₹9,20,000 (diff: ₹1,20,000).
    Janata board: missing item-wise cost breakdown.
    """
    case_dir = base_dir / "case_2_cost_mismatch"
    case_dir.mkdir(parents=True, exist_ok=True)

    title = "Community Tank Desiltation & Feeder Channel"
    work_id = "WRK-AP-2026-00204"
    agency = "Amberpet Gram Panchayat"

    # 1. Janata Board Image (missing item-wise costs)
    items = [
        ("Excavator Machine Rental", "120 Hours", ""),
        ("Silt Transport Tractor Trips", "350 Trips", ""),
        ("Feeder Channel Stone Revetment", "80 Cu.m", ""),
    ]
    create_board_image(
        case_dir / "janata_board.jpg",
        title=title,
        work_id=work_id,
        agency=agency,
        labour_days="600 Person-Days",
        items=items,
        total_cost="₹8,00,000.00",
        include_item_costs=False,  # Planted omission!
    )

    # 2. Sanction PDF for ₹8,00,000
    boq = [
        ("Excavator desiltation hire charges", "120 Hours", "2500.00", "3,00,000.00"),
        ("Tractor silt carting & spreading", "350 Trips", "600.00", "2,10,000.00"),
        ("Feeder channel stone revetment", "80 Cu.m", "1375.00", "1,10,000.00"),
        ("Manual silt clearance labour wages", "600 Person-days", "300.00", "1,80,000.00"),
    ]
    create_sanction_pdf(
        case_dir / "sanction_order.pdf",
        title=title,
        work_id=work_id,
        order_no="EE/PR/SAN/2026/0589",
        sanc_date="2026-07-10",
        sanc_amount="₹8,00,000.00",
        line_items=boq,
    )

    # 3. Bills totalling ₹9,20,000 (₹1,20,000 difference!)
    bills_data = [
        {"bill_no": "BILL-DES-01", "work_id": work_id, "vendor": "Deccan Heavy Machinery", "bill_date": "2026-07-25", "amount": 380000.00, "category": "machinery"},
        {"bill_no": "BILL-DES-02", "work_id": work_id, "vendor": "Ganga Transport Fleet", "bill_date": "2026-08-04", "amount": 290000.00, "category": "transport"},
        {"bill_no": "BILL-DES-03", "work_id": work_id, "vendor": "Raja Stone Pitching", "bill_date": "2026-08-14", "amount": 250000.00, "category": "material"},
    ]
    pd.DataFrame(bills_data).to_csv(case_dir / "bills_vouchers.csv", index=False)

    # 4. Weekly disclosure
    disc_data = [
        {"work_id": work_id, "week_ending": "2026-08-01", "person_days": 300, "wages_disbursed": 90000.00, "material_spent": 380000.00, "progress_percent": 45.0},
        {"work_id": work_id, "week_ending": "2026-08-15", "person_days": 300, "wages_disbursed": 90000.00, "material_spent": 540000.00, "progress_percent": 100.0},
    ]
    pd.DataFrame(disc_data).to_csv(case_dir / "weekly_disclosure.csv", index=False)

    # 5. Labour muster records
    labour_data = [
        {"work_id": work_id, "worker_ref": "WRK-010", "work_start": "2026-07-14", "work_end": "2026-07-20", "muster_ref": "MR-201", "muster_closed": "2026-07-21", "wage_due": 2100.00, "fto_date": "2026-07-24", "credit_date": "2026-07-28"},
        {"work_id": work_id, "worker_ref": "WRK-011", "work_start": "2026-07-21", "work_end": "2026-07-27", "muster_ref": "MR-202", "muster_closed": "2026-07-28", "wage_due": 2100.00, "fto_date": "2026-07-31", "credit_date": "2026-08-04"},
    ]
    pd.DataFrame(labour_data).to_csv(case_dir / "labour_records.csv", index=False)

    # 6. Stage photos
    create_stage_illustration(case_dir / "stage_1_initial.jpg", "Stage 1: Tank Bed Inspection", (100, 80, 60), "foundation")
    create_stage_illustration(case_dir / "stage_2_intermediate.jpg", "Stage 2: Desiltation Excavation", (130, 90, 70), "structure")
    create_stage_illustration(case_dir / "stage_3_final.jpg", "Stage 3: Deepened Tank & Bund", (80, 110, 130), "completed")

    return case_dir


def generate_case_3(base_dir: Path) -> Path:
    """Case 3: Photo Similarity and Date Anomaly (Check Dam Construction).
    - Stage 1 and Stage 3 photos are near-identical copies.
    - Bill 1 is dated prior to administrative sanction date.
    """
    case_dir = base_dir / "case_3_evidence_anomaly"
    case_dir.mkdir(parents=True, exist_ok=True)

    title = "Check Dam Construction across Vagu Stream"
    work_id = "WRK-AP-2026-00309"
    agency = "Amberpet Gram Panchayat"

    # 1. Janata Board Image
    items = [
        ("Cement 43 Grade (Bags)", "250 Bags", "95,000.00"),
        ("Coarse Sand (Cu.m)", "45 Cu.m", "36,000.00"),
        ("Granite Rubble (Cu.m)", "90 Cu.m", "1,08,000.00"),
    ]
    create_board_image(
        case_dir / "janata_board.jpg",
        title=title,
        work_id=work_id,
        agency=agency,
        labour_days="450 Person-Days",
        items=items,
        total_cost="₹4,00,000.00",
        include_item_costs=True,
    )

    # 2. Sanction PDF dated 2026-07-15
    boq = [
        ("Foundation excavation in rocky bed", "60 Cu.m", "500.00", "30,000.00"),
        ("Rubble stone masonry in cement mortar 1:6", "90 Cu.m", "2655.55", "2,39,000.00"),
        ("Labour wage component", "436 Person-days", "300.00", "1,31,000.00"),
    ]
    create_sanction_pdf(
        case_dir / "sanction_order.pdf",
        title=title,
        work_id=work_id,
        order_no="EE/PR/SAN/2026/0881",
        sanc_date="2026-07-15",
        sanc_amount="₹4,00,000.00",
        line_items=boq,
    )

    # 3. Bills: Planted pre-sanction bill dated 2026-06-25 (Sanction is 2026-07-15!)
    bills_data = [
        {"bill_no": "BILL-PRE-01", "work_id": work_id, "vendor": "Bhavani Cement Depot", "bill_date": "2026-06-25", "amount": 95000.00, "category": "material"},
        {"bill_no": "BILL-POST-02", "work_id": work_id, "vendor": "Vagu Sand Quarry", "bill_date": "2026-07-22", "amount": 36000.00, "category": "material"},
        {"bill_no": "BILL-POST-03", "work_id": work_id, "vendor": "Kakatiya Stone Works", "bill_date": "2026-08-01", "amount": 108000.00, "category": "material"},
    ]
    pd.DataFrame(bills_data).to_csv(case_dir / "bills_vouchers.csv", index=False)

    # 4. Weekly disclosure
    disc_data = [
        {"work_id": work_id, "week_ending": "2026-07-26", "person_days": 200, "wages_disbursed": 60000.00, "material_spent": 131000.00, "progress_percent": 50.0},
        {"work_id": work_id, "week_ending": "2026-08-09", "person_days": 236, "wages_disbursed": 71000.00, "material_spent": 108000.00, "progress_percent": 100.0},
    ]
    pd.DataFrame(disc_data).to_csv(case_dir / "weekly_disclosure.csv", index=False)

    # 5. Labour muster records
    labour_data = [
        {"work_id": work_id, "worker_ref": "WRK-021", "work_start": "2026-07-16", "work_end": "2026-07-22", "muster_ref": "MR-301", "muster_closed": "2026-07-23", "wage_due": 2100.00, "fto_date": "2026-07-26", "credit_date": "2026-07-30"},
    ]
    pd.DataFrame(labour_data).to_csv(case_dir / "labour_records.csv", index=False)

    # 6. Stage Photos: Stage 1 and Stage 3 are near-identical copies!
    p1_path = case_dir / "stage_1_initial.jpg"
    create_stage_illustration(p1_path, "Stage 1: Stream Bed Excavation", (120, 110, 90), "foundation")
    create_stage_illustration(case_dir / "stage_2_intermediate.jpg", "Stage 2: Masonry Structure", (150, 150, 150), "structure")
    # Stage 3 created as near-duplicate of Stage 1!
    create_stage_illustration(case_dir / "stage_3_final.jpg", "Stage 3: Completed Stream Bund", (120, 110, 90), near_dup_of=p1_path)

    return case_dir


def generate_all_cases(root_dir: Path | str = "sample_cases") -> Dict[str, Path]:
    """Generates all 3 synthetic demonstration bundles."""
    base = Path(root_dir)
    base.mkdir(parents=True, exist_ok=True)

    return {
        "case_1": generate_case_1(base),
        "case_2": generate_case_2(base),
        "case_3": generate_case_3(base),
    }


if __name__ == "__main__":
    generate_all_cases()
