"""
face_auth.py  (v2 -- embedding-based, replaces LBPH)
-----------------------------------------------------
Face-based authentication using genuine 128-dimensional face embeddings.

MODEL CHOICE -- OpenCV YuNet (detector) + SFace (recognizer)
    - Both are official OpenCV Zoo models (github.com/opencv/opencv_zoo),
      Apache-2.0 licensed.
    - SFace (`cv2.FaceRecognizerSF`) is documented by OpenCV and independently
      confirmed to output an exactly 128-dimensional feature vector per face
      (verified before implementation -- see README.md "Model Verification"
      section for sources). This is NOT a randomly-sized or invented vector;
      it is the fixed output shape of the SFace network's final layer.
    - Chosen over a dlib-based library (e.g. `face_recognition`, which is
      also genuinely 128-D) specifically because it stays inside the OpenCV
      ecosystem this project already depends on -- no new heavy dlib/CMake
      build toolchain is required, which matters for reliable installation
      across teammates' machines before a hackathon demo.
    - `cv2.FaceRecognizerSF` additionally provides a built-in `.match()`
      method for cosine / L2-normalized distance comparison, so the matching
      logic below uses OpenCV's own reference implementation rather than a
      hand-rolled distance function.

WHY THIS REPLACES LBPH:
    LBPH is a texture-histogram classifier trained per-user; it does not
    produce a fixed-length, comparable "embedding" at all, and cannot satisfy
    a "128-D embedding" requirement by definition. SFace instead produces a
    true fixed-length embedding per face image, independent of how many
    users are enrolled, which is what the project specification requires.

ENCRYPTION AT REST:
    Embeddings are sensitive biometric data. Each embedding is encrypted
    individually with AES-256-GCM (authenticated encryption) before being
    written to the database. See `_get_encryption_key()` for key-management
    details -- the key is NEVER hardcoded and must come from the
    SECUREFORENSICS_FACE_ENC_KEY environment variable.

FAIL-CLOSED BEHAVIOUR:
    Every function below raises/returns a clear failure if models are
    missing, the encryption key is missing, no embeddings are enrolled, or
    input is malformed -- authentication never silently "passes" in a
    degraded state.
"""

import base64
import os
import struct

import cv2
import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from database.db import get_connection

# ----------------------------------------------------------------------
# Model files -- these are NOT bundled (see README.md "Model Setup"); run
# download_models.py once to fetch them from the official OpenCV Zoo source.
# ----------------------------------------------------------------------
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
YUNET_MODEL_PATH = os.path.join(MODEL_DIR, "face_detection_yunet_2023mar.onnx")
SFACE_MODEL_PATH = os.path.join(MODEL_DIR, "face_recognition_sface_2021dec.onnx")

EMBEDDING_DIM = 128  # SFace's fixed output size -- used to sanity-check every embedding produced

# Detector input size. Frames are resized to this before detection; must be
# passed consistently to FaceDetectorYN.
DETECTOR_INPUT_SIZE = (320, 320)

# ----------------------------------------------------------------------
# Configurable matching threshold (env-overridable). SFace's own
# documentation/sample code uses ~0.363 as an illustrative cosine-similarity
# cutoff on their internal benchmark -- we do NOT claim this value is
# "secure" for your specific deployment, lighting conditions, or camera
# hardware. TREAT THIS AS A STARTING POINT ONLY and re-tune it using your
# own enrolled users' data (see README.md "Threshold Tuning").
# ----------------------------------------------------------------------
DEFAULT_COSINE_THRESHOLD = 0.363
COSINE_THRESHOLD = float(os.environ.get("SECUREFORENSICS_FACE_THRESHOLD", DEFAULT_COSINE_THRESHOLD))

# Minimum detector confidence to accept a detected face at all (separate from
# the identity-matching threshold above).
DETECTION_SCORE_THRESHOLD = 0.9

# Basic input-validation limits to reject obviously-invalid/oversized payloads
# before they ever reach OpenCV.
MAX_IMAGE_BYTES = 8 * 1024 * 1024   # 8 MB per image
MIN_IMAGE_DIM = 60                   # px, after decode -- rejects tiny/garbage images


class FaceAuthError(ValueError):
    """Raised for any face-detection / validation failure. Caught by app.py
    and converted into a generic 4xx response -- messages here are safe to
    show to the caller (they never include embedding values or file paths)."""
    pass


# ------------------------------------------------------------------
# Lazy-loaded model singletons (loaded once per process, not per request)
# ------------------------------------------------------------------
_detector = None
_recognizer = None


