# Crypty

Crypty is an early-stage, cross-platform workstation for authorized data
recovery, digital-forensics workflows, and media sanitization. The product
goal is a dependable, local-first tool that helps an operator preserve source
media, recover what remains recoverable, sanitize only explicitly authorized
targets, and produce reviewable records of what happened. Development currently
happens on Windows, but platform-specific behavior must stay behind explicit
adapters so Windows, Linux, and macOS support can be built and tested without
rewriting the product core.

This repository is a prototype, not a production forensic suite. Some native
filesystem and recovery code, a Python desktop UI, an authentication service,
and a static product website exist, but feature completeness, safety controls,
and recovery results still need systematic validation. Do not use it as the
sole tool for high-value evidence, and do not promise recovery or sanitization
outcomes based on the prototype.

## Start here

### Prerequisites

- Python 3.10 or newer
- CMake 3.20 or newer and a C++17 compiler for the native core
- Git

The native storage boundary now has Windows and POSIX implementations, and
the CMake configuration selects one for the host OS. Linux/macOS builds,
permissions, recovery behavior, UI packaging, and physical-device support
still need validation in CI and on those operating systems before they can be
claimed as release-ready.

The desktop UI and native core are separate components. Install Python
dependencies from the repository root:

```sh
python -m pip install -r requirements.txt
```

Build the C++ libraries and run the native tests on Windows, Linux, or macOS:

```sh
cmake -S . -B build
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

The UI uses the authentication service in `auth/api`. Install its dependencies
with the same Python interpreter you will use to start the service. Avoid a
standalone `pip install` if multiple Python installations are present:

```sh
python -m pip install -r auth/api/requirements.txt
python -c "import sys, flask; print(sys.executable); print(flask.__version__)"
```

If using the Windows Python launcher, consistently select one version for
installation, account setup, and startup (for example, replace `python` in
these commands with `py -3.13`):

```sh
python auth/api/create_first_admin.py admin1 "choose-a-strong-password"
python auth/api/app.py
```

If the import check fails, install the service dependencies using the exact
interpreter printed by `python -c "import sys; print(sys.executable)"`, then
run the service with that same interpreter. For example:

```sh
python -m pip install -r auth/api/requirements.txt
python auth/api/app.py
```

The service defaults to `http://127.0.0.1:5000`; set `CRYPTY_AUTH_URL` if your
development service uses another address. Do not expose the development
service publicly or treat its current authentication setup as production
deployment guidance.
The SQLite database uses `CRYPTY_AUTH_DB` when set, preserves the existing
development database beside the API when present, and otherwise uses the
operating system's per-user application-data directory.

With the authentication service running, launch the desktop UI from another
terminal at the repository root:

```sh
python -m app.main
```

## Building a local app bundle

Build and package on the same operating system and CPU architecture you intend
to distribute. Crypty's native library is not cross-compiled by this workflow.
The current PyInstaller spec creates a **development folder bundle**, not a
signed installer or a release-ready app package.

### Windows (PowerShell)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python build_native.py
python -m PyInstaller --clean --noconfirm Crypty.spec
```

The development bundle is `dist\Crypty\Crypty.exe` plus its `_internal`
dependencies. Zip the whole `dist\Crypty` directory for internal testing; do
not distribute the executable alone.

### Linux (Bash)

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python build_native.py
python -m PyInstaller --clean --noconfirm Crypty.spec
```

The development bundle is `dist/Crypty/`. Verify it on each supported Linux
distribution before publishing. A signed AppImage or distribution package
(.deb/.rpm) still needs a separate release pipeline.

### macOS (zsh)

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python build_native.py
python -m PyInstaller --clean --noconfirm Crypty.spec
```

This creates a folder bundle for local testing, not a signed/notarized `.app`
or `.dmg`. Build separately on each target architecture (Apple Silicon and,
if supported, Intel); sign and notarize before external distribution.

These desktop commands do not install or start the Flask authentication
service. Today the desktop app still expects `auth/api` to be running at
`CRYPTY_AUTH_URL` (default `http://127.0.0.1:5000`). That is a development
dependency, not a viable end-user installation flow. Before an MVP release,
either add a properly designed offline/local-user mode or deploy and document
a secured account service; do not make customers run the developer bootstrap
script or expose the development Flask server.

### Website

The website is a static concept/marketing page. Its contact/interest form is
demo-only and does not submit or store data. The chat is an optional local
Python service; setup and limitations are in [`website/README.txt`](website/README.txt).
Do not advertise the page's mock dashboard, plans, or architecture diagrams
as released product capabilities.

