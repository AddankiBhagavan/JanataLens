"""Pydantic v2 data models and strict enums for JanataLens AI.

Enforces:
- Strict finding statuses (CONSISTENT, MISMATCH_FOUND, MISSING_EVIDENCE, NEEDS_HUMAN_REVIEW)
- Evidence categories and extraction statuses
- Decimal for all monetary amounts
- Traceable evidence references
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Strict Enums
# ---------------------------------------------------------------------------

class FindingStatus(str, Enum):
    """Strict finding status enum. Must not be altered or aliased in storage."""
    CONSISTENT = "CONSISTENT"
    MISMATCH_FOUND = "MISMATCH_FOUND"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


class Severity(str, Enum):
    """Review priority severity, not a guilt or fraud score."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EvidenceCategory(str, Enum):
    """Supported evidence categories."""
    JANATA_BOARD_PHOTO = "JANATA_BOARD_PHOTO"
    SANCTION_ORDER = "SANCTION_ORDER"
    ESTIMATE_OR_BOQ = "ESTIMATE_OR_BOQ"
    WEEKLY_DISCLOSURE = "WEEKLY_DISCLOSURE"
    MUSTER_OR_ATTENDANCE_RECORD = "MUSTER_OR_ATTENDANCE_RECORD"
    BILL_OR_VOUCHER = "BILL_OR_VOUCHER"
    WAGE_PAYMENT_RECORD = "WAGE_PAYMENT_RECORD"
    STAGE_PHOTO = "STAGE_PHOTO"
    OTHER_SUPPORTING_EVIDENCE = "OTHER_SUPPORTING_EVIDENCE"


class ExtractionStatus(str, Enum):
    """State of an extracted field."""
    EXTRACTED_UNREVIEWED = "EXTRACTED_UNREVIEWED"
    USER_CONFIRMED = "USER_CONFIRMED"
    USER_CORRECTED = "USER_CORRECTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNREADABLE = "UNREADABLE"
    NOT_PRESENT = "NOT_PRESENT"


# ---------------------------------------------------------------------------
# Core Provenance & Field Models
# ---------------------------------------------------------------------------

