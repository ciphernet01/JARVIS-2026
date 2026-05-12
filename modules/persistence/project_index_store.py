"""
Project Index Storage
Discovers and stores workspace-level project metadata for context recall.
"""

import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


class ProjectIndexStore:
    """Persist discovered projects and provide workspace summaries."""

    IGNORE_DIRS = {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "node_modules",
        "dist",
        "build",
        ".venv",
        "venv",
        "env",
        "captures",
    }

    MANIFEST_FILES = (
        "README.md",
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "Pipfile",
        "poetry.lock",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "Cargo.toml",
        "go.mod",
        "Dockerfile",
    )

    def __init__(self, db_manager):
        self.db = db_manager

    def _resolve_root(self, workspace_root: Optional[str | Path] = None) -> Path:
        if workspace_root:
            return Path(workspace_root).expanduser().resolve()

        fallback = os.getenv("JARVIS_WORKSPACE")
        if fallback:
            return Path(fallback).expanduser().resolve()

        return Path(__file__).resolve().parents[2]

    def _safe_text(self, value: str, default: str = "Untitled project") -> str:
        text = re.sub(r"\s+", " ", (value or "").strip())
        return text or default

    def _read_text(self, path: Path, limit: int = 4000) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:limit]
        except Exception:
            return ""

    def _project_type_from_files(self, files: Iterable[str], root: Path) -> str:
        file_set = {name.lower() for name in files}
        if "package.json" in file_set:
            package_path = root / "package.json"
            try:
                package_data = json.loads(self._read_text(package_path, limit=10000) or "{}")
            except Exception:
                package_data = {}

            deps = {}
            for key in ("dependencies", "devDependencies"):
                deps.update(package_data.get(key, {}) or {})
            if any(name in deps for name in ("react", "next", "vite", "@vitejs", "react-dom")):
                return "react-app"
            return "node-project"

        if "pyproject.toml" in file_set or "requirements.txt" in file_set or "Pipfile" in file_set:
            return "python-project"
        if "pom.xml" in file_set or "build.gradle" in file_set or "build.gradle.kts" in file_set:
            return "java-project"
        if "Cargo.toml" in file_set:
            return "rust-project"
        if "go.mod" in file_set:
            return "go-project"
        if "dockerfile" in file_set:
            return "containerized-project"
        return "project"

    def _project_name_from_marker(self, root: Path, marker_file: str) -> str:
        marker = root / marker_file
        if marker_file.lower() == "package.json" and marker.exists():
            try:
                package_data = json.loads(self._read_text(marker, limit=10000) or "{}")
                if package_data.get("name"):
                    return self._safe_text(str(package_data["name"]))
            except Exception:
                pass

        if marker_file.lower() == "readme.md" and marker.exists():
            content = self._read_text(marker)
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("#"):
                    return self._safe_text(line.lstrip("#").strip())

        return self._safe_text(root.name)

    def _summarize_project(self, project_name: str, project_type: str, source_file: str, root: Path) -> str:
        rel_path = str(root)
        pieces = [project_name, project_type.replace("-", " ")]
        if source_file:
            pieces.append(f"discovered from {source_file}")
        pieces.append(f"at {rel_path}")
        return "; ".join(piece for piece in pieces if piece)

    def _detect_marker(self, root: Path, files: List[str]) -> Optional[str]:
        lower_files = {name.lower(): name for name in files}
        for candidate in self.MANIFEST_FILES:
            if candidate.lower() in lower_files:
                return lower_files[candidate.lower()]
        return None

    def _iter_project_directories(self, workspace_root: Path, max_depth: int = 4) -> List[Path]:
        found: List[Path] = []
        for current, dirnames, filenames in os.walk(workspace_root):
            current_path = Path(current)
            rel_parts = current_path.relative_to(workspace_root).parts if current_path != workspace_root else ()
            if len(rel_parts) > max_depth:
                dirnames[:] = []
                continue

            dirnames[:] = [d for d in dirnames if d not in self.IGNORE_DIRS and not d.startswith(".")]

            marker = self._detect_marker(current_path, filenames)
            if marker:
                found.append(current_path)

        return sorted({path.resolve() for path in found}, key=lambda path: (len(path.parts), str(path).lower()))

    def refresh_index(self, workspace_root: Optional[str | Path] = None, max_depth: int = 4) -> List[Dict[str, Any]]:
        """Scan the workspace and store project metadata in SQLite."""
        root = self._resolve_root(workspace_root)
        if not root.exists():
            logger.warning(f"Project index workspace does not exist: {root}")
            return []

        try:
            self.db.execute("DELETE FROM project_index WHERE workspace_root = ?", (str(root),))
            self.db.commit()
        except Exception as exc:
            logger.warning(f"Failed to clear existing project index rows: {exc}")

        discovered: List[Dict[str, Any]] = []
        for project_root in self._iter_project_directories(root, max_depth=max_depth):
            files = [item.name for item in project_root.iterdir() if item.is_file()]
            marker = self._detect_marker(project_root, files)
            if not marker:
                continue

            project_type = self._project_type_from_files(files, project_root)
            project_name = self._project_name_from_marker(project_root, marker)
            summary = self._summarize_project(project_name, project_type, marker, project_root)
            metadata = {
                "workspace_root": str(root),
                "relative_path": str(project_root.relative_to(root)),
                "marker_files": sorted(name for name in files if name in self.MANIFEST_FILES),
                "project_type": project_type,
            }

            row = {
                "id": str(uuid.uuid4()),
                "workspace_root": str(root),
                "root_path": str(project_root),
                "project_name": project_name,
                "project_type": project_type,
                "summary": summary,
                "source_file": marker,
                "metadata": json.dumps(metadata),
            }

            try:
                self.db.execute(
                    """
                    INSERT OR REPLACE INTO project_index
                        (id, workspace_root, root_path, project_name, project_type, summary, source_file, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        row["id"],
                        row["workspace_root"],
                        row["root_path"],
                        row["project_name"],
                        row["project_type"],
                        row["summary"],
                        row["source_file"],
                        row["metadata"],
                    ),
                )
                discovered.append(row)
            except Exception as exc:
                logger.warning(f"Failed to store project index entry for {project_root}: {exc}")

        try:
            self.db.commit()
        except Exception as exc:
            logger.warning(f"Failed to commit project index refresh: {exc}")

        logger.info(f"Indexed {len(discovered)} project(s) under {root}")
        return discovered

    def list_projects(self, workspace_root: Optional[str | Path] = None) -> List[Dict[str, Any]]:
        """Load the indexed projects for a workspace."""
        root = self._resolve_root(workspace_root)
        try:
            cursor = self.db.execute(
                """
                SELECT * FROM project_index
                WHERE workspace_root = ?
                ORDER BY root_path ASC
                """,
                (str(root),),
            )
            if not cursor:
                return []
            return [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            logger.warning(f"Failed to load project index: {exc}")
            return []

    def build_summary(self, workspace_root: Optional[str | Path] = None, limit: int = 8) -> Dict[str, Any]:
        """Return a compact project inventory for prompt context."""
        projects = self.list_projects(workspace_root=workspace_root)
        limited = projects[:limit]
        workspace = self._resolve_root(workspace_root)

        if not limited:
            return {
                "workspace_root": str(workspace),
                "project_count": 0,
                "summary": "No indexed projects found yet.",
                "projects": [],
            }

        project_lines = []
        for item in limited:
            name = item.get("project_name", "Untitled project")
            project_type = item.get("project_type", "project")
            root_path = item.get("root_path", "")
            rel_path = root_path
            try:
                rel_path = str(Path(root_path).resolve().relative_to(workspace))
            except Exception:
                pass
            project_lines.append(f"- {name} [{project_type}] at {rel_path}")

        summary = "Project index:\n" + "\n".join(project_lines)
        return {
            "workspace_root": str(workspace),
            "project_count": len(projects),
            "summary": summary,
            "projects": limited,
        }