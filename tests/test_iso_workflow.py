from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/astra-iso.yml"


def test_iso_workflow_uses_debian_builder_and_retains_evidence():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "debian:12-slim" in text
    assert "docker run --privileged" in text
    assert "./os-distribution/build-iso.sh --non-interactive" in text
    assert "./scripts/qemu_boot_smoke.sh" in text
    assert "scripts/inspect_iso_payload.py" in text
    assert "actions/upload-artifact@v4" in text
    assert "if: always()" in text
    for evidence in (
        "build-host-packages.tsv",
        "wheelhouse-manifest.json",
        "qemu-serial.log",
        "ci-build.log",
        "iso-inspection.json",
    ):
        assert evidence in text
    assert "$RUNNER_TEMP/astra-iso-artifacts" in text
    assert "ASTRA_BUILD_DIR=/tmp/astra-build" in text
    assert "ASTRA_OUTPUT_DIR=/artifacts" in text
    assert "ASTRA_FRONTEND_STAGING_DIR=/tmp/astra-frontend-staging" in text


def test_qemu_harness_supports_persistent_ci_log():
    text = (ROOT / "scripts/qemu_boot_smoke.sh").read_text(encoding="utf-8")
    assert "ASTRA_QEMU_LOG" in text
    assert 'mkdir -p "$(dirname "$LOG_FILE")"' in text
