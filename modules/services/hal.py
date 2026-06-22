"""HAL interface and factory helpers for A.S.T.R.A"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import os

try:
    from abc import ABC, abstractmethod
except Exception:
    ABC = object
    def abstractmethod(f):
        return f


class DeviceHAL(ABC):
    """Abstract HAL for device management."""

    @abstractmethod
    def list_devices(self) -> List[Dict[str, Any]]:
        raise NotImplementedError()

    @abstractmethod
    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError()

    @abstractmethod
    def add_device(self, device_id: str, device_type: str, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError()

    @abstractmethod
    def remove_device(self, device_id: str) -> Dict[str, Any]:
        raise NotImplementedError()

    @abstractmethod
    def set_device_property(self, device_id: str, key: str, value: Any) -> Dict[str, Any]:
        raise NotImplementedError()

    @abstractmethod
    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        raise NotImplementedError()

    @abstractmethod
    def power_cycle_device(self, device_id: str, offline_seconds: float = 0.05) -> Dict[str, Any]:
        raise NotImplementedError()


def get_device_manager(simulated: Optional[bool] = None):
    """Factory to return either the real DeviceManager or the simulated one.

    Behavior:
    - If `simulated` is True -> return SimulatedDeviceManager
    - If `simulated` is False -> return DeviceManager
    - If `simulated` is None -> consult `JARVIS_SIMULATE_DEVICES` env var
    """
    if simulated is None:
        env = os.environ.get("JARVIS_SIMULATE_DEVICES", "0")
        simulated = env.strip() in {"1", "true", "yes"}

    if simulated:
        from modules.services.simulated_device_manager import SimulatedDeviceManager

        return SimulatedDeviceManager()

    # Default: real device manager
    from modules.services.device_manager import DeviceManager

    return DeviceManager()
