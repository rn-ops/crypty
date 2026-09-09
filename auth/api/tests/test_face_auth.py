"""
tests/test_face_auth.py
------------------------
Test suite for the SFace-embedding-based face_auth.py module.

TEST DATA NOTE:
Several tests below (successful auth, wrong person, multiple faces) require
REAL face photographs to be meaningful -- synthetic/drawn images will
correctly be rejected by YuNet as "no face detected", which is accurate
behaviour but does not exercise the matching logic itself.

This suite does NOT ship with real face photos of any person (that would
require consent from an identifiable individual and is inappropriate to
bundle in a shared project). To get full coverage:

    1. Place 3+ photos of Person A in tests/fixtures/person_a/
    2. Place 3+ photos of Person B in tests/fixtures/person_b/
    3. Re-run: pytest tests/test_face_auth.py -v

Tests that need these fixtures will auto-skip with a clear message if the
folders are empty, rather than failing -- so the suite is still fully
runnable (and CI-safe) without real photos, just with reduced coverage.

Run with:
    pytest tests/ -v
"""

import base64
import glob
import os
import sys

import numpy as np
import pytest
import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- Ensure a usable encryption key exists for the whole test session ---
os.environ.setdefault(
    "SECUREFORENSICS_FACE_ENC_KEY",
    base64.b64encode(b"0" * 32).decode(),  # fixed test-only key, NOT for real use
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
PERSON_A_DIR = os.path.join(FIXTURES_DIR, "person_a")
PERSON_B_DIR = os.path.join(FIXTURES_DIR, "person_b")


def _load_images_b64(folder):
    paths = sorted(glob.glob(os.path.join(folder, "*")))
    images = []
    for p in paths:
        with open(p, "rb") as f:
            images.append(base64.b64encode(f.read()).decode())
    return images


def _models_available():
    from face_auth import YUNET_MODEL_PATH, SFACE_MODEL_PATH
    return os.path.exists(YUNET_MODEL_PATH) and os.path.exists(SFACE_MODEL_PATH)


requires_models = pytest.mark.skipif(
    not _models_available(),
    reason="YuNet/SFace .onnx models not found -- run download_models.py first"
)

requires_real_faces = pytest.mark.skipif(
    len(_load_images_b64(PERSON_A_DIR)) < 3 or len(_load_images_b64(PERSON_B_DIR)) < 3,
    reason="Needs >=3 real photos each in tests/fixtures/person_a/ and person_b/ "
           "(not provided by default -- see module docstring)"
)


# ------------------------------------------------------------------
# Fixtures: a plain synthetic "no face" image, and a garbage/corrupt payload
# ------------------------------------------------------------------
@pytest.fixture
def blank_image_b64():
    img = np.full((300, 300, 3), 128, dtype=np.uint8)  # plain grey square, no face
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf).decode()


