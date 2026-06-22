import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_distribution.py"


def test_distribution_preflight_reports_machine_readable_results():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["summary"]["fail"] == 0
    assert {check["name"] for check in report["checks"]} >= {
        "required_files",
        "shell_syntax",
        "distribution_identity",
        "service_posture",
        "release_configuration",
        "offline_runtime",
    }


def test_distribution_preflight_strict_mode_passes_hardened_baseline():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "service_posture" in result.stdout