def _require_models():
    """
    Fail-closed check: if the model files are missing, every enroll/auth
    call fails immediately with a clear error rather than silently degrading
    or falling back to an insecure path.
    """
    global _detector, _recognizer

    if not os.path.exists(YUNET_MODEL_PATH) or not os.path.exists(SFACE_MODEL_PATH):
        raise FaceAuthError(
            "Face recognition models are not installed on this server. "
            "Run download_models.py once (see README.md) before using face auth."
        )

    if _detector is None:
        _detector = cv2.FaceDetectorYN.create(
            YUNET_MODEL_PATH, "", DETECTOR_INPUT_SIZE,
            score_threshold=DETECTION_SCORE_THRESHOLD, nms_threshold=0.3, top_k=5000,
        )
    if _recognizer is None:
        _recognizer = cv2.FaceRecognizerSF.create(SFACE_MODEL_PATH, "")

    return _detector, _recognizer


# ------------------------------------------------------------------
# Encryption (AES-256-GCM) -- see README.md "Key Management" for full rationale
# ------------------------------------------------------------------
def _get_encryption_key() -> bytes:
    """
    Loads the 256-bit embedding-encryption key from the environment.
    NEVER hardcoded. The app must fail closed if this is missing -- we would
    rather refuse to enroll/authenticate than silently store biometric data
    unencrypted or with a guessable key.

    Expected format: base64-encoded 32-byte key, e.g. generated once via:
        python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
    """
    key_b64 = os.environ.get("SECUREFORENSICS_FACE_ENC_KEY")
    if not key_b64:
        raise FaceAuthError(
            "Server misconfiguration: face-embedding encryption key is not set. "
            "Face authentication is disabled until SECUREFORENSICS_FACE_ENC_KEY is configured."
        )
    try:
        key = base64.b64decode(key_b64)
    except Exception:
        raise FaceAuthError("Server misconfiguration: encryption key is not valid base64.")
    if len(key) != 32:
        raise FaceAuthError("Server misconfiguration: encryption key must decode to exactly 32 bytes (AES-256).")
    return key


def _encrypt_embedding(embedding: np.ndarray) -> tuple:
    """Returns (ciphertext_b64, nonce_b64). A fresh random nonce is used for every call."""
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce, standard for GCM
    plaintext = struct.pack(f"{EMBEDDING_DIM}f", *embedding.astype(np.float32).tolist())
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)
    return base64.b64encode(ciphertext).decode(), base64.b64encode(nonce).decode()


def _decrypt_embedding(ciphertext_b64: str, nonce_b64: str) -> np.ndarray:
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    ciphertext = base64.b64decode(ciphertext_b64)
    nonce = base64.b64decode(nonce_b64)
    # AESGCM.decrypt raises InvalidTag (a subclass of Exception) if the
    # ciphertext was tampered with or the key is wrong -- this propagates up
    # as a failure, which is the correct fail-closed behaviour.
    plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
    values = struct.unpack(f"{EMBEDDING_DIM}f", plaintext)
    return np.array(values, dtype=np.float32)


# ------------------------------------------------------------------
# Image decoding & validation
# ------------------------------------------------------------------
def _decode_base64_image(b64_string: str) -> np.ndarray:
    if "," in b64_string:  # strip data URL prefix e.g. "data:image/jpeg;base64,"
        b64_string = b64_string.split(",", 1)[1]

    try:
        img_bytes = base64.b64decode(b64_string, validate=True)
    except Exception:
        raise FaceAuthError("Invalid image data: not valid base64")

    if len(img_bytes) == 0:
        raise FaceAuthError("Invalid image data: empty payload")
    if len(img_bytes) > MAX_IMAGE_BYTES:
        raise FaceAuthError(f"Image too large: exceeds {MAX_IMAGE_BYTES // (1024*1024)} MB limit")

    np_arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None:
        raise FaceAuthError("Invalid or corrupt image: could not decode")

    h, w = img.shape[:2]
    if h < MIN_IMAGE_DIM or w < MIN_IMAGE_DIM:
        raise FaceAuthError("Image resolution too low to process safely")

    return img


def _detect_single_face(bgr_img: np.ndarray, detector) -> np.ndarray:
    """
    Detects faces and enforces "exactly one usable face per image" as required.
    Returns the aligned+cropped face image ready for embedding extraction.
    """
    h, w = bgr_img.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(bgr_img)

    if faces is None or len(faces) == 0:
        raise FaceAuthError("No face detected in image")

    if len(faces) > 1:
        raise FaceAuthError(
            "Multiple faces detected in image -- please provide a photo containing only one person"
        )

    face_box = faces[0]  # shape (15,): x,y,w,h,5 landmark points,score
    if face_box[-1] < DETECTION_SCORE_THRESHOLD:
        raise FaceAuthError("Detected face did not meet the minimum confidence threshold")

    return face_box


def _extract_embedding(bgr_img: np.ndarray) -> np.ndarray:
    """Full pipeline: detect -> align+crop -> extract 128-D SFace embedding."""
    detector, recognizer = _require_models()
    face_box = _detect_single_face(bgr_img, detector)

    aligned_face = recognizer.alignCrop(bgr_img, face_box)
    embedding = recognizer.feature(aligned_face)  # shape (1, 128) float32
    embedding = np.asarray(embedding).flatten()

    if embedding.shape[0] != EMBEDDING_DIM:
        # Defensive check -- should never trigger with the correct SFace model file,
        # but guards against a mismatched/corrupted model file being dropped in place.
        raise FaceAuthError("Face embedding extraction failed (unexpected output size)")

    return embedding.astype(np.float32)


