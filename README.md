# Crypty

Crypty is an integrated digital forensics and data sanitization platform skeleton.
The desktop frontend is a PySide6 application backed by a portable C++ workflow
core. The MVP never touches real storage.


#
3. Preserve ALL data runs

4. Then deleted-file detection
✅ NTFS boot/partition detection
✅ MFT enumeration
✅ $FILE_NAME parsing
✅ parent MFT references
✅ reconstructed NTFS paths
✅ $STANDARD_INFORMATION timestamps
✅ data-run parsing
✅ source offsets
✅ read-only raw-media access
✅ native → Python → UI pipeline
⏳ preserve all data runs
⏳ proper deleted-file detection
⏳ actual recovery using those runs
⏳ recovery validation/reporting
#5 actual recovery

Something like:

Deleted FileEntry
       ↓
MFT metadata
       ↓
all data runs
       ↓
raw-media reads
       ↓
reconstruct bytes in order
       ↓
write recovered copy elsewhere
       ↓
verify size / hashes
       ↓
report

Deleted file
    ↓
NTFS MFT record remains
    ↓
Crypty reads the MFT
    ↓
Detects inactive FILE record
    ↓
Extracts filename
    ↓
Extracts metadata/timestamps
    ↓
Preserves data runs
    ↓
FileEntry.deleted = true
    ↓
C++ → native bridge → Python
    ↓
UI displays "Traced"
    ↓
UI search finds it

```
recovery pipeline
                    DELETED FILE
                         │
                         ▼
                  FileEntry
                         │
                  ┌──────┴──────┐
                  │             │
             resident       non-resident
               data            data runs
                  │             │
                  └──────┬──────┘
                         ▼
                  raw media reads
                         │
                         ▼
                  reconstructed
                     bytes
                         │
                         ▼
                  recovered file
                         │
                         ▼
                  size / hash verify
                         │
                         ▼
                    Crypty report
```

core/
├── evidence/
│   ├── evidence_source.cpp
│   └── ...
├── filesystem/
│   ├── ntfs/
│   │   ├── boot.cpp
│   │   ├── mft.cpp
│   │   ├── attributes.cpp
│   │   ├── data_runs.cpp
│   │   └── recovery.cpp
│   ├── fat32/
│   └── exfat/
├── platform/
│   └── windows/
├── storage/
│   ├── raw_reader.cpp
│   └── ...
└── recovery/
    └── ...

    Recovery attack plan

1. Handle resident files

Small NTFS files can have their contents stored directly inside the MFT record.
This is especially important because your tiny deleted test file may be resident.
We'll preserve those bytes during scanning.

2. Handle non-resident files

Iterate through every DataRun in order.
Convert:
LCN × cluster_size

into the physical source offset.

Read each run from the raw NTFS volume.
Reassemble the file in the correct order.
Respect the original file size.
Handle sparse runs correctly.

3. Expose recovery through the native bridge

Something along the lines of:

Python UI
   ↓
crypty_workflow_recover_file(index, destination)
   ↓
Workflow
   ↓
NTFS recovery
   ↓
raw reader
   ↓
destination file

4. Verify it

The demo shouldn't merely say:

Recovery complete

It should actually produce:

recovered/
└── test_file.txt

and we verify its size/content.

Scan evidence
      ↓
NTFS detector
      ↓
969 entries
      ↓
deleted test_file.txt
      ↓
select row
      ↓
Recover Selected ENABLES
      ↓
click
      ↓
Python backend
      ↓
crypty_workflow_recover_ntfs_file()
      ↓
NtfsDetector::recover_to()
      ↓
recovered/test_file.txt

## Run the Python Qt UI

delete root dll. run py -3 build_native.py or make to rebuild dll 


Install the Python dependency from the repository root:

```powershell
python -m pip install -r requirements.txt
```

The desktop UI authenticates against the Flask service in `auth/api`. Install
its dependencies and create the first admin account once:

```powershell
py -3 -m pip install -r auth\api\requirements.txt
cd auth\api
py -3 create_first_admin.py admin1 "choose-a-strong-password"
py -3 app.py
```

`create_first_admin.py` only creates a new account. If `admin1` already exists,
reset its password explicitly:

```powershell
py -3 reset_password.py admin1 "choose-a-strong-password"
```

Leave that service running on `http://127.0.0.1:5000`, open a second terminal,
and launch the desktop UI from the directory containing the `crypty` package:

Run the UI from the directory containing the `crypty` package:

```powershell
python -m crypty.app.main
```

Set `CRYPTY_AUTH_URL` if the authentication service runs elsewhere.

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

The sanitization language is intentionally framed as procedures designed with
reference to NIST SP 800-88 Rev. 2; this prototype does not claim certification
or compliance.

The tree below reflects the current repository. `evidence/`, `filesystem/`,
`platform/`, and a top-level `sanitization/` C++ module are possible future
modules; they are not present yet.

