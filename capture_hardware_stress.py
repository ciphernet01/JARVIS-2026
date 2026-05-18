"""Run a Phase 4 JARVIS OS hardware stress/thermal capture."""

import argparse
import json
from pathlib import Path

from modules.services.hardware_stress_manager import HardwareStressManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Run JARVIS OS hardware stress/thermal capture.")
    parser.add_argument("--label", default="manual-stress-capture", help="Report label.")
    parser.add_argument("--notes", default="", help="Optional report notes.")
    parser.add_argument("--duration", type=float, default=30.0, help="Capture duration in seconds, capped at 300.")
    parser.add_argument("--interval", type=float, default=2.0, help="Sample interval in seconds.")
    parser.add_argument("--no-save", action="store_true", help="Do not persist the report JSON.")
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parent), help="Workspace root.")
    args = parser.parse_args()

    manager = HardwareStressManager(workspace_root=args.workspace)
    report = manager.run_capture(
        label=args.label,
        notes=args.notes,
        duration_seconds=args.duration,
        interval_seconds=args.interval,
        save=not args.no_save,
    )
    print(json.dumps({
        "id": report["id"],
        "label": report["label"],
        "overall_status": report["overall_status"],
        "duration_seconds": report["duration_seconds"],
        "sample_count": report["sample_count"],
        "summary": report["summary"],
        "saved": not args.no_save,
    }, indent=2))
    return 0 if report["overall_status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
