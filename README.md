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
and create the first local admin account from the repository root:

```sh
python -m pip install -r auth/api/requirements.txt
python auth/api/create_first_admin.py admin1 "choose-a-strong-password"
```

Then start the service in a terminal:

```sh
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
- `core/device_access.hpp` and `core/platform/`: platform-neutral storage
  interface and OS-specific enumeration/read adapters. The native algorithms
  should consume bounded reads and remain independent of OS handles.
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

## Cross-platform core MVP roadmap

Treat portability as an architectural constraint from the beginning, not a
cleanup project to defer until all features are complete. Keep changes small
and continuously build/test on each target OS. Do not move destructive
operations into real-device workflows before the preceding safety, testing,
and audit gates are met.

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