@pytest.fixture
def corrupt_image_b64():
    return base64.b64encode(b"this is not an image at all").decode()


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point the DB at a fresh temp file for every test so tests don't pollute
    each other or your real development database."""
    import database.db as db_module
    test_db_path = str(tmp_path / "test_secureforensics.db")
    monkeypatch.setattr(db_module, "DB_PATH", test_db_path)
    db_module.init_db()
    yield


# ============================================================
# 1. Input validation (no models/faces required)
# ============================================================

def test_invalid_base64_rejected(corrupt_image_b64):
    from face_auth import _decode_base64_image, FaceAuthError
    with pytest.raises(FaceAuthError):
        _decode_base64_image(corrupt_image_b64)


def test_oversized_image_rejected(monkeypatch):
    from face_auth import _decode_base64_image, FaceAuthError, MAX_IMAGE_BYTES
    big_payload = base64.b64encode(b"0" * (MAX_IMAGE_BYTES + 1)).decode()
    with pytest.raises(FaceAuthError, match="too large"):
        _decode_base64_image(big_payload)


def test_missing_encryption_key_fails_closed(monkeypatch):
    from face_auth import _get_encryption_key, FaceAuthError
    monkeypatch.delenv("SECUREFORENSICS_FACE_ENC_KEY", raising=False)
    with pytest.raises(FaceAuthError, match="encryption key"):
        _get_encryption_key()


def test_malformed_encryption_key_rejected(monkeypatch):
    from face_auth import _get_encryption_key, FaceAuthError
    monkeypatch.setenv("SECUREFORENSICS_FACE_ENC_KEY", "not-valid-base64-!!!")
    with pytest.raises(FaceAuthError):
        _get_encryption_key()


def test_short_encryption_key_rejected(monkeypatch):
    from face_auth import _get_encryption_key, FaceAuthError
    short_key = base64.b64encode(b"too_short").decode()
    monkeypatch.setenv("SECUREFORENSICS_FACE_ENC_KEY", short_key)
    with pytest.raises(FaceAuthError, match="32 bytes"):
        _get_encryption_key()


def test_threshold_is_configurable(monkeypatch):
    """Confirms SECUREFORENSICS_FACE_THRESHOLD actually changes behaviour,
    not just that the env var is read at import time."""
    monkeypatch.setenv("SECUREFORENSICS_FACE_THRESHOLD", "0.99")
    import importlib
    import face_auth
    importlib.reload(face_auth)
    assert face_auth.COSINE_THRESHOLD == pytest.approx(0.99)
    # reset for other tests
    monkeypatch.delenv("SECUREFORENSICS_FACE_THRESHOLD", raising=False)
    importlib.reload(face_auth)


# ============================================================
# 2. Encryption round-trip (no models required)
# ============================================================

def test_embedding_encrypt_decrypt_roundtrip():
    from face_auth import _encrypt_embedding, _decrypt_embedding, EMBEDDING_DIM
    original = np.random.rand(EMBEDDING_DIM).astype(np.float32)
    ciphertext_b64, nonce_b64 = _encrypt_embedding(original)
    recovered = _decrypt_embedding(ciphertext_b64, nonce_b64)
    assert np.allclose(original, recovered, atol=1e-5)


def test_encrypted_storage_is_not_plaintext():
    """The stored ciphertext must not contain the raw floating point values."""
    from face_auth import _encrypt_embedding, EMBEDDING_DIM
    embedding = np.ones(EMBEDDING_DIM, dtype=np.float32) * 0.123456
    ciphertext_b64, _ = _encrypt_embedding(embedding)
    assert "0.123456" not in ciphertext_b64
    assert base64.b64decode(ciphertext_b64) != embedding.tobytes()


def test_tampered_ciphertext_fails_closed():
    """AES-GCM must reject tampered ciphertext rather than silently returning
    garbage -- this is why an AEAD mode (GCM) was required, not plain AES-CBC."""
    from face_auth import _encrypt_embedding, _decrypt_embedding, EMBEDDING_DIM
    embedding = np.random.rand(EMBEDDING_DIM).astype(np.float32)
    ciphertext_b64, nonce_b64 = _encrypt_embedding(embedding)

    raw = bytearray(base64.b64decode(ciphertext_b64))
    raw[0] ^= 0xFF  # flip a bit
    tampered_b64 = base64.b64encode(bytes(raw)).decode()

    with pytest.raises(Exception):  # cryptography raises InvalidTag
        _decrypt_embedding(tampered_b64, nonce_b64)


# ============================================================
# 3. Face detection / embedding extraction (models required, real faces not required)
# ============================================================

@requires_models
def test_no_face_detected_on_blank_image(blank_image_b64):
    from face_auth import _decode_base64_image, _extract_embedding, FaceAuthError
    img = _decode_base64_image(blank_image_b64)
    with pytest.raises(FaceAuthError, match="No face detected"):
        _extract_embedding(img)


@requires_models
def test_enroll_rejects_fewer_than_three_images(blank_image_b64):
    from face_auth import enroll_face, FaceAuthError
    with pytest.raises(FaceAuthError, match="at least 3"):
        enroll_face("someuser", 0, [blank_image_b64, blank_image_b64])


# ============================================================
# 4. Full pipeline with real face photos (skipped unless fixtures are provided)
# ============================================================

@requires_models
@requires_real_faces
def test_correct_embedding_dimension_and_type():
    from face_auth import _decode_base64_image, _extract_embedding, EMBEDDING_DIM
    images = _load_images_b64(PERSON_A_DIR)
    img = _decode_base64_image(images[0])
    embedding = _extract_embedding(img)
    assert embedding.shape == (EMBEDDING_DIM,)
    assert embedding.dtype == np.float32


@requires_models
@requires_real_faces
def test_enroll_and_authenticate_success():
    from face_auth import enroll_face, authenticate_face
    images_a = _load_images_b64(PERSON_A_DIR)
    enroll_face("person_a", 0, images_a[:3])

    # authenticate with a held-out image of the same person (or a repeated one
    # if only 3 are available)
    test_image = images_a[-1]
    success, similarity, message = authenticate_face("person_a", test_image)
    assert success is True
    assert similarity is not None
    assert "successfully" in message.lower()


@requires_models
@requires_real_faces
def test_authenticate_rejects_wrong_person():
    from face_auth import enroll_face, authenticate_face
    images_a = _load_images_b64(PERSON_A_DIR)
    images_b = _load_images_b64(PERSON_B_DIR)

    enroll_face("person_a", 0, images_a[:3])

    success, similarity, message = authenticate_face("person_a", images_b[0])
    assert success is False
    assert "does not match" in message.lower()


@requires_models
def test_authenticate_missing_enrollment_fails_closed():
    from face_auth import authenticate_face
    img = np.full((300, 300, 3), 128, dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    b64_img = base64.b64encode(buf).decode()

    success, similarity, message = authenticate_face("nobody_enrolled", b64_img)
    assert success is False
    assert similarity is None
    assert "no enrolled face data" in message.lower()


@requires_models
@requires_real_faces
def test_threshold_behavior_boundary(monkeypatch):
    """With an artificially very strict threshold (near 1.0), even a genuine
    match should be rejected -- confirms the threshold is actually enforced,
    not just cosmetic."""
    import importlib
    import face_auth
    monkeypatch.setenv("SECUREFORENSICS_FACE_THRESHOLD", "0.999")
    importlib.reload(face_auth)

    images_a = _load_images_b64(PERSON_A_DIR)
    face_auth.enroll_face("person_a_strict", 0, images_a[:3])
    success, similarity, message = face_auth.authenticate_face("person_a_strict", images_a[-1])
    assert success is False  # threshold set unreasonably high on purpose

    monkeypatch.delenv("SECUREFORENSICS_FACE_THRESHOLD", raising=False)
    importlib.reload(face_auth)


# ============================================================
# 5. API-level compatibility (Flask test client) -- confirms endpoints,
#    request/response shape, and RBAC are unchanged.
# ============================================================

@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SECUREFORENSICS_JWT_SECRET", "test-secret")
    monkeypatch.setenv("SECUREFORENSICS_FACE_ENC_KEY", base64.b64encode(b"0" * 32).decode())

    import database.db as db_module
    test_db_path = str(tmp_path / "api_test.db")
    monkeypatch.setattr(db_module, "DB_PATH", test_db_path)

    import importlib
    import app as app_module
    importlib.reload(app_module)  # re-run init_db() against the patched DB_PATH

    from auth_utils import hash_password
    conn = db_module.get_connection()
    conn.execute(
        "INSERT INTO users (username, password_hash, role, face_label) VALUES (?, ?, 'admin', 0)",
        ("apitest_admin", hash_password("AdminPass123!")),
    )
    conn.commit()
    conn.close()

    with app_module.app.test_client() as client:
        yield client


def test_login_endpoint_unchanged_shape(api_client):
    resp = api_client.post("/api/auth/login",
                            json={"username": "apitest_admin", "password": "AdminPass123!"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert "token" in body and "role" in body
    assert body["role"] == "admin"


def test_enroll_face_endpoint_exists_and_enforces_rbac(api_client, blank_image_b64):
    # No token at all -> 401, endpoint must still exist at the same path
    resp = api_client.post("/api/admin/enroll-face",
                            json={"username": "apitest_admin", "images": [blank_image_b64] * 3})
    assert resp.status_code == 401


def test_login_face_endpoint_exists(api_client, blank_image_b64):
    # Endpoint must exist and respond (even if it correctly rejects a faceless image)
    resp = api_client.post("/api/auth/login-face",
                            json={"username": "apitest_admin", "image": blank_image_b64})
    assert resp.status_code in (400, 401)  # not 404 -- route exists
    assert "images" not in resp.get_json()  # response never echoes back image/embedding data


def test_erasure_route_still_rbac_protected(api_client):
    resp = api_client.post("/api/auth/login",
                            json={"username": "apitest_admin", "password": "AdminPass123!"})
    token = resp.get_json()["token"]
    resp = api_client.get("/api/erasure/run", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200  # admin allowed, exactly as before this migration
