from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "crypty_native.dll"


def main() -> None:
    compiler = shutil.which("g++")
    if compiler is None:
        raise SystemExit("g++ was not found. Install MinGW or build crypty_native with CMake.")

    command = [
        compiler,
        "-std=c++17",
        "-shared",
        "-static-libgcc",
        "-static-libstdc++",
        str(ROOT / "core" / "src" / "workflow.cpp"),
        str(ROOT / "core" / "src" / "native_bridge.cpp"),
        "-I" + str(ROOT / "core" / "include"),
        "-o",
        str(OUTPUT),
    ]
    subprocess.run(command, check=True)

    runtime = Path(compiler).resolve().parent / "libwinpthread-1.dll"
    if runtime.is_file():
        shutil.copy2(runtime, ROOT / runtime.name)

    print(f"Built {OUTPUT}")


if __name__ == "__main__":
    main()
