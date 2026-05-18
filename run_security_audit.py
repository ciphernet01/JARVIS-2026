"""Run a Phase 6 JARVIS OS security hardening audit."""

import argparse
import json

from modules.services.safety_manager import SafetyManager
from modules.services.security_audit_manager import SecurityAuditManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Run JARVIS OS security hardening audit.")
    parser.add_argument("--no-save", action="store_true", help="Do not persist the audit report.")
    parser.add_argument("--json", action="store_true", help="Print the full report JSON.")
    args = parser.parse_args()

    manager = SecurityAuditManager()
    report = manager.run_audit(
        cors_origins=[],
        session_tokens={},
        safety_state=SafetyManager().state(),
        save=not args.no_save,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{report['id']} {report['overall_status']} score={report['score']}")
        for check in report["checks"]:
            print(f"- {check['status'].upper()} {check['label']}: {check['detail']}")
    return 0 if report["overall_status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
