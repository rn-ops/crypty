# SecureForensics — Authentication & Access Control Module

This is the **security/authentication layer** for the SecureForensics project
(Integrated Secure Data Erasure and Advanced File Recovery Tool). It sits in
front of the Recovery and Erasure modules and enforces:

1. **Face recognition login** (with password fallback) — **now using genuine
   128-D SFace embeddings**, replacing the earlier LBPH implementation
2. **Role-Based Access Control (RBAC)** — Admin / Investigator / Auditor
3. **Tamper-evident, hash-chained audit logging** of every action

> **v2 migration note:** Face recognition was upgraded from OpenCV LBPH
> (a texture-histogram classifier, not a true embedding) to OpenCV
> **YuNet (detector) + SFace (recognizer)**, which produces genuine
> 128-dimensional face embeddings, AES-256-GCM encrypted at rest. The Flask
> API contract (`/api/admin/enroll-face`, `/api/auth/login-face`), JWT
> issuance, RBAC, and audit logging are unchanged — see "What Changed and
> Why" below.

---

## Folder Structure

```
secureforensics_auth/
├── app.py                     # Flask API — all routes (UNCHANGED in this migration)
├── auth_utils.py               # password hashing (bcrypt) + JWT tokens (UNCHANGED)
├── face_auth.py                 # v2: YuNet + SFace 128-D embeddings, AES-GCM storage (REWRITTEN)
├── rbac.py                       # @token_required / @role_required decorators (UNCHANGED)
├── audit.py                       # SHA-256 hash-chained audit logging (UNCHANGED)
├── download_models.py              # NEW — one-time script to fetch YuNet/SFace .onnx files
├── create_first_admin.py            # one-time bootstrap script (UNCHANGED)
├── test_client.py                    # end-to-end demo script (UNCHANGED)
├── .env.example                       # NEW — documents required environment variables
├── database/
│   └── db.py                           # UPDATED — added face_embeddings table only
├── models/                              # YuNet + SFace .onnx files go here (see Model Setup)
├── tests/
│   ├── test_face_auth.py                 # NEW — full test suite (see Testing section)
│   └── fixtures/person_a/, person_b/       # you provide real face photos here (optional)
└── requirements.txt                          # UPDATED — added `cryptography`
```

## Setup

```bash
pip install -r requirements.txt

# NEW STEP — one-time download of the YuNet + SFace model files.
# These are NOT bundled in this project (see "Model Setup" below for why).
# Requires normal internet access; verifies SHA-256 checksums automatically.
python download_models.py

# NEW STEP — set required secrets as environment variables.
# Copy .env.example to .env and fill in real values, or export directly:
export SECUREFORENSICS_JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export SECUREFORENSICS_FACE_ENC_KEY="$(python -c 'import os,base64; print(base64.b64encode(os.urandom(32)).decode())')"
# (On Windows CMD/PowerShell, set these with `set` / `$env:` instead of `export`.)

# One-time: create the first admin account (bypasses the API, since the
# register endpoint itself requires an admin token — bootstrap problem)
python create_first_admin.py admin1 "AdminPass123!"

# Start the API server
python app.py
```

Server runs at `http://127.0.0.1:5000`.

### Model Setup — why a separate download step?

The YuNet (`face_detection_yunet_2023mar.onnx`, ~230 KB) and SFace
(`face_recognition_sface_2021dec.onnx`, ~39 MB) model files are distributed
by the official **OpenCV Zoo** (`github.com/opencv/opencv_zoo`) via Git LFS,
and mirrored on Hugging Face. They cannot be embedded directly in this
project's source tree, so `download_models.py` fetches and verifies them
(against their published SHA-256 checksums) the first time you set up the
project. This is a one-time step per machine — the files are then reused
for every enrollment/login.

If `download_models.py` cannot reach either source (e.g. restricted
network), you can download them manually and place them in `models/`:
- https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface

## Quick Test (end-to-end demo)

```bash
python test_client.py
```

