"""
audit.py
--------
Tamper-evident audit logging using a SHA-256 hash chain.

Every log entry's hash is computed from its own content PLUS the previous
entry's hash. If any past entry is edited, its hash changes, which breaks
the chain for every entry after it -- making tampering immediately detectable
by re-verification (see verify_chain()).

This mirrors the "chain of custody" requirement for forensic tools.
"""

import hashlib
import json
from database.db import get_connection

GENESIS_HASH = "0" * 64  # hash used as "previous hash" for the very first log entry


def _compute_hash(
    prev_hash: str,
    timestamp: str,
    username: str | None,
    action: str,
    details: str | None,
    account: str | None = None,
    account_plan: str | None = None,
    case_id: str | None = None,
    case_name: str | None = None,
    device_fingerprint: str | None = None,
    version: int = 1,
) -> str:
    payload_data = {
        "prev_hash": prev_hash,
        "timestamp": timestamp,
        "username": username,
        "action": action,
        "details": details,
    }
    if version >= 2:
        payload_data.update({
            "account": account,
            "account_plan": account_plan,
            "case_id": case_id,
            "case_name": case_name,
            "device_fingerprint": device_fingerprint,
        })
    payload = json.dumps(payload_data, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def log_action(
    username: str | None,
    action: str,
    details: str = "",
    *,
    account_plan: str | None = None,
    case_id: str | None = None,
    case_name: str | None = None,
    device_fingerprint: str | None = None,
    connection=None,
):
    """
    Append a new tamper-evident entry to the audit log.
    Call this after every security-relevant event:
    login attempts (success/fail), enrollments, recovery/erasure operations, etc.
    """
    owns_connection = connection is None
    conn = connection or get_connection()
    cur = conn.cursor()
    if owns_connection:
        cur.execute("BEGIN IMMEDIATE")
    if account_plan is None and username:
        user = cur.execute(
            "SELECT account_plan FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user:
            account_plan = user["account_plan"]

    cur.execute("SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    prev_hash = row["entry_hash"] if row else GENESIS_HASH

    cur.execute("SELECT datetime('now') AS ts")
    timestamp = cur.fetchone()["ts"]

    entry_hash = _compute_hash(
        prev_hash,
        timestamp,
        username,
        action,
        details,
        account=username,
        account_plan=account_plan,
        case_id=case_id,
        case_name=case_name,
        device_fingerprint=device_fingerprint,
        version=2,
    )

    cur.execute(
        "INSERT INTO audit_log (timestamp, username, action, details, prev_hash, entry_hash, "
        "account, account_plan, case_id, case_name, device_fingerprint, entry_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 2)",
        (
            timestamp, username, action, details, prev_hash, entry_hash, username,
            account_plan, case_id, case_name, device_fingerprint,
        ),
    )
    if owns_connection:
        conn.commit()
        conn.close()
    return entry_hash


def verify_chain():
    """
    Walk the entire audit log and recompute each hash to confirm the chain
    has not been tampered with. Returns (is_valid: bool, broken_at_id: int|None).
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM audit_log ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    expected_prev = GENESIS_HASH
    for row in rows:
        version = row["entry_version"] if "entry_version" in row.keys() else 1
        recomputed = _compute_hash(
            expected_prev,
            row["timestamp"],
            row["username"],
            row["action"],
            row["details"],
            row["account"] if version >= 2 else None,
            row["account_plan"] if version >= 2 else None,
            row["case_id"] if version >= 2 else None,
            row["case_name"] if version >= 2 else None,
            row["device_fingerprint"] if version >= 2 else None,
            version=version,
        )
        if row["prev_hash"] != expected_prev or row["entry_hash"] != recomputed:
            return False, row["id"]
        expected_prev = row["entry_hash"]

    return True, None


def get_logs(limit: int | None = None):
    conn = get_connection()
    cur = conn.cursor()
    columns = (
        "SELECT id, timestamp, username, account, account_plan, case_id, case_name, "
        "device_fingerprint, action, details, entry_hash FROM audit_log ORDER BY id DESC"
    )
    if limit is None:
        cur.execute(columns)
    else:
        cur.execute(columns + " LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
