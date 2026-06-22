#!/usr/bin/env python3
"""Inspect a built A.S.T.R.A ISO for required files and forbidden leakage."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, List


REQUIRED_PATHS = frozenset(
    {
        "opt/astra/venv/bin/python",
        "opt/jarvis/backend/server.py",
        "opt/jarvis/frontend/build/index.html",
        "etc/systemd/system/jarvis.service",
        "etc/systemd/system/astra-shell.service",
        "etc/systemd/system/astra-control-broker.service",
        "etc/systemd/system/astra-boot-ready.service",
        "usr/share/doc/astra/wheelhouse-manifest.json",
        "usr/share/doc/astra/runtime-smoke.json",
    }
)

FORBIDDEN_COMPONENTS = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "backups",
        "test_reports",
        "__pycache__",
    }
)

FORBIDDEN_FILENAMES = frozenset(
    {
        ".env",
        ".session_token",
        "jarvis.db",
        "credentials.json",
    }
)


def normalize_entries(entries: Iterable[str]) -> List[str]:
    return sorted(
        {
            entry.strip().replace("\\", "/").lstrip("./")
            for entry in entries
            if entry.strip()
        }
    )


def inspect_entries(entries: Iterable[str]) -> dict:
    normalized = normalize_entries(entries)
    entry_set = set(normalized)
    missing = sorted(REQUIRED_PATHS - entry_set)
    forbidden = []
    for entry in normalized:
        path = Path(entry)
        parts = set(path.parts)
        if parts & FORBIDDEN_COMPONENTS or path.name in FORBIDDEN_FILENAMES:
            forbidden.append(entry)
    return {
        "ok": not missing and not forbidden,
        "entry_count": len(normalized),
        "required_count": len(REQUIRED_PATHS),
        "missing": missing,
        "forbidden": forbidden,
    }


def list_iso(iso_path: Path) -> List[str]:
    try:
        archive = subprocess.run(
            ["bsdtar", "-tf", str(iso_path)],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("bsdtar is required; install libarchive-tools") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Unable to inspect ISO: {exc.stderr.strip()}") from exc
    members = archive.stdout.splitlines()
    squashfs_member = next(
        (member for member in members if member.endswith("/filesystem.squashfs")),
        None,
    )
    if not squashfs_member:
        raise RuntimeError("ISO does not contain live/filesystem.squashfs")

    with tempfile.TemporaryDirectory(prefix="astra-iso-inspect-") as temp_dir:
        squashfs_path = Path(temp_dir) / "filesystem.squashfs"
        with squashfs_path.open("wb") as output:
            try:
                subprocess.run(
                    ["bsdtar", "-xOf", str(iso_path), squashfs_member],
                    stdout=output,
                    stderr=subprocess.PIPE,
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    f"Unable to extract SquashFS: {exc.stderr.decode(errors='replace').strip()}"
                ) from exc
        try:
            listing = subprocess.run(
                ["unsquashfs", "-ll", "-no-progress", str(squashfs_path)],
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("unsquashfs is required; install squashfs-tools") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Unable to list SquashFS: {exc.stderr.strip()}") from exc

    entries = []
    for line in listing.stdout.splitlines():
        marker = "squashfs-root"
        position = line.find(marker)
        if position < 0:
            continue
        entry = line[position + len(marker):].lstrip("/")
        if entry:
            entries.append(entry)
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.iso.is_file():
        parser.error(f"ISO not found: {args.iso}")
    report = inspect_entries(list_iso(args.iso))
    report["iso"] = str(args.iso.resolve())
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
