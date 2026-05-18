"""Run a Phase 6 performance baseline from the command line."""

import argparse
import json

from modules.services.performance_baseline_manager import PerformanceBaselineManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a JARVIS production performance baseline.")
    parser.add_argument("--label", default="release-performance-baseline", help="Human-readable report label.")
    parser.add_argument("--notes", default="", help="Optional release validation notes.")
    parser.add_argument("--duration", type=float, default=30.0, help="Capture duration in seconds.")
    parser.add_argument("--interval", type=float, default=2.0, help="Sampling interval in seconds.")
    parser.add_argument("--no-save", action="store_true", help="Print report without saving it.")
    args = parser.parse_args()

    manager = PerformanceBaselineManager()
    report = manager.run_baseline(
        label=args.label,
        notes=args.notes,
        duration_seconds=args.duration,
        interval_seconds=args.interval,
        save=not args.no_save,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("overall_status") != "fail" else 2


if __name__ == "__main__":
    raise SystemExit(main())
