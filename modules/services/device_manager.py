"""
Device Manager for JARVIS OS
Provides efficient hardware and platform snapshots for the control surface.
"""

import logging
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import psutil

logger = logging.getLogger(__name__)

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

try:
    import speech_recognition as sr
except Exception:  # pragma: no cover
    sr = None

try:
    import pyttsx3
except Exception:  # pragma: no cover
    pyttsx3 = None

try:
    from tkinter import Tk
except Exception:  # pragma: no cover
    Tk = None


@dataclass(frozen=True)
class DeviceSnapshot:
    platform: str
    kernel: str
    machine: str
    cpu_cores: int
    cpu_freq_mhz: int
    memory_total_gb: float
    memory_available_gb: float
    disk_total_gb: float
    disk_free_gb: float
    battery_percent: Optional[float]
    power_plugged: Optional[bool]
    display_width: Optional[int]
    display_height: Optional[int]
    camera_available: bool
    microphone_available: bool
    tts_available: bool
    sensor_support: bool
    network_interfaces: int
    timestamp: str


class DeviceManager:
    """Build and cache OS hardware snapshots."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or Path.cwd())

    @lru_cache(maxsize=1)
    def _screen_geometry(self) -> tuple[Optional[int], Optional[int]]:
        if not Tk:
            return None, None
        try:
            root = Tk()
            root.withdraw()
            width = root.winfo_screenwidth()
            height = root.winfo_screenheight()
            root.destroy()
            return width, height
        except Exception:
            return None, None

    def snapshot(self) -> Dict[str, Any]:
        """Return a compact, high-signal snapshot of hardware readiness."""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(str(self.workspace_root.anchor or self.workspace_root))
        battery = psutil.sensors_battery()
        cpu_freq = psutil.cpu_freq()
        width, height = self._screen_geometry()
        net_ifaces = len(psutil.net_if_addrs())

        data = DeviceSnapshot(
            platform=f"{platform.system()} {platform.release()}",
            kernel=platform.version(),
            machine=platform.machine(),
            cpu_cores=psutil.cpu_count(logical=True) or 0,
            cpu_freq_mhz=round(cpu_freq.current) if cpu_freq and cpu_freq.current else 0,
            memory_total_gb=round(memory.total / (1024**3), 1),
            memory_available_gb=round(memory.available / (1024**3), 1),
            disk_total_gb=round(disk.total / (1024**3), 1),
            disk_free_gb=round(disk.free / (1024**3), 1),
            battery_percent=battery.percent if battery else None,
            power_plugged=battery.power_plugged if battery else None,
            display_width=width,
            display_height=height,
            camera_available=bool(cv2),
            microphone_available=bool(sr),
            tts_available=bool(pyttsx3),
            sensor_support=hasattr(psutil, "sensors_temperatures"),
            network_interfaces=net_ifaces,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        return data.__dict__

    def capability_matrix(self) -> Dict[str, Any]:
        """Return feature availability for UI presentation."""
        snap = self.snapshot()
        return {
            "camera": {"available": snap["camera_available"], "configured": snap["camera_available"]},
            "microphone": {"available": snap["microphone_available"], "configured": snap["microphone_available"]},
            "tts": {"available": snap["tts_available"], "configured": snap["tts_available"]},
            "display": {
                "available": snap["display_width"] is not None and snap["display_height"] is not None,
                "width": snap["display_width"],
                "height": snap["display_height"],
            },
            "battery": {"available": snap["battery_percent"] is not None, "percent": snap["battery_percent"]},
            "network": {"interfaces": snap["network_interfaces"]},
        }
