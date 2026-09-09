# Crypty

Crypty is an integrated digital forensics and data sanitization platform skeleton.
The desktop frontend is a PySide6 application backed by a portable C++ workflow
core. The MVP never touches real storage.

## Run the Python Qt UI

Install the Python dependency from the repository root:

```powershell
python -m pip install -r requirements.txt
```

Run the UI from the directory containing the `crypty` package:

```powershell
python -m crypty.app.main
```

From this repository directory, use the makefile shortcut:

```powershell
make run
```

## CMake build

```sh
cmake -S . -B build
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

The CMake build compiles the portable `crypty_core` library and exposes a
`crypty_native` library for the Python UI plus a `crypty_ui` target that
launches the Python Qt application. Build `crypty_native` before starting the
UI.

For a MinGW build, place any required runtime DLLs beside `crypty_native.dll`
before packaging. The PyInstaller spec automatically includes
`libwinpthread-1.dll` when it is present.

With MinGW installed, build the native bridge and package the app with:

```powershell
py -3 build_native.py
py -3 -m PyInstaller --clean --noconfirm Crypty.spec
```

Or use `make package`. The spec stops with a clear error instead of producing
an executable without the native engine.

## Layout

- `core/include/crypty/`: public workflow model and API
- `core/src/`: media-aware operation state and audit events
- `reporting/`: report serialization boundary
- `app/`: Python application bootstrap
- `ui/`: PySide6 desktop presentation layer
- `auth/`, `ml/`: reserved and intentionally untouched

The sanitization language is intentionally framed as procedures designed with
reference to NIST SP 800-88 Rev. 2; this prototype does not claim certification
or compliance.
