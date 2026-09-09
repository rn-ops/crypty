"""
auth_utils.py
-------------
Password hashing (bcrypt) and JWT session token generation/validation.
"""

import bcrypt
import jwt
import datetime
import os

# In production, load this from an environment variable / secrets manager --
# never hardcode it in source control.
JWT_SECRET = os.environ.get("SECUREFORENSICS_JWT_SECRET", "CHANGE_THIS_SECRET_BEFORE_DEPLOYMENT")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 30


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_token(username: str, role: str) -> str:
    payload = {
        "username": username,
        "role": role,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=JWT_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str):
    """Returns the decoded payload, or raises jwt exceptions on invalid/expired tokens."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