This exercises the full flow: admin login → register investigator → enroll
face → password login → RBAC-protected recovery access (allowed) → RBAC-protected
erasure access (denied for investigator) → view audit log → verify tamper-integrity.

**Note on the demo face images:** `test_client.py` still uses a synthetically
drawn "face" image so the script runs without a webcam. YuNet correctly
rejects it ("No face detected"), which is expected — it is not a real photo.
To exercise real face matching, use the `tests/` suite with real photos (see
"Testing" below), or wire up a webcam capture from your desktop/web client
and call `/api/admin/enroll-face` / `/api/auth/login-face` directly.

## Testing

```bash
pip install pytest
pytest tests/ -v
```

The suite covers every case required for this module:

| Case | Test |
|---|---|
| Correct 128-D embedding | `test_correct_embedding_dimension_and_type` |
| Successful authentication | `test_enroll_and_authenticate_success` |
| Wrong person rejected | `test_authenticate_rejects_wrong_person` |
| No face detected | `test_no_face_detected_on_blank_image` |
| Multiple faces | enforced in `_detect_single_face()`; add a multi-face fixture photo to exercise it directly |
| Invalid/corrupt image | `test_invalid_base64_rejected`, `test_oversized_image_rejected` |
| Missing enrollment | `test_authenticate_missing_enrollment_fails_closed` |
| Encrypted storage | `test_embedding_encrypt_decrypt_roundtrip`, `test_encrypted_storage_is_not_plaintext`, `test_tampered_ciphertext_fails_closed` |
| Threshold behaviour | `test_threshold_is_configurable`, `test_threshold_behavior_boundary` |
| API compatibility | `test_login_endpoint_unchanged_shape`, `test_enroll_face_endpoint_exists_and_enforces_rbac`, `test_login_face_endpoint_exists` |
| Existing RBAC unchanged | `test_erasure_route_still_rbac_protected` |

**Tests requiring real face photos auto-skip if fixtures aren't provided.**
To unlock full coverage, add 3+ photos each of two different people to:
```
tests/fixtures/person_a/
tests/fixtures/person_b/
```
(Use your own or teammates' photos with their consent — do not use photos of
people who haven't agreed to be part of your test data.)

---

## What Changed and Why (LBPH → SFace Embedding Migration)

### Model Verification (done before implementation, as required)

**Chosen: OpenCV YuNet (detector) + SFace (recognizer), via `cv2.FaceDetectorYN`
and `cv2.FaceRecognizerSF`.**

- Both are official models published in the **OpenCV Zoo**
  (`github.com/opencv/opencv_zoo`), Apache-2.0 licensed (commercial-safe,
  no research-only restriction unlike some alternatives such as InsightFace's
  ArcFace/buffalo models).
- SFace's output is documented and independently confirmed (OpenCV's own DNN
  face recognition tutorial, and third-party technical references) to be a
  **genuine, fixed 128-dimensional feature vector** per detected face — not
  a variable-length or invented value. This was verified via OpenCV's
  official documentation before writing any code.
- **Why SFace over a dlib-based library** (e.g. `face_recognition`, also
  genuinely 128-D via an OpenFace/FaceNet-derived model): SFace stays inside
  the OpenCV ecosystem this project already depends on (`opencv-contrib-python`
  was already a requirement for LBPH), avoiding a new dlib/CMake build
  toolchain that is a common source of installation failure across
  teammates' machines before a hackathon demo.
- **Why not a 512-D InsightFace/ArcFace model:** those produce 512-D
  embeddings, not 128-D as this project's specification requires, and their
  pretrained weights are licensed for non-commercial research use only.

### Key Management Design

- The AES-256-GCM key (`SECUREFORENSICS_FACE_ENC_KEY`) is **never hardcoded**
  and must be supplied via environment variable — the module raises
  `FaceAuthError` and refuses to enroll/authenticate if it is missing,
  malformed, or the wrong length (fail-closed, not fail-open).
