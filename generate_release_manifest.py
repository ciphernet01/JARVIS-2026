"""Generate a Phase 7 release manifest."""

import argparse
import json

from modules.services.release_manifest_manager import ReleaseManifestManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a JARVIS OS release manifest.")
    parser.add_argument("--notes", default="", help="Optional manifest notes.")
    parser.add_argument("--no-save", action="store_true", help="Print manifest without saving it.")
    args = parser.parse_args()

    manifest = ReleaseManifestManager().generate_manifest(notes=args.notes, save=not args.no_save)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
