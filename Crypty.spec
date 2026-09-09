# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path(SPECPATH)
native_candidates = [
    project_root / 'crypty_native.dll',
    project_root / 'build' / 'Release' / 'libcrypty_native.dll',
    project_root / 'build' / 'Release' / 'crypty_native.dll',
    project_root / 'build' / 'libcrypty_native.dll',
    project_root / 'build' / 'crypty_native.dll',
]
native_library = next((path for path in native_candidates if path.is_file()), None)
if native_library is None:
    raise FileNotFoundError(
        'crypty_native.dll was not found. Build the native bridge before packaging.'
    )
native_binaries = [(str(native_library), '.')]
runtime_library = project_root / 'libwinpthread-1.dll'
if runtime_library.is_file():
    native_binaries.append((str(runtime_library), '.'))

a = Analysis(
    [str(project_root / 'app' / 'main.py')],
    pathex=[str(project_root.parent)],
    binaries=native_binaries,
    datas=[(str(project_root / 'resources'), 'resources')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'cv2'],
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
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(project_root / 'resources' / 'crypty.ico')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Crypty',
)
