"""
download_models.py
-------------------
One-time setup script: downloads the two OpenCV Zoo model files required by
face_auth.py (YuNet face detector + SFace face recognizer) and verifies their
SHA-256 checksums against the official published values before saving them.

WHY THIS SCRIPT EXISTS INSTEAD OF BUNDLING THE FILES:
These models are distributed via Git LFS on GitHub (and mirrored on Hugging
Face). They are NOT bundled in this project's source tree/zip because LFS
binaries cannot be fetched from a restricted build environment. This script
fetches them from the official sources over your own internet connection.

Usage:
    python download_models.py

Run this once before using face enrollment/authentication. It is safe to
re-run; it will overwrite existing files after re-verifying checksums.
"""

import hashlib
import os
import sys
import urllib.request

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

# (filename, primary_url, fallback_url, expected_sha256, expected_size_bytes)
MODELS = [
    (
        "face_detection_yunet_2023mar.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        232589,
    ),
    (
        "face_recognition_sface_2021dec.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        38696353,
    ),
]


def _sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url, dest_path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest_path, "wb") as out:
        out.write(resp.read())


def fetch(filename, primary_url, fallback_url, expected_sha256, expected_size):
    os.makedirs(MODEL_DIR, exist_ok=True)
    dest_path = os.path.join(MODEL_DIR, filename)

    if os.path.exists(dest_path) and _sha256_of(dest_path) == expected_sha256:
        print(f"[OK]   {filename} already present and verified.")
        return True

    for url in (primary_url, fallback_url):
        print(f"[...]  Downloading {filename} from {url}")
        try:
            _download(url, dest_path)
        except Exception as e:
            print(f"[WARN] Failed from this source: {e}")
            continue

        size = os.path.getsize(dest_path)
        digest = _sha256_of(dest_path)

        if size != expected_size or digest != expected_sha256:
            print(f"[FAIL] Checksum/size mismatch for {filename} "
                  f"(got size={size}, sha256={digest[:16]}...). Discarding file.")
            os.remove(dest_path)
            continue

        print(f"[OK]   {filename} downloaded and verified (sha256 matches official value).")
        return True

    print(f"[ERROR] Could not obtain a verified copy of {filename} from any source.")
    return False


def main():
    all_ok = True
    for model in MODELS:
        all_ok = fetch(*model) and all_ok

    if not all_ok:
        print("\nOne or more models could not be downloaded/verified. "
              "Face authentication will not work until this is resolved. "
              "You can also manually download from https://github.com/opencv/opencv_zoo "
              "and place the files in the models/ directory yourself.")
        sys.exit(1)

    print("\nAll models ready. You can now start the server: python app.py")


if __name__ == "__main__":
    main()
