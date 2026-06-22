#!/usr/bin/env python3
"""Validate the critical A.S.T.R.A backend import surface inside an image."""

from __future__ import annotations

import argparse
import importlib
import json
from dataclasses import asdict, dataclass
from typing import Callable, Iterable, List


CRITICAL_MODULES = (
    "fastapi", "uvicorn", "motor", "pymongo", "dotenv", "psutil",
    "requests", "httpx", "pydantic", "aiofiles", "numpy", "cv2",
    "PIL", "cryptography", "openai", "google.genai",
)

OPTIONAL_MODULES = (
    "mediapipe", "speech_recognition", "pyttsx3", "whisper", "torch", "pyautogui",
)


@dataclass(frozen=True)
class ImportResult:
    module: str
    required: bool
    available: bool
    error: str = ""


def validate_modules(
    critical: Iterable[str] = CRITICAL_MODULES,
    optional: Iterable[str] = OPTIONAL_MODULES,
    importer: Callable[[str], object] = importlib.import_module,
) -> List[ImportResult]:
    results: List[ImportResult] = []
    for required, names in ((True, critical), (False, optional)):
        for name in names:
            try:
                importer(name)
                results.append(ImportResult(name, required, True))
            except Exception as exc:
                results.append(ImportResult(name, required, False, f"{type(exc).__name__}: {exc}"))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable results")
    args = parser.parse_args()
    results = validate_modules()
    payload = {
        "ok": all(result.available for result in results if result.required),
        "critical": [asdict(result) for result in results if result.required],
        "optional": [asdict(result) for result in results if not result.required],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for result in results:
            status = "PASS" if result.available else ("FAIL" if result.required else "SKIP")
            detail = f": {result.error}" if result.error else ""
            print(f"[{status}] {result.module}{detail}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
