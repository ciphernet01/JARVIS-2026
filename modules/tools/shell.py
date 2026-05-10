"""
Shell tool for JARVIS agent.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


def _sanitize_path(path: str) -> str:
    """Prevent directory traversal outside workspace."""
    resolved = Path(path).resolve()
    workspace = Path(os.getenv("JARVIS_WORKSPACE", Path.home() / "jarvis-workspace")).resolve()
    # Allow paths inside workspace or temp
    temp = Path(os.getenv("TMPDIR", os.getenv("TEMP", "/tmp"))).resolve()
    try:
        resolved.relative_to(workspace)
        return str(resolved)
    except ValueError:
        pass
    try:
        resolved.relative_to(temp)
        return str(resolved)
    except ValueError:
        pass
    logger.warning(f"Path blocked: {path}")
    raise PermissionError(f"Path {path} is outside allowed workspace")


def run_shell(command: str, timeout: int = 30) -> Dict[str, object]:
    """Run a shell command. Returns stdout, stderr, returncode."""
    logger.info(f"Tool run_shell: {command[:200]}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        logger.warning(f"Shell command timed out after {timeout}s: {command[:200]}")
        return {
            "success": False,
            "output": "",
            "error": f"Command timed out after {timeout} seconds",
            "returncode": -1,
        }
    except Exception as exc:
        logger.error(f"Shell command failed: {exc}")
        return {
            "success": False,
            "output": "",
            "error": str(exc),
            "returncode": -1,
        }
