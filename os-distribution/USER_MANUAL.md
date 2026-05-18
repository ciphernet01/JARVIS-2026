# JARVIS OS User Manual

## Overview

JARVIS OS is a local assistant operating environment with a React control surface, FastAPI backend, voice tools, hardware managers, safety gates, and release validation workflows.

Use the React interface for normal operation. Use the CLI scripts for release validation and recovery evidence.

## Start The System

Backend:

```powershell
cd C:\JARVIS-2026\backend
uvicorn server:app --host 0.0.0.0 --port 8001
```

Frontend:

```powershell
cd C:\JARVIS-2026\frontend
$env:REACT_APP_BACKEND_URL="http://localhost:8001"
npm start
```

Open:

```text
http://localhost:3000
```

## First Run

After login, onboarding shows a readiness checklist. Work through warnings in this order:

1. Create a recovery checkpoint.
2. Complete voice training if voice is available.
3. Confirm language and accessibility preferences.
4. Run hardware validation on the current machine.
5. Run production hardening checks.

## Main Controls

Dashboard:

- System resource telemetry
- Voice analytics
- Readiness status
- Navigation to Settings and OS Control

Settings:

- Recovery and safety controls
- Checkpoint create, restore plan, restore execution
- Maintenance diagnostics
- Package lifecycle
- Voice training
- Language and accessibility preferences
- Production hardening evidence

OS Control:

- App launch plans and confirmations
- Service lifecycle plans and execution
- Hardware and process visibility

## Safety Modes

Safe mode limits risky runtime actions.

Recovery mode is stricter and treats mutating command paths as read-only by default.

Use Settings > Recovery & Safety to toggle modes. Always add a reason so audit entries are useful later.

## Recovery Checkpoints

Create a checkpoint before:

- Package changes
- Service lifecycle changes
- Patch installation
- Release-candidate validation

Restore flow:

1. Select a checkpoint.
2. Run a restore plan.
3. Review staged files.
4. Execute restore only after confirmation.

## Production Hardening

Use Settings > Production Hardening or the CLI:

```powershell
python run_security_audit.py
python run_performance_baseline.py
python run_failover_drill.py
python run_release_evidence.py
```

Release status meanings:

- `ready`: required evidence passed.
- `ready_with_warnings`: required evidence passed, but recommended evidence is missing or warning.
- `blocked`: required evidence is missing or failed.

## Hardware Validation

Run validation on every target device profile:

```powershell
python validate_hardware.py --label "device-name"
python capture_hardware_stress.py --label "device-name-stress"
```

Save the resulting reports and create a release evidence bundle afterwards.

## Troubleshooting

Authentication failure:

- Confirm the backend is running on port `8001`.
- Refresh login and use a current session token.

Voice unavailable:

- Check microphone permission.
- Complete voice training.
- Confirm STT/TTS dependencies are installed.

Package provider unavailable:

- Install one supported provider: `winget`, `choco`, `brew`, `apt-get`, `dnf`, or `pacman`.

Build warnings:

- Existing unused-import warnings do not block the production build.
- New warnings should be reviewed before release.

## Data Locations

- Runtime preferences: `memory/preferences/`
- Safety state and audit logs: `memory/safety/`
- Voice training profile: `memory/voice/`
- Recovery checkpoints: `backups/recovery/`
- Validation reports: `test_reports/`
