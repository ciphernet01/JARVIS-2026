"""Run a Phase 6 failover drill from the command line."""

import argparse
import json

from modules.services.failover_drill_manager import FailoverDrillManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Run non-mutating JARVIS failover drills.")
    parser.add_argument("--label", default="release-failover-drill", help="Human-readable report label.")
    parser.add_argument("--notes", default="", help="Optional release validation notes.")
    parser.add_argument("--no-save", action="store_true", help="Print report without saving it.")
    args = parser.parse_args()

    manager = FailoverDrillManager()
    report = manager.run_drill(label=args.label, notes=args.notes, save=not args.no_save)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("overall_status") != "fail" else 2


if __name__ == "__main__":
    raise SystemExit(main())
