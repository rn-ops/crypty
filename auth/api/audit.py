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


def _compute_hash(prev_hash: str, timestamp: str, username: str, action: str, details: str) -> str:
    payload = json.dumps({
        "prev_hash": prev_hash,
        "timestamp": timestamp,
        "username": username,
        "action": action,
        "details": details,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def log_action(username: str, action: str, details: str = ""):
    """
    Append a new tamper-evident entry to the audit log.
    Call this after every security-relevant event:
    login attempts (success/fail), enrollments, recovery/erasure operations, etc.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    prev_hash = row["entry_hash"] if row else GENESIS_HASH

    cur.execute("SELECT datetime('now') AS ts")
    timestamp = cur.fetchone()["ts"]

    entry_hash = _compute_hash(prev_hash, timestamp, username, action, details)

    cur.execute(
        "INSERT INTO audit_log (timestamp, username, action, details, prev_hash, entry_hash) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (timestamp, username, action, details, prev_hash, entry_hash),
    )
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
        recomputed = _compute_hash(expected_prev, row["timestamp"], row["username"],
                                    row["action"], row["details"])
        if row["prev_hash"] != expected_prev or row["entry_hash"] != recomputed:
            return False, row["id"]
        expected_prev = row["entry_hash"]

    return True, None


def get_logs(limit: int = 200):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, timestamp, username, action, details, entry_hash FROM audit_log "
                "ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
