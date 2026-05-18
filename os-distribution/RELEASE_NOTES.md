# JARVIS OS Release Notes

## Release Candidate: Phase 7 Start

Status: release-candidate preparation

This release candidate introduces the production-hardening evidence workflow needed before broader distribution. It is not a final public release until target-machine evidence has been captured and reviewed.

## Highlights

- Added first-run readiness and onboarding so setup blockers are visible after login.
- Added recovery checkpoints, restore planning, safe mode, recovery mode, and maintenance diagnostics.
- Added safety gates for destructive and mutating shell/developer commands.
- Added package lifecycle, app launcher, and service lifecycle controls behind confirmation gates.
- Added repeatable hardware validation and hardware stress reports.
- Added voice training, language preferences, and accessibility settings.
- Added production hardening checks:
  - Security audit
  - Performance baseline and memory drift check
  - Failover drill
  - Release evidence bundle
- Added release manifest generation and manifest-backed update planning/execution tooling.
- Added Settings UI controls and CLIs for release validation evidence.

## Required Release Evidence

Before marking a build as ready, capture:

```powershell
python run_security_audit.py
python run_performance_baseline.py --duration 30 --interval 2
python run_failover_drill.py
python run_release_evidence.py
python generate_release_manifest.py --notes "release candidate manifest"
```

Recommended target-machine evidence:

```powershell
python validate_hardware.py --label "target-device"
python capture_hardware_stress.py --label "target-device-stress" --duration 120 --interval 5
python run_release_evidence.py --label "target-device-rc"
```

## Known Warnings

- Frontend production build succeeds but reports existing unused import warnings in unrelated components:
  - `DevWorkspace.js`
  - `StatusPanel.js`
  - `SystemDiagnostics.js`
  - `WeatherWidget.js`
- Phase 4 target coverage still needs evidence from multiple hardware configurations.
- Existing deployment status docs may contain stale counts from earlier phases. Treat `ROADMAP_CURRENT_STATUS.md` and release evidence bundles as current.

## Upgrade Notes

- Runtime evidence is saved under `test_reports/`.
- Release manifests are saved under `os-distribution/manifests/`.
- Manifest-backed update backups are saved under `backups/updates/`.
- Safety and preference state is saved under `memory/`.
- Recovery checkpoint data is saved under `backups/recovery/`.
- Do not delete these directories during patch validation unless you intentionally want a clean first-run state.

## Validation Snapshot

Latest focused validation at Phase 7 start:

- Phase 6 focused tests: `21 passed`
- Frontend production build: passed with unrelated warnings
- Python compile checks for new managers and CLIs: passed
