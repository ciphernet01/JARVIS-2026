"""Release manifest and update planning for Phase 7 distribution."""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_MANIFEST_PATHS = [
    "README.md",
    "requirements.txt",
    "backend/server.py",
    "frontend/package.json",
    "frontend/package-lock.json",
    "os-distribution/VERSION.json",
    "os-distribution/README.md",
    "os-distribution/RELEASE_NOTES.md",
    "os-distribution/USER_MANUAL.md",
    "os-distribution/PATCH_UPDATE_PROCESS.md",
    "os-distribution/SUPPORT_WORKFLOW.md",
    "os-distribution/build-iso.sh",
    "os-distribution/first-boot-setup.sh",
    "os-distribution/jarvis-shell",
    "os-distribution/config/jarvis.service",
    "os-distribution/config/live-build.conf",
    "os-distribution/config/packages.list",
    "run_security_audit.py",
    "run_performance_baseline.py",
    "run_failover_drill.py",
    "run_release_evidence.py",
    "validate_hardware.py",
    "capture_hardware_stress.py",
]


@dataclass(frozen=True)
class ReleaseFile:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ReleaseManifest:
    id: str
    created_at: str
    version: Dict[str, Any]
    file_count: int
    files: List[ReleaseFile]
    notes: str = ""


class ReleaseManifestManager:
    """Generate release manifests and compare candidate patch payloads."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.manifest_dir = self.workspace_root / "os-distribution" / "manifests"
        self.version_path = self.workspace_root / "os-distribution" / "VERSION.json"

    def generate_manifest(
        self,
        *,
        paths: Optional[List[str]] = None,
        notes: str = "",
        save: bool = True,
    ) -> Dict[str, Any]:
        version = self._version_metadata()
        files = [self._release_file(path) for path in (paths or DEFAULT_MANIFEST_PATHS) if (self.workspace_root / path).is_file()]
        files = sorted(files, key=lambda item: item.path)
        manifest = ReleaseManifest(
            id=f"release-manifest-{version.get('version', 'unknown')}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            created_at=datetime.now(timezone.utc).isoformat(),
            version=version,
            file_count=len(files),
            files=files,
            notes=notes.strip()[:500],
        )
        payload = self._manifest_payload(manifest)
        if save:
            self._save_manifest(payload)
        return payload

    def list_manifests(self, limit: int = 10) -> List[Dict[str, Any]]:
        manifests = []
        if not self.manifest_dir.exists():
            return manifests
        for path in sorted(self.manifest_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                manifests.append({
                    "id": data.get("id", path.stem),
                    "created_at": data.get("created_at"),
                    "version": data.get("version", {}),
                    "file_count": data.get("file_count", 0),
                    "path": str(path.relative_to(self.workspace_root)),
                })
            except Exception:
                continue
            if len(manifests) >= max(1, limit):
                break
        return manifests

    def plan_update(self, current_manifest_path: str, candidate_manifest_path: str) -> Dict[str, Any]:
        current = self._load_manifest(current_manifest_path)
        candidate = self._load_manifest(candidate_manifest_path)
        current_files = {item["path"]: item for item in current.get("files", [])}
        candidate_files = {item["path"]: item for item in candidate.get("files", [])}

        added = sorted(path for path in candidate_files if path not in current_files)
        removed = sorted(path for path in current_files if path not in candidate_files)
        changed = sorted(
            path
            for path in candidate_files
            if path in current_files and candidate_files[path].get("sha256") != current_files[path].get("sha256")
        )
        critical = [path for path in changed + added + removed if self._is_critical(path)]
        requires_checkpoint = bool(changed or added or removed)
        return {
            "status": "success",
            "current_version": current.get("version", {}),
            "candidate_version": candidate.get("version", {}),
            "summary": {
                "added": len(added),
                "changed": len(changed),
                "removed": len(removed),
                "critical": len(critical),
            },
            "added": added,
            "changed": changed,
            "removed": removed,
            "critical_paths": critical,
            "requires_checkpoint": requires_checkpoint,
            "requires_release_evidence": requires_checkpoint,
            "recommendation": (
                "Create a recovery checkpoint, apply the patch, run focused tests, and regenerate release evidence."
                if requires_checkpoint
                else "No file changes detected between manifests."
            ),
        }

    def _version_metadata(self) -> Dict[str, Any]:
        if not self.version_path.exists():
            return {"name": "JARVIS OS", "version": "unknown", "channel": "unknown"}
        return json.loads(self.version_path.read_text(encoding="utf-8"))

    def _release_file(self, relative_path: str) -> ReleaseFile:
        path = (self.workspace_root / relative_path).resolve()
        path.relative_to(self.workspace_root)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return ReleaseFile(relative_path.replace("\\", "/"), path.stat().st_size, digest)

    def _load_manifest(self, raw_path: str) -> Dict[str, Any]:
        candidate = (self.workspace_root / raw_path).resolve()
        candidate.relative_to(self.workspace_root)
        return json.loads(candidate.read_text(encoding="utf-8"))

    def _is_critical(self, path: str) -> bool:
        critical_prefixes = ["backend/", "modules/services/", "modules/tools/", "modules/skills/", "os-distribution/config/"]
        critical_names = {"requirements.txt", "frontend/package.json", "frontend/package-lock.json", "os-distribution/VERSION.json"}
        return path in critical_names or any(path.startswith(prefix) for prefix in critical_prefixes)

    def _manifest_payload(self, manifest: ReleaseManifest) -> Dict[str, Any]:
        return {
            **asdict(manifest),
            "files": [asdict(item) for item in manifest.files],
        }

    def _save_manifest(self, payload: Dict[str, Any]) -> None:
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        path = self.manifest_dir / f"{payload['id']}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
