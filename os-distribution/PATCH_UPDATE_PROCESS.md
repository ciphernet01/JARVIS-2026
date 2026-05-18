# Patch And Update Process

## Purpose

This process keeps JARVIS OS patches reversible, auditable, and tied to release evidence.

## Patch Classes

Critical:

- Security gate fixes
- Recovery restore fixes
- Authentication or token handling fixes
- Data loss or destructive command prevention

Standard:

- Feature improvements
- UI fixes
- Hardware compatibility improvements
- Performance improvements

Documentation:

- Manuals
- Release notes
- Support procedures

## Pre-Patch Checklist

1. Review `git status --short`.
2. Create a recovery checkpoint in Settings or through the backend.
3. Run focused tests for the touched subsystem.
4. Record the current release evidence bundle if validating a release candidate.
5. Generate or collect the current release manifest.

Recommended commands:

```powershell
git status --short
python generate_release_manifest.py --notes "pre-patch manifest"
python run_release_evidence.py --label "pre-patch"
```

If you have both current and candidate manifests, plan the update before applying it:

```powershell
python plan_update.py os-distribution/manifests/current.json os-distribution/manifests/candidate.json
```

To inspect the exact file actions from a candidate payload, run the update command without `--execute`:

```powershell
python apply_update.py os-distribution/manifests/current.json os-distribution/manifests/candidate.json candidate-payload
```

## Apply Patch

1. Keep code changes scoped to the subsystem.
2. Preserve user/runtime state under `memory/`, `backups/`, and `test_reports/`.
3. Avoid deleting generated evidence unless starting a clean validation cycle intentionally.
4. Update tests with the behavioral change.
5. Update documentation if operator workflow changes.

For manifest-backed patch payloads, apply only after creating a checkpoint and reviewing the dry-run plan:

```powershell
python apply_update.py os-distribution/manifests/current.json os-distribution/manifests/candidate.json candidate-payload --execute --confirmed
```

File removals are skipped by default. To allow removals from the candidate manifest, add `--allow-removals`; removed files are backed up first under `backups/updates/`.

## Post-Patch Validation

For backend or service changes:

```powershell
python -m py_compile modules/services/*.py
python -m pytest tests/test_security_audit_manager.py tests/test_performance_baseline_manager.py tests/test_failover_drill_manager.py tests/test_release_evidence_manager.py --basetemp=.tmp\pytest-phase7
```

For frontend changes:

```powershell
cd frontend
npm.cmd run build
```

For release-candidate validation:

```powershell
python run_security_audit.py
python run_performance_baseline.py --duration 30 --interval 2
python run_failover_drill.py
python run_release_evidence.py --label "post-patch"
```

## Rollback

Use rollback when a patch fails validation or blocks required release evidence.

1. Enable safe mode.
2. Select the latest known-good checkpoint.
3. Run restore plan.
4. Review staged files.
5. Execute restore with confirmation.
6. Re-run release evidence.

Do not use broad destructive git commands as rollback on user machines. Prefer the checkpoint restore flow.

Manifest-backed updates also create per-file backups under:

```text
backups/updates/
```

## Versioning

Use this version shape until packaging automation is added:

```text
YYYY.MM.DD-rc.N
YYYY.MM.DD-hotfix.N
```

Examples:

```text
2026.05.17-rc.1
2026.05.17-hotfix.1
```

The active package metadata lives in:

```text
os-distribution/VERSION.json
```

## Patch Acceptance Criteria

A patch can be accepted when:

- Required focused tests pass.
- Frontend build passes if UI changed.
- Security audit is not failed.
- Performance baseline is not failed.
- Failover drill is not failed.
- Release evidence is not `blocked`.
- Known warnings are documented.
- A release manifest exists for the accepted patch.
- Manifest-backed updates have a dry-run plan and backup path for changed files.