- **AES-GCM specifically** (an AEAD/authenticated encryption mode) was chosen
  over a non-authenticated mode (plain AES-CBC) so that any tampering with a
  stored ciphertext is cryptographically detected and rejected at decryption
  time (`test_tampered_ciphertext_fails_closed` verifies this), not silently
  decrypted into garbage.
- A **fresh random 96-bit nonce is generated for every encryption operation**
  and stored alongside the ciphertext — reusing a nonce with the same key in
  GCM is a well-known way to catastrophically break its security guarantees,
  so this project never does so.
- **For a real deployment** (beyond this class project), the key should live
  in a secrets manager (e.g. AWS Secrets Manager, HashiCorp Vault, or even
  OS-level keychain) rather than a plain environment variable, and should be
  rotated periodically — this project uses an env var as a reasonable,
  simple baseline appropriate for a hackathon/academic scope, and this
  limitation is stated explicitly rather than glossed over.

### Matching Strategy — Compare Against All Enrolled Embeddings, Don't Average

When a user enrolls with 3+ photos, this system stores **one embedding per
photo** (not a single averaged "mean embedding"). At login, the live
embedding is compared against **every** stored embedding for that user using
SFace's own `.match()` cosine-similarity function, and the **best (highest)
similarity score wins**.

This was a deliberate choice over averaging: averaging a handful of
embeddings into one centroid can blur out genuine variation between photos
(different angle, expression, lighting), and with only 3-5 samples the
resulting centroid can occasionally match **worse** than any individual real
enrollment photo would have. Comparing against every stored embedding
individually avoids this robustness loss, at the cost of a few extra (cheap)
cosine comparisons per login — negligible for the small number of enrolled
investigators this tool is designed for.

### Threshold — Explicitly Not Claimed as "Universally Secure"

