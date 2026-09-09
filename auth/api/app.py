"""
app.py
------
SecureForensics Authentication & Access Control API.

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

from flask import Flask, request, jsonify, g
from flask_cors import CORS

from database.db import init_db, get_connection
from auth_utils import hash_password, verify_password, generate_token
from face_auth import enroll_face, authenticate_face
from rbac import token_required, role_required
from audit import log_action, verify_chain, get_logs

app = Flask(__name__)
CORS(app)

init_db()


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
    app.run(debug=True, port=5000)
