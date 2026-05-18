"""
Shell tool for JARVIS agent.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

from modules.services.safety_manager import SafetyGate, SafetyManager, SafetyState

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


def run_shell(command: str, timeout: int = 30, *, confirmed: bool = False, safety_state: Optional[SafetyState] = None) -> Dict[str, object]:
    """Run a shell command. Returns stdout, stderr, returncode."""
    logger.info(f"Tool run_shell: {command[:200]}")
    safety = SafetyManager(workspace_root=os.getenv("JARVIS_WORKSPACE", os.getcwd()))
    if safety_state is not None:
        decision = SafetyGate(safety_state).evaluate(command, confirmed=confirmed)
    else:
        decision = safety.evaluate_shell_command(command, confirmed=confirmed)
    safety.audit_command_decision(decision, "modules.tools.shell")
    if not decision.allowed:
        return {
            "success": False,
            "output": "",
            "error": decision.reason,
            "returncode": -2,
            "safety": {
                "category": decision.category,
                "requires_confirmation": decision.requires_confirmation,
                "blocked": True,
            },
        }
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
            "safety": {
                "category": decision.category,
                "requires_confirmation": decision.requires_confirmation,
                "blocked": False,
            },
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
