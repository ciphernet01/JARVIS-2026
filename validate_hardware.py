"""Run a Phase 4 JARVIS OS hardware validation report."""

import argparse
import json
from pathlib import Path

from modules.services.hardware_validation_manager import HardwareValidationManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Run JARVIS OS hardware validation.")
    parser.add_argument("--label", default="manual-hardware-validation", help="Report label.")
    parser.add_argument("--notes", default="", help="Optional report notes.")
    parser.add_argument("--no-save", action="store_true", help="Do not persist the report JSON.")
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parent), help="Workspace root.")
    args = parser.parse_args()

    manager = HardwareValidationManager(workspace_root=args.workspace)
    report = manager.run_validation(label=args.label, notes=args.notes, save=not args.no_save)
    print(json.dumps({
        "id": report["id"],
        "label": report["label"],
        "overall_status": report["overall_status"],
        "score": report["score"],
        "target_config_id": report["target_config_id"],
        "saved": not args.no_save,
    }, indent=2))
    return 0 if report["overall_status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
