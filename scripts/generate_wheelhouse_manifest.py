#!/usr/bin/env python3
"""Hash an offline Python wheelhouse for A.S.T.R.A image provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate(wheelhouse: Path, output: Path) -> Path:
    wheelhouse = wheelhouse.resolve()
    wheels = sorted(wheelhouse.glob("*.whl"), key=lambda path: path.name.lower())
    if not wheels:
        raise ValueError(f"No wheels found in {wheelhouse}")
    payload = {
        "schema_version": 1,
        "artifact_count": len(wheels),
        "artifacts": [
            {"filename": wheel.name, "size_bytes": wheel.stat().st_size, "sha256": sha256(wheel)}
            for wheel in wheels
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheelhouse", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(generate(args.wheelhouse, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
