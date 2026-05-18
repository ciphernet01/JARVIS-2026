"""Apply a manifest-backed JARVIS update payload."""

import argparse
import json

from modules.services.release_update_manager import ReleaseUpdateManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or apply a JARVIS OS update payload.")
    parser.add_argument("current_manifest", help="Current manifest path relative to workspace root.")
    parser.add_argument("candidate_manifest", help="Candidate manifest path relative to workspace root.")
    parser.add_argument("candidate_root", help="Candidate payload root relative to workspace root.")
    parser.add_argument("--execute", action="store_true", help="Apply the update instead of dry-run planning.")
    parser.add_argument("--confirmed", action="store_true", help="Confirm file writes/removals.")
    parser.add_argument("--allow-removals", action="store_true", help="Allow removed files from the candidate manifest to be deleted after backup.")
    args = parser.parse_args()

    result = ReleaseUpdateManager().apply_update(
        args.current_manifest,
        args.candidate_manifest,
        args.candidate_root,
        dry_run=not args.execute,
        confirmed=args.confirmed,
        allow_removals=args.allow_removals,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"planned", "applied", "no_changes"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
