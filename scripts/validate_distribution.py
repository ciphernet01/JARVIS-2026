#!/usr/bin/env python3
"""Static preflight checks for the A.S.T.R.A Debian distribution payload."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "os-distribution"


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def check_required_files() -> Check:
    required = [
        ROOT / "backend/server.py",
        DIST / "build-iso.sh",
        DIST / "boot-init.sh",
        DIST / "first-boot-setup.sh",
        DIST / "jarvis-shell-session.sh",
        DIST / "config/live-build.conf",
        DIST / "config/packages.list",
        DIST / "config/jarvis.service",
        DIST / "config/astra-shell.service",
        DIST / "config/astra-control-broker.service",
        DIST / "config/astra-boot-ready.service",
        DIST / "astra-boot-ready.sh",
        DIST / "BUILD_HOST.md",
        ROOT / "scripts/qemu_boot_smoke.sh",
        ROOT / "scripts/generate_iso_provenance.py",
        ROOT / "scripts/generate_wheelhouse_manifest.py",
        ROOT / "requirements.runtime.txt",
        ROOT / "scripts/validate_runtime_imports.py",
        ROOT / ".github/workflows/astra-iso.yml",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        return Check("required_files", "fail", f"Missing: {', '.join(missing)}")
    return Check("required_files", "pass", f"Found all {len(required)} required files")


def check_shell_syntax() -> Check:
    scripts = [
        DIST / "build-iso.sh",
        DIST / "boot-init.sh",
        DIST / "first-boot-setup.sh",
        DIST / "jarvis-shell-session.sh",
        DIST / "astra-boot-ready.sh",
        ROOT / "scripts/start_astra.sh",
        ROOT / "scripts/qemu_boot_smoke.sh",
    ]
    failures: list[str] = []
    for script in scripts:
        result = subprocess.run(
            ["bash", "-n", str(script)], capture_output=True, text=True, check=False
        )
        if result.returncode:
            failures.append(f"{script.relative_to(ROOT)}: {result.stderr.strip()}")
    if failures:
        return Check("shell_syntax", "fail", "; ".join(failures))
    return Check("shell_syntax", "pass", f"Validated {len(scripts)} shell scripts")


def check_distribution_identity() -> Check:
    config = (DIST / "config/live-build.conf").read_text(encoding="utf-8")
    required = ['LB_ISO_APPLICATION="A.S.T.R.A OS"', 'LB_ISO_VOLUME="ASTRA_OS"']
    missing = [value for value in required if value not in config]
    if missing:
        return Check("distribution_identity", "fail", f"Missing settings: {', '.join(missing)}")
    return Check("distribution_identity", "pass", "ISO identity is A.S.T.R.A OS")


def check_service_posture() -> Check:
    unit = (DIST / "config/jarvis.service").read_text(encoding="utf-8")
    shell_unit = (DIST / "config/astra-shell.service").read_text(encoding="utf-8")
    broker_unit = (DIST / "config/astra-control-broker.service").read_text(encoding="utf-8")
    unsafe = []
    if "User=root" in unit:
        unsafe.append("service runs as root")
    for setting in ("ProtectSystem=no", "ProtectHome=no", "NoNewPrivileges=false"):
        if setting in unit:
            unsafe.append(setting)
    required_backend = (
        "User=astra",
        "NoNewPrivileges=yes",
        "ProtectSystem=strict",
        "CapabilityBoundingSet=",
        "ASTRA_STATE_DIR=/var/lib/astra",
    )
    for setting in required_backend:
        if setting not in unit:
            unsafe.append(f"backend missing {setting}")
    required_shell = ("User=astra", "NoNewPrivileges=yes", "ProtectSystem=strict")
    for setting in required_shell:
        if setting not in shell_unit:
            unsafe.append(f"shell missing {setting}")
    required_broker = (
        "User=root",
        "NoNewPrivileges=yes",
        "ProtectSystem=strict",
        "CapabilityBoundingSet=",
        "RestrictAddressFamilies=AF_UNIX",
        "ASTRA_CONTROL_SOCKET=/run/astra-control/control.sock",
    )
    for setting in required_broker:
        if setting not in broker_unit:
            unsafe.append(f"broker missing {setting}")
    if unsafe:
        return Check(
            "service_posture",
            "warn",
            "Prototype privilege boundary only: " + ", ".join(unsafe),
        )
    return Check(
        "service_posture",
        "pass",
        "Unprivileged runtime services and the root control broker have separate hardened units",
    )


def check_release_configuration() -> Check:
    config = (DIST / "config/live-build.conf").read_text(encoding="utf-8")
    warnings = []
    if 'LB_SECURITY="false"' in config:
        warnings.append("Debian security updates are disabled")
    if 'LB_CHECKSUMS="md5"' in config:
        warnings.append("live-build checksum mode is MD5")
    if warnings:
        return Check("release_configuration", "warn", "; ".join(warnings))
    return Check("release_configuration", "pass", "Release configuration has no known weak defaults")


def check_offline_runtime() -> Check:
    unit = (DIST / "config/jarvis.service").read_text(encoding="utf-8")
    first_boot = (DIST / "first-boot-setup.sh").read_text(encoding="utf-8")
    builder = (DIST / "build-iso.sh").read_text(encoding="utf-8")
    failures = []
    if "ExecStart=/opt/astra/venv/bin/python" not in unit:
        failures.append("backend does not use /opt/astra/venv")
    if "--no-index" not in builder or "requirements.runtime.txt" not in builder:
        failures.append("builder does not enforce offline wheel installation")
    if "validate_runtime_imports.py" not in builder:
        failures.append("builder does not smoke-test the installed runtime")
    forbidden = ("pip3 install", "pip install", "npm install", "apt-get update", "apt-get upgrade")
    found = [command for command in forbidden if command in first_boot]
    if found:
        failures.append("first boot contains network installers: " + ", ".join(found))
    if failures:
        return Check("offline_runtime", "fail", "; ".join(failures))
    return Check(
        "offline_runtime",
        "pass",
        "Backend uses the image-local venv and first boot performs no package downloads",
    )


def run_checks() -> list[Check]:
    checks = [check_required_files(), check_shell_syntax()]
    if checks[0].status == "fail":
        return checks
    checks.extend(
        [
            check_distribution_identity(),
            check_service_posture(),
            check_release_configuration(),
            check_offline_runtime(),
        ]
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as release-blocking"
    )
    args = parser.parse_args()
    checks = run_checks()
    summary = {
        status: sum(check.status == status for check in checks)
        for status in ("pass", "warn", "fail")
    }
    if args.json:
        print(json.dumps({"checks": [asdict(check) for check in checks], "summary": summary}, indent=2))
    else:
        for check in checks:
            print(f"[{check.status.upper():4}] {check.name}: {check.detail}")
        print(
            f"Summary: {summary['pass']} passed, {summary['warn']} warnings, "
            f"{summary['fail']} failed"
        )
    return 1 if summary["fail"] or (args.strict and summary["warn"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
