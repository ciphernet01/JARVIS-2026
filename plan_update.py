"""Compare two release manifests and print a safe patch plan."""

import argparse
import json

from modules.services.release_manifest_manager import ReleaseManifestManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan a JARVIS OS update from two release manifests.")
    parser.add_argument("current_manifest", help="Path to the current manifest, relative to workspace root.")
    parser.add_argument("candidate_manifest", help="Path to the candidate manifest, relative to workspace root.")
    args = parser.parse_args()

    plan = ReleaseManifestManager().plan_update(args.current_manifest, args.candidate_manifest)
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
