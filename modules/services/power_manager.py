"""
PowerManager: Handles system power state detection and power actions.
Provides cross-platform power management with safe operation execution.
"""
import logging
import platform
import subprocess
from dataclasses import dataclass
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class PowerAction(Enum):
    """Available power actions."""
    SLEEP = "sleep"
    RESTART = "restart"
    SHUTDOWN = "shutdown"
    HIBERNATE = "hibernate"


@dataclass(frozen=True)
class PowerState:
    """Immutable representation of system power state."""
    ac_powered: bool
    battery_percent: Optional[float]  # 0-100, None if no battery
    charging: bool
    on_battery: bool
    low_battery: bool  # < 20%
    critical_battery: bool  # < 10%
    estimated_runtime_minutes: Optional[float]  # Estimated time on battery


@dataclass(frozen=True)
class PowerActionResult:
    """Result of a power action execution."""
    success: bool
    action: PowerAction
    message: str


class PowerManager:
    """
    Singleton power management system.
    Handles power state detection and safe power actions with confirmation gates.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._platform = platform.system()
        self._power_state_cache = None
        PowerManager._initialized = True
    
    def state(self) -> PowerState:
        """
        Get current system power state.
        
        Returns:
            PowerState with battery and power information
        """
        try:
            if self._platform == "Windows":
                return self._get_power_state_windows()
            elif self._platform == "Linux":
                return self._get_power_state_linux()
            elif self._platform == "Darwin":
                return self._get_power_state_macos()
        except Exception as e:
            logger.error(f"Error getting power state: {e}")
        
        # Safe default state
        return PowerState(
            ac_powered=True,
            battery_percent=None,
            charging=False,
            on_battery=False,
            low_battery=False,
            critical_battery=False,
            estimated_runtime_minutes=None
        )
    
    def _get_power_state_windows(self) -> PowerState:
        """Get Windows power state using WMI."""
        try:
            import psutil
            
            battery = psutil.sensors_battery()
            if battery is None:
                # No battery, presumably AC powered
                return PowerState(
                    ac_powered=True,
                    battery_percent=None,
                    charging=False,
                    on_battery=False,
                    low_battery=False,
                    critical_battery=False,
                    estimated_runtime_minutes=None
                )
            
            battery_percent = battery.percent
            is_charging = battery.power_plugged
            
            return PowerState(
                ac_powered=is_charging,
                battery_percent=battery_percent,
                charging=is_charging,
                on_battery=not is_charging,
                low_battery=battery_percent < 20,
                critical_battery=battery_percent < 10,
                estimated_runtime_minutes=battery.secsleft / 60.0 if battery.secsleft > 0 else None
            )
        except Exception as e:
            logger.warning(f"Failed to get Windows power state: {e}")
            return PowerState(
                ac_powered=True,
                battery_percent=None,
                charging=False,
                on_battery=False,
                low_battery=False,
                critical_battery=False,
                estimated_runtime_minutes=None
            )
    
    def _get_power_state_linux(self) -> PowerState:
        """Get Linux power state using /sys/class/power_supply."""
        try:
            import psutil
            
            battery = psutil.sensors_battery()
            if battery is None:
                return PowerState(
                    ac_powered=True,
                    battery_percent=None,
                    charging=False,
                    on_battery=False,
                    low_battery=False,
                    critical_battery=False,
                    estimated_runtime_minutes=None
                )
            
            battery_percent = battery.percent
            is_charging = battery.power_plugged
            
            return PowerState(
                ac_powered=is_charging,
                battery_percent=battery_percent,
                charging=is_charging,
                on_battery=not is_charging,
                low_battery=battery_percent < 20,
                critical_battery=battery_percent < 10,
                estimated_runtime_minutes=battery.secsleft / 60.0 if battery.secsleft > 0 else None
            )
        except Exception as e:
            logger.warning(f"Failed to get Linux power state: {e}")
            return PowerState(
                ac_powered=True,
                battery_percent=None,
                charging=False,
                on_battery=False,
                low_battery=False,
                critical_battery=False,
                estimated_runtime_minutes=None
            )
    
    def _get_power_state_macos(self) -> PowerState:
        """Get macOS power state using pmset."""
        try:
            import psutil
            
            battery = psutil.sensors_battery()
            if battery is None:
                return PowerState(
                    ac_powered=True,
                    battery_percent=None,
                    charging=False,
                    on_battery=False,
                    low_battery=False,
                    critical_battery=False,
                    estimated_runtime_minutes=None
                )
            
            battery_percent = battery.percent
            is_charging = battery.power_plugged
            
            return PowerState(
                ac_powered=is_charging,
                battery_percent=battery_percent,
                charging=is_charging,
                on_battery=not is_charging,
                low_battery=battery_percent < 20,
                critical_battery=battery_percent < 10,
                estimated_runtime_minutes=battery.secsleft / 60.0 if battery.secsleft > 0 else None
            )
        except Exception as e:
            logger.warning(f"Failed to get macOS power state: {e}")
            return PowerState(
                ac_powered=True,
                battery_percent=None,
                charging=False,
                on_battery=False,
                low_battery=False,
                critical_battery=False,
                estimated_runtime_minutes=None
            )
    
    def sleep(self, confirmed: bool = False) -> PowerActionResult:
        """
        Initiate system sleep.
        
        Args:
            confirmed: Whether this action has been user-confirmed
            
        Returns:
            PowerActionResult indicating success or failure
        """
        if not confirmed:
            return PowerActionResult(
                success=False,
                action=PowerAction.SLEEP,
                message="Action requires user confirmation"
            )
        
        try:
            if self._platform == "Windows":
                subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], timeout=5)
            elif self._platform == "Linux":
                subprocess.run(["systemctl", "suspend"], timeout=5)
            elif self._platform == "Darwin":
                subprocess.run(["osascript", "-e", "tell application \"System Events\" to sleep"], timeout=5)
            else:
                return PowerActionResult(
                    success=False,
                    action=PowerAction.SLEEP,
                    message=f"Sleep not implemented for {self._platform}"
                )
            
            logger.info("System sleep initiated")
            return PowerActionResult(
                success=True,
                action=PowerAction.SLEEP,
                message="System entering sleep mode"
            )
        except Exception as e:
            logger.error(f"Failed to initiate sleep: {e}")
            return PowerActionResult(
                success=False,
                action=PowerAction.SLEEP,
                message=f"Sleep failed: {str(e)}"
            )
    
    def restart(self, confirmed: bool = False) -> PowerActionResult:
        """
        Initiate system restart.
        
        Args:
            confirmed: Whether this action has been user-confirmed
            
        Returns:
            PowerActionResult indicating success or failure
        """
        if not confirmed:
            return PowerActionResult(
                success=False,
                action=PowerAction.RESTART,
                message="Action requires user confirmation"
            )
        
        try:
            if self._platform == "Windows":
                subprocess.run(["shutdown", "/r", "/t", "30", "/c", "JARVIS system restart"], timeout=5)
            elif self._platform == "Linux":
                subprocess.run(["shutdown", "-r", "+1"], timeout=5)
            elif self._platform == "Darwin":
                subprocess.run(["osascript", "-e", "tell application \"System Events\" to restart"], timeout=5)
            else:
                return PowerActionResult(
                    success=False,
                    action=PowerAction.RESTART,
                    message=f"Restart not implemented for {self._platform}"
                )
            
            logger.info("System restart initiated")
            return PowerActionResult(
                success=True,
                action=PowerAction.RESTART,
                message="System restart initiated (30 second countdown)"
            )
        except Exception as e:
            logger.error(f"Failed to initiate restart: {e}")
            return PowerActionResult(
                success=False,
                action=PowerAction.RESTART,
                message=f"Restart failed: {str(e)}"
            )
    
    def shutdown(self, confirmed: bool = False) -> PowerActionResult:
        """
        Initiate system shutdown.
        
        Args:
            confirmed: Whether this action has been user-confirmed
            
        Returns:
            PowerActionResult indicating success or failure
        """
        if not confirmed:
            return PowerActionResult(
                success=False,
                action=PowerAction.SHUTDOWN,
                message="Action requires user confirmation"
            )
        
        try:
            if self._platform == "Windows":
                subprocess.run(["shutdown", "/s", "/t", "30", "/c", "JARVIS system shutdown"], timeout=5)
            elif self._platform == "Linux":
                subprocess.run(["shutdown", "-h", "+1"], timeout=5)
            elif self._platform == "Darwin":
                subprocess.run(["osascript", "-e", "tell application \"System Events\" to shut down"], timeout=5)
            else:
                return PowerActionResult(
                    success=False,
                    action=PowerAction.SHUTDOWN,
                    message=f"Shutdown not implemented for {self._platform}"
                )
            
            logger.info("System shutdown initiated")
            return PowerActionResult(
                success=True,
                action=PowerAction.SHUTDOWN,
                message="System shutdown initiated (30 second countdown)"
            )
        except Exception as e:
            logger.error(f"Failed to initiate shutdown: {e}")
            return PowerActionResult(
                success=False,
                action=PowerAction.SHUTDOWN,
                message=f"Shutdown failed: {str(e)}"
            )
    
    def hibernate(self, confirmed: bool = False) -> PowerActionResult:
        """
        Initiate system hibernation (Windows only).
        
        Args:
            confirmed: Whether this action has been user-confirmed
            
        Returns:
            PowerActionResult indicating success or failure
        """
        if not confirmed:
            return PowerActionResult(
                success=False,
                action=PowerAction.HIBERNATE,
                message="Action requires user confirmation"
            )
        
        if self._platform != "Windows":
            return PowerActionResult(
                success=False,
                action=PowerAction.HIBERNATE,
                message="Hibernation only available on Windows"
            )
        
        try:
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "1,1,1"], timeout=5)
            logger.info("System hibernation initiated")
            return PowerActionResult(
                success=True,
                action=PowerAction.HIBERNATE,
                message="System entering hibernation"
            )
        except Exception as e:
            logger.error(f"Failed to initiate hibernation: {e}")
            return PowerActionResult(
                success=False,
                action=PowerAction.HIBERNATE,
                message=f"Hibernation failed: {str(e)}"
            )
    
    def cancel_pending_action(self) -> PowerActionResult:
        """
        Cancel any pending shutdown/restart operation.
        
        Returns:
            PowerActionResult indicating success or failure
        """
        try:
            if self._platform == "Windows":
                subprocess.run(["shutdown", "/a"], timeout=5)
            elif self._platform == "Linux":
                subprocess.run(["shutdown", "-c"], timeout=5)
            else:
                return PowerActionResult(
                    success=False,
                    action=PowerAction.SHUTDOWN,
                    message="Cancel not supported on this platform"
                )
            
            logger.info("Pending power action cancelled")
            return PowerActionResult(
                success=True,
                action=PowerAction.SHUTDOWN,
                message="Pending shutdown/restart cancelled"
            )
        except Exception as e:
            logger.warning(f"Failed to cancel pending action: {e}")
            return PowerActionResult(
                success=False,
                action=PowerAction.SHUTDOWN,
                message=f"Cancel failed: {str(e)}"
            )
    
    def capability_matrix(self) -> dict:
        """
        Get power management capabilities for UI.
        
        Returns:
            dict with capability flags
        """
        state = self.state()
        return {
            "ac_powered": state.ac_powered,
            "on_battery": state.on_battery,
            "can_sleep": True,
            "can_restart": True,
            "can_shutdown": True,
            "can_hibernate": self._platform == "Windows",
            "battery_available": state.battery_percent is not None
        }
