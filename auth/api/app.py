"""
app.py
------
Crypty Authentication & Access Control API.

Endpoints:
  POST /api/admin/register        (admin only) create a new user with password + role
  POST /api/admin/enroll-face     (admin only) enroll/update a user's face data
  POST /api/auth/login            username + password  -> JWT
  POST /api/auth/login-face       username + face image -> JWT
  GET  /api/audit/logs            (admin/auditor) view audit trail
  GET  /api/audit/verify          (admin/auditor) verify audit log has not been tampered with
  GET  /api/recovery/run          (admin/investigator) example protected recovery-module endpoint
  GET  /api/erasure/run           (admin only)          example protected erasure-module endpoint

Run:
  python app.py
Then see README.md for example curl requests / test_client.py for a full demo flow.
"""

import hmac
import json
import os
import re
import sqlite3
import uuid

from flask import Flask, request, jsonify, g
from flask_cors import CORS

from database.db import init_db, get_connection
from auth_utils import hash_password, verify_password, generate_token
from rbac import token_required, role_required
from audit import log_action, verify_chain, get_logs

app = Flask(__name__)
CORS(app)

init_db()


def _account_plan(username):
    conn = get_connection()
    row = conn.execute(
        "SELECT account_plan FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return row["account_plan"] if row else None


def _case_payload(conn, case_row):
    devices = conn.execute(
        "SELECT device_fingerprint, name, filesystem, capacity, attached_at "
        "FROM case_devices WHERE case_id = ? ORDER BY attached_at DESC",
        (case_row["id"],),
    ).fetchall()
    return {
        "id": case_row["id"],
        "name": case_row["name"],
        "category": case_row["category"],
        "reference": case_row["reference"],
        "operator": case_row["operator"],
        "scope": case_row["scope"],
        "created_at": case_row["created_at"],
        "devices": [
            {
                "identity": device["device_fingerprint"],
                "fingerprint": device["device_fingerprint"],
                "name": device["name"],
                "filesystem": device["filesystem"],
                "capacity": device["capacity"],
                "attached_at": device["attached_at"],
            }
            for device in devices
        ],
    }


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"service": "Crypty authentication", "status": "ok"}), 200


# ------------------------------------------------------------------
# WEBSITE: public plan catalogue and service-authenticated registration
# ------------------------------------------------------------------
@app.route("/api/plans", methods=["GET"])
def plans():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, rank, price_inr, features FROM plans ORDER BY rank"
    ).fetchall()
    conn.close()
    return jsonify([
        {
            "id": row["id"],
            "name": row["name"],
            "rank": row["rank"],
            "price_inr": row["price_inr"],
            "features": json.loads(row["features"]),
        }
        for row in rows
    ]), 200


@app.route("/api/internal/signup", methods=["POST"])
def website_signup():
    service_key = os.environ.get("CRYPTY_SERVICE_KEY", "")
    supplied_key = request.headers.get("X-Service-Key", "")
    if not service_key:
        return jsonify({"error": "Website registration is not configured."}), 503
    if not supplied_key or not hmac.compare_digest(service_key, supplied_key):
        return jsonify({"error": "Invalid website service credentials."}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON account request is required."}), 400

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    plan_id = data.get("plan_id")
    if not isinstance(plan_id, str):
        return jsonify({"error": "Choose a valid account plan."}), 400
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", username):
        return jsonify({"error": "Username must be 3-64 characters: letters, numbers, dot, underscore, or hyphen."}), 400
    if not isinstance(email, str) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({"error": "A valid email address is required."}), 400
    if len(email) > 320:
        return jsonify({"error": "Email address is too long."}), 400
    if not isinstance(password, str) or len(password) < 10:
        return jsonify({"error": "Password must be at least 10 characters."}), 400
    if len(password.encode("utf-8")) > 72:
        return jsonify({"error": "Password must not exceed 72 UTF-8 bytes."}), 400

    password_hash = hash_password(password)
    conn = get_connection()
    plan = conn.execute(
        "SELECT id, name FROM plans WHERE id = ?", (plan_id,)
    ).fetchone()
    if not plan:
        conn.close()
        return jsonify({"error": "Choose a valid account plan."}), 400
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO users (username, password_hash, role, email, account_plan) "
                "VALUES (?, ?, 'investigator', ?, ?)",
                (username, password_hash, email, plan["id"]),
            )
            log_action(
                username,
                "ACCOUNT_CREATED",
                "Account created through the Crypty website.",
                account_plan=plan["id"],
                connection=conn,
            )
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            return jsonify({"error": "That username or email is already registered."}), 409
        raise
    finally:
        conn.close()
    return jsonify({
        "message": "Account created. You can now sign in to the Crypty desktop app.",
        "account": {"username": username, "email": email, "plan_id": plan["id"], "plan_name": plan["name"]},
    }), 201