```text
Crypty/
├── app/
│   └── main.py                     # Desktop application entry point
├── auth/
│   └── api/                        # Flask authentication service
│       ├── app.py                  # HTTP routes and service startup
│       ├── auth_utils.py           # Authentication helpers
│       ├── audit.py                # Authentication audit events
│       ├── rbac.py                 # Role-based access control
│       ├── face_auth.py            # Face authentication endpoints/helpers
│       ├── create_first_admin.py   # Initial administrator setup
│       ├── reset_password.py       # Administrator password reset utility
│       ├── database/
│       │   └── db.py               # Authentication database access
│       ├── models/                 # Face model assets
│       └── requirements.txt        # Service-specific dependencies
├── core/
│   ├── include/crypty/
│   │   └── workflow.hpp            # Public C++ workflow types and API
│   ├── recovery/
│   │   ├── ntfs_detector.cpp       # NTFS scanning and recovery implementation - actually a 1300+ LOC rushed engine
│   │   ├── ntfs_detector.hpp       # NTFS detector interface
│   │   ├── fat32_detector.cpp      # FAT32 scanning and recovery implementation
│   │   ├── fat32_detector.hpp      # FAT32 detector interface
│   │   ├── exfat_detector.cpp      # exFAT scanning and recovery implementation
│   │   └── exfat_detector.hpp      # exFAT detector interface
│   ├── src/
│   │   ├── native_bridge.cpp       # C ABI called by Python via ctypes
│   │   └── workflow.cpp            # Workflow state and audit-event implementation
│   ├── __init__.py
│   ├── backend.py                 # Simulated/demo backend
│   ├── device_manager.py          # Detected-device list and selection
│   ├── native_backend.py          # Python adapter for the native C++ library
│   ├── recovery_engine.py         # Recovery orchestration facade (currently thin)
│   └── sanitization_engine.py     # Sanitization orchestration facade (currently thin)
├── data/
│   └── demo_data.py                # Sample data for demo behavior
├── reporting/
│   ├── report.cpp                  # Native report serialization
│   └── report.hpp                  # Native report declarations
├── ui/
│   ├── auth/
│   │   ├── auth_window.py          # Full-screen authentication UI
│   │   ├── login.py                # Login dialog / authentication UI
│   │   └── saved_accounts.py       # Saved-account UI/storage helpers
│   ├── dashboard/
│   │   ├── main_window.py          # Main workspace and page routing
│   │   ├── shared_elements.py     # Shared dashboard components
│   │   ├── dashboard.py            # Overview page
│   │   ├── devices.py              # Device/evidence page
│   │   ├── recovery.py             # Recovery page and user actions
│   │   ├── sanitization.py         # Sanitization page and user actions
│   │   └── reports.py              # Reports and audit pages
│   └── styles.py                   # Shared Qt styles
├── __init__.py
├── auth_client.py                  # Desktop-to-auth-service client
├── build_native.py                 # Native library build helper
├── CMakeLists.txt                  # C++ build targets
├── makefile                        # Common build/run/package commands
├── Crypty.spec                     # PyInstaller packaging configuration
├── requirements.txt                # Desktop Python dependencies
└── README.md
```

### Python and C++ boundary

The desktop UI and application services are Python. The native library owns
the C++ workflow state and filesystem-specific scanning/recovery algorithms.
`core/native_backend.py` declares the native functions with `ctypes`, converts
Python device data into native calls, and converts native results back into
Python dictionaries for the UI. `core/src/native_bridge.cpp` is the narrow C
ABI layer: it accepts C-compatible arguments, calls the C++ workflow or
detectors, and returns C-compatible results. It should not contain a second
implementation of recovery policy.

`core/include/crypty/workflow.hpp` defines the workflow model and public C++
interface; `core/src/workflow.cpp` implements operation state, progress, and
audit events. The detector files under `core/recovery/` implement filesystem
specific scanning and recovery. The intended call path is:

```text
UI page → RecoveryEngine → NativeBackend → native_bridge.cpp
        → Workflow / filesystem detector → native_bridge.cpp
        → NativeBackend → UI page
```

`core/recovery_engine.py` and `core/sanitization_engine.py` are currently thin
facades that hold a backend reference; they do not yet implement a separate
workflow. `core/backend.py` supplies a simulated demo backend and is a separate
backend option, not another implementation inside the native call path. Keep
business decisions in one layer: Python coordinates UI requests, the bridge
translates calls, and C++ owns native workflow and filesystem operations.


## DISTRIBUTION
For Windows, the simplest route is **PyInstaller**, then optionally wrap the output in an installer such as Inno Setup.

**1. Install packaging tools**

From the folder containing `crypty`:

```powershell
py -3 -m pip install -r crypty/requirements.txt
py -3 -m pip install pyinstaller
```

**2. Build the application**

```powershell
py -3.13 -m PyInstaller --clean --windowed --name Crypty --icon resources/crypty.ico --add-data "resources;resources" --paths . app/main.py 
```

The distributable application will be generated under:

```text
dist/Crypty/
```

Test it with:

```powershell
dist/Crypty/Crypty.exe
```

**Build sequence**

From your project root:
```
python build_native.py
```
Verify:
crypty_native.dll
libwinpthread-1.dll

Then:
```
pyinstaller Crypty.spec --clean
```
Then:
dist\Crypty\Crypty.exe
should launch.

And importantly, inspect:
dist\Crypty\_internal\
You should see:
crypty_native.dll
libwinpthread-1.dll