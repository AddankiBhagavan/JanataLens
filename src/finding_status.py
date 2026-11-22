"""Conservative display-only mapping for audit findings.

The engine's FindingStatus values are preserved.  This module only derives the
four presentation labels used by the UI and report exports.
"""

from __future__ import annotations

import re
from typing import Optional

from src.schemas import AuditBundle, AuditFinding, AuditReport, FindingStatus


SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")


def has_valid_provenance(finding: AuditFinding) -> bool:
    """Requires a valid source identity and exact SHA-256 hash."""
    if not finding.evidence_references:
        return False
    return all(
        bool(ref.evidence_id)
        and bool(ref.filename)
        and bool(ref.sha256)
        and SHA256_RE.fullmatch(ref.sha256) is not None
        and ref.file_size_bytes >= 0
        for ref in finding.evidence_references
    )


def consistent_check_has_sufficient_evidence(
    finding: AuditFinding,
    bundle: Optional[AuditBundle] = None,
) -> bool:
    """Returns whether a CONSISTENT finding meets rule-specific display criteria."""
    if bundle is None:
        return False
    if not has_valid_provenance(finding):
        return False

    if finding.rule_id == "JL-01":
        board = bundle.board_data
        return bool(
            board
            and board.work_name
            and board.work_name.get_effective_value()
            and board.estimated_labour_days
            and board.estimated_labour_days.get_effective_value() is not None
            and board.material_entries
            and all(item.quantity is not None and item.item_cost is not None for item in board.material_entries)
            and board.evidence_references
        )

    if finding.rule_id == "JL-02":
        sanction = bundle.sanction_data
        return bool(
            sanction
            and sanction.original_sanction_amount
            and sanction.original_sanction_amount.is_eligible_for_calculation()
            and sanction.original_sanction_amount.get_effective_value() is not None
            and sanction.evidence_references
            and bundle.bills
            and all(bill.evidence is not None for bill in bundle.bills)
        )

    if finding.rule_id == "JL-03":
        return bool(
            bundle.labour_records
            and all(
                record.evidence is not None
                and record.work_end_date is not None
                and record.actual_credit_date is not None
                and record.muster_closure_date is not None
                for record in bundle.labour_records
            )
        )

    if finding.rule_id == "JL-04":
        return bool(
            bundle.sanction_data
            and bundle.sanction_data.original_sanction_date
            and bundle.sanction_data.original_sanction_date.get_effective_value() is not None
            and bundle.sanction_data.evidence_references
            and bundle.bills
            and all(bill.evidence is not None and bill.bill_date is not None for bill in bundle.bills)
        )

    if finding.rule_id == "JL-05":
        return bool(
            len(bundle.stage_photos) >= 2
            and all(
                SHA256_RE.fullmatch(photo.sha256) is not None
                and photo.phash
                and re.fullmatch(r"[0-9a-fA-F]{16}", photo.phash) is not None
                and photo.dhash
                and re.fullmatch(r"[0-9a-fA-F]{16}", photo.dhash) is not None
                and photo.evidence_reference.evidence_id
                and photo.evidence_reference.filename
                for photo in bundle.stage_photos
            )
        )

    return False


def map_finding_display_state(
    finding: AuditFinding,
    bundle: Optional[AuditBundle] = None,
    report: Optional[AuditReport] = None,
) -> str:
    """Maps engine status to exactly one conservative display state."""
    if finding.status == FindingStatus.MISSING_EVIDENCE:
        return "MISSING"
    if finding.status == FindingStatus.MISMATCH_FOUND:
        return "INCONSISTENT"
    if finding.status == FindingStatus.NEEDS_HUMAN_REVIEW:
        return "UNVERIFIED"
    if finding.status == FindingStatus.CONSISTENT:
        if bundle is not None:
            if consistent_check_has_sufficient_evidence(finding, bundle):
                return "VERIFIED"
            return "UNVERIFIED"

        if report is not None and has_valid_provenance(finding):
            observed = finding.observed_values
            if finding.rule_id == "JL-01":
                sufficient = all(
                    key in observed
                    for key in ("work_name", "estimated_labour_days", "material_items_count")
                )
            elif finding.rule_id == "JL-02":
                sufficient = all(
                    key in observed
                    for key in ("cumulative_bills_total", "effective_sanction_amount")
                )
            elif finding.rule_id == "JL-03":
                sufficient = (
                    "days_elapsed" in observed
                    or "days_from_closure" in observed
                )
            elif finding.rule_id == "JL-04":
                sufficient = "sanction_date" in observed
            elif finding.rule_id == "JL-05":
                sufficient = "photos_compared" in observed
            else:
                sufficient = False
            if sufficient:
                return "VERIFIED"
        return "UNVERIFIED"
    return "UNVERIFIED"