## Product principles

1. **Preserve first.** Recovery analysis must not write to source evidence.
   Acquire or select a verified image where possible; otherwise use a
   demonstrably read-only source path. Write recovered output to a separate
   destination.
2. **Make risk explicit.** Show the selected device identity, operation,
   destination, and consequences before any destructive action. Recovery and
   sanitization must be separate workflows with separate permissions and
   confirmations.
3. **Record enough to review.** Persist operation start, target identity,
   configuration, progress, warnings, result, verification, and operator
   actions. Keep raw recovered content out of routine audit records.
4. **Report limitations honestly.** Recovery depends on filesystem state,
   overwritten sectors, TRIM, flash translation layers, device health, and
   media type. Sanitization assurance also depends on the device and method;
   a successful software write is not proof that every physical cell was
   erased.
5. **Local-first and least privilege.** Device data stays local by default.
   Network services should receive only the minimum metadata required for
   their purpose.

## Current shape of the code

- `app/` and `ui/`: PySide6 desktop entry point, authentication screens, and
  workspace pages.
- `core/`: Python orchestration/adapters and the C++ workflow, filesystem,
  storage, recovery, reporting, and sanitization modules.
- `core/native_backend.py` and `core/src/native_bridge.cpp`: Python-to-native
  boundary. Keep it narrow and typed; avoid implementing product policy in
  both languages.
- `core/includes/crypty/` is the single public native header/API tree.
  `core/platform/` contains OS-specific enumeration/read adapters, while
  private implementation headers stay with their `.cpp` files.
- `auth/`: separate Flask authentication API, its database/models, and
  development utilities.
- `tests/`: C++ workflow, filesystem detection, FAT32 recovery, NTFS boot
  parsing, and platform-independent image-read tests.
- `website/`: static landing page and an optional local chat server.
- `data/`: demo data. Clearly label simulated output wherever it appears.

The Python recovery and sanitization engine classes are currently thin
facades. The presence of a UI page or native source file does not by itself
mean an end-to-end, production-safe workflow exists. Platform adapters are a
first portability step, not proof of validated cross-platform operation.

## Project structure

This tree highlights the source files contributors are most likely to work
in. Comments describe each path's responsibility, not a claim that every
planned capability is complete.

```text
crypty/
├── .github/
│   └── workflows/
│       └── ci.yml                     # Cross-platform build, test, and Python checks
├── app/
│   └── main.py                        # Desktop entry point and application composition
├── auth/
│   └── api/
│       ├── app.py                      # Flask authentication API startup and routes
│       ├── auth_utils.py               # Password/token helpers
│       ├── audit.py                    # Authentication audit logging
│       ├── rbac.py                     # Role-based access decisions
│       ├── face_auth.py                # Optional face-auth flows; not core recovery
│       ├── database/
│       │   └── db.py                   # SQLite connection and schema setup
│       ├── tests/                      # Authentication API tests and fixtures
│       └── requirements.txt            # Authentication-service dependencies
├── core/
│   ├── __init__.py                     # Python package marker
│   ├── backend.py                      # Simulated/demo backend
│   ├── device_manager.py               # Device discovery and active selection
│   ├── native_backend.py               # Python ctypes adapter for the native library
│   ├── recovery_engine.py              # Python recovery orchestration facade
│   ├── sanitization_engine.py          # Python sanitization orchestration facade
│   ├── includes/                       # The one public C++ header tree
│   │   └── crypty/
│   │       ├── workflow.hpp            # Workflow types and public C++ workflow API
│   │       ├── filesystem/
│   │       │   ├── reader.hpp          # Bounded random-access reader contract
│   │       │   └── types.hpp           # Filesystem metadata and detection types
│   │       └── platform/
│   │           └── device_access.hpp   # Platform-neutral storage-device contract
│   ├── filesystem/
│   │   ├── detector.cpp/.hpp           # Internal filesystem detection implementation
│   │   └── volume_info.cpp/.hpp        # Internal validated-geometry helpers
│   ├── platform/
│   │   ├── windows_device_access.cpp   # Windows volume discovery and read-only access
│   │   └── posix_device_access.cpp     # Linux/macOS volume discovery and read-only access
│   ├── recovery/
│   │   ├── recovery_engine.cpp/.hpp    # Filesystem dispatch and recovery orchestration
│   │   ├── fat32/                      # FAT32 deleted-entry scan and recovery
│   │   ├── exfat/                      # exFAT deleted-entry scan
│   │   └── ntfs/                       # NTFS MFT, attributes, runlists, and scan
│   ├── reporting/
│   │   └── report.cpp/.hpp             # Native operation report serialization
│   ├── sanitization/
│   │   └── sanitization_engine.cpp/.hpp # Native sanitization orchestration; incomplete
│   └── src/
│       ├── native_bridge.cpp            # C ABI boundary exported to Python
│       └── workflow.cpp                 # Workflow state and in-memory events
├── data/
│   └── demo_data.py                    # Clearly labeled sample/demo content
├── docs/                               # Product and engineering documentation
├── resources/
│   └── crypty.ico                      # Windows application icon
├── tests/
│   ├── workflow_test.cpp               # Workflow-state tests
│   ├── filesystem_detector_test.cpp    # Filesystem detection fixtures
│   ├── fat32_recovery_test.cpp          # FAT32 recovery tests
│   ├── ntfs_boot_test.cpp               # NTFS boot-sector geometry tests
│   └── platform_read_test.cpp           # Read-only image-file access test
├── ui/
│   ├── auth/                            # Desktop login and saved-account UI
│   ├── dashboard/                       # Workspace, devices, recovery, sanitization, reports
│   └── styles.py                        # Shared desktop styling
├── website/
│   ├── index.html                       # Static product website
│   ├── styles.css                       # Website presentation
│   ├── script.js                        # Website interactions
│   ├── README.txt                       # Website run instructions and limitations
│   └── bot/                             # Optional local website chat service
├── CMakeLists.txt                       # Native targets, OS adapter selection, CTest
├── Crypty.spec                          # PyInstaller folder-bundle recipe
├── build_native.py                      # CMake-based native build helper
├── auth_client.py                       # Desktop client for the auth API
├── makefile                             # Common local developer shortcuts
├── requirements.txt                     # Desktop Python dependencies
└── README.md                            # Onboarding, setup, architecture, and MVP plan
```

