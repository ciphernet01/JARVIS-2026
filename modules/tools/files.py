"""
File system tools for JARVIS agent.
"""

import logging
import os
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


def _workspace_root() -> Path:
    return Path(os.getenv("JARVIS_WORKSPACE", Path.home() / "jarvis-workspace")).resolve()


def _allow_path(path: str) -> Path:
    """Sanitize and validate path is within workspace."""
    resolved = Path(path).resolve()
    workspace = _workspace_root()
    temp = Path(os.getenv("TMPDIR", os.getenv("TEMP", "/tmp"))).resolve()
    try:
        resolved.relative_to(workspace)
        return resolved
    except ValueError:
        pass
    try:
        resolved.relative_to(temp)
        return resolved
    except ValueError:
        pass
    logger.warning(f"Path blocked: {path}")
    raise PermissionError(f"Path {path} is outside allowed workspace")


def write_file(path: str, content: str) -> Dict[str, object]:
    """Write content to a file. Creates directories if needed."""
    logger.info(f"Tool write_file: {path}")
    try:
        target = _allow_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "output": f"File written: {target}",
            "error": None,
        }
    except Exception as exc:
        logger.error(f"write_file failed: {exc}")
        return {
            "success": False,
            "output": "",
            "error": str(exc),
        }


def read_file(path: str) -> Dict[str, object]:
    """Read a file and return its content."""
    logger.info(f"Tool read_file: {path}")
    try:
        target = _allow_path(path)
        if not target.exists():
            return {
                "success": False,
                "output": "",
                "error": f"File not found: {target}",
            }
        content = target.read_text(encoding="utf-8")
        return {
            "success": True,
            "output": content,
            "error": None,
        }
    except Exception as exc:
        logger.error(f"read_file failed: {exc}")
        return {
            "success": False,
            "output": "",
            "error": str(exc),
        }


def list_directory(path: str) -> Dict[str, object]:
    """List files and folders at a path."""
    logger.info(f"Tool list_directory: {path}")
    try:
        target = _allow_path(path)
        if not target.exists():
            return {
                "success": False,
                "output": "",
                "error": f"Directory not found: {target}",
            }
        items = []
        for entry in target.iterdir():
            items.append(
                {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else None,
                }
            )
        return {
            "success": True,
            "output": items,
            "error": None,
        }
    except Exception as exc:
        logger.error(f"list_directory failed: {exc}")
        return {
            "success": False,
            "output": "",
            "error": str(exc),
        }
