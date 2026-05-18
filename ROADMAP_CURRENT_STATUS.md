# JARVIS-2026 Roadmap Status

Last updated: 2026-05-13

## Current Assessment

| Phase | Status | Evidence | Next Focus |
| --- | --- | --- | --- |
| Phase 1: Voice Stack | Partial / active | `VoiceManager`, voice router, wake-word toggles, TTS/STT adapters, voice analytics endpoints and UI exist. | Harden provider selection, offline STT, latency telemetry, and microphone permission UX. |
| Phase 2: System Software Layer | Advanced / active | Filesystem explorer, OS control, service listing, audio/camera/network/power managers, settings panel, and safety-gated package lifecycle controls exist. | Expand app launcher UX and service lifecycle actions. |
| Phase 3: Recovery & Safety | Advanced / active | Added `SafetyManager`, `/api/os/safety/*`, checkpoint backups/restores, allowlisted maintenance diagnostics, command safety gates, audit logging, and Settings UI controls. | Extend safety gates to hardware/power/network mutations and begin Phase 4 validation scripts. |
| Phase 4: Hardware Validation | Advanced / active | Added repeatable hardware validation reports, compatibility matrix storage, backend endpoints, CLI runners, GPU/Bluetooth probes, audio latency estimation, camera/audio workload checks, and stress/thermal capture. | Run reports on 5+ target hardware configurations and collect compatibility evidence. |
| Phase 5: UX Polish | Partial | OS login, biometric enrollment, boot sequence, dashboard, dock, analytics/settings panels exist. | Add onboarding, voice training wizard, accessibility, language settings. |
| Phase 6: Production Hardening | Advanced / active | Security audit, performance baseline, failover drill, release evidence managers, CLIs, backend endpoints, Settings UI, readiness integration, and focused tests exist. | Capture release-candidate evidence on target machines and stabilize findings. |
| Phase 7: Distribution & Support | Active | Deployment/readiness docs, release evidence bundling, release notes, user manual, patch/update process, support workflow, package metadata, release manifests, update planning, and manifest-backed update execution exist. | Add installer automation and final target-machine release evidence. |

## Immediate Roadmap Direction

The safest next engineering path is:

1. Finish Phase 3 enforcement so high-risk Phase 2 features can be built safely.
2. Add package/app lifecycle management only after confirmation gates and audit entries are active.
3. Turn hardware validation into repeatable scripts and reports before broad UX polish.

## Phase 3 Work Completed In This Pass

- Added a durable safety state file under `memory/safety/safety_state.json`.
- Added recovery checkpoint manifests under `backups/recovery/`.
- Added safe mode and recovery mode backend controls.
- Added audit logging for safety state changes.
- Added a Recovery & Safety section to the Settings panel.
- Added unit coverage for the safety manager.

## Phase 2 Work Completed After Safety Gates

- Added provider detection for `winget`, `choco`, `apt-get`, `dnf`, `pacman`, and `brew`.
- Added package search, installed listing, install, uninstall, and update planning.
- Added explicit confirmation gates for package-changing actions.
- Blocked package-changing actions while safe mode or recovery mode is active.
- Added Package Lifecycle controls to Settings.
- Added unit coverage for package lifecycle planning and safety blocking.

## Phase 2 Work Completed In App/Service Slice

- Added allowlisted app launcher endpoints with dry-run planning and explicit launch confirmation.
- Added tracked service lifecycle endpoints for start, stop, restart, and status.
- Restricted service start directories to the JARVIS workspace boundary.
- Blocked service start/restart while safe mode or recovery mode is active.
- Added App Launcher and Service Lifecycle controls to the OS Control panel.
- Added audit records for app launch and service lifecycle actions.

## Phase 3 Work Completed In Restore/Maintenance Slice

- Extended recovery checkpoints from metadata-only manifests into restorable tracked-file backups.
- Added dry-run restore planning, explicit restore confirmation, workspace-boundary validation, and restore state persistence.
- Added an allowlisted offline maintenance command runner for read-only diagnostics.
- Added `/api/os/safety/restore` and `/api/os/safety/maintenance-command` endpoints with audit records.
- Added Settings UI controls for checkpoint selection, restore planning/execution, and maintenance diagnostics.
- Added unit coverage for restore confirmation, tracked-file restore, and blocked maintenance commands.

## Phase 3 Work Completed In Command Enforcement Slice

- Added a centralized command safety gate for shell/developer command classification.
- Blocked destructive shell commands such as recursive remove, disk formatting, shutdown/reboot, hard resets, and forced git cleans.
- Required explicit confirmation before mutating shell commands such as package installs, service lifecycle commands, file moves/copies, and git write operations.
- Blocked mutating shell commands while recovery mode is active.
- Routed `modules.tools.shell.run_shell` and `ExecuteCommandSkill` through the command safety gate.
- Added local JSONL command-gate audit records under `memory/safety/command_audit.jsonl`.
- Tightened developer file management so read/write requests cannot escape the workspace boundary.
- Added unit coverage for destructive blocking, mutating confirmation, recovery-mode blocking, shell tool enforcement, and developer skill enforcement.