class EvidenceReference(BaseModel):
    """Points to exact source evidence for any extracted field or audit finding."""
    model_config = ConfigDict(extra="ignore")

    evidence_id: str
    filename: str
    evidence_type: EvidenceCategory
    sha256: str
    file_size_bytes: int
    page_number: Optional[int] = None
    row_number: Optional[int] = None
    text_excerpt: Optional[str] = None
    bounding_box: Optional[Dict[str, float]] = None
    synthetic: bool = False

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            raise ValueError("SHA-256 evidence hashes must be exactly 64 hexadecimal characters")
        return value.lower()

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Evidence reference ID must not be empty")
        return value

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Evidence filename must not be empty")
        return value

    @field_validator("file_size_bytes")
    @classmethod
    def validate_file_size(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Evidence file size must not be negative")
        return value


class ExtractedField(BaseModel):
    """Wraps an extracted value with provenance, confidence, and human review status."""
    model_config = ConfigDict(extra="ignore")

    field_name: str
    raw_value: Optional[Any] = None
    raw_text: Optional[str] = None
    normalised_value: Optional[Any] = None
    source: Optional[EvidenceReference] = None
    extraction_method: str = "manual"  # pymupdf_text, gemini_multimodal, csv_parser, manual, synthetic_fixture
    confidence: Optional[float] = None
    extraction_status: ExtractionStatus = ExtractionStatus.EXTRACTED_UNREVIEWED
    reviewed_by_user: bool = False

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    def is_eligible_for_calculation(self) -> bool:
        """Only user-confirmed, user-corrected, or synthetic fixture fields can enter calculations."""
        if self.reviewed_by_user:
            return True
        if self.extraction_status in (ExtractionStatus.USER_CONFIRMED, ExtractionStatus.USER_CORRECTED):
            return True
        if self.source and self.source.synthetic and self.extraction_status != ExtractionStatus.UNREADABLE:
            return True
        return False

    def get_effective_value(self) -> Any:
        """Returns normalised_value if set, otherwise raw_value."""
        if self.normalised_value is not None:
            return self.normalised_value
        return self.raw_value


# ---------------------------------------------------------------------------
# Domain Models
# ---------------------------------------------------------------------------

class MaterialEntry(BaseModel):
    """An item-wise material entry on a Janata Board or Estimate."""
    model_config = ConfigDict(extra="ignore")

    local_name: str
    normalised_name: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    item_cost: Optional[Decimal] = None
    source: Optional[EvidenceReference] = None


class JanataBoardData(BaseModel):
    """Structured data from worksite Janata Board photograph/record."""
    model_config = ConfigDict(extra="ignore")

    work_name: Optional[ExtractedField] = None
    work_id: Optional[ExtractedField] = None
    implementing_agency: Optional[ExtractedField] = None
    gram_panchayat: Optional[ExtractedField] = None
    village: Optional[ExtractedField] = None
    block: Optional[ExtractedField] = None
    district: Optional[ExtractedField] = None
    state: Optional[ExtractedField] = None
    location_description: Optional[ExtractedField] = None
    estimated_labour_days: Optional[ExtractedField] = None
    material_entries: List[MaterialEntry] = Field(default_factory=list)
    total_cost: Optional[ExtractedField] = None
    board_photo_metadata: Optional[Dict[str, Any]] = None
    evidence_references: List[EvidenceReference] = Field(default_factory=list)


class EstimateLineItem(BaseModel):
    """Line item in a technical estimate or bill of quantities."""
    model_config = ConfigDict(extra="ignore")

    item_id: Optional[str] = None
    description: str
    specification: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    rate: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    cost_category: Optional[str] = None  # labour, material, machinery, administrative
    source: Optional[EvidenceReference] = None


class RevisedSanction(BaseModel):
    """Revision order modifying administrative or financial sanction."""
    model_config = ConfigDict(extra="ignore")

    revised_order_number: Optional[str] = None
    revised_date: Optional[date] = None
    revised_amount: Decimal
    scope_change: Optional[str] = None
    evidence: Optional[EvidenceReference] = None


class SanctionEstimateData(BaseModel):
    """Administrative sanction order and technical estimate data."""
    model_config = ConfigDict(extra="ignore")

    work_id: Optional[ExtractedField] = None
    work_name: Optional[ExtractedField] = None
    sanction_order_number: Optional[ExtractedField] = None
    sanction_authority: Optional[ExtractedField] = None
    original_sanction_date: Optional[ExtractedField] = None
    original_sanction_amount: Optional[ExtractedField] = None
    revised_sanctions: List[RevisedSanction] = Field(default_factory=list)
    estimate_items: List[EstimateLineItem] = Field(default_factory=list)
    scope: Optional[str] = None
    relevant_period_start: Optional[date] = None
    relevant_period_end: Optional[date] = None
    evidence_references: List[EvidenceReference] = Field(default_factory=list)


class WeeklyDisclosureData(BaseModel):
    """Proactive weekly disclosure table or report."""
    model_config = ConfigDict(extra="ignore")

    work_id: Optional[ExtractedField] = None
    work_name: Optional[ExtractedField] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    publication_date: Optional[date] = None
    person_days_aggregate: Optional[Decimal] = None
    wage_amount_aggregate: Optional[Decimal] = None
    material_amount_aggregate: Optional[Decimal] = None
    material_quantities: List[Dict[str, Any]] = Field(default_factory=list)
    physical_progress_percent: Optional[Decimal] = None
    physical_progress_description: Optional[str] = None
    line_items: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_references: List[EvidenceReference] = Field(default_factory=list)


class BillVoucherRecord(BaseModel):
    """Material bill, tax invoice, voucher, or hire charge record."""
    model_config = ConfigDict(extra="ignore")

    bill_number: str
    work_id: Optional[str] = None
    vendor_or_payee: Optional[str] = None
    bill_date: Optional[date] = None
    amount: Decimal
    cost_category: Optional[str] = "material"  # material, machinery, administrative, etc.
    description: Optional[str] = None
    items: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: Optional[EvidenceReference] = None


class LabourPaymentRecord(BaseModel):
    """Wage payment transaction. Pseudonymous only; no Aadhaar or bank account numbers."""
    model_config = ConfigDict(extra="ignore")

    work_id: str
    worker_ref: str  # pseudonymous identifier, e.g. "WRK-001"
    work_start_date: Optional[date] = None
    work_end_date: Optional[date] = None
    muster_roll_ref: Optional[str] = None
    muster_closure_date: Optional[date] = None
    wage_amount_due: Decimal
    fto_processing_date: Optional[date] = None  # separate from credit date
    actual_credit_date: Optional[date] = None  # bank/post-office credit confirmation
    payment_status: Optional[str] = None
    evidence: Optional[EvidenceReference] = None


class StagePhotoEvidence(BaseModel):
    """Stage photograph and forensic metadata."""
    model_config = ConfigDict(extra="ignore")

    photo_id: str
    evidence_reference: EvidenceReference
    declared_stage_label: str  # e.g., "Stage 1: Foundation", "Stage 2: Superstructure"
    declared_order: int
    capture_timestamp: Optional[datetime] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    sha256: str
    phash: Optional[str] = None
    dhash: Optional[str] = None
    metadata_warnings: List[str] = Field(default_factory=list)

    @field_validator("sha256")
    @classmethod
    def validate_stage_sha256(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            raise ValueError("Stage photograph SHA-256 hashes must be exactly 64 hexadecimal characters")
        return value.lower()

    @field_validator("phash", "dhash")
    @classmethod
    def validate_perceptual_hash(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not re.fullmatch(r"[0-9a-fA-F]{16}", value):
            raise ValueError("Perceptual hashes must be exactly 16 hexadecimal characters")
        return value.lower() if value is not None else None


# ---------------------------------------------------------------------------
# Rule Source & Audit Findings
# ---------------------------------------------------------------------------

class RuleSource(BaseModel):
    """Source authority and citation for an audit check."""
    model_config = ConfigDict(extra="ignore")

    rule_id: str
    version: str
    title: str
    issuing_authority: str
    url: Optional[str] = None
    retrieval_date: Optional[date] = None
    section_reference: Optional[str] = None
    effective_date: Optional[date] = None
    end_date: Optional[date] = None
    jurisdiction: str = "national"
    calculation_basis: Optional[str] = None
    limitations: Optional[str] = None


class AuditFinding(BaseModel):
    """Evidence-linked finding produced by deterministic audit engine."""
    model_config = ConfigDict(extra="ignore")

    finding_id: str
    rule_id: str
    rule_version: str = "1.0"
    title: str
    status: FindingStatus
    severity: Severity
    summary: str
    observed_values: Dict[str, Any] = Field(default_factory=dict)
    comparison_values: Dict[str, Any] = Field(default_factory=dict)
    exact_calculation: Optional[str] = None
    evidence_references: List[EvidenceReference] = Field(default_factory=list)
    rule_source: Optional[RuleSource] = None
    human_verification_steps: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditBundle(BaseModel):
    """Complete bundle of evidence and parsed structures for a single work audit session."""
    model_config = ConfigDict(extra="ignore")

    work_id: str
    work_name: str
    synthetic: bool = False
    evidence_files: List[EvidenceReference] = Field(default_factory=list)
    board_data: Optional[JanataBoardData] = None
    sanction_data: Optional[SanctionEstimateData] = None
    weekly_disclosures: List[WeeklyDisclosureData] = Field(default_factory=list)
    bills: List[BillVoucherRecord] = Field(default_factory=list)
    labour_records: List[LabourPaymentRecord] = Field(default_factory=list)
    stage_photos: List[StagePhotoEvidence] = Field(default_factory=list)


class AuditReport(BaseModel):
    """Full evidence-backed audit report suitable for export."""
    model_config = ConfigDict(extra="ignore")

    session_id: str
    work_id: Optional[str] = None
    work_name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    application_version: str = "1.0.0"
    spec_version: str = "2026-11-21"
    synthetic: bool = False
    evidence_inventory: List[EvidenceReference] = Field(default_factory=list)
    extraction_summary: Dict[str, Any] = Field(default_factory=dict)
    work_linkage_result: Dict[str, Any] = Field(default_factory=dict)
    rule_execution_summary: Dict[str, Any] = Field(default_factory=dict)
    findings: List[AuditFinding] = Field(default_factory=list)
    overall_review_state: str = "NEEDS_HUMAN_REVIEW"
    explanation_en: Optional[str] = None
    explanation_te: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
