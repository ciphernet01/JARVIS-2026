#!/usr/bin/env python3
"""Check whether a QEMU serial log contains the A.S.T.R.A boot-ready marker."""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_MARKER = "ASTRA_BOOT_READY broker=active backend=active"


def log_contains_marker(log_text: str, marker: str = DEFAULT_MARKER) -> bool:
    """Return True if the boot-ready marker appears in the log text."""
    if marker in log_text:
        return True
    # Tolerate small formatting differences while still requiring the same state.
    return "ASTRA_BOOT_READY" in log_text and "broker=active" in log_text and "backend=active" in log_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_file", type=Path)
    parser.add_argument("--marker", default=DEFAULT_MARKER)
    args = parser.parse_args()

    if not args.log_file.is_file():
        parser.error(f"Log file not found: {args.log_file}")

    log_text = args.log_file.read_text(encoding="utf-8", errors="replace")
    return 0 if log_contains_marker(log_text, args.marker) else 1


if __name__ == "__main__":
    raise SystemExit(main())