# ------------------------------------------------------------------
# WEBSITE: account profile
# ------------------------------------------------------------------
@app.route("/api/account/me", methods=["GET"])
@token_required
def account_me():
    conn = get_connection()
    user = conn.execute(
        "SELECT username, email, role, account_plan FROM users WHERE username = ?",
        (g.current_user,),
    ).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "Account not found."}), 404
    plan = conn.execute(
        "SELECT name FROM plans WHERE id = ?", (user["account_plan"],)
    ).fetchone() if user["account_plan"] else None
    conn.close()
    return jsonify({
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "plan": {
            "id": user["account_plan"],
            "name": plan["name"] if plan else None,
            "status": "active" if user["account_plan"] else "none",
            "expires_at": None,
        },
        "options": [],
        "open_order": None,
    }), 200


# ------------------------------------------------------------------
# CASES: user-scoped case register and device association
# ------------------------------------------------------------------
@app.route("/api/cases", methods=["GET"])
@token_required
@role_required("admin", "investigator")
def list_cases():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM cases WHERE account = ? ORDER BY created_at DESC, id DESC",
        (g.current_user,),
    ).fetchall()
    result = [_case_payload(conn, row) for row in rows]
    conn.close()
    return jsonify(result), 200


@app.route("/api/cases", methods=["POST"])
@token_required
@role_required("admin", "investigator")
def create_case():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON case request is required."}), 400
    name = data.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        return jsonify({"error": "Case name must contain 1-200 characters."}), 400

    case = {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "category": str(data.get("category", "")).strip()[:100],
        "reference": str(data.get("reference", "")).strip()[:200],
        "operator": str(data.get("operator", "")).strip()[:100],
        "scope": str(data.get("scope", "")).strip()[:4000],
    }
    conn = get_connection()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO cases (id, account, name, category, reference, operator, scope) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    case["id"], g.current_user, case["name"], case["category"],
                    case["reference"], case["operator"], case["scope"],
                ),
            )
            user_plan = conn.execute(
                "SELECT account_plan FROM users WHERE username = ?",
                (g.current_user,),
            ).fetchone()["account_plan"]
            log_action(
                g.current_user,
                "CASE_CREATED",
                f"Created case '{case['name']}'.",
                account_plan=user_plan,
                case_id=case["id"],
                case_name=case["name"],
                connection=conn,
            )
            case_row = conn.execute(
                "SELECT * FROM cases WHERE id = ?", (case["id"],)
            ).fetchone()
            result = _case_payload(conn, case_row)
    finally:
        conn.close()
    return jsonify(result), 201


@app.route("/api/cases/<case_id>/devices", methods=["POST"])
@token_required
@role_required("admin", "investigator")
def attach_case_device(case_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON device request is required."}), 400
    fingerprint = data.get("device_fingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", fingerprint):
        return jsonify({"error": "A SHA-256 device fingerprint is required."}), 400

    conn = get_connection()
    case_row = conn.execute(
        "SELECT * FROM cases WHERE id = ? AND account = ?",
        (case_id, g.current_user),
    ).fetchone()
    if not case_row:
        conn.close()
        return jsonify({"error": "Case not found."}), 404
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO case_devices (case_id, device_fingerprint, name, filesystem, capacity) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    case_id,
                    fingerprint.lower(),
                    str(data.get("name", "")).strip()[:200],
                    str(data.get("filesystem", "")).strip()[:50],
                    str(data.get("capacity", "")).strip()[:50],
                ),
            )
            user_plan = conn.execute(
                "SELECT account_plan FROM users WHERE username = ?",
                (g.current_user,),
            ).fetchone()["account_plan"]
            log_action(
                g.current_user,
                "DEVICE_ATTACHED",
                f"Attached device '{str(data.get('name', '')).strip()[:200]}'.",
                account_plan=user_plan,
                case_id=case_id,
                case_name=case_row["name"],
                device_fingerprint=fingerprint.lower(),
                connection=conn,
            )
            result = _case_payload(conn, case_row)
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            return jsonify({"error": "This device is already attached to the case."}), 409
        raise
    finally:
        conn.close()
    return jsonify(result), 201


