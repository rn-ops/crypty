# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve()
if sys.platform == "win32":
    library_names = ("crypty_native.dll",)
elif sys.platform == "darwin":
    library_names = ("libcrypty_native.dylib",)
else:
    library_names = ("libcrypty_native.so",)

library_candidates = [
    ROOT / "build" / "Release" / name for name in library_names
] + [
    ROOT / "build" / name for name in library_names
]
native_library = next((path for path in library_candidates if path.is_file()), None)
if native_library is None:
    raise SystemExit(
        "Build crypty_native before packaging; searched: "
        + ", ".join(str(path) for path in library_candidates)
    )

app_icon = str(ROOT / "resources" / "crypty.ico") if sys.platform == "win32" else None


a = Analysis(
    [str(ROOT / 'app' / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[(str(native_library), '.')],
    datas=[(str(ROOT / 'resources'), 'resources')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Crypty',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Crypty',
)
