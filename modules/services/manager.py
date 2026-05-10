"""
Service Manager for JARVIS
Start, stop, and monitor built services / apps.
"""

import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class ServiceRecord:
    """Tracked service instance."""

    name: str
    pid: int
    port: Optional[int] = None
    directory: str = ""
    command: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "running"


class ServiceManager:
    """Manage long-running services that JARVIS builds."""

    def __init__(self, state_path: Optional[str] = None):
        workspace = Path(os.getenv("JARVIS_WORKSPACE", Path.home() / "jarvis-workspace"))
        workspace.mkdir(parents=True, exist_ok=True)
        self.state_path = state_path or str(workspace / "services.json")
        self._services: Dict[str, ServiceRecord] = {}
        self._load_state()

    def _load_state(self) -> None:
        import json

        try:
            if Path(self.state_path).exists():
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, rec in data.items():
                    self._services[name] = ServiceRecord(**rec)
        except Exception as exc:
            logger.warning(f"Failed to load service state: {exc}")

    def _save_state(self) -> None:
        import json

        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                payload = {name: rec.__dict__ for name, rec in self._services.items()}
                json.dump(payload, f, indent=2, default=str)
        except Exception as exc:
            logger.warning(f"Failed to save service state: {exc}")

    def start(
        self,
        name: str,
        command: str,
        directory: str = "",
        port: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Start a service and track it."""
        logger.info(f"Starting service '{name}': {command}")
        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=directory or None,
            )
            record = ServiceRecord(
                name=name,
                pid=proc.pid,
                port=port,
                directory=directory,
                command=command,
            )
            self._services[name] = record
            self._save_state()
            return {
                "success": True,
                "output": f"Service '{name}' started with PID {proc.pid}",
                "error": None,
                "pid": proc.pid,
            }
        except Exception as exc:
            logger.error(f"Failed to start service '{name}': {exc}")
            return {
                "success": False,
                "output": "",
                "error": str(exc),
            }

    def stop(self, name: str) -> Dict[str, Any]:
        """Stop a tracked service by name."""
        record = self._services.get(name)
        if not record:
            return {
                "success": False,
                "output": "",
                "error": f"Service '{name}' not found",
            }
        try:
            proc = psutil.Process(record.pid)
            proc.terminate()
            proc.wait(timeout=10)
            record.status = "stopped"
            self._save_state()
            return {
                "success": True,
                "output": f"Service '{name}' stopped",
                "error": None,
            }
        except psutil.NoSuchProcess:
            record.status = "stopped"
            self._save_state()
            return {
                "success": True,
                "output": f"Service '{name}' was not running",
                "error": None,
            }
        except Exception as exc:
            logger.error(f"Failed to stop service '{name}': {exc}")
            return {
                "success": False,
                "output": "",
                "error": str(exc),
            }

    def restart(self, name: str) -> Dict[str, Any]:
        """Restart a tracked service."""
        record = self._services.get(name)
        if not record:
            return {
                "success": False,
                "output": "",
                "error": f"Service '{name}' not found",
            }
        self.stop(name)
        return self.start(
            name=name,
            command=record.command,
            directory=record.directory,
            port=record.port,
        )

    def status(self, name: str) -> Dict[str, Any]:
        """Check whether a service is alive."""
        record = self._services.get(name)
        if not record:
            return {
                "success": False,
                "output": "",
                "error": f"Service '{name}' not found",
            }
        try:
            proc = psutil.Process(record.pid)
            is_alive = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            record.status = "running" if is_alive else "stopped"
            return {
                "success": True,
                "output": {
                    "name": record.name,
                    "pid": record.pid,
                    "port": record.port,
                    "directory": record.directory,
                    "command": record.command,
                    "started_at": record.started_at,
                    "status": record.status,
                    "is_alive": is_alive,
                },
                "error": None,
            }
        except psutil.NoSuchProcess:
            record.status = "stopped"
            return {
                "success": True,
                "output": {
                    "name": record.name,
                    "pid": record.pid,
                    "status": "stopped",
                    "is_alive": False,
                },
                "error": None,
            }

    def list_services(self) -> List[Dict[str, Any]]:
        """List all tracked services."""
        results: List[Dict[str, Any]] = []
        for name, record in self._services.items():
            st = self.status(name)
            results.append(st.get("output", {}))
        return results

    def cleanup(self) -> None:
        """Stop all tracked services."""
        for name in list(self._services.keys()):
            self.stop(name)
        self._services.clear()
        self._save_state()