`SECUREFORENSICS_FACE_THRESHOLD` (default `0.363`, a starting point drawn
from OpenCV's own SFace sample code) controls the cosine-similarity cutoff
for a match. **This default is not validated for your specific cameras,
lighting, or users.** Before relying on this in any real demo:
1. Enroll 2-3 real test users.
2. Try genuine logins and impostor attempts, logging the `similarity` value
   the API returns each time.
3. Pick a threshold that separates genuine-match scores from impostor scores
   with a safety margin, and set it via `SECUREFORENSICS_FACE_THRESHOLD`.

The `similarity` value returned by the API is a **raw cosine similarity
score**, not a calibrated probability — do not present it to end users as
"87% confidence" without your own calibration work.

---

## API Reference

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/auth/login` | POST | none | `{username, password}` → JWT |
| `/api/auth/login-face` | POST | none | `{username, image (base64)}` → JWT |
| `/api/admin/register` | POST | admin token | `{username, password, role}` |
| `/api/admin/enroll-face` | POST | admin token | `{username, images: [base64,...]}` (3+ images) |
| `/api/audit/logs` | GET | admin/auditor token | Returns audit trail |
| `/api/audit/verify` | GET | admin/auditor token | Verifies hash-chain integrity |
| `/api/recovery/run` | GET | admin/investigator token | Example protected recovery endpoint |
| `/api/erasure/run` | GET | admin token only | Example protected erasure endpoint |

All protected endpoints expect: `Authorization: Bearer <token>`

### Example: enroll a face (client sends base64 images captured from webcam)

```bash
curl -X POST http://127.0.0.1:5000/api/admin/enroll-face \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"username": "investigator1", "images": ["<base64_img1>", "<base64_img2>", "<base64_img3>"]}'
```

### Example: login with face

```bash
curl -X POST http://127.0.0.1:5000/api/auth/login-face \
  -H "Content-Type: application/json" \
  -d '{"username": "investigator1", "image": "<base64_img>"}'
```

---

## Security Design Decisions (for your report / viva)

**Why SFace (128-D embeddings) instead of LBPH?** — see "Model Verification"
above for the full comparison. In short: LBPH is a histogram-based classifier
retrained on every enrollment, not a true fixed-length embedding, and cannot
satisfy a "128-D embedding" requirement by definition; SFace produces a
genuine, comparable 128-D vector per face and stays within the OpenCV
ecosystem already used elsewhere in this project.

**Why password fallback alongside face auth?**
Face recognition can fail due to lighting, camera quality, or hardware
availability. A password fallback keeps the system usable while still
defaulting to biometric login as the primary path — this is a standard
multi-factor design pattern, not a weakening of security, since both paths
require correctly-provisioned credentials created only by an admin.

**Why hash-chained audit logs instead of a plain log table?**
A plain log table can be edited or deleted by anyone with database access,
including a malicious insider — which defeats the purpose of a forensic
audit trail. By embedding each entry's hash of the *previous* entry, any
retroactive edit breaks the chain from that point forward, and
`/api/audit/verify` detects it immediately. This directly supports the
"chain of custody" requirement of a forensic tool.

**Why RBAC with three roles (Admin / Investigator / Auditor)?**
This limits blast radius: an investigator (who runs recovery operations
daily) cannot also trigger irreversible erasure — that requires elevated
admin privilege. An auditor can review everything but change nothing. This
separation-of-duties pattern is standard practice in security-sensitive
systems and directly addresses the "what if someone misuses this tool"
concern that motivated this module.

**On Aadhaar / government ID verification:**
As discussed in the project design document, genuine Aadhaar-based
verification requires UIDAI AUA/KUA licensing that is not available to
student projects. This module implements locally-controlled biometric
(face) authentication instead, and documents UIDAI-compliant verification
as a **future roadmap item** for production deployment — this is the
honest, defensible position to take in a review/viva.

---

## Known Limitations / Security Assumptions (stated explicitly, not glossed over)

- **No liveness / anti-spoofing yet (by design for this task).** The current
  system authenticates based on face embedding similarity only. It has
  **no defense against a printed photo, a screen replay, or a video** being
  held up to the camera. This is a real, meaningful gap for any production
  use and is intentionally scoped out of this task — see "Recommended Next
  Step" below.
- `SECUREFORENSICS_FACE_THRESHOLD`'s default (`0.363`) is a documented
  starting point, not a validated security boundary for your cameras/users —
  see "Threshold" section above.
- SFace/LBPH-style local matching is appropriate for a small, known set of
  enrolled investigators (tens of users). It has not been evaluated at
  larger scale (thousands of users) in this project.
- The encryption key is loaded from a plain environment variable, which is a
  reasonable baseline for this project's scope but not equivalent to a
  managed secrets store for a real production deployment.
- The JWT secret in `auth_utils.py` must be set via the
  `SECUREFORENSICS_JWT_SECRET` environment variable before any real deployment
  (this was already true before this migration and is unchanged).
- No rate-limiting yet on `/api/auth/login` or `/api/auth/login-face` — add
  `flask-limiter` before any real-world exposure to slow brute-force/replay
  attempts.
- For production, run behind a proper WSGI server (gunicorn/uWSGI), not
  Flask's built-in development server.
- **This system should not be described as "production-grade" merely because
  face recognition now works correctly** — production-readiness also
  requires liveness detection, rate-limiting, secrets management, and
  security review, none of which are complete yet.

## Recommended Next Step: Liveness / Anti-Spoofing

As explicitly scoped, this task did not include liveness detection. The
natural next step is to add a **passive or active liveness check** before
accepting a face match, for example:
- **Passive:** a lightweight CNN-based spoof classifier (e.g. an anti-spoofing
  model from the OpenCV Zoo or a MiniFASNet-style model) run on the same
  captured frame, flagging print/screen-replay artifacts.
- **Active:** prompt the user for a small live action (blink, turn head) and
  verify it occurs across a short frame sequence before proceeding to
  embedding comparison.

This should be implemented as a new, separate check that runs **before**
`authenticate_face()` is trusted, so that this migration's `face_auth.py`
API surface does not need to change again when liveness is added.
