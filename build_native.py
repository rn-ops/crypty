from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"


def main() -> None:
    cmake = shutil.which("cmake")
    if cmake is None:
        raise SystemExit("CMake was not found. Install CMake 3.20 or newer.")

    subprocess.run(
        [cmake, "-S", str(ROOT), "-B", str(BUILD_DIR)],
        check=True,
    )
    subprocess.run(
        [
            cmake,
            "--build",
            str(BUILD_DIR),
            "--target",
            "crypty_native",
            "--config",
            "Release",
        ],
        check=True,
    )
    print(f"Built crypty_native in {BUILD_DIR}")

if __name__ == "__main__":
    main()