# ------------------------------------------------------------------
# Public API -- SAME SIGNATURES as the old LBPH version, so app.py needs
# ZERO changes. `face_label` is accepted for backward compatibility with
# app.py's existing call site but is no longer used internally (matching is
# keyed by username directly against the face_embeddings table).
# ------------------------------------------------------------------
def enroll_face(username: str, face_label: int, base64_images: list):
    """
    Enrolls a user's face: for each of the >=3 provided images, detects
    exactly one face, extracts its 128-D embedding, encrypts it, and stores
    it. Re-running enrollment for a user REPLACES their previous embeddings
    (old ones are deleted first) rather than accumulating indefinitely.

    Raw images are never written to disk -- only the encrypted embeddings
    derived from them are persisted.
    """
    if len(base64_images) < 3:
        raise FaceAuthError("At least 3 face images are required for reliable enrollment")

    embeddings = []
    for idx, b64_img in enumerate(base64_images):
        img = _decode_base64_image(b64_img)
        try:
            embedding = _extract_embedding(img)
        except FaceAuthError as e:
            # Re-raise with which image failed, without leaking any biometric detail
            raise FaceAuthError(f"Enrollment image {idx + 1}: {e}")
        embeddings.append(embedding)

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Replace old embeddings for this user (avoids unbounded growth across
        # repeated re-enrollments and prevents stale embeddings lingering).
        cur.execute("DELETE FROM face_embeddings WHERE username = ?", (username,))
        for embedding in embeddings:
            ciphertext_b64, nonce_b64 = _encrypt_embedding(embedding)
            cur.execute(
                "INSERT INTO face_embeddings (username, embedding_ciphertext, embedding_nonce) "
                "VALUES (?, ?, ?)",
                (username, ciphertext_b64, nonce_b64),
            )
        conn.commit()
    finally:
        conn.close()

    return True


def authenticate_face(claimed_username: str, base64_image: str):
    """
    Verifies a live face capture against ALL enrolled embeddings for
    claimed_username. Returns (success: bool, similarity: float|None, message: str),
    matching the exact return shape the old LBPH version used.

    MATCHING STRATEGY -- "best of all enrolled embeddings" (max similarity),
    NOT an average embedding:
        Averaging several embeddings into one "mean face" can blur out
        genuine per-image variation (angle, expression, lighting) and can
        occasionally produce a centroid that matches WORSE than any single
        real enrollment sample, especially with only 3-5 images. Comparing
        the live embedding against every stored embedding individually and
        taking the best match is simpler, avoids that robustness loss, and
        is the strategy OpenCV's own SFace sample code uses for 1:N
        comparison. The trade-off is slightly more computation at login
        time (a handful of cosine comparisons), which is negligible for a
        small enrolled-user base such as this tool's investigator accounts.

    "similarity" is a cosine similarity score in roughly [-1, 1] from
    OpenCV's own FaceRecognizerSF.match(). This is a RAW SIMILARITY SCORE,
    NOT a calibrated probability of correct match -- do not present it to
    end users as "XX% confidence" without your own calibration study.
    """
    if not claimed_username or not base64_image:
        raise FaceAuthError("Username and image are required")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT embedding_ciphertext, embedding_nonce FROM face_embeddings WHERE username = ?",
        (claimed_username,),
    )
    rows = cur.fetchall()
    conn.close()

    # Fail closed: no enrolled data at all -> cannot authenticate, full stop.
    if not rows:
        return False, None, "This user has no enrolled face data"

    img = _decode_base64_image(base64_image)
    live_embedding = _extract_embedding(img)  # raises FaceAuthError -> caught by caller

    _, recognizer = _require_models()

    best_similarity = -1.0
    for row in rows:
        try:
            stored_embedding = _decrypt_embedding(row["embedding_ciphertext"], row["embedding_nonce"])
        except Exception:
            # A corrupted/tampered stored embedding is skipped, not fatal for
            # the whole login -- but never surfaces WHY to the caller.
            continue

        # Reshape to the (1, 128) row-vectors FaceRecognizerSF.match() expects.
        similarity = recognizer.match(
            live_embedding.reshape(1, -1), stored_embedding.reshape(1, -1),
            cv2.FaceRecognizerSF_FR_COSINE,
        )
        best_similarity = max(best_similarity, similarity)

    if best_similarity < 0 and len(rows) > 0:
        # every stored row failed to decrypt
        return False, None, "Enrolled face data could not be verified (fail-closed)"

    if best_similarity >= COSINE_THRESHOLD:
        return True, best_similarity, "Face authenticated successfully"

    return False, best_similarity, "Face does not match the claimed identity"
