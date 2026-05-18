# Support Workflow

## Support Goals

Support should preserve user data, avoid unsafe system mutation, and produce enough evidence for a fix without guessing.

## Triage Levels

P0: Critical outage

- System cannot boot or backend cannot start.
- Recovery restore is broken.
- Safety gate allows destructive commands.
- Authentication is bypassed or unusable.

P1: Major feature blocked

- Voice stack unusable.
- Settings or OS Control unavailable.
- Package/service lifecycle actions fail.
- Hardware validation cannot run on a target device.

P2: Degraded operation

- Readiness warnings.
- Performance baseline warns.
- Hardware stress warns.
- Frontend build warnings that do not block release.

P3: Documentation or usability

- Manual gaps.
- Unclear messages.
- Cosmetic UI issues.

## Intake Checklist

Collect:

- JARVIS version or release label.
- Operating system and hardware model.
- Exact action attempted.
- Screenshot or copied error text.
- Latest release evidence bundle path.
- Latest relevant report path under `test_reports/`.

Commands:

```powershell
git status --short
python run_release_evidence.py --label "support-intake"
```

Optional targeted reports:

```powershell
python run_security_audit.py
python run_performance_baseline.py --duration 30 --interval 2
python run_failover_drill.py
python validate_hardware.py --label "support-device"
```

## First Response

1. Confirm whether the issue is safety-critical.
2. If safety-critical, ask the operator to enable safe mode.
3. If recovery is needed, use checkpoint restore planning before execution.
4. Request the latest evidence bundle and specific failed report.
5. Avoid asking the operator to run destructive shell commands.

## Investigation Flow

Backend issue:

- Check backend process and logs.
- Confirm port `8001`.
- Run focused pytest for the changed subsystem.

Frontend issue:

- Confirm backend URL.
- Run `npm.cmd run build`.
- Check browser console output.

Voice issue:

- Check microphone permission.
- Check voice training profile.
- Check STT/TTS capability matrix.

Hardware issue:

- Run hardware validation.
- Run hardware stress capture if thermal or load behavior matters.
- Compare compatibility matrix entries.

Release issue:

- Run all required Phase 6 evidence scripts.
- Review the item that makes release evidence `blocked`.
- For patch issues, run `plan_update.py` and `apply_update.py` without `--execute` to capture the intended file actions.

## Escalation Package

For P0/P1 escalation, attach or reference:

- `ROADMAP_CURRENT_STATUS.md`
- Latest `test_reports/release_evidence/*.json`
- Relevant failed report under `test_reports/`
- Latest safety audit or command audit under `memory/safety/`
- Relevant update backup under `backups/updates/` if a manifest-backed patch was applied
- Steps to reproduce
- Expected versus actual result

## Resolution Checklist

Before closing:

- Root cause is documented.
- Fix or workaround is documented.
- Focused tests pass.
- Frontend build passes if UI changed.
- Release evidence is recreated.
- Roadmap or release notes are updated if behavior changed.

## Known Current Support Notes

- PowerShell may block `npm.ps1`; use `npm.cmd run build`.
- Pytest may lack permission to use the default Windows temp directory; use `--basetemp=.tmp\pytest-name`.
- Existing frontend unused-import warnings are known and do not currently block builds.
