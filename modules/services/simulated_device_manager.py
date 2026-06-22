"""
Simulated Device Manager

Provides a safe, in-memory DeviceManager implementation for CI and development
without touching real hardware. Implements a compatible surface for higher-level
services and tests.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from modules.security.policy import PolicyExecutor
import time
import threading

try:
    from modules.services.device_manager import DeviceManager
except Exception:  # pragma: no cover - fallback for lightweight test loading
    class DeviceManager:  # minimal fallback so simulated loader works in CI
        def __init__(self, workspace_root: Optional[str] = None):
            self.workspace_root = workspace_root


class SimulatedDeviceManager(DeviceManager):
    """In-memory simulated device manager for testing and CI.

    Devices are simple dicts with keys: id, name, type, status, properties
    where `status` is one of: 'online', 'offline', 'error'.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        super().__init__(workspace_root=workspace_root)
        self._lock = threading.RLock()
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.policy = PolicyExecutor()
        self._init_default_devices()

    def _init_default_devices(self) -> None:
        # Create a few simulated devices to mirror common hardware
        self.add_device("mock-camera-1", "camera", {"resolution": "1280x720"})
        self.add_device("mock-mic-1", "microphone", {"sensitivity": "medium"})
        self.add_device("mock-sensor-1", "sensor", {"unit": "celsius"})

    def add_device(self, device_id: str, device_type: str, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Enforce policy for adding devices
        self.policy.enforce("add_device", actor="simulator", resource={"device_id": device_id, "type": device_type})
        with self._lock:
            device = {
                "id": device_id,
                "name": device_id,
                "type": device_type,
                "status": "online",
                "properties": properties or {},
            }
            self.devices[device_id] = device
            return {"success": True, "device": device}

    def remove_device(self, device_id: str) -> Dict[str, Any]:
        self.policy.enforce("remove_device", actor="simulator", resource={"device_id": device_id})
        with self._lock:
            if device_id in self.devices:
                del self.devices[device_id]
                return {"success": True}
            return {"success": False, "error": "not_found"}

    def list_devices(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.devices.values())

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.devices.get(device_id)

    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        dev = self.get_device(device_id)
        if not dev:
            return {"success": False, "error": "not_found"}
        return {"success": True, "status": dev["status"]}

    def set_device_property(self, device_id: str, key: str, value: Any) -> Dict[str, Any]:
        self.policy.enforce("set_property", actor="simulator", resource={"device_id": device_id, "key": key})
        with self._lock:
            dev = self.devices.get(device_id)
            if not dev:
                return {"success": False, "error": "not_found"}
            dev["properties"][key] = value
            return {"success": True, "device": dev}

    def power_cycle_device(self, device_id: str, offline_seconds: float = 0.05) -> Dict[str, Any]:
        """Simulate power-cycling: set offline briefly and back online."""
        self.policy.enforce("power_cycle", actor="simulator", resource={"device_id": device_id})
        with self._lock:
            dev = self.devices.get(device_id)
            if not dev:
                return {"success": False, "error": "not_found"}
            dev["status"] = "offline"

        # Sleep outside lock to allow other threads to observe offline state
        time.sleep(offline_seconds)

        with self._lock:
            dev["status"] = "online"
            return {"success": True, "device": dev}

    def simulate_failure(self, device_id: str) -> Dict[str, Any]:
        with self._lock:
            dev = self.devices.get(device_id)
            if not dev:
                return {"success": False, "error": "not_found"}
            dev["status"] = "error"
            return {"success": True, "device": dev}
