"""
database/db.py
--------------
SQLite database setup for SecureForensics authentication system.

Tables:
  users       -> stores login credentials, role, and face-enrollment status
  audit_log   -> tamper-evident, hash-chained log of every security-relevant action
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "secureforensics.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
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
            face_enrolled INTEGER NOT NULL DEFAULT 0,
            face_label INTEGER,               -- numeric label used internally by the LBPH recognizer
            created_at TEXT DEFAULT (datetime('now')),
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)

    # NOTE (embedding migration): replaces the old LBPH model.yml/labels.txt
    # file-based storage with per-image encrypted embeddings in the DB.
    # Additive change only -- 'users' and 'audit_log' tables are untouched.
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
            entry_hash TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