## Phase 4 Work Completed In Hardware Validation Slice

- Added `HardwareValidationManager` to generate repeatable compatibility reports from device, audio, camera, network, and power managers.
- Added pass/warn/fail/unknown checks for CPU, memory, storage, display, audio, camera, network, battery, thermal sensors, GPU, and Bluetooth.
- Persisted validation reports under `test_reports/hardware_validation/`.
- Added compatibility matrix summaries grouped by target hardware configuration.
- Added backend endpoints for validation runs, saved report listing, and compatibility matrix retrieval.
- Added `validate_hardware.py` CLI for target-machine validation outside the web UI.
- Added deterministic unit coverage for report structure, persistence, matrix generation, and low-resource failure cases.

## Phase 4 Work Completed In Driver Probe Slice

- Added platform GPU probes using Windows CIM, Linux `lspci`/`nvidia-smi`, and macOS `system_profiler`.
- Added platform Bluetooth probes using Windows PnP, Linux `bluetoothctl`/`hciconfig`, and macOS `system_profiler`.
- Added PyAudio-based audio latency estimation from default input/output device latency metadata.
- Updated hardware validation checks so GPU, Bluetooth, and audio latency now pass/warn/fail/unknown from probe evidence.
- Added deterministic unit coverage for probe-backed pass results, missing probe tools, and high-latency audio failure.

## Phase 4 Work Completed In Stress/Thermal Capture Slice

- Added `HardwareStressManager` for repeatable CPU, memory, disk, network, battery, and thermal sampling.
- Added pass/warn/fail summary logic for high CPU, memory pressure, high temperature, and missing thermal data.
- Persisted stress reports under `test_reports/hardware_stress/`.
- Added backend endpoints for stress capture runs and saved stress report listing.
- Added `capture_hardware_stress.py` CLI for target-machine capture during validation sessions.
- Added deterministic unit coverage for report summaries, thermal warnings, high-temperature failures, and saved reports.

## Phase 4 Work Completed In Camera/Audio Workload Slice

- Added audio workload readiness checks for default input/output device availability and sample-rate metadata.
- Added camera snapshot workload checks that try to capture a validation frame and restore prior camera state afterward.
- Integrated camera/audio workload evidence into hardware validation reports.
- Added deterministic coverage for pass, unknown, warn, and fail workload outcomes.

## Phase 5 Work Completed In First-Run Readiness Slice

- Added `/api/os/readiness` to summarize system resources, recovery checkpoints, package provider, voice stack, device matrix, hardware validation, and service lifecycle readiness.
- Added a first-run onboarding screen after login with a readiness score, checklist, checkpoint creation, and Settings handoff.
- Persisted onboarding completion in browser local storage so normal boot goes straight to the OS after setup.
- Added a dashboard initial-panel handoff so onboarding can route directly to Settings when setup needs attention.

## Phase 5 Work Completed In Voice Training Slice

- Fixed `/api/os/voice/state`, `/api/os/voice/listen`, and `/api/os/voice/speak` to match the current `VoiceManager` dataclass contract.
- Added persisted voice training profiles under `memory/voice/training_profile.json`.
- Added `/api/os/voice/training`, `/api/os/voice/training/record`, and `/api/os/voice/training/reset` endpoints with audit entries for training changes.
- Added a Settings voice training wizard with prompt playback, browser speech capture when available, manual transcript fallback, confidence calibration, progress tracking, and reset.
- Added unit coverage for voice training persistence and reset behavior.

## Phase 5 Work Completed In Preferences & Accessibility Slice

- Added persistent OS preferences for language, TTS voice style, high contrast, large text, reduced motion, scanlines, and telemetry refresh cadence.
- Added `/api/os/preferences`, `/api/os/preferences/reset`, and readiness integration for accessibility/language setup.
- Wired global UI preference application through `App.js`, including document language, contrast, scanline, motion, and large-text classes.
- Added Settings controls for language, voice style, accessibility toggles, and telemetry refresh interval.
- Connected telemetry refresh preferences to Dashboard and OS Control polling cadence.
- Added unit coverage for preference validation, persistence, reset, and bounds clamping.

## Phase 6 Work Completed In Security Audit Slice

- Added `SecurityAuditManager` for repeatable production hardening checks across environment secrets, CORS, session token posture, safety gates, audit artifacts, dependency lockfiles, runtime artifacts, and sensitive file permissions.
- Added saved security audit reports under `test_reports/security_audit/`.
- Added `run_security_audit.py` CLI for release validation outside the web UI.
- Added `/api/os/security/audit` and `/api/os/security/audits` backend endpoints.
- Added security audit readiness integration so first-run readiness tracks whether a hardening audit has been captured.
- Added a Production Hardening section to Settings with audit execution, score, status, recent report count, and check-level findings.
- Added deterministic unit coverage for report generation, wildcard CORS warnings, short token failures, missing safety gate failures, and saved report listing.

