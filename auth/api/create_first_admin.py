"""
create_first_admin.py
----------------------
Run this ONCE, directly on the server, to create the very first admin account.

Why this exists: /api/admin/register requires an admin JWT to call it (correctly,
since only an admin should create users) -- but that means there must already
be one admin account to bootstrap the system. This script creates that first
account directly in the database, bypassing the API.

Usage:
    python create_first_admin.py <username> <password>
"""

import sys
from database.db import init_db, get_connection
from auth_utils import hash_password
from audit import log_action

def main():
    if len(sys.argv) != 3:
        print("Usage: python create_first_admin.py <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]
    init_db()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cur.fetchone():
        print(f"User '{username}' already exists.")
        conn.close()
        sys.exit(1)

    cur.execute(
        "INSERT INTO users (username, password_hash, role, face_label) VALUES (?, ?, 'admin', 0)",
        (username, hash_password(password)),
    )
    conn.commit()
    conn.close()

    log_action(username, "USER_REGISTERED", "Bootstrap: first admin account created")
    print(f"First admin account '{username}' created successfully.")
    print("You can now log in via POST /api/auth/login and use the returned token "
          "to register further users via /api/admin/register.")

if __name__ == "__main__":
    main()
