"""Report generator for JanataLens AI.

Serializes the actual AuditReport object into:
1. Machine-readable JSON report
2. Evidence-backed Markdown audit report
Never creates a hardcoded template of expected outcomes.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from src.schemas import AuditReport, FindingStatus
from src.finding_status import map_finding_display_state


def generate_json_report(report: AuditReport) -> str:
    """Serializes the complete AuditReport into formatted JSON."""
    payload = report.model_dump()
    payload["display_statuses"] = {
        finding.finding_id: map_finding_display_state(finding, report=report)
        for finding in report.findings
    }
    return json.dumps(payload, indent=2, default=str)


def generate_markdown_report(report: AuditReport) -> str:
    """Generates an evidence-backed Markdown report from the AuditReport object."""
    lines = []

    # Watermark
    if report.synthetic:
        lines.append("> ⚠️ **SYNTHETIC DEMO DATA — NOT AN OFFICIAL GOVERNMENT RECORD**")
        lines.append("> Generated for demonstration and software testing purposes under JanataLens AI.\n")

    lines.append(f"# JanataLens AI — Audit Review Report")
    lines.append(f"**Session ID:** `{report.session_id}`  ")
    lines.append(f"**Work Identity / Project Code:** `{report.work_id or 'Unspecified'}`  ")
    lines.append(f"**Work Title:** {report.work_name or 'Unspecified'}  ")
    lines.append(f"**Generated At:** {report.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}  ")
    lines.append(f"**Spec / Engine Version:** {report.spec_version} (App v{report.application_version})  ")
    lines.append(f"**Overall Review State:** **`{report.overall_review_state}`**\n")

    # Important Disclaimer
    lines.append("---")
    lines.append("### Important Review Notice & Product Boundary")
    lines.append(
        "JanataLens is an evidence-review assistant designed to assist community reviewers and social-audit facilitators. "
        "It is **not** a government portal, an official audit authority, a legal decision-maker, or a fraud detector. "
        "All calculations and findings indicate review exceptions requiring human verification.\n"
    )

    # Executive Summary
    lines.append("## 1. Audit Summary")
    exec_summary = report.rule_execution_summary
    rules_exec = ", ".join(exec_summary.get("rules_executed", [])) or "None"
    rules_skip = exec_summary.get("rules_skipped", {})

    status_counts: Dict[str, int] = {}
    for f in report.findings:
        status_counts[f.status.value] = status_counts.get(f.status.value, 0) + 1

    lines.append(f"- **Rules Executed:** {rules_exec}")
    lines.append(f"- **Total Findings:** {len(report.findings)}")
    for st, count in status_counts.items():
        lines.append(f"  - `{st}`: {count}")

    if rules_skip:
        lines.append("\n**Rules Skipped:**")
        for r_id, reason in rules_skip.items():
            lines.append(f"- `{r_id}`: {reason}")
    lines.append("")

    # Work Linkage
    lines.append("## 2. Work Identity & Record Linkage")
    linkage = report.work_linkage_result
    lines.append(f"- **Linkage Status:** `{linkage.get('status', 'UNVERIFIED')}`")
    lines.append(f"- **Details:** {linkage.get('message', 'N/A')}")
    if linkage.get("conflicts"):
        lines.append("- **Conflicts Flagged:**")
        for conf in linkage["conflicts"]:
            lines.append(f"  - ⚠️ {conf}")
    lines.append("")

    # Evidence Inventory
    lines.append("## 3. Evidence Inventory")
    if not report.evidence_inventory:
        lines.append("*No files registered in evidence inventory.*")
    else:
        lines.append("| Filename | Category | SHA-256 (first 12) | Size (bytes) | Synthetic |")
        lines.append("|---|---|---|---|---|")
        for ev in report.evidence_inventory:
            lines.append(
                f"| `{ev.filename}` | `{ev.evidence_type.value}` | `{ev.sha256[:12]}...` | {ev.file_size_bytes:,} | {'Yes' if ev.synthetic else 'No'} |"
            )
        lines.append(
            "\nSource-file SHA-256 values identify the supplied file. They do not uniquely identify individual CSV rows."
        )
    lines.append("")

    # Detailed Findings
    lines.append("## 4. Audit Findings & Reconciliations")
    if not report.findings:
        lines.append("*No findings generated.*")
    else:
        for idx, f in enumerate(report.findings, start=1):
            badge = "VERIFIED" if f.status == FindingStatus.CONSISTENT else ("INCONSISTENT" if f.status == FindingStatus.MISMATCH_FOUND else ("MISSING" if f.status == FindingStatus.MISSING_EVIDENCE else "UNVERIFIED"))
            lines.append(f"### Finding {idx}: {badge} [{f.rule_id}] {f.title}")
            display_state = map_finding_display_state(f, report=report)
            lines.append(
                f"- **Engine Status:** `{f.status.value}` | "
                f"**Display State:** `{display_state}` | **Severity:** `{f.severity.value}`"
            )
            lines.append(f"- **Summary:** {f.summary}")
            if f.exact_calculation:
                lines.append(f"- **Exact Calculation:** `{f.exact_calculation}`")

            # Observed & Comparison values
            if f.observed_values:
                lines.append(f"- **Observed Values:** `{json.dumps(f.observed_values)}`")
            if f.comparison_values:
                lines.append(f"- **Comparison Standard:** `{json.dumps(f.comparison_values)}`")

            # Rule Source
            if f.rule_source:
                lines.append(
                    f"- **Statutory / Rule Source:** {f.rule_source.section_reference} ({f.rule_source.issuing_authority})"
                )

            # Evidence References
            if f.evidence_references:
                lines.append("- **Supporting Evidence:**")
                for ev in f.evidence_references:
                    pg_str = f" (Page {ev.page_number})" if ev.page_number else ""
                    row_str = f" (Row {ev.row_number})" if ev.row_number else ""
                    lines.append(f"  - `{ev.filename}`{pg_str}{row_str} [SHA-256: `{ev.sha256[:8]}`]")

            # Human Verification Steps
            if f.human_verification_steps:
                lines.append("- **Recommended Human Verification Steps:**")
                for step in f.human_verification_steps:
                    lines.append(f"  1. {step}")

            lines.append("")

    # Plain language explanation
    if report.explanation_en:
        lines.append("## 5. Reviewer Summary (English)")
        lines.append(report.explanation_en)
        lines.append("")

    if report.explanation_te:
        lines.append("## 6. Reviewer Summary (తెలుగు / Telugu)")
        lines.append(report.explanation_te)
        lines.append("")

    # Limitations & Legal Framework
    lines.append("## 7. Limitations & Framework Notes")
    for lim in report.limitations:
        lines.append(f"- {lim}")

    lines.append("\n---\n*Report generated deterministically by JanataLens AI.*")

    return "\n".join(lines)
