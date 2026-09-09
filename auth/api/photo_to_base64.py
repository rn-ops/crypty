"""
photo_to_base64.py
-------------------
Quick helper for manual testing: converts a JPG/PNG photo into a base64
string you can paste directly into Postman or a curl command.

Usage:
    python photo_to_base64.py my_photo.jpg

It will print the base64 string AND save it to base64_output.txt so you
don't have to scroll through a huge terminal blob.
"""

import base64
import sys

if len(sys.argv) != 2:
    print("Usage: python photo_to_base64.py <path_to_photo.jpg>")
    sys.exit(1)

path = sys.argv[1]
with open(path, "rb") as f:
    encoded = base64.b64encode(f.read()).decode()

with open("base64_output.txt", "w") as f:
    f.write(encoded)

print(f"Base64 string saved to base64_output.txt ({len(encoded)} characters)")
print("Copy its contents into your Postman request body / curl command.")