`app/main.py` is intentionally a small entry point; screens belong in `ui/`,
native orchestration and domain code in `core/`, and account service code in
`auth/`. Keep OS APIs in `core/platform/`. Some directories (such as
`core/evidence/` and `core/storage/`) are reserved or currently contain no
implemented source; add files there only when a concrete responsibility and
tests exist. Build outputs, virtual environments, local databases, credentials,
and acquired evidence should not be committed.

## Cross-platform core MVP roadmap

Treat portability as an architectural constraint from the beginning, not a
cleanup project to defer until all features are complete. Keep changes small
and continuously build/test on each target OS. Do not move destructive
operations into real-device workflows before the preceding safety, testing,
and audit gates are met.

### Fastest responsible path to the promised MVP

Keep the MVP to one desktop workstation workflow on each declared OS:
**inspect/acquire evidence → recover to a separate destination → sanitize an
explicitly selected supported target → export a durable operation report**.
The website should explain the actual release, limitations, and support path;
it is not a second product backend.

To avoid ballooning the first release, defer face authentication, AI chat,
payments, licensing, team/central audit, cloud synchronization, and broad
filesystem/device coverage. Keep them visibly planned on the website rather
than making them prerequisites for the local workstation MVP. Use the current
auth API only for development until a supported user/account model is chosen.

Execute in this order, making each row a release gate:

| Gate | Ship this | Exit criteria |
| --- | --- | --- |
| 0. Scope | Freeze OS/CPU targets, filesystems, supported source types, and non-goals | A capability matrix separates implemented, experimental, and unavailable operations |
| 1. Portability | Green native build, unit tests, and app startup on Windows/Linux/macOS CI | Each OS has a real tested adapter; unsupported hardware access fails clearly |
| 2. Evidence safety | Inspect/acquire a source read-only, verify an image hash, and keep output elsewhere | Fixture tests prove source bytes do not change; interrupted/error cases are reported |
| 3. Recovery | Finish one filesystem end-to-end first, then add others only when tested | Known image fixtures recover expected bytes/hashes; partial recovery is explicit |
| 4. Audit/report | Persist operation ID, actor, target identity, settings, timestamps, warnings, result, and verification | Restarting the app does not erase records; report export matches stored operation data |
| 5. Sanitization | Start with plan/preview; enable a real method only for supported, unambiguous media after review | Wrong-target, missing-permission, cancellation, and verification-failure tests all fail safe |
| 6. Product release | Resolve the auth startup dependency, package per OS, publish accurate website/help | Fresh-machine install and basic workflow validated on every declared target |

