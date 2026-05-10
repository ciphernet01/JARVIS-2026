"""
Code execution tools for JARVIS agent.
Runs Python and Node.js in subprocess sandboxes.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


def _sandbox_dir() -> Path:
    base = Path(os.getenv("JARVIS_WORKSPACE", Path.home() / "jarvis-workspace")).resolve() / "code_sandbox"
    base.mkdir(parents=True, exist_ok=True)
    return base


def run_python(code: str, timeout: int = 30) -> Dict[str, object]:
    """Execute Python code in a subprocess sandbox. Returns output."""
    logger.info("Tool run_python: executing Python code")
    sandbox = _sandbox_dir()
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", dir=sandbox, delete=False
        ) as f:
            f.write(code)
            script_path = f.name

        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(sandbox),
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Python execution timed out after {timeout} seconds",
            "returncode": -1,
        }
    except Exception as exc:
        logger.error(f"run_python failed: {exc}")
        return {
            "success": False,
            "output": "",
            "error": str(exc),
            "returncode": -1,
        }


def run_node(code: str, timeout: int = 30) -> Dict[str, object]:
    """Execute Node.js code in a subprocess sandbox. Returns output."""
    logger.info("Tool run_node: executing Node.js code")
    sandbox = _sandbox_dir()
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", dir=sandbox, delete=False
        ) as f:
            f.write(code)
            script_path = f.name

        result = subprocess.run(
            ["node", script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(sandbox),
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Node.js execution timed out after {timeout} seconds",
            "returncode": -1,
        }
    except Exception as exc:
        logger.error(f"run_node failed: {exc}")
        return {
            "success": False,
            "output": "",
            "error": str(exc),
            "returncode": -1,
        }
