"""
JARVIS System Manager Service
Native OS control for Audio, Brightness, Power, and Processes.
"""

import os
import sys
import logging
import platform
import psutil
import threading
import time
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Windows specific imports
try:
    import wmi
    import comtypes
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from ctypes import cast, POINTER
except ImportError:
    logger.warning("Windows-specific system control libraries not fully available")

# Cross-platform brightness
try:
    import screen_brightness_control as sbc
except ImportError:
    sbc = None


class SystemManager:
    """
    Manages native OS hardware and system settings.
    Provides a unified interface for Volume, Brightness, and Power.
    """

    def __init__(self):
        self._os_type = platform.system()
        self._wmi = None
        if self._os_type == "Windows":
            try:
                self._wmi = wmi.WMI()
            except Exception:
                pass
        
        logger.info(f"SystemManager initialized for {self._os_type}")

    # ── Audio Controls ───────────────────────────────────────────────────

    def get_volume(self) -> Dict[str, Any]:
        """Get current system volume and mute status."""
        if self._os_type != "Windows":
            return {"status": "unsupported", "volume": 0, "muted": False}
        
        try:
            comtypes.CoInitialize()
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
            volume_api = cast(interface, POINTER(IAudioEndpointVolume))
            
            vol = volume_api.GetMasterVolumeLevelScalar()
            muted = volume_api.GetMute()
            
            return {
                "status": "success",
                "volume": int(vol * 100),
                "muted": bool(muted)
            }
        except Exception as exc:
            logger.error(f"Failed to get volume: {exc}")
            return {"status": "error", "message": str(exc)}
        finally:
            try: comtypes.CoUninitialize() 
            except: pass

    def set_volume(self, level: int) -> Dict[str, Any]:
        """Set system volume (0-100)."""
        if self._os_type != "Windows":
            return {"status": "unsupported"}
        
        try:
            level = max(0, min(100, level))
            comtypes.CoInitialize()
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
            volume_api = cast(interface, POINTER(IAudioEndpointVolume))
            
            volume_api.SetMasterVolumeLevelScalar(level / 100.0, None)
            return {"status": "success", "volume": level}
        except Exception as exc:
            logger.error(f"Failed to set volume: {exc}")
            return {"status": "error", "message": str(exc)}
        finally:
            try: comtypes.CoUninitialize()
            except: pass

    def toggle_mute(self) -> Dict[str, Any]:
        """Toggle system mute status."""
        if self._os_type != "Windows":
            return {"status": "unsupported"}
            
        try:
            comtypes.CoInitialize()
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
            volume_api = cast(interface, POINTER(IAudioEndpointVolume))
            
            is_muted = volume_api.GetMute()
            volume_api.SetMute(not is_muted, None)
            return {"status": "success", "muted": not is_muted}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
        finally:
            try: comtypes.CoUninitialize()
            except: pass

    # ── Display Controls ────────────────────────────────────────────────

    def get_brightness(self) -> Dict[str, Any]:
        """Get current screen brightness."""
        if not sbc:
            return {"status": "unavailable", "brightness": 0}
            
        try:
            # Get brightness for primary monitor
            brightness = sbc.get_brightness()
            if isinstance(brightness, list):
                brightness = brightness[0]
            
            return {"status": "success", "brightness": brightness}
        except Exception as exc:
            logger.error(f"Failed to get brightness: {exc}")
            return {"status": "error", "message": str(exc)}

    def set_brightness(self, level: int) -> Dict[str, Any]:
        """Set screen brightness (0-100)."""
        if not sbc:
            return {"status": "unavailable"}
            
        try:
            level = max(0, min(100, level))
            sbc.set_brightness(level)
            return {"status": "success", "brightness": level}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    # ── Power & Performance ───────────────────────────────────────────

    def get_power_status(self) -> Dict[str, Any]:
        """Get battery level and charging status."""
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return {"status": "no_battery", "percent": 100, "power_plugged": True}
            
            return {
                "status": "success",
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
                "seconds_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else -1
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_system_load(self) -> Dict[str, Any]:
        """Get real-time CPU, RAM, and Disk metrics."""
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "boot_time": psutil.boot_time()
        }

    # ── Capability Matrix ────────────────────────────────────────────

    def capability_matrix(self) -> Dict[str, Any]:
        """Return what this OS allows JARVIS to control."""
        return {
            "os": self._os_type,
            "features": {
                "audio": self._os_type == "Windows",
                "brightness": sbc is not None,
                "battery": psutil.sensors_battery() is not None,
                "process_monitoring": True
            }
        }