## Phase 6 Work Completed In Performance Baseline Slice

- Added `PerformanceBaselineManager` for repeatable lightweight memory drift, CPU, thread, handle, and operation-latency sampling.
- Added saved performance baseline reports under `test_reports/performance_baselines/`.
- Added `run_performance_baseline.py` CLI for release-candidate baseline capture outside the web UI.
- Added `/api/os/performance/baseline` and `/api/os/performance/baselines` backend endpoints with audit records.
- Added performance baseline readiness integration so first-run readiness tracks whether a production baseline has been captured.
- Extended the Production Hardening Settings section with a 5-second baseline action, status, RSS growth, and recent report count.
- Added deterministic unit coverage for report structure, memory-growth warnings, operation-failure failures, and saved report listing.

## Phase 6 Work Completed In Failover Drill Slice

- Added `FailoverDrillManager` for non-mutating recovery, fallback control, command-gate, maintenance shell, and service inventory drills.
- Added saved failover drill reports under `test_reports/failover_drills/`.
- Added `run_failover_drill.py` CLI for release-candidate drill capture outside the web UI.
- Added `/api/os/failover/drill` and `/api/os/failover/drills` backend endpoints with audit records.
- Added failover drill readiness integration so first-run readiness tracks whether a drill has been captured.
- Extended the Production Hardening Settings section with failover drill execution, score, status, recent report count, and compact check results.
- Added deterministic unit coverage for report structure, missing checkpoint warnings, destructive gate failures, service inventory failures, and saved report listing.

## Phase 6 Work Completed In Release Evidence Slice

- Added `ReleaseEvidenceManager` to bundle the latest saved security audit, performance baseline, failover drill, hardware validation, and stress evidence into one release-candidate report.
- Added saved release evidence bundles under `test_reports/release_evidence/`.
- Added `run_release_evidence.py` CLI for release-candidate evidence capture outside the web UI.
- Added `/api/os/release/evidence` backend endpoints for creating and listing release evidence bundles with audit records.
- Added release evidence readiness integration so first-run readiness tracks whether an evidence bundle has been captured.
- Extended the Production Hardening Settings section with release evidence bundle creation, status, score, bundle count, and item-level evidence status.
- Added deterministic unit coverage for missing required evidence, ready-with-warnings evidence, fully ready evidence, failed required reports, and saved bundle listing.

## Phase 7 Work Started In Distribution Docs Slice

- Added `os-distribution/RELEASE_NOTES.md` with release-candidate scope, required evidence commands, known warnings, upgrade notes, and validation snapshot.
- Added `os-distribution/USER_MANUAL.md` with startup, first-run, Settings, safety mode, checkpoint, hardening, hardware validation, troubleshooting, and data-location guidance.
- Added `os-distribution/PATCH_UPDATE_PROCESS.md` with patch classes, pre-patch checkpointing, validation commands, rollback flow, versioning, and acceptance criteria.
- Added `os-distribution/SUPPORT_WORKFLOW.md` with triage levels, intake checklist, investigation flow, escalation package, and resolution checklist.
- Updated `os-distribution/README.md` to point operators at the Phase 7 documents and current release evidence workflow.

## Phase 7 Work Completed In Manifest & Update Planning Slice

- Added `os-distribution/VERSION.json` as release-candidate package metadata.
- Added `ReleaseManifestManager` for generating SHA-256 release manifests from distribution-critical files.
- Added saved release manifests under `os-distribution/manifests/`.
- Added `generate_release_manifest.py` CLI for packaging metadata generation.
- Added `plan_update.py` CLI to compare current and candidate manifests, summarize added/changed/removed files, flag critical paths, and require checkpoint/evidence gates.
- Updated release notes, patch process, and distribution README with manifest and update-planning commands.
- Added deterministic unit coverage for manifest hashing, saved manifest listing, update diff detection, critical path detection, and no-change plans.

## Phase 7 Work Completed In Update Execution Slice

- Added `ReleaseUpdateManager` for manifest-backed patch payload dry-runs and explicitly confirmed execution.
- Added hash verification for candidate files before copying them into the workspace.
- Added automatic changed-file backups under `backups/updates/` before confirmed writes.
- Skipped file removals by default unless operators pass an explicit removal flag.
- Added `apply_update.py` CLI for update dry-run planning and confirmed patch execution.
- Updated release notes, patch process, support workflow, and distribution README with update execution guidance.
- Added deterministic unit coverage for dry-run planning, confirmation blocking, confirmed copy with backup, hash mismatch blocking, and default removal skipping.