For speed, do not parallelize recovery and real sanitization implementation
before the evidence boundary and audit schema stabilize. Build recovery and
sanitization as separate use cases, but share device identity, permissions,
progress/error reporting, operation IDs, and report infrastructure.

### 1. Define the MVP and platform support contract

- Specify supported OS versions, filesystems, device types, and operation
  modes; decide which operating systems will be first-class MVP targets and
  which may follow.
- Decide what the first release will explicitly not support (for example,
  RAID, encrypted volumes without keys, damaged hardware, or guaranteed SSD
  recovery).
- Define a platform capability matrix for volume enumeration, raw read-only
  access, permissions, imaging, recovery, sanitization, and packaging.
- Document operator authorization, privacy/data retention, and incident
  handling expectations.
- Create a feature matrix that labels each capability as implemented,
  experimental, simulated, or planned.

**Done when:** product scope and claims are testable and match the code.

### 2. Establish and enforce the portability boundary

- Continue inventorying OS-specific paths, compiler assumptions, packaging,
  and dependencies.
- Keep the platform-neutral device/storage interface. Windows and POSIX
  adapters now live in separate platform-specific source files; select them
  in CMake without leaking OS headers into shared interfaces.
- Keep filesystem parsing and recovery algorithms platform-independent:
  give them a bounded random-access reader interface, not OS handles or
  device paths.
- Use `std::filesystem` and platform-neutral Python APIs for ordinary paths;
  isolate raw-device access, privilege checks, alignment, and device identity
  behind adapters.
- Make unsupported platform operations return an explicit capability/error,
  never a demo success or silent fallback.
- Keep CI builds and tests on every declared target green before expanding
  features.

**Done when:** the core builds on each declared OS, platform-specific code is
isolated, and unsupported device operations fail clearly.

### 3. Make evidence acquisition safe and repeatable

- Implement reliable device identification and stable source handles.
- Default evidence access to read-only; make read/write state visible and
  fail closed if the requested protection cannot be established.
- Add image acquisition to a separate destination, with source/image size,
  timestamps, errors, and cryptographic hashes recorded.
- Reopen and verify acquired images before analysis; never recover files back
  onto the source.
- Test against disposable images and virtual disks before physical media.

**Done when:** tests prove analysis does not modify source bytes, and image
hashes and errors are reproducible.

### 4. Deliver a bounded recovery workflow

- Establish small, known-good image fixtures for each supported filesystem.
- Validate detection, metadata parsing, deleted-entry identification, and
  file reconstruction independently.
- Handle resident data, fragmented extents, sparse regions, partial reads,
  malformed metadata, path collisions, and interrupted operations.
- Write output only to a user-selected destination; verify reconstructed size
  and hash where possible and label partial/uncertain results.
- Add progress, cancellation, safe error reporting, and testable confidence
  reasons rather than presenting a score without evidence.

**Done when:** automated tests cover normal, damaged, truncated, and
interrupted cases and compare output against known fixture hashes.

### 5. Add a durable operation ledger

- Use structured operation records/events with stable IDs, timestamps,
  actor, target fingerprint, operation/configuration, outcome, and
  verification fields.
- Persist locally before showing an operation as complete. Handle disk-full,
  process crash, clock issues, and interrupted writes explicitly.
- Export a human-readable report plus machine-readable data; include schema
  version and hashes for the report/evidence image where appropriate.
- Add search/filtering and retention controls. Protect sensitive paths and
  personal data in logs.

**Done when:** an operator can reconstruct who did what, to which target,
with what settings and result, including failed/interrupted runs.

### 6. Implement sanitization only after safety review

- Begin with a **simulation/planning mode** that identifies the target,
  evaluates the device and available methods, and produces a preview without
  modifying media.
- For real execution, require explicit authorization, strong target
  re-identification, a separate destructive-action permission, and a
  deliberate confirmation that cannot be triggered by the recovery workflow.
- Use an appropriate, documented device/platform method and verify/report
  its result. Clearly state when verification is unavailable or limited.
- Base method selection and claims on current recognized guidance (including
  NIST SP 800-88 Rev. 2 where applicable), device documentation, and expert
  review. Do not invent universal overwrite-pass guarantees.
- Keep sanitization disabled on unsupported or ambiguous devices; retain
  operation evidence without claiming certification.

