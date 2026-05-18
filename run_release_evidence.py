"""Create a Phase 6 release-candidate evidence bundle from saved reports."""

import argparse
import json

from modules.services.release_evidence_manager import ReleaseEvidenceManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a JARVIS release evidence bundle.")
    parser.add_argument("--label", default="release-candidate-evidence", help="Human-readable bundle label.")
    parser.add_argument("--notes", default="", help="Optional release validation notes.")
    parser.add_argument("--no-save", action="store_true", help="Print bundle without saving it.")
    args = parser.parse_args()

    manager = ReleaseEvidenceManager()
    bundle = manager.create_bundle(label=args.label, notes=args.notes, save=not args.no_save)
    print(json.dumps(bundle, indent=2, sort_keys=True))
    return 0 if bundle.get("release_status") != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
