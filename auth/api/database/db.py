"""
database/db.py
--------------
SQLite database setup for Crypty authentication system.

Tables:
  users       -> stores login credentials, role, and face-enrollment status
  audit_log   -> tamper-evident, hash-chained log of every security-relevant action
"""

import sqlite3
import os
import sys
from pathlib import Path

_LEGACY_DB_PATH = Path(__file__).resolve().with_name("secureforensics.db")


def _default_db_path() -> Path:
    configured_path = os.environ.get("CRYPTY_AUTH_DB")
    if configured_path:
        return Path(configured_path).expanduser()
    if _LEGACY_DB_PATH.is_file():
        return _LEGACY_DB_PATH

    if sys.platform == "win32":
        data_root = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
    elif sys.platform == "darwin":
        data_root = Path.home() / "Library" / "Application Support"
    else:
        data_root = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        )
    return data_root / "Crypty" / "secureforensics.db"


DB_PATH = _default_db_path()


def get_connection():
    db_path = Path(DB_PATH).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they do not already exist. Safe to call on every startup."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'investigator', 'auditor')),
            email TEXT UNIQUE,
            account_plan TEXT,
            face_enrolled INTEGER NOT NULL DEFAULT 0,
            face_label INTEGER,               -- numeric label used internally by the LBPH recognizer
            created_at TEXT DEFAULT (datetime('now')),
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)

    user_columns = {row["name"] for row in cur.execute("PRAGMA table_info(users)")}
    if "email" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "account_plan" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN account_plan TEXT")
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique "
        "ON users(email) WHERE email IS NOT NULL"
    )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            rank INTEGER NOT NULL,
            price_inr INTEGER,
            features TEXT NOT NULL
        )
    """)
    default_plans = (
        ("starter", "Starter", 1, None, '["case_management", "audit_logging"]'),
        ("professional", "Professional", 2, None, '["case_management", "audit_logging", "recovery"]'),
        ("organization", "Organization", 3, None, '["case_management", "audit_logging", "recovery", "sanitization"]'),
    )
    cur.executemany(
        "INSERT OR IGNORE INTO plans (id, name, rank, price_inr, features) VALUES (?, ?, ?, ?, ?)",
        default_plans,
    )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY,
            account TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            reference TEXT NOT NULL DEFAULT '',
            operator TEXT NOT NULL DEFAULT '',
            scope TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (account) REFERENCES users(username)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS case_devices (
            case_id TEXT NOT NULL,
            device_fingerprint TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            filesystem TEXT NOT NULL DEFAULT '',
            capacity TEXT NOT NULL DEFAULT '',
            attached_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (case_id, device_fingerprint),
            FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
        )
    """)

    # NOTE (embedding migration): replaces the old LBPH model.yml/labels.txt
    # file-based storage with per-image encrypted embeddings in the DB.
    # Additive migration preserves user and audit rows.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS face_embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            embedding_ciphertext TEXT NOT NULL,   -- base64 AES-GCM ciphertext (includes auth tag)
            embedding_nonce TEXT NOT NULL,        -- base64 96-bit nonce, unique per encryption
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (username) REFERENCES users(username)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (datetime('now')),
            username TEXT,
            action TEXT NOT NULL,
            details TEXT,
            prev_hash TEXT NOT NULL,
            entry_hash TEXT NOT NULL,
            account TEXT,
            account_plan TEXT,
            case_id TEXT,
            case_name TEXT,
            device_fingerprint TEXT,
            entry_version INTEGER NOT NULL DEFAULT 1
        )
    """)

    audit_columns = {row["name"] for row in cur.execute("PRAGMA table_info(audit_log)")}
    for column, definition in (
        ("account", "TEXT"),
        ("account_plan", "TEXT"),
        ("case_id", "TEXT"),
        ("case_name", "TEXT"),
        ("device_fingerprint", "TEXT"),
        ("entry_version", "INTEGER NOT NULL DEFAULT 1"),
    ):
        if column not in audit_columns:
            cur.execute(f"ALTER TABLE audit_log ADD COLUMN {column} {definition}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