**Done when:** misuse tests prove the wrong device cannot be silently erased,
the operation is auditable, and the report states exactly what was and was
not verified.

### 7. Harden, package, and support the desktop workstation

- Centralize configuration, logging, error types, and version reporting.
- Add per-platform dependency/build configuration, reproducible builds,
  signed release artifacts, and update/rollback procedures.
- Test fresh install, least-privilege use, recovery from crashes, multiple
  display/DPI settings, and supported OS/device combinations.
- Remove development auth bypasses and secrets from distributable builds;
  review authentication, authorization, local database protection, and
  session expiry before any external pilot.
- Add operator help, safety checklists, release notes, and a support/bug
  report path.

**Done when:** another team member can install, validate, and use a release
from documented steps without developer-only setup.

### 8. Make the website launch-ready

- Replace mock product metrics and simulated workflow imagery with clearly
  labeled product screenshots or architecture illustrations.
- Publish an accurate support/filesystem matrix, limitations, data handling
  and privacy policy, security contact, version/status, and safety
  disclaimers.
- Either wire the interest form to a consent-aware backend with spam
  protection and privacy notice, or keep it explicitly marked as a demo.
- Treat pricing, waitlist, team audit console, licensing, and centralized
  services as proposals until they exist; avoid implying they are available.
- Keep the optional chatbot isolated from forensic data, avoid collecting
  secrets/evidence, and provide a clear non-AI support route.
- Add accessible mobile layouts, metadata/SEO, analytics only with an
  appropriate privacy approach, and automated checks for links/forms.

**Done when:** every public claim maps to a tested capability or is visibly
marked as planned/conceptual.

## Architecture and maintainability decisions

### Keep modules organized around responsibilities

Use explicit boundaries: UI → application use case → domain types/policy →
platform/storage adapter → filesystem implementation. Keep report rendering,
authentication, website concerns, and device I/O out of filesystem parsers.
Prefer small typed interfaces and structured results to generic dictionaries
crossing the Python/C++ boundary. Avoid a large rewrite; extract seams while
adding tested behavior.

The single file in `app/` is currently just the desktop entry point and
composition root; the screens live under `ui/`, while authentication and
workflows live elsewhere. That is not automatically a defect. Keep
`app/main.py` small and split bootstrap/configuration or application use cases
into modules only when they have real responsibilities. Do not move UI code
into `app/` simply to make the directory look fuller.

### Cross-platform status

The C++ core now has a platform-neutral storage boundary, a Windows adapter,
and a POSIX adapter selected by CMake. The Python native-library loader and
build/package entry points also select platform-specific library names. CI is
configured for Windows, Linux, and macOS. Only the Windows build and tests
have been run in the current development environment; Linux/macOS CI results
and physical-device behavior still need validation.

The next portability work is to confirm CI on all three operating systems,
test privilege/error behavior with disposable images and devices, verify
native packaging and Qt startup on each OS, and improve device identity and
capability reporting. Keep platform gaps explicit; a successful build is not
proof of safe physical-device access.

### Use an event ledger, not event sourcing everywhere

An event-based audit trail is worthwhile for forensic accountability, but a
general event bus or full event-sourced architecture is likely unnecessary
for the MVP. Start with explicit operation commands that append structured,
durable audit events and update a simple current-operation state. Keep event
creation in the application/use-case boundary; let UI progress subscribe to
notifications without becoming the source of truth. Add an outbox/central
sync later only if offline team workflows require it.

### Testing and delivery discipline

- Make deterministic image fixtures the core test assets; never use a user's
  live disk as a routine test.
- Add Python unit/integration tests alongside the existing C++ tests.
- Require tests, static analysis, and a clean build in CI for pull requests.
- Review every hardware-facing change for read/write behavior, cancellation,
  permissions, error paths, and audit coverage.
- Keep security-sensitive decisions documented and get qualified review
  before real sanitization or evidence-handling claims.

## Contributing

1. Open an issue or small design note describing the user impact, supported
   target, safety implications, and acceptance tests.
2. Keep changes focused; add or update deterministic tests and relevant
   operator documentation.
3. Run the CMake build and CTest suite. Include the exact commands and
   results in the pull request; include Python/UI checks when those areas
   change.
4. Do not include real evidence, credentials, customer data, or generated
   forensic artifacts in commits or issue attachments.

For an initial contribution, start with test fixtures, clear error handling,
read-only guarantees, report schemas, or documentation rather than enabling
real-device sanitization.