@app.route("/api/audit/events", methods=["POST"])
@token_required
@role_required("admin", "investigator")
def create_audit_event():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON audit event is required."}), 400
    action = data.get("action")
    if not isinstance(action, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", action):
        return jsonify({"error": "Audit action must be an uppercase action code."}), 400

    case_id = data.get("case_id")
    if case_id is not None and not isinstance(case_id, str):
        return jsonify({"error": "Case id must be a string."}), 400
    case_name = None
    fingerprint = data.get("device_fingerprint")
    if fingerprint is not None and (
        not isinstance(fingerprint, str)
        or not re.fullmatch(r"[a-fA-F0-9]{64}", fingerprint)
    ):
        return jsonify({"error": "Device fingerprint must be a SHA-256 fingerprint."}), 400
    if case_id is not None:
        conn = get_connection()
        case_row = conn.execute(
            "SELECT name FROM cases WHERE id = ? AND account = ?",
            (case_id, g.current_user),
        ).fetchone()
        if not case_row:
            conn.close()
            return jsonify({"error": "Case not found."}), 404
        case_name = case_row["name"]
        if fingerprint is not None:
            linked = conn.execute(
                "SELECT 1 FROM case_devices WHERE case_id = ? AND device_fingerprint = ?",
                (case_id, fingerprint.lower()),
            ).fetchone()
            if not linked:
                conn.close()
                return jsonify({"error": "Device is not attached to this case."}), 400
        conn.close()

    details = data.get("details", "")
    if not isinstance(details, str) or len(details) > 2000:
        return jsonify({"error": "Audit details must be text of at most 2000 characters."}), 400
    log_action(
        g.current_user,
        action,
        details,
        account_plan=_account_plan(g.current_user),
        case_id=case_id,
        case_name=case_name,
        device_fingerprint=fingerprint.lower() if fingerprint else None,
    )
    return jsonify({"message": "Audit event recorded."}), 201

# ------------------------------------------------------------------
# ADMIN: create a new user (password-based credentials + assigned role)
# ------------------------------------------------------------------
@app.route("/api/admin/register", methods=["POST"])
@token_required
@role_required("admin")
def register_user():
    data = request.get_json(force=True)
    username = data.get("username")
    password = data.get("password")
    role = data.get("role")

    if not username or not password or role not in ("admin", "investigator", "auditor"):
        return jsonify({"error": "username, password, and a valid role are required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cur.fetchone():
        conn.close()
        return jsonify({"error": "Username already exists"}), 409

    cur.execute("SELECT COALESCE(MAX(face_label), -1) + 1 AS next_label FROM users")
    next_label = cur.fetchone()["next_label"]

    cur.execute(
        "INSERT INTO users (username, password_hash, role, face_label) VALUES (?, ?, ?, ?)",
        (username, hash_password(password), role, next_label),
    )
    conn.commit()
    conn.close()

    log_action(g.current_user, "USER_REGISTERED", f"Created user '{username}' with role '{role}'")
    return jsonify({"message": f"User '{username}' registered successfully", "face_label": next_label}), 201


# ------------------------------------------------------------------
# ADMIN: enroll a user's face (send 3+ base64 images captured client-side)
# ------------------------------------------------------------------
@app.route("/api/admin/enroll-face", methods=["POST"])
@token_required
@role_required("admin")
def enroll_face_route():
    from face_auth import enroll_face

    data = request.get_json(force=True)
    username = data.get("username")
    images = data.get("images", [])  # list of base64-encoded image strings

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT face_label FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    try:
        enroll_face(username, row["face_label"], images)
    except ValueError as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

    cur.execute("UPDATE users SET face_enrolled = 1 WHERE username = ?", (username,))
    conn.commit()
    conn.close()

    log_action(g.current_user, "FACE_ENROLLED", f"Enrolled face data for user '{username}'")
    return jsonify({"message": f"Face enrolled for '{username}'"}), 200


# ------------------------------------------------------------------
# LOGIN: password-based (fallback / initial method)
# ------------------------------------------------------------------
@app.route("/api/auth/login", methods=["POST"])
def login_password():
    data = request.get_json(force=True)
    username = data.get("username")
    password = data.get("password")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,))
    user = cur.fetchone()
    conn.close()

    if not user or not verify_password(password, user["password_hash"]):
        log_action(username or "unknown", "LOGIN_FAILED", "Invalid username or password")
        return jsonify({"error": "Invalid username or password"}), 401

    token = generate_token(user["username"], user["role"])
    log_action(user["username"], "LOGIN_SUCCESS", "Authenticated via password")
    return jsonify({"token": token, "role": user["role"]}), 200


# ------------------------------------------------------------------
# LOGIN: face-based
# ------------------------------------------------------------------
@app.route("/api/auth/login-face", methods=["POST"])
def login_face():
    from face_auth import authenticate_face

    data = request.get_json(force=True)
    username = data.get("username")
    image = data.get("image")  # single base64 image from live capture

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,))
    user = cur.fetchone()
    conn.close()

    if not user:
        log_action(username or "unknown", "LOGIN_FAILED", "Unknown username (face login)")
        return jsonify({"error": "Invalid username"}), 401

    if not user["face_enrolled"]:
        return jsonify({"error": "Face authentication is not set up for this user"}), 400

    try:
        success, confidence, message = authenticate_face(username, image)
    except ValueError as e:
        log_action(username, "LOGIN_FAILED", f"Face login error: {e}")
        return jsonify({"error": str(e)}), 400

    if not success:
        log_action(username, "LOGIN_FAILED", f"Face mismatch ({message}, confidence={confidence})")
        return jsonify({"error": message}), 401

    token = generate_token(user["username"], user["role"])
    log_action(user["username"], "LOGIN_SUCCESS", f"Authenticated via face (confidence={confidence:.2f})")
    return jsonify({"token": token, "role": user["role"], "confidence": confidence}), 200


