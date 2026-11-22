"""Local SQLite metadata persistence for JanataLens AI.

Stores ephemeral session and audit metadata for local development.
Does not store private worker identities, Aadhaar, or bank account numbers.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_FILE = Path("janatalens_local.db")


def init_db(db_path: Path | str = DB_FILE):
    """Initializes local SQLite metadata tables."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_sessions (
            session_id TEXT PRIMARY KEY,
            work_id TEXT,
            work_name TEXT,
            synthetic INTEGER,
            overall_state TEXT,
            created_at TEXT,
            total_findings INTEGER,
            summary_json TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS session_evidence (
            evidence_id TEXT PRIMARY KEY,
            session_id TEXT,
            filename TEXT,
            evidence_type TEXT,
            sha256 TEXT,
            file_size_bytes INTEGER,
            synthetic INTEGER,
            FOREIGN KEY (session_id) REFERENCES audit_sessions(session_id)
        )
        """
    )
    conn.commit()
    conn.close()


def save_session_record(
    session_id: str,
    work_id: str,
    work_name: str,
    synthetic: bool,
    overall_state: str,
    findings_count: int,
    summary: Dict[str, Any],
    evidence_inventory: List[Dict[str, Any]],
    db_path: Path | str = DB_FILE,
):
    """Saves session metadata and evidence references."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    now_iso = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        INSERT OR REPLACE INTO audit_sessions 
        (session_id, work_id, work_name, synthetic, overall_state, created_at, total_findings, summary_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            work_id,
            work_name,
            1 if synthetic else 0,
            overall_state,
            now_iso,
            findings_count,
            json.dumps(summary),
        ),
    )

    for ev in evidence_inventory:
        cur.execute(
            """
            INSERT OR REPLACE INTO session_evidence
            (evidence_id, session_id, filename, evidence_type, sha256, file_size_bytes, synthetic)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ev.get("evidence_id"),
                session_id,
                ev.get("filename"),
                ev.get("evidence_type"),
                ev.get("sha256"),
                ev.get("file_size_bytes"),
                1 if ev.get("synthetic") else 0,
            ),
        )

    conn.commit()
    conn.close()


def get_recent_sessions(limit: int = 10, db_path: Path | str = DB_FILE) -> List[Dict[str, Any]]:
    """Retrieves recent sessions for local review history."""
    if not Path(db_path).exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT session_id, work_id, work_name, synthetic, overall_state, created_at, total_findings
        FROM audit_sessions ORDER BY created_at DESC LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
