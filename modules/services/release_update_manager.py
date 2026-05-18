"""Safe update execution from release manifests for Phase 7."""

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .release_manifest_manager import ReleaseManifestManager


@dataclass(frozen=True)
class UpdateAction:
    action: str
    path: str
    status: str
    detail: str
    backup_path: Optional[str] = None


class ReleaseUpdateManager:
    """Apply manifest-backed patch payloads with explicit confirmation."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.backup_dir = self.workspace_root / "backups" / "updates"
        self.manifest_manager = ReleaseManifestManager(workspace_root=str(self.workspace_root))

    def apply_update(
        self,
        current_manifest_path: str,
        candidate_manifest_path: str,
        candidate_root: str,
        *,
        dry_run: bool = True,
        confirmed: bool = False,
        allow_removals: bool = False,
    ) -> Dict[str, Any]:
        plan = self.manifest_manager.plan_update(current_manifest_path, candidate_manifest_path)
        candidate_manifest = self._load_workspace_json(candidate_manifest_path)
        candidate_files = {item["path"]: item for item in candidate_manifest.get("files", [])}
        root = self._resolve_candidate_root(candidate_root)
        actions: List[UpdateAction] = []

        for relative in plan["added"]:
            actions.append(self._copy_action(relative, candidate_files[relative], root, dry_run, confirmed, "add"))
        for relative in plan["changed"]:
            actions.append(self._copy_action(relative, candidate_files[relative], root, dry_run, confirmed, "change"))
        for relative in plan["removed"]:
            actions.append(self._remove_action(relative, dry_run, confirmed, allow_removals))

        blocked = [item for item in actions if item.status == "blocked"]
        failed = [item for item in actions if item.status == "failed"]
        changed = [item for item in actions if item.status in {"planned", "applied", "skipped"}]
        if not actions:
            status = "no_changes"
        elif dry_run:
            status = "planned"
        elif blocked or failed:
            status = "blocked"
        else:
            status = "applied"

        return {
            "status": status,
            "dry_run": dry_run,
            "confirmed": confirmed,
            "allow_removals": allow_removals,
            "requires_checkpoint": bool(actions),
            "requires_release_evidence": bool(actions),
            "plan": plan,
            "summary": {
                "actions": len(actions),
                "blocked": len(blocked),
                "failed": len(failed),
                "ready": len(changed),
            },
            "actions": [asdict(item) for item in actions],
            "recommendation": self._recommendation(status, dry_run),
        }

    def _copy_action(
        self,
        relative: str,
        expected: Dict[str, Any],
        candidate_root: Path,
        dry_run: bool,
        confirmed: bool,
        action: str,
    ) -> UpdateAction:
        source = self._resolve_under(candidate_root, relative)
        target = self._resolve_workspace_path(relative)
        if not source.exists() or not source.is_file():
            return UpdateAction(action, relative, "blocked", "Candidate file is missing.")
        actual_hash = self._sha256(source)
        if actual_hash != expected.get("sha256"):
            return UpdateAction(action, relative, "blocked", "Candidate file hash does not match manifest.")
        if dry_run:
            return UpdateAction(action, relative, "planned", "File is ready to copy from candidate payload.")
        if not confirmed:
            return UpdateAction(action, relative, "blocked", "Confirmation required before applying update.")

        backup = self._backup_file(target) if target.exists() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return UpdateAction(action, relative, "applied", "File copied from candidate payload.", backup)

    def _remove_action(self, relative: str, dry_run: bool, confirmed: bool, allow_removals: bool) -> UpdateAction:
        target = self._resolve_workspace_path(relative)
        if not allow_removals:
            return UpdateAction("remove", relative, "skipped", "Removal skipped; pass allow_removals to remove files.")
        if dry_run:
            return UpdateAction("remove", relative, "planned", "File would be removed after backup.")
        if not confirmed:
            return UpdateAction("remove", relative, "blocked", "Confirmation required before removing files.")
        if not target.exists():
            return UpdateAction("remove", relative, "skipped", "Target file is already absent.")

        backup = self._backup_file(target)
        target.unlink()
        return UpdateAction("remove", relative, "applied", "File removed after backup.", backup)

    def _backup_file(self, target: Path) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        relative = target.relative_to(self.workspace_root)
        backup = self.backup_dir / stamp / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
        return str(backup.relative_to(self.workspace_root))

    def _resolve_workspace_path(self, relative: str) -> Path:
        path = (self.workspace_root / relative).resolve()
        path.relative_to(self.workspace_root)
        return path

    def _resolve_candidate_root(self, raw_root: str) -> Path:
        root = (self.workspace_root / raw_root).resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError("Candidate root does not exist or is not a directory.")
        return root

    def _resolve_under(self, root: Path, relative: str) -> Path:
        path = (root / relative).resolve()
        path.relative_to(root)
        return path

    def _load_workspace_json(self, raw_path: str) -> Dict[str, Any]:
        path = self._resolve_workspace_path(raw_path)
        return json.loads(path.read_text(encoding="utf-8"))

    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _recommendation(self, status: str, dry_run: bool) -> str:
        if status == "no_changes":
            return "No file changes detected between manifests."
        if dry_run:
            return "Review planned actions, create a recovery checkpoint, then rerun with execute and confirmation."
        if status == "applied":
            return "Run focused tests and regenerate release evidence before marking the patch accepted."
        return "Resolve blocked actions before retrying the update."
