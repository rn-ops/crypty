"""
test_client.py
---------------
End-to-end demo of the authentication API using Python's `requests` library.
This simulates what a desktop/web client would do.

For face enrollment/login, this script uses OpenCV to generate a synthetic
face-like test image just so the flow is runnable without a webcam. When
integrating a real client, replace `sample_face_base64()` with an actual
webcam capture encoded to base64.

Run the Flask server first:  python app.py
Then in another terminal:    python test_client.py
"""

import requests
import base64
import cv2
import numpy as np

BASE = "http://127.0.0.1:5000"


def sample_face_base64(seed=0):
    """
    Generates a synthetic grayscale 'face-like' image for demo purposes only.
    NOTE: Haar cascade face detection will only succeed on REAL face photos.
    Replace this function with a real webcam-captured image (see README.md)
    to actually exercise the face-recognition path.
    """
    img = np.zeros((250, 250, 3), dtype=np.uint8)
    img[:] = (200, 200, 200)
    cv2.circle(img, (125, 125), 90, (180, 160, 140), -1)      # face
    cv2.circle(img, (95, 100), 12, (30, 30, 30), -1)          # left eye
    cv2.circle(img, (155, 100), 12, (30, 30, 30), -1)         # right eye
    cv2.ellipse(img, (125, 160), (40, 20), 0, 0, 180, (60, 40, 40), 3)  # mouth
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf).decode("utf-8")


def main():
    print("1) Logging in as bootstrap admin (create this first with create_first_admin.py)")
    resp = requests.post(f"{BASE}/api/auth/login", json={"username": "admin1", "password": "AdminPass123!"})
    print(resp.status_code, resp.json())
    if resp.status_code != 200:
        print("Create the admin first: python create_first_admin.py admin1 AdminPass123!")
        return
    admin_token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    print("\n2) Registering a new investigator user")
    resp = requests.post(f"{BASE}/api/admin/register", headers=headers,
                          json={"username": "investigator1", "password": "InvestPass123!", "role": "investigator"})
    print(resp.status_code, resp.json())

    print("\n3) Enrolling face data for investigator1 (synthetic demo images)")
    images = [sample_face_base64(i) for i in range(4)]
    resp = requests.post(f"{BASE}/api/admin/enroll-face", headers=headers,
                          json={"username": "investigator1", "images": images})
    print(resp.status_code, resp.json())

    print("\n4) investigator1 logs in with PASSWORD")
    resp = requests.post(f"{BASE}/api/auth/login", json={"username": "investigator1", "password": "InvestPass123!"})
    print(resp.status_code, resp.json())
    invest_token = resp.json().get("token")

    print("\n5) investigator1 accesses the recovery module (should succeed)")
    if invest_token:
        resp = requests.get(f"{BASE}/api/recovery/run", headers={"Authorization": f"Bearer {invest_token}"})
        print(resp.status_code, resp.json())

    print("\n6) investigator1 tries to access the erasure module (should be DENIED - RBAC working)")
    if invest_token:
        resp = requests.get(f"{BASE}/api/erasure/run", headers={"Authorization": f"Bearer {invest_token}"})
        print(resp.status_code, resp.json())

    print("\n7) Admin views the audit log")
    resp = requests.get(f"{BASE}/api/audit/logs", headers=headers)
    print(resp.status_code)
    for entry in resp.json():
        print("  ", entry)

    print("\n8) Admin verifies audit log integrity (tamper check)")
    resp = requests.get(f"{BASE}/api/audit/verify", headers=headers)
    print(resp.status_code, resp.json())


if __name__ == "__main__":
    main()
