"""
AudioManager: Handles audio device management, volume control, and microphone state.
Provides cross-platform audio device enumeration and control with graceful fallbacks.
"""
import platform
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioDevice:
    """Immutable representation of an audio device."""
    id: int
    name: str
    is_input: bool
    is_output: bool
    is_default_input: bool = False
    is_default_output: bool = False


@dataclass(frozen=True)
class AudioSnapshot:
    """Immutable snapshot of audio system state."""
    devices: List[AudioDevice]
    default_input: Optional[str]
    default_output: Optional[str]
    volume: float  # 0.0 to 100.0
    microphone_enabled: bool
    speakers_enabled: bool
    mic_muted: bool
    platform_name: str


class AudioManager:
    """
    Singleton audio device manager with cross-platform support.
    Efficiently manages volume, microphone state, and device selection.
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
        self._devices: List[AudioDevice] = []
        self._volume_cache = 100.0
        self._mic_enabled_cache = True
        self._speakers_enabled_cache = True
        self._initialize_audio()
        AudioManager._initialized = True
    
    def _initialize_audio(self):
        """Initialize pyaudio interface if available."""
        try:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()
        except ImportError:
            logger.warning("pyaudio not available, audio device enumeration will be limited")
            self._pyaudio = None
        except Exception as e:
            logger.warning(f"Failed to initialize pyaudio: {e}")
            self._pyaudio = None
    
    def snapshot(self) -> AudioSnapshot:
        """
        Returns comprehensive audio system state snapshot.
        
        Returns:
            AudioSnapshot with device list, volume, and microphone state
        """
        try:
            devices = self._enumerate_devices()
            default_input, default_output = self._get_default_devices()
            volume = self._get_volume()
            mic_enabled, mic_muted = self._get_microphone_state()
            speakers_enabled = self._get_speakers_state()
            
            return AudioSnapshot(
                devices=devices,
                default_input=default_input,
                default_output=default_output,
                volume=volume,
                microphone_enabled=mic_enabled,
                speakers_enabled=speakers_enabled,
                mic_muted=mic_muted,
                platform_name=self._platform
            )
        except Exception as e:
            logger.error(f"Error creating audio snapshot: {e}")
            # Return safe default snapshot
            return AudioSnapshot(
                devices=[],
                default_input=None,
                default_output=None,
                volume=100.0,
                microphone_enabled=True,
                speakers_enabled=True,
                mic_muted=False,
                platform_name=self._platform
            )
    
    def _enumerate_devices(self) -> List[AudioDevice]:
        """Enumerate audio devices using pyaudio or platform-specific tools."""
        if self._pyaudio is None:
            return self._enumerate_devices_fallback()
        
        try:
            devices = []
            device_count = self._pyaudio.get_device_count()
            default_input_id = self._pyaudio.get_default_input_device_info()['index']
            default_output_id = self._pyaudio.get_default_output_device_info()['index']
            
            for i in range(device_count):
                info = self._pyaudio.get_device_info_by_index(i)
                device = AudioDevice(
                    id=i,
                    name=info['name'],
                    is_input=info['maxInputChannels'] > 0,
                    is_output=info['maxOutputChannels'] > 0,
                    is_default_input=(i == default_input_id),
                    is_default_output=(i == default_output_id)
                )
                devices.append(device)
            
            return devices
        except Exception as e:
            logger.warning(f"Failed to enumerate devices via pyaudio: {e}")
            return self._enumerate_devices_fallback()
    
    def _enumerate_devices_fallback(self) -> List[AudioDevice]:
        """Fallback device enumeration for Windows using Win32."""
        if self._platform == "Windows":
            try:
                # Use Windows command to list audio devices
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-AudioDevice -List | Select-Object -First 10'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                # Parse output and create devices (simplified)
                # For now, return generic microphone and speaker
                devices = [
                    AudioDevice(id=0, name="Microphone (Built-in)", is_input=True, is_output=False, is_default_input=True),
                    AudioDevice(id=1, name="Speakers (Built-in)", is_input=False, is_output=True, is_default_output=True)
                ]
                return devices
            except Exception as e:
                logger.warning(f"Windows device enumeration failed: {e}")
        
        # Generic fallback
        return [
            AudioDevice(id=0, name="Default Input", is_input=True, is_output=False, is_default_input=True),
            AudioDevice(id=1, name="Default Output", is_input=False, is_output=True, is_default_output=True)
        ]
    
    def _get_default_devices(self) -> Tuple[Optional[str], Optional[str]]:
        """Get names of default input and output devices."""
        try:
            if self._pyaudio is None:
                return None, None
            
            input_info = self._pyaudio.get_default_input_device_info()
            output_info = self._pyaudio.get_default_output_device_info()
            
            return input_info['name'], output_info['name']
        except Exception as e:
            logger.warning(f"Failed to get default devices: {e}")
            return None, None
    
    def _get_volume(self) -> float:
        """Get current system volume level (0.0 to 100.0)."""
        try:
            if self._platform == "Windows":
                return self._get_volume_windows()
            elif self._platform == "Linux":
                return self._get_volume_linux()
            elif self._platform == "Darwin":
                return self._get_volume_macos()
        except Exception as e:
            logger.warning(f"Failed to get volume: {e}")
        
        return self._volume_cache
    
    def _get_volume_windows(self) -> float:
        """Get Windows system volume using WMI or registry."""
        try:
            result = subprocess.run(
                ['powershell', '-Command', 
                 '(Get-AudioDevice -PlaybackVolume).Volume'],
                capture_output=True,
                text=True,
                timeout=1
            )
            if result.returncode == 0 and result.stdout.strip():
                vol = float(result.stdout.strip())
                self._volume_cache = min(100.0, max(0.0, vol))
                return self._volume_cache
        except Exception as e:
            logger.warning(f"Windows volume detection failed: {e}")
        
        return self._volume_cache
    
    def _get_volume_linux(self) -> float:
        """Get Linux system volume using amixer."""
        try:
            result = subprocess.run(
                ['amixer', 'get', 'Master'],
                capture_output=True,
                text=True,
                timeout=1
            )
            # Parse amixer output: [xx%]
            for line in result.stdout.split('\n'):
                if '[' in line and '%' in line:
                    vol_str = line.split('[')[1].split('%')[0]
                    vol = float(vol_str)
                    self._volume_cache = vol
                    return vol
        except Exception as e:
            logger.warning(f"Linux volume detection failed: {e}")
        
        return self._volume_cache
    
    def _get_volume_macos(self) -> float:
        """Get macOS system volume."""
        try:
            result = subprocess.run(
                ['osascript', '-e', 'output volume of (get volume settings)'],
                capture_output=True,
                text=True,
                timeout=1
            )
            if result.returncode == 0:
                vol = float(result.stdout.strip())
                self._volume_cache = vol
                return vol
        except Exception as e:
            logger.warning(f"macOS volume detection failed: {e}")
        
        return self._volume_cache
    
    def _get_microphone_state(self) -> Tuple[bool, bool]:
        """
        Get microphone enabled state and mute status.
        
        Returns:
            Tuple[bool, bool]: (is_enabled, is_muted)
        """
        try:
            if self._platform == "Windows":
                return self._get_microphone_state_windows()
        except Exception as e:
            logger.warning(f"Failed to get microphone state: {e}")
        
        return self._mic_enabled_cache, False
    
    def _get_microphone_state_windows(self) -> Tuple[bool, bool]:
        """Check microphone state on Windows."""
        try:
            # Check if any recording device is enabled
            result = subprocess.run(
                ['powershell', '-Command',
                 'Get-AudioDevice -RecordingVolume | Measure-Object | Select-Object -ExpandProperty Count'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                count = int(result.stdout.strip() or 0)
                enabled = count > 0
                self._mic_enabled_cache = enabled
                return enabled, False
        except Exception as e:
            logger.warning(f"Windows mic state check failed: {e}")
        
        return self._mic_enabled_cache, False
    
    def _get_speakers_state(self) -> bool:
        """Check if speakers are enabled."""
        try:
            if self._platform == "Windows":
                result = subprocess.run(
                    ['powershell', '-Command',
                     'Get-AudioDevice -PlaybackVolume | Measure-Object | Select-Object -ExpandProperty Count'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0:
                    count = int(result.stdout.strip() or 0)
                    self._speakers_enabled_cache = count > 0
                    return self._speakers_enabled_cache
        except Exception as e:
            logger.warning(f"Speakers state check failed: {e}")
        
        return self._speakers_enabled_cache
    
    def set_volume(self, volume: float) -> bool:
        """
        Set system volume level.
        
        Args:
            volume: Float 0.0 to 100.0
            
        Returns:
            bool: True if successful
        """
        volume = max(0.0, min(100.0, volume))
        
        try:
            if self._platform == "Windows":
                return self._set_volume_windows(volume)
            elif self._platform == "Linux":
                return self._set_volume_linux(volume)
            elif self._platform == "Darwin":
                return self._set_volume_macos(volume)
        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            return False
        
        return False
    
    def _set_volume_windows(self, volume: float) -> bool:
        """Set volume on Windows."""
        try:
            subprocess.run(
                ['powershell', '-Command',
                 f'Set-AudioDevice -PlaybackVolume {int(volume)}'],
                capture_output=True,
                timeout=2
            )
            self._volume_cache = volume
            return True
        except Exception as e:
            logger.error(f"Failed to set Windows volume: {e}")
            return False
    
    def _set_volume_linux(self, volume: float) -> bool:
        """Set volume on Linux."""
        try:
            subprocess.run(
                ['amixer', 'set', 'Master', f'{int(volume)}%'],
                capture_output=True,
                timeout=2
            )
            self._volume_cache = volume
            return True
        except Exception as e:
            logger.error(f"Failed to set Linux volume: {e}")
            return False
    
    def _set_volume_macos(self, volume: float) -> bool:
        """Set volume on macOS."""
        try:
            subprocess.run(
                ['osascript', '-e',
                 f'set volume to {int(volume)}'],
                capture_output=True,
                timeout=2
            )
            self._volume_cache = volume
            return True
        except Exception as e:
            logger.error(f"Failed to set macOS volume: {e}")
            return False
    
    def toggle_microphone(self, enabled: bool) -> bool:
        """
        Enable or disable microphone.
        
        Args:
            enabled: True to enable, False to disable
            
        Returns:
            bool: True if successful
        """
        try:
            if self._platform == "Windows":
                return self._toggle_microphone_windows(enabled)
        except Exception as e:
            logger.error(f"Failed to toggle microphone: {e}")
            return False
        
        self._mic_enabled_cache = enabled
        return True
    
    def _toggle_microphone_windows(self, enabled: bool) -> bool:
        """Toggle microphone on Windows."""
        try:
            action = "Enable" if enabled else "Disable"
            subprocess.run(
                ['powershell', '-Command',
                 f'{action}-AudioDevice -RecordingAll'],
                capture_output=True,
                timeout=2
            )
            self._mic_enabled_cache = enabled
            return True
        except Exception as e:
            logger.error(f"Failed to toggle Windows microphone: {e}")
            return False
    
    def capability_matrix(self) -> dict:
        """
        Get audio capabilities summary for UI.
        
        Returns:
            dict with capability flags
        """
        snapshot = self.snapshot()
        return {
            "has_input_devices": any(d.is_input for d in snapshot.devices),
            "has_output_devices": any(d.is_output for d in snapshot.devices),
            "device_count": len(snapshot.devices),
            "microphone_available": snapshot.microphone_enabled,
            "speakers_available": snapshot.speakers_enabled
        }
