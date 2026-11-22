"""Pure deterministic audit engine for JanataLens AI.

Implements rules JL-01 through JL-05 and the work-identity/linkage gate.
Does NOT import Streamlit or call Gemini.
Uses Decimal for financial precision and records exact calculations.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

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
    RevisedSanction,
    RuleSource,
    SanctionEstimateData,
    Severity,
    StagePhotoEvidence,
    WeeklyDisclosureData,
)


def _dedupe_refs(refs: List[EvidenceReference]) -> List[EvidenceReference]:
    """Deduplicates a list of EvidenceReference objects by evidence_id."""
    seen = set()
    result = []
    for r in refs:
        if r.evidence_id not in seen:
            seen.add(r.evidence_id)
            result.append(r)
    return result


# ---------------------------------------------------------------------------
# Rule Source Registry
# ---------------------------------------------------------------------------

RULE_SOURCES: Dict[str, RuleSource] = {
    "JL-01": RuleSource(
        rule_id="JL-01",
        version="1.0",
        title="Janata Board Completeness Check",
        issuing_authority="Gazette of India / Ministry of Rural Development",
        url="https://egazette.gov.in/WriteReadData/2025/268696.pdf",
        retrieval_date=date(2026, 11, 21),
        section_reference="Schedule I, paragraph 25(2)(b), VB–G RAM G Act, 2025",
        effective_date=date(2026, 7, 1),
        jurisdiction="national",
        calculation_basis="Presence and completeness of statutory worksite board fields",
        limitations="Only flags missing fields required by Schedule I, paragraph 25(2)(b). Does not evaluate physical signboard material durability.",
    ),
    "JL-02": RuleSource(
        rule_id="JL-02",
        version="1.0",
        title="Financial Expenditure vs Sanction Reconciliation",
        issuing_authority="Statutory Social Audit & Financial Guidelines",
        url="https://egazette.gov.in/WriteReadData/2025/268696.pdf",
        retrieval_date=date(2026, 11, 21),
        section_reference="Schedule I, paragraph 14; Section 23(1)-(2), VB–G RAM G Act, 2025",
        effective_date=date(2026, 7, 1),
        jurisdiction="national",
        calculation_basis="Cumulative bills/vouchers compared against the latest supplied administrative or financial sanction",
        limitations="Calculates documentary differences only. A mismatch requires human review and does not establish a legally defined violation, misuse, or impropriety.",
    ),
    "JL-03": RuleSource(
        rule_id="JL-03",
        version="1.0",
        title="Labour Wage Timing and Delay Compensation Review",
        issuing_authority="Gazette of India",
        url="https://egazette.gov.in/WriteReadData/2025/268696.pdf",
        retrieval_date=date(2026, 11, 21),
        section_reference="Section 5(3); Schedule I, paragraph 16; Schedule II, paragraph 6",
        effective_date=date(2026, 7, 1),
        jurisdiction="national",
        calculation_basis="Weekly/fortnight wage timing under Section 5(3); measurements under Schedule I, paragraph 16; separate operational Schedule II, paragraph 6 delay-compensation calculation",
        limitations="Requires confirmed bank/post-office credit date. FTO generation/upload is not proof of credit. The 15-day muster-close delay clock is reported only as a separate operational compensation check where its applicable source is cited.",
    ),
    "JL-04": RuleSource(
        rule_id="JL-04",
        version="1.0",
        title="Chronological Integrity and Sequence Verification",
        issuing_authority="Financial and Works Execution Standards",
        url="https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/may/doc2026511867901.pdf",
        retrieval_date=date(2026, 11, 21),
        section_reference="General Financial Rules / Works Execution Sequence",
        effective_date=date(2026, 7, 1),
        jurisdiction="national",
        calculation_basis="Date sequence comparison across sanction, expenditure, muster rolls, and stage photographs",
        limitations="Unverified device EXIF or missing metadata is treated as uncertain, not malicious.",
    ),
    "JL-05": RuleSource(
        rule_id="JL-05",
        version="1.0",
        title="Photo Evidence Reuse and Hash Comparison",
        issuing_authority="Digital Forensic Audit Guidelines",
        url="https://ai.google.dev/gemini-api/docs/models",
        retrieval_date=date(2026, 11, 21),
        section_reference="Stage Photo Verification Standards",
        effective_date=date(2026, 7, 1),
        jurisdiction="national",
        calculation_basis="Pairwise SHA-256 exact match and perceptual hash (pHash/dHash) Hamming distance",
        limitations="Visual similarity indicates potential image reuse across distinct stages. Requires human visual inspection.",
    ),
}


# ---------------------------------------------------------------------------
# Work Identity & Linkage Gate
# ---------------------------------------------------------------------------

def validate_work_linkage(bundle: AuditBundle) -> Tuple[bool, Dict[str, Any]]:
    """Validates that all evidence records belong to the same work/project.

    Returns:
        (is_linked, details_dict)
    """
    work_id = bundle.work_id.strip() if bundle.work_id else ""
    work_name = bundle.work_name.strip() if bundle.work_name else ""

    conflicts: List[str] = []
    matched_sources: List[str] = []
    warnings: List[str] = []

    # 1. Check Janata Board
    if bundle.board_data:
        board_id_val = bundle.board_data.work_id.get_effective_value() if bundle.board_data.work_id else None
        if board_id_val:
            bid = str(board_id_val).strip()
            if work_id and bid.lower() != work_id.lower():
                conflicts.append(f"Janata Board work ID '{bid}' does not match session work ID '{work_id}'")
            else:
                matched_sources.append("Janata Board Photo")

    # 2. Check Sanction Data
    if bundle.sanction_data:
        sanc_id_val = bundle.sanction_data.work_id.get_effective_value() if bundle.sanction_data.work_id else None
        if sanc_id_val:
            sid = str(sanc_id_val).strip()
            if work_id and sid.lower() != work_id.lower():
                conflicts.append(f"Sanction order work ID '{sid}' does not match session work ID '{work_id}'")
            else:
                matched_sources.append("Sanction Order")

    # 3. Check Bills
    for bill in bundle.bills:
        if bill.work_id:
            bid = bill.work_id.strip()
            if work_id and bid.lower() != work_id.lower():
                conflicts.append(f"Bill '{bill.bill_number}' work ID '{bid}' conflicts with session work ID '{work_id}'")
            else:
                matched_sources.append(f"Bill {bill.bill_number}")

    # 4. Check Labour Records
    for lr in bundle.labour_records:
        if lr.work_id:
            lid = lr.work_id.strip()
            if work_id and lid.lower() != work_id.lower():
                conflicts.append(f"Labour record '{lr.worker_ref}' work ID '{lid}' conflicts with session work ID '{work_id}'")

    # 5. Check stage-photograph evidence ownership within the bundle.
    inventory_by_id = {ev.evidence_id: ev for ev in bundle.evidence_files}
    inventory_by_sha = {ev.sha256: ev for ev in bundle.evidence_files}
    for photo in bundle.stage_photos:
        pref = photo.evidence_reference
        if pref.evidence_id not in inventory_by_id and pref.sha256 not in inventory_by_sha:
            conflicts.append(
                f"Stage photograph '{pref.filename}' is not owned or referenced by the current work bundle."
            )
        else:
            owning_ref = inventory_by_id.get(pref.evidence_id) or inventory_by_sha.get(pref.sha256)
            if owning_ref and owning_ref.sha256 != pref.sha256:
                conflicts.append(
                    f"Stage photograph '{pref.filename}' has an evidence SHA-256 mismatch."
                )

    if conflicts:
        return False, {
            "status": "CONFLICT_DETECTED",
            "conflicts": conflicts,
            "message": "Evidence documents contain conflicting work identifiers. Cross-document comparison cannot proceed reliably.",
        }

    return True, {
        "status": "LINKAGE_VERIFIED",
        "work_id": work_id,
        "work_name": work_name,
        "matched_sources": list(set(matched_sources)),
        "message": "All supplied records are linked to the declared work identity.",
    }


# ---------------------------------------------------------------------------
# JL-01: Janata Board Completeness
# ---------------------------------------------------------------------------

def audit_jl01_board_completeness(bundle: AuditBundle) -> AuditFinding:
    """JL-01: Verifies presence of statutory worksite board fields under Schedule I, paragraph 25(2)(b)."""
    board = bundle.board_data
    if not board:
        return AuditFinding(
            finding_id="JL-01-F1",
            rule_id="JL-01",
            title="Janata Board Evidence Missing",
            status=FindingStatus.MISSING_EVIDENCE,
            severity=Severity.HIGH,
            summary="No worksite Janata Board photograph or record was supplied in the audit bundle.",
            observed_values={"janata_board_present": False},
            comparison_values={"statutory_requirement": "Mandatory worksite board under Schedule I, paragraph 25(2)(b)"},
            evidence_references=[],
            rule_source=RULE_SOURCES["JL-01"],
            human_verification_steps=[
                "Confirm whether a physical Janata Board is erected at the actual worksite.",
                "Capture and upload a clear photograph of the worksite board if available.",
            ],
        )

    # Check statutory components:
    # 1. Work details
    # 2. Estimated labour days
    # 3. Material quantities in local terminology
    # 4. Item-wise costs
    missing_fields: List[str] = []
    unreviewed_fields: List[str] = []

    # Work name / details
    work_name_val = board.work_name.get_effective_value() if board.work_name else None
    if not work_name_val:
        missing_fields.append("Work details / title")

    # Estimated labour days
    labour_days_val = board.estimated_labour_days.get_effective_value() if board.estimated_labour_days else None
    if not labour_days_val:
        missing_fields.append("Estimated labour person-days")

    # Material entries & item-wise costs
    if not board.material_entries:
        missing_fields.append("Material quantities and item-wise costs breakdown")
    else:
        # Check if item costs are populated
        items_missing_cost = [m.local_name for m in board.material_entries if m.item_cost is None]
        if items_missing_cost:
            missing_fields.append(f"Item-wise cost breakdown missing for: {', '.join(items_missing_cost)}")

    ev_refs = board.evidence_references

    if missing_fields:
        return AuditFinding(
            finding_id="JL-01-F1",
            rule_id="JL-01",
            title="Janata Board Statutory Fields Incomplete",
            status=FindingStatus.MISSING_EVIDENCE,
            severity=Severity.HIGH,
            summary=f"The worksite Janata Board record is missing required statutory disclosures: {'; '.join(missing_fields)}.",
            observed_values={
                "missing_fields": missing_fields,
                "has_labour_days": labour_days_val is not None,
                "material_entries_count": len(board.material_entries),
            },
            comparison_values={
                "statutory_mandate": "Work details, estimated labour days, material quantities, and item-wise costs (Schedule I, paragraph 25(2)(b))"
            },
            evidence_references=ev_refs,
            rule_source=RULE_SOURCES["JL-01"],
            human_verification_steps=[
                "Inspect the physical Janata Board at the worksite to check if the missing details are painted on another panel.",
                "Request the implementing agency to update the worksite board with complete item-wise costs and labour days.",
            ],
        )

    return AuditFinding(
        finding_id="JL-01-F1",
        rule_id="JL-01",
        title="Janata Board Statutory Disclosures Present",
        status=FindingStatus.CONSISTENT,
        severity=Severity.INFO,
        summary="Worksite Janata Board includes required work details, estimated labour days, material quantities, and item-wise cost breakdown.",
        observed_values={
            "work_name": str(work_name_val),
            "estimated_labour_days": str(labour_days_val),
            "material_items_count": len(board.material_entries),
        },
        comparison_values={"requirement": "Schedule I, paragraph 25(2)(b) completeness criteria"},
        evidence_references=ev_refs,
        rule_source=RULE_SOURCES["JL-01"],
        human_verification_steps=[
            "Verify legibility of the physical board during Gram Sabha field inspection.",
        ],
    )


# ---------------------------------------------------------------------------
# JL-02: Financial Expenditure vs Sanction Reconciliation
# ---------------------------------------------------------------------------

def audit_jl02_financial_reconciliation(
    bundle: AuditBundle, tolerance: Decimal = Decimal("0.00")
) -> List[AuditFinding]:
    """JL-02: Compares cumulative bills/expenditure against administrative sanction and estimates using Decimal."""
    findings: List[AuditFinding] = []
    sanction = bundle.sanction_data

    if not sanction:
        findings.append(
            AuditFinding(
                finding_id="JL-02-F1",
                rule_id="JL-02",
                title="Sanction Order Evidence Missing",
                status=FindingStatus.MISSING_EVIDENCE,
                severity=Severity.HIGH,
                summary="No administrative sanction order or technical estimate was supplied to verify expenditure against.",
                observed_values={},
                comparison_values={},
                evidence_references=[],
                rule_source=RULE_SOURCES["JL-02"],
                human_verification_steps=["Obtain the approved administrative sanction order and technical estimate/BOQ."],
            )
        )
        return findings

    # Determine approved ceiling: check original sanction and latest revised sanction
    orig_amount_field = sanction.original_sanction_amount
    orig_amount_val = orig_amount_field.get_effective_value() if orig_amount_field else None
    orig_is_verified = bool(orig_amount_field and orig_amount_field.is_eligible_for_calculation())
    if not bundle.synthetic and orig_amount_field:
        orig_is_verified = (
            orig_amount_field.reviewed_by_user
            or orig_amount_field.extraction_status in (
                ExtractionStatus.USER_CONFIRMED,
                ExtractionStatus.USER_CORRECTED,
            )
        )
    if orig_amount_field and not orig_is_verified:
        findings.append(
            AuditFinding(
                finding_id="JL-02-F1",
                rule_id="JL-02",
                title="Sanctioned Amount Unconfirmed",
                status=FindingStatus.MISSING_EVIDENCE,
                severity=Severity.HIGH,
                summary="The extracted sanctioned amount has not been confirmed and cannot enter financial reconciliation.",
                observed_values={"extraction_status": orig_amount_field.extraction_status.value},
                comparison_values={"calculation_requirement": "Sanctioned amount must be confirmed or synthetic"},
                evidence_references=sanction.evidence_references,
                rule_source=RULE_SOURCES["JL-02"],
                human_verification_steps=["Review and confirm the sanction amount against the source page, or upload a complete sanction order."],
            )
        )
        return findings
    if orig_amount_val is None:
        findings.append(
            AuditFinding(
                finding_id="JL-02-F1",
                rule_id="JL-02",
                title="Sanctioned Amount Unspecified",
                status=FindingStatus.MISSING_EVIDENCE,
                severity=Severity.MEDIUM,
                summary="The administrative sanction document does not contain an approved monetary amount.",
                observed_values={},
                comparison_values={},
                evidence_references=sanction.evidence_references,
                rule_source=RULE_SOURCES["JL-02"],
                human_verification_steps=["Inspect sanction order page 1 to verify sanctioned monetary ceiling."],
            )
        )
        return findings

    orig_sanction_amt = Decimal(str(orig_amount_val))
    effective_sanction_amt = orig_sanction_amt
    has_revised_sanction = False

    if sanction.revised_sanctions:
        # Sort revised sanctions by date or amount
        latest_revision = sanction.revised_sanctions[-1]
        if not latest_revision.evidence:
            findings.append(
                AuditFinding(
                    finding_id="JL-02-F1",
                    rule_id="JL-02",
                    title="Revised Sanction Evidence Missing",
                    status=FindingStatus.MISSING_EVIDENCE,
                    severity=Severity.HIGH,
                    summary="A revised sanction amount was supplied without a source evidence reference, so it cannot establish a revised ceiling.",
                    observed_values={"revised_amount": str(latest_revision.revised_amount)},
                    comparison_values={"requirement": "Revised sanction must link to a source document"},
                    evidence_references=sanction.evidence_references,
                    rule_source=RULE_SOURCES["JL-02"],
                    human_verification_steps=["Attach the revised sanction/revision order and verify its work identity and issue date."],
                )
            )
            return findings
        effective_sanction_amt = latest_revision.revised_amount
        has_revised_sanction = True

    # Sum compatible bills/vouchers
    if not bundle.bills:
        findings.append(
            AuditFinding(
                finding_id="JL-02-F1",
                rule_id="JL-02",
                title="Vouchers / Bills Missing for Financial Reconciliation",
                status=FindingStatus.MISSING_EVIDENCE,
                severity=Severity.LOW,
                summary="No bills or vouchers were supplied for financial expenditure comparison.",
                observed_values={"sanctioned_amount": str(effective_sanction_amt)},
                comparison_values={},
                evidence_references=sanction.evidence_references,
                rule_source=RULE_SOURCES["JL-02"],
                human_verification_steps=["Provide relevant material bills, machinery vouchers, and payment vouchers."],
            )
        )
        return findings

    missing_bill_evidence = [b.bill_number for b in bundle.bills if b.evidence is None]
    if missing_bill_evidence:
        findings.append(
            AuditFinding(
                finding_id="JL-02-F1",
                rule_id="JL-02",
                title="Bill Evidence References Missing",
                status=FindingStatus.MISSING_EVIDENCE,
                severity=Severity.HIGH,
                summary="One or more bills cannot be reconciled because no source evidence reference is attached.",
                observed_values={"bills_without_evidence": missing_bill_evidence},
                comparison_values={"requirement": "Every bill used in reconciliation must have a traceable source"},
                evidence_references=sanction.evidence_references,
                rule_source=RULE_SOURCES["JL-02"],
                human_verification_steps=["Attach the original bill/voucher file and verify each bill row belongs to the declared work."],
            )
        )
        return findings

    total_bills = Decimal("0.00")
    bill_refs: List[EvidenceReference] = []
    for b in bundle.bills:
        total_bills += b.amount
        if b.evidence:
            bill_refs.append(b.evidence)

    # Compare total bills against sanction
    diff = total_bills - effective_sanction_amt
    ev_all = _dedupe_refs(sanction.evidence_references + bill_refs)

    if diff > tolerance:
        calc_str = f"₹{total_bills:,.2f} - ₹{effective_sanction_amt:,.2f} = ₹{diff:,.2f}"
        findings.append(
            AuditFinding(
                finding_id="JL-02-F1",
                rule_id="JL-02",
                title="Cumulative Expenditure Exceeds Sanctioned Amount",
                status=FindingStatus.MISMATCH_FOUND,
                severity=Severity.HIGH,
                summary=(
                    f"Cumulative supplied bills (₹{total_bills:,.2f}) exceed the approved sanction "
                    f"(₹{effective_sanction_amt:,.2f}) by ₹{diff:,.2f}. "
                    "This discrepancy requires human review to check whether a revised sanction exists or bills include separate works."
                ),
                observed_values={
                    "cumulative_bills_total": str(total_bills),
                    "original_sanction_amount": str(orig_sanction_amt),
                    "effective_sanction_amount": str(effective_sanction_amt),
                    "has_revised_sanction": has_revised_sanction,
                    "difference": str(diff),
                },
                comparison_values={
                    "approved_ceiling": str(effective_sanction_amt),
                },
                exact_calculation=calc_str,
                evidence_references=ev_all,
                rule_source=RULE_SOURCES["JL-02"],
                human_verification_steps=[
                    "Check whether a revised technical sanction or administrative approval exists that was not supplied in this bundle.",
                    "Verify whether any included bills relate to a different phase, work code, or separate financial head.",
                    "Verify whether GST or contingency charges were accounted for in a separate estimate line item.",
                ],
            )
        )
    else:
        findings.append(
            AuditFinding(
                finding_id="JL-02-F1",
                rule_id="JL-02",
                title="Expenditure Within Approved Sanction Ceiling",
                status=FindingStatus.CONSISTENT,
                severity=Severity.INFO,
                summary=f"Cumulative bills (₹{total_bills:,.2f}) are within the approved sanction ceiling of ₹{effective_sanction_amt:,.2f}.",
                observed_values={
                    "cumulative_bills_total": str(total_bills),
                    "effective_sanction_amount": str(effective_sanction_amt),
                    "balance_unspent": str(effective_sanction_amt - total_bills),
                },
                comparison_values={"approved_ceiling": str(effective_sanction_amt)},
                exact_calculation=f"₹{effective_sanction_amt:,.2f} - ₹{total_bills:,.2f} = ₹{(effective_sanction_amt - total_bills):,.2f} headroom",
                evidence_references=ev_all,
                rule_source=RULE_SOURCES["JL-02"],
                human_verification_steps=["Reconcile remaining balance against measured physical progress at the worksite."],
            )
        )

    # Secondary check: If board has item costs and estimate has line items, compare item-level rates
    if bundle.board_data and bundle.board_data.material_entries and sanction.estimate_items:
        estimate_map = {item.description.lower().strip(): item for item in sanction.estimate_items}
        for b_item in bundle.board_data.material_entries:
            norm_key = (b_item.normalised_name or b_item.local_name).lower().strip()
            # Match directly or subphrase
            matched_est = None
            for e_desc, e_obj in estimate_map.items():
                if norm_key in e_desc or e_desc in norm_key:
                    matched_est = e_obj
                    break
            if matched_est and b_item.item_cost is not None and matched_est.amount is not None:
                item_diff = b_item.item_cost - matched_est.amount
                if abs(item_diff) > tolerance:
                    findings.append(
                        AuditFinding(
                            finding_id=f"JL-02-ITEM-{norm_key[:10]}",
                            rule_id="JL-02",
                            title=f"Material Item Cost Discrepancy: {b_item.local_name}",
                            status=FindingStatus.MISMATCH_FOUND,
                            severity=Severity.MEDIUM,
                            summary=(
                                f"Board cost for '{b_item.local_name}' (₹{b_item.item_cost:,.2f}) differs from "
                                f"approved estimate amount (₹{matched_est.amount:,.2f}) by ₹{item_diff:,.2f}."
                            ),
                            observed_values={"board_cost": str(b_item.item_cost), "estimate_cost": str(matched_est.amount)},
                            comparison_values={"approved_estimate_item": str(matched_est.amount)},
                            exact_calculation=f"₹{b_item.item_cost:,.2f} - ₹{matched_est.amount:,.2f} = ₹{item_diff:,.2f}",
                            evidence_references=_dedupe_refs(bundle.board_data.evidence_references + sanction.evidence_references),
                            rule_source=RULE_SOURCES["JL-02"],
                            human_verification_steps=["Inspect revised BOQ or local market rate adjustments."],
                        )
                    )

    return findings


# ---------------------------------------------------------------------------
# JL-03: Labour, Wage, and Delay Timeline
# ---------------------------------------------------------------------------

def audit_jl03_labour_timeline(bundle: AuditBundle) -> List[AuditFinding]:
    """JL-03: Separately evaluates Section 5(3) wage timing and the Schedule II paragraph 6 operational compensation check."""
    findings: List[AuditFinding] = []
    labour_records = bundle.labour_records

    if not labour_records:
        findings.append(
            AuditFinding(
                finding_id="JL-03-F1",
                rule_id="JL-03",
                title="Labour & Wage Records Missing",
                status=FindingStatus.MISSING_EVIDENCE,
                severity=Severity.LOW,
                summary="No muster roll or wage payment records were supplied for labour timeline review.",
                observed_values={},
                comparison_values={},
                evidence_references=[],
                rule_source=RULE_SOURCES["JL-03"],
                human_verification_steps=["Obtain muster roll closure records and bank credit/payment scrolls."],
            )
        )
        return findings

    # Check A: Section 5(3) Wage Disbursement Timing (weekly / within 14 days of work done)
    for idx, lr in enumerate(labour_records):
        f_id = f"JL-03-WAGE-{idx+1}"
        ev_refs = [lr.evidence] if lr.evidence else []

        if lr.evidence is None:
            findings.append(
                AuditFinding(
                    finding_id=f"{f_id}-A",
                    rule_id="JL-03",
                    title=f"Wage Evidence Provenance Missing: Worker {lr.worker_ref}",
                    status=FindingStatus.MISSING_EVIDENCE,
                    severity=Severity.HIGH,
                    summary=f"No source evidence reference is attached to worker '{lr.worker_ref}' wage record; disbursement conclusions cannot be established.",
                    observed_values={"worker_ref": lr.worker_ref},
                    comparison_values={"requirement": "Labour/muster/payment records must remain traceable to a source"},
                    evidence_references=[],
                    rule_source=RULE_SOURCES["JL-03"],
                    human_verification_steps=["Attach the muster roll or payment scroll and verify the worker reference belongs to the declared work."],
                )
            )
            continue

        if not lr.work_end_date:
            findings.append(
                AuditFinding(
                    finding_id=f"{f_id}-A",
                    rule_id="JL-03",
                    title=f"Work Completion Date Missing: Worker {lr.worker_ref}",
                    status=FindingStatus.MISSING_EVIDENCE,
                    severity=Severity.MEDIUM,
                    summary=f"Worker record '{lr.worker_ref}' has no work completion date to evaluate Section 5(3) timing.",
                    observed_values={"worker_ref": lr.worker_ref},
                    comparison_values={"statutory_clock": "Work end date to disbursement (<= 14 days)"},
                    evidence_references=ev_refs,
                    rule_source=RULE_SOURCES["JL-03"],
                    human_verification_steps=["Check attendance / muster roll start and end dates."],
                )
            )
            continue

        if not lr.actual_credit_date:
            # Check if only FTO processing exists
            if lr.fto_processing_date:
                findings.append(
                    AuditFinding(
                        finding_id=f"{f_id}-A",
                        rule_id="JL-03",
                        title=f"Actual Wage Credit Evidence Missing: Worker {lr.worker_ref}",
                        status=FindingStatus.NEEDS_HUMAN_REVIEW,
                        severity=Severity.MEDIUM,
                        summary=(
                            f"Worker record '{lr.worker_ref}' shows FTO processing on {lr.fto_processing_date}, "
                            "but no bank/post-office account credit date. FTO processing does not prove wage receipt."
                        ),
                        observed_values={"fto_date": str(lr.fto_processing_date), "credit_date": None},
                        comparison_values={"statutory_requirement": "Actual disbursement within 14 days (Sec 5(3))"},
                        evidence_references=ev_refs,
                        rule_source=RULE_SOURCES["JL-03"],
                        human_verification_steps=["Inspect bank response file or post office credit scroll."],
                    )
                )
            else:
                findings.append(
                    AuditFinding(
                        finding_id=f"{f_id}-A",
                        rule_id="JL-03",
                        title=f"Wage Disbursement Record Missing: Worker {lr.worker_ref}",
                        status=FindingStatus.MISSING_EVIDENCE,
                        severity=Severity.HIGH,
                        summary=f"No payment evidence exists for worker '{lr.worker_ref}' after work completed on {lr.work_end_date}.",
                        observed_values={"work_end_date": str(lr.work_end_date)},
                        comparison_values={},
                        evidence_references=ev_refs,
                        rule_source=RULE_SOURCES["JL-03"],
                        human_verification_steps=["Check whether wages were disbursed for this muster roll."],
                    )
                )
            continue

        # Both dates present: evaluate 14-day clock under Section 5(3)
        days_to_pay = (lr.actual_credit_date - lr.work_end_date).days
        if days_to_pay > 14:
            findings.append(
                AuditFinding(
                    finding_id=f"{f_id}-A",
                    rule_id="JL-03",
                    title=f"Wage Disbursement Beyond Statutory Fortnight: Worker {lr.worker_ref}",
                    status=FindingStatus.NEEDS_HUMAN_REVIEW,
                    severity=Severity.MEDIUM,
                    summary=(
                        f"Wages for worker '{lr.worker_ref}' were credited {days_to_pay} days after work completion "
                        f"(Work end: {lr.work_end_date}, Credit: {lr.actual_credit_date}). Statutory window under Section 5(3) is 14 days."
                    ),
                    observed_values={
                        "work_end_date": str(lr.work_end_date),
                        "actual_credit_date": str(lr.actual_credit_date),
                        "days_elapsed": days_to_pay,
                    },
                    comparison_values={"statutory_disbursement_window": "14 days"},
                    exact_calculation=f"{lr.actual_credit_date} - {lr.work_end_date} = {days_to_pay} days (> 14 days)",
                    evidence_references=ev_refs,
                    rule_source=RULE_SOURCES["JL-03"],
                    human_verification_steps=["Check reason for disbursement delay with Programme Officer."],
                )
            )
        else:
            findings.append(
                AuditFinding(
                    finding_id=f"{f_id}-A",
                    rule_id="JL-03",
                    title=f"Wage Disbursement Timely: Worker {lr.worker_ref}",
                    status=FindingStatus.CONSISTENT,
                    severity=Severity.INFO,
                    summary=f"Wages for worker '{lr.worker_ref}' credited within {days_to_pay} days of work completion (compliant with 14-day window).",
                    observed_values={"days_elapsed": days_to_pay},
                    comparison_values={"statutory_window": "14 days"},
                    evidence_references=ev_refs,
                    rule_source=RULE_SOURCES["JL-03"],
                    human_verification_steps=[],
                )
            )

        # Separate operational check: Schedule II Paragraph 6 compensation clock
        if not lr.muster_closure_date:
            findings.append(
                AuditFinding(
                    finding_id=f"{f_id}-B",
                    rule_id="JL-03",
                    title=f"Muster Roll Closure Date Missing: Worker {lr.worker_ref}",
                    status=FindingStatus.MISSING_EVIDENCE,
                    severity=Severity.LOW,
                    summary=f"Muster roll closure date missing for worker '{lr.worker_ref}'; delay compensation calculation cannot run.",
                    observed_values={"worker_ref": lr.worker_ref},
                    comparison_values={"compensation_clock": "15 days from muster roll closure (Schedule II)"},
                    evidence_references=ev_refs,
                    rule_source=RULE_SOURCES["JL-03"],
                    human_verification_steps=["Obtain muster roll closure timestamp from MIS record."],
                )
            )
            continue

        days_from_closure = (lr.actual_credit_date - lr.muster_closure_date).days
        if days_from_closure > 15:
            delay_days = days_from_closure - 15
            daily_rate = Decimal("0.0005")  # 0.05%
            comp_amount = (lr.wage_amount_due * daily_rate * Decimal(delay_days)).quantize(Decimal("0.01"))
            calc_str = f"₹{lr.wage_amount_due:,.2f} × 0.05% × {delay_days} days = ₹{comp_amount:,.2f}"

            findings.append(
                AuditFinding(
                    finding_id=f"{f_id}-B",
                    rule_id="JL-03",
                    title=f"Delay Compensation Applicable: Worker {lr.worker_ref}",
                    status=FindingStatus.NEEDS_HUMAN_REVIEW,
                    severity=Severity.HIGH,
                    summary=(
                        f"Wages paid {days_from_closure} days after muster closure ({delay_days} days beyond the separate Schedule II Paragraph 6 15-day operational threshold). "
                        f"The separate delay-compensation calculation indicates ₹{comp_amount:,.2f}; entitlement remains subject to human review."
                    ),
                    observed_values={
                        "muster_closure_date": str(lr.muster_closure_date),
                        "actual_credit_date": str(lr.actual_credit_date),
                        "delay_days_beyond_15": delay_days,
                        "wage_amount": str(lr.wage_amount_due),
                        "calculated_compensation": str(comp_amount),
                    },
                    comparison_values={"operational_threshold": "Separate Schedule II paragraph 6 clock: 15 days from muster closure"},
                    exact_calculation=calc_str,
                    evidence_references=ev_refs,
                    rule_source=RULE_SOURCES["JL-03"],
                    human_verification_steps=[
                        "Verify whether delay compensation was already disbursed under Schedule II paragraph 6.",
                        "Inspect delay attribution report in NREGAsoft / MIS.",
                    ],
                )
            )
        else:
            findings.append(
                AuditFinding(
                    finding_id=f"{f_id}-B",
                    rule_id="JL-03",
                    title=f"Wages Paid Within 15 Days of Muster Closure: Worker {lr.worker_ref}",
                    status=FindingStatus.CONSISTENT,
                    severity=Severity.INFO,
                    summary=f"Wages paid {days_from_closure} days after muster closure; no delay compensation triggered.",
                    observed_values={"days_from_closure": days_from_closure},
                    comparison_values={"operational_threshold": "Separate Schedule II paragraph 6 clock: 15 days"},
                    evidence_references=ev_refs,
                    rule_source=RULE_SOURCES["JL-03"],
                    human_verification_steps=[],
                )
            )

    return findings


# ---------------------------------------------------------------------------
# JL-04: Chronological Integrity
# ---------------------------------------------------------------------------

def audit_jl04_chronological_integrity(bundle: AuditBundle) -> List[AuditFinding]:
    """JL-04: Examines date consistency across sanction, expenditure, muster rolls, and photographs."""
    findings: List[AuditFinding] = []
    sanction = bundle.sanction_data

    sanction_date_val = sanction.original_sanction_date.get_effective_value() if (sanction and sanction.original_sanction_date) else None
    sanction_date: Optional[date] = None
    if sanction_date_val:
        if isinstance(sanction_date_val, date):
            sanction_date = sanction_date_val
        elif isinstance(sanction_date_val, str):
            try:
                sanction_date = datetime.strptime(sanction_date_val, "%Y-%m-%d").date()
            except ValueError:
                pass

    if not sanction_date:
        findings.append(
            AuditFinding(
                finding_id="JL-04-F1",
                rule_id="JL-04",
                title="Sanction Date Missing for Chronology Checks",
                status=FindingStatus.MISSING_EVIDENCE,
                severity=Severity.LOW,
                summary="Administrative sanction date is not available; sequence checks against sanction date cannot be performed.",
                observed_values={},
                comparison_values={},
                evidence_references=sanction.evidence_references if sanction else [],
                rule_source=RULE_SOURCES["JL-04"],
                human_verification_steps=["Inspect administrative sanction order for issuance date."],
            )
        )
        return findings

    # Check 1: Bill dates vs Sanction date
    pre_sanction_bills: List[BillVoucherRecord] = []
    for b in bundle.bills:
        if b.bill_date and b.bill_date < sanction_date:
            pre_sanction_bills.append(b)

    if pre_sanction_bills:
        details = [f"Bill {b.bill_number} ({b.bill_date})" for b in pre_sanction_bills]
        ev_refs = [b.evidence for b in pre_sanction_bills if b.evidence] + (sanction.evidence_references if sanction else [])
        findings.append(
            AuditFinding(
                finding_id="JL-04-F1",
                rule_id="JL-04",
                title="Bills Dated Prior to Administrative Sanction Date",
                status=FindingStatus.NEEDS_HUMAN_REVIEW,
                severity=Severity.HIGH,
                summary=(
                    f"Found {len(pre_sanction_bills)} bill(s) dated prior to the administrative sanction date "
                    f"({sanction_date}): {', '.join(details)}. "
                    "This chronological anomaly requires human review to confirm whether retrospective sanction was granted."
                ),
                observed_values={
                    "sanction_date": str(sanction_date),
                    "anomalous_bills": details,
                },
                comparison_values={"chronological_rule": "Bill date >= Sanction issuance date"},
                exact_calculation=f"Bill date {pre_sanction_bills[0].bill_date} < Sanction date {sanction_date}",
                evidence_references=ev_refs,
                rule_source=RULE_SOURCES["JL-04"],
                human_verification_steps=[
                    "Verify whether administrative sanction order had retrospective approval or an earlier administrative approval number.",
                    "Verify if bills were misattributed from preparatory survey expenses.",
                ],
            )
        )
    elif bundle.bills:
        findings.append(
            AuditFinding(
                finding_id="JL-04-F1",
                rule_id="JL-04",
                title="Bill Dates Chronologically Consistent with Sanction",
                status=FindingStatus.CONSISTENT,
                severity=Severity.INFO,
                summary=f"All {len(bundle.bills)} bills are dated on or after the administrative sanction date ({sanction_date}).",
                observed_values={"sanction_date": str(sanction_date), "bills_evaluated": len(bundle.bills)},
                comparison_values={"rule": "Bill date >= Sanction date"},
                evidence_references=sanction.evidence_references if sanction else [],
                rule_source=RULE_SOURCES["JL-04"],
                human_verification_steps=[],
            )
        )

    # Check 2: Stage photo capture timestamps vs Sanction date & stage sequence
    photos_with_time = [p for p in bundle.stage_photos if p.capture_timestamp]
    if len(photos_with_time) >= 2:
        # Check chronological order of declared stages
        sorted_by_stage = sorted(photos_with_time, key=lambda p: p.declared_order)
        sequence_violation = False
        violation_notes = []
        for i in range(len(sorted_by_stage) - 1):
            p1 = sorted_by_stage[i]
            p2 = sorted_by_stage[i+1]
            if p1.capture_timestamp and p2.capture_timestamp:
                if p1.capture_timestamp > p2.capture_timestamp:
                    sequence_violation = True
                    violation_notes.append(
                        f"{p1.declared_stage_label} ({p1.capture_timestamp}) is dated after {p2.declared_stage_label} ({p2.capture_timestamp})"
                    )

        if sequence_violation:
            findings.append(
                AuditFinding(
                    finding_id="JL-04-F2",
                    rule_id="JL-04",
                    title="Stage Photo Sequence Inconsistent with Declared Progress",
                    status=FindingStatus.NEEDS_HUMAN_REVIEW,
                    severity=Severity.MEDIUM,
                    summary=f"Stage photograph capture timestamps conflict with declared stage progression: {'; '.join(violation_notes)}.",
                    observed_values={"violations": violation_notes},
                    comparison_values={"rule": "Earlier declared stage photo timestamp <= later stage photo timestamp"},
                    evidence_references=[p.evidence_reference for p in photos_with_time],
                    rule_source=RULE_SOURCES["JL-04"],
                    human_verification_steps=[
                        "Check device clock settings on the field inspection camera.",
                        "Verify physical stage progress with Gram Sabha participants.",
                    ],
                )
            )

    return findings


# ---------------------------------------------------------------------------
# JL-05: Photo Reuse and Hash Comparison
# ---------------------------------------------------------------------------

def audit_jl05_photo_reuse(
    bundle: AuditBundle,
    phash_threshold: int = 8,
    dhash_threshold: int = 8,
) -> List[AuditFinding]:
    """JL-05: Compares stage photographs pairwise using exact SHA-256 and perceptual hash Hamming distances."""
    findings: List[AuditFinding] = []
    photos = bundle.stage_photos

    if len(photos) < 2:
        findings.append(
            AuditFinding(
                finding_id="JL-05-F1",
                rule_id="JL-05",
                title="Insufficient Stage Photographs for Pairwise Review",
                status=FindingStatus.MISSING_EVIDENCE,
                severity=Severity.LOW,
                summary=f"Only {len(photos)} stage photograph(s) supplied. At least two stage photographs are required to test for reuse.",
                observed_values={"photos_count": len(photos)},
                comparison_values={"minimum_required": 2},
                evidence_references=[p.evidence_reference for p in photos],
                rule_source=RULE_SOURCES["JL-05"],
                human_verification_steps=["Upload photographs for each required stage (Initial, Intermediate, Final)."],
            )
        )
        return findings

    # Pairwise comparison
    matched_pairs: List[Dict[str, Any]] = []

    for i in range(len(photos)):
        for j in range(i + 1, len(photos)):
            p1 = photos[i]
            p2 = photos[j]

            # 1. Exact SHA-256 match
            is_exact_dup = (p1.sha256 == p2.sha256)

            # 2. Perceptual hash distance (if computed)
            phash_dist = None
            dhash_dist = None

            if p1.phash and p2.phash:
                try:
                    phash_dist = bin(int(p1.phash, 16) ^ int(p2.phash, 16)).count("1")
                except Exception:
                    pass

            if p1.dhash and p2.dhash:
                try:
                    dhash_dist = bin(int(p1.dhash, 16) ^ int(p2.dhash, 16)).count("1")
                except Exception:
                    pass

            # Potential reuse condition
            is_similar = False
            reasons = []

            if is_exact_dup:
                is_similar = True
                reasons.append("Identical SHA-256 binary hash")

            if phash_dist is not None and phash_dist <= phash_threshold:
                is_similar = True
                reasons.append(f"pHash Hamming distance {phash_dist} (<= threshold {phash_threshold})")

            if dhash_dist is not None and dhash_dist <= dhash_threshold:
                is_similar = True
                reasons.append(f"dHash Hamming distance {dhash_dist} (<= threshold {dhash_threshold})")

            if is_similar:
                matched_pairs.append({
                    "photo_1": p1.declared_stage_label,
                    "photo_2": p2.declared_stage_label,
                    "p1_file": p1.evidence_reference.filename,
                    "p2_file": p2.evidence_reference.filename,
                    "reasons": reasons,
                    "phash_dist": phash_dist,
                    "dhash_dist": dhash_dist,
                    "exact_dup": is_exact_dup,
                    "evidence_refs": [p1.evidence_reference, p2.evidence_reference],
                })

    if matched_pairs:
        for idx, match in enumerate(matched_pairs):
            findings.append(
                AuditFinding(
                    finding_id=f"JL-05-F{idx+1}",
                    rule_id="JL-05",
                    title=f"Potential Stage Photograph Reuse: {match['photo_1']} vs {match['photo_2']}",
                    status=FindingStatus.NEEDS_HUMAN_REVIEW,
                    severity=Severity.HIGH,
                    summary=(
                        f"High visual similarity or identical file detected between '{match['photo_1']}' ({match['p1_file']}) "
                        f"and '{match['photo_2']}' ({match['p2_file']}): {'; '.join(match['reasons'])}. "
                        "This indicates potential photo reuse across different progress stages and requires visual human inspection."
                    ),
                    observed_values={
                        "stage_1": match["photo_1"],
                        "stage_2": match["photo_2"],
                        "file_1": match["p1_file"],
                        "file_2": match["p2_file"],
                        "phash_hamming_distance": match["phash_dist"],
                        "dhash_hamming_distance": match["dhash_dist"],
                        "exact_file_match": match["exact_dup"],
                    },
                    comparison_values={
                        "phash_threshold": phash_threshold,
                        "dhash_threshold": dhash_threshold,
                    },
                    exact_calculation=f"pHash distance={match['phash_dist']}, dHash distance={match['dhash_dist']}",
                    evidence_references=match["evidence_refs"],
                    rule_source=RULE_SOURCES["JL-05"],
                    human_verification_steps=[
                        "Compare both photographs side by side to verify if the same physical structure or view was photographed.",
                        "Check whether an identical file was accidentally uploaded twice during entry.",
                        "Inspect worksite physically to verify actual construction progress at each stage.",
                    ],
                )
            )
    else:
        findings.append(
            AuditFinding(
                finding_id="JL-05-F1",
                rule_id="JL-05",
                title="No Exact or Near-Duplicate Photo Signal Found",
                status=FindingStatus.CONSISTENT,
                severity=Severity.INFO,
                summary=f"Configured SHA-256 and perceptual-hash comparisons found no exact or near-duplicate signal among {len(photos)} stage photographs. This does not establish authenticity, location, capture date, chronology, or work progress.",
                observed_values={"photos_compared": len(photos)},
                comparison_values={"threshold": f"pHash <= {phash_threshold}, dHash <= {dhash_threshold}"},
                evidence_references=[p.evidence_reference for p in photos],
                rule_source=RULE_SOURCES["JL-05"],
                human_verification_steps=[],
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Master Audit Orchestration
# ---------------------------------------------------------------------------

def run_full_audit(bundle: AuditBundle) -> AuditReport:
    """Runs all deterministic audit rules (JL-01 to JL-05) after checking linkage."""
    now = datetime.now(timezone.utc)
    is_linked, linkage_details = validate_work_linkage(bundle)

    findings: List[AuditFinding] = []
    rules_executed: List[str] = []
    rules_skipped: Dict[str, str] = {}

    if not is_linked:
        # Stop dependent comparisons and report human review finding
        linkage_finding = AuditFinding(
            finding_id="GATE-LINKAGE",
            rule_id="GATE",
            title="Work Record Linkage Conflict",
            status=FindingStatus.NEEDS_HUMAN_REVIEW,
            severity=Severity.HIGH,
            summary=linkage_details.get("message", "Evidence documents contain conflicting work identifiers."),
            observed_values={"conflicts": linkage_details.get("conflicts", [])},
            comparison_values={"requirement": "All documents must refer to the same work/project code"},
            evidence_references=bundle.evidence_files,
            human_verification_steps=["Re-verify uploaded files to ensure they all belong to the declared work."],
        )
        findings.append(linkage_finding)
        for r in ["JL-01", "JL-02", "JL-03", "JL-04", "JL-05"]:
            rules_skipped[r] = "Skipped due to work-linkage conflicts across evidence documents"

        overall_state = "NEEDS_HUMAN_REVIEW"
    else:
        # JL-01
        findings.append(audit_jl01_board_completeness(bundle))
        rules_executed.append("JL-01")

        # JL-02
        f_jl02 = audit_jl02_financial_reconciliation(bundle)
        findings.extend(f_jl02)
        rules_executed.append("JL-02")

        # JL-03
        f_jl03 = audit_jl03_labour_timeline(bundle)
        findings.extend(f_jl03)
        rules_executed.append("JL-03")

        # JL-04
        f_jl04 = audit_jl04_chronological_integrity(bundle)
        findings.extend(f_jl04)
        rules_executed.append("JL-04")

        # JL-05
        f_jl05 = audit_jl05_photo_reuse(bundle)
        findings.extend(f_jl05)
        rules_executed.append("JL-05")

        # Determine overall state:
        statuses = [f.status for f in findings]
        if FindingStatus.MISMATCH_FOUND in statuses:
            overall_state = "MISMATCH_FOUND"
        elif FindingStatus.NEEDS_HUMAN_REVIEW in statuses:
            overall_state = "NEEDS_HUMAN_REVIEW"
        elif FindingStatus.MISSING_EVIDENCE in statuses:
            overall_state = "MISSING_EVIDENCE"
        else:
            overall_state = "CONSISTENT"

    report = AuditReport(
        session_id=f"SESS-{bundle.work_id}-{now.strftime('%Y%m%d%H%M%S')}",
        work_id=bundle.work_id,
        work_name=bundle.work_name,
        created_at=now,
        synthetic=bundle.synthetic,
        evidence_inventory=bundle.evidence_files,
        work_linkage_result=linkage_details,
        rule_execution_summary={
            "rules_executed": rules_executed,
            "rules_skipped": rules_skipped,
            "total_findings": len(findings),
        },
        findings=findings,
        overall_review_state=overall_state,
        limitations=[
            "JanataLens is an evidence-review assistant, not an official audit or fraud investigation.",
            "Calculations rely strictly on supplied and confirmed records.",
            "A mismatch or anomaly indicates a review exception, not proof of wrongdoing.",
        ],
    )
    return report