# ------------------------------------------------------------------
# AUDIT: view logs (admin + auditor)
# ------------------------------------------------------------------
@app.route("/api/audit/logs", methods=["GET"])
@token_required
@role_required("admin", "auditor")
def audit_logs():
    return jsonify(get_logs()), 200


# ------------------------------------------------------------------
# AUDIT: verify chain integrity (admin + auditor)
# ------------------------------------------------------------------
@app.route("/api/audit/verify", methods=["GET"])
@token_required
@role_required("admin", "auditor")
def audit_verify():
    is_valid, broken_at = verify_chain()
    if is_valid:
        return jsonify({"valid": True, "message": "Audit log chain is intact"}), 200
    return jsonify({"valid": False, "message": f"Tampering detected at log entry id={broken_at}"}), 200


# ------------------------------------------------------------------
# EXAMPLE PROTECTED MODULE ROUTES (placeholders for Recovery / Erasure modules)
# ------------------------------------------------------------------
@app.route("/api/recovery/run", methods=["GET"])
@token_required
@role_required("admin", "investigator")
def run_recovery():
    log_action(g.current_user, "RECOVERY_INITIATED", "Recovery module accessed")
    return jsonify({"message": f"Recovery module access granted to '{g.current_user}' ({g.current_role})"}), 200


@app.route("/api/erasure/run", methods=["GET"])
@token_required
@role_required("admin")
def run_erasure():
    log_action(g.current_user, "ERASURE_INITIATED", "Erasure module accessed")
    return jsonify({"message": f"Erasure module access granted to '{g.current_user}' ({g.current_role})"}), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
