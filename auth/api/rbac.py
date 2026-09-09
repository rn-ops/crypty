"""
rbac.py
-------
Role-Based Access Control decorators for Flask routes.

Usage:
    @app.route("/api/erasure/run")
    @token_required
    @role_required("admin")
    def run_erasure():
        ...
"""

from functools import wraps
from flask import request, jsonify, g
import jwt as pyjwt
from auth_utils import decode_token
from audit import log_action


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401

        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
        except pyjwt.ExpiredSignatureError:
            return jsonify({"error": "Session token expired, please log in again"}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({"error": "Invalid session token"}), 401

        g.current_user = payload["username"]
        g.current_role = payload["role"]
        return f(*args, **kwargs)
    return decorated


def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.current_role not in allowed_roles:
                log_action(g.current_user, "ACCESS_DENIED",
                           f"Attempted to access {request.path} requiring role(s) {allowed_roles}")
                return jsonify({"error": "Insufficient permissions for this operation"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
