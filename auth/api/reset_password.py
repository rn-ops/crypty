"""
Reset a local Crypty account password.

Usage:
    py -3 reset_password.py <username> <new-password>
"""

import sys

from auth_utils import hash_password
from audit import log_action
from database.db import get_connection, init_db


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: py -3 reset_password.py <username> <new-password>")
        raise SystemExit(1)

    username, password = sys.argv[1:]
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = ?, is_active = 1 WHERE username = ?",
        (hash_password(password), username),
    )
    if cursor.rowcount != 1:
        conn.close()
        print(f"User '{username}' was not found.")
        raise SystemExit(1)
    conn.commit()
    conn.close()
    log_action(username, "PASSWORD_RESET", "Password reset by local administrator")
    print(f"Password reset for '{username}'.")


if __name__ == "__main__":
    main()
