#!/usr/bin/env python3
"""Generate machine-readable provenance for an A.S.T.R.A ISO artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build_timestamp() -> str:
    epoch = os.getenv("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def generate(iso_path: Path, output_path: Optional[Path] = None) -> Path:
    iso_path = iso_path.resolve()
    if not iso_path.is_file():
        raise FileNotFoundError(f"ISO not found: {iso_path}")
    version_path = ROOT / "os-distribution/VERSION.json"
    inputs = [
        ROOT / "os-distribution/config/live-build.conf",
        ROOT / "os-distribution/config/packages.list",
        ROOT / "frontend/package-lock.json",
        ROOT / "backend/requirements.txt",
        ROOT / "requirements.linux.txt",
        ROOT / "requirements.runtime.txt",
    ]
    commit = git_value("rev-parse", "HEAD")
    dirty = bool(git_value("status", "--porcelain"))
    payload = {
        "schema_version": 1,
        "product": json.loads(version_path.read_text(encoding="utf-8")),
        "artifact": {
            "name": iso_path.name,
            "size_bytes": iso_path.stat().st_size,
            "sha256": sha256(iso_path),
        },
        "source": {"commit": commit, "dirty": dirty},
        "build": {
            "timestamp": build_timestamp(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "inputs": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in inputs
            if path.is_file()
        },
    }
    wheelhouse_manifest = Path(
        os.getenv("ASTRA_WHEELHOUSE_DIR", os.getenv("TMPDIR", "/tmp") + "/astra-wheelhouse")
    ) / "manifest.json"
    if wheelhouse_manifest.is_file():
        manifest = json.loads(wheelhouse_manifest.read_text(encoding="utf-8"))
        payload["runtime_wheelhouse"] = {
            "manifest_sha256": sha256(wheelhouse_manifest),
            "artifact_count": manifest.get("artifact_count"),
            "artifacts": manifest.get("artifacts", []),
        }
    destination = output_path or iso_path.with_suffix(iso_path.suffix + ".provenance.json")
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    destination = generate(args.iso, args.output)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
