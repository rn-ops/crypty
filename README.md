# Crypty

Crypty is an integrated digital forensics and data sanitization platform skeleton.
The code is intentionally split into a portable C++ workflow core, reporting,
and a replaceable desktop frontend. The MVP never touches real storage.

## Run the native demo

On Windows with MinGW g++, build the executable from the repository root:

```powershell
g++ -std=c++17 -municode -mwindows app/main.cpp ui/desktop_ui.cpp core/src/workflow.cpp reporting/report.cpp -Iui -Icore/include -Ireporting -o crypty.exe -lcomctl32
```

Then run `crypty.exe`. The native demo is the primary MVP surface.

## CMake build

```sh
cmake -S . -B build
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

On Windows, CMake builds the native `crypty.exe`. On other platforms it builds
the portable `crypty_core` library and leaves the UI adapter as the next step.

## Layout

- `core/include/crypty/`: public workflow model and API
- `core/src/`: media-aware operation state and audit events
- `reporting/`: report serialization boundary
- `app/`: executable bootstrap only; calls `initialize_ui()`
- `ui/`: desktop presentation layer; replace with Qt, wxWidgets, or another native UI
- `auth/`, `ml/`: reserved and intentionally untouched

The sanitization language is intentionally framed as procedures designed with
reference to NIST SP 800-88 Rev. 2; this prototype does not claim certification
or compliance.
