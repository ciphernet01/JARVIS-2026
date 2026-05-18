"""
Hardware validation reporting for Phase 4.

Creates repeatable compatibility reports from the existing device, audio,
camera, network, and power managers.
"""

import hashlib
import json
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .audio_manager import AudioManager
from .camera_manager import CameraManager
from .device_manager import DeviceManager
from .network_manager import ConnectionType, NetworkManager
from .power_manager import PowerManager


@dataclass(frozen=True)
class HardwareValidationCheck:
    """A single hardware validation result."""
    category: str
    name: str
    status: str
    message: str
    evidence: Dict[str, Any]
    recommendation: str = ""


@dataclass(frozen=True)
class HardwareValidationReport:
    """A complete hardware compatibility report."""
    id: str
    label: str
    created_at: str
    target_config_id: str
    platform_name: str
    machine: str
    overall_status: str
    score: int
    checks: List[HardwareValidationCheck]
    snapshot_summary: Dict[str, Any]
    notes: str = ""


class HardwareValidationManager:
    """Build and persist repeatable hardware validation reports."""

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        *,
        device_manager: Optional[Any] = None,
        audio_manager: Optional[Any] = None,
        camera_manager: Optional[Any] = None,
        network_manager: Optional[Any] = None,
        power_manager: Optional[Any] = None,
        gpu_probe: Optional[Dict[str, Any]] = None,
        bluetooth_probe: Optional[Dict[str, Any]] = None,
        audio_latency_probe: Optional[Dict[str, Any]] = None,
        audio_workload_probe: Optional[Dict[str, Any]] = None,
        camera_workload_probe: Optional[Dict[str, Any]] = None,
    ):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.report_dir = self.workspace_root / "test_reports" / "hardware_validation"
        self.device_manager = device_manager or DeviceManager(workspace_root=str(self.workspace_root))
        self.audio_manager = audio_manager or AudioManager()
        self.camera_manager = camera_manager or CameraManager()
        self.network_manager = network_manager or NetworkManager()
        self.power_manager = power_manager or PowerManager()
        self._gpu_probe_override = gpu_probe
        self._bluetooth_probe_override = bluetooth_probe
        self._audio_latency_probe_override = audio_latency_probe
        self._audio_workload_probe_override = audio_workload_probe
        self._camera_workload_probe_override = camera_workload_probe

    def run_validation(self, label: Optional[str] = None, notes: str = "", save: bool = True) -> Dict[str, Any]:
        """Run validation checks and optionally persist the report."""
        created_at = datetime.now(timezone.utc).isoformat()
        snapshots = self._collect_snapshots()
        checks = self._build_checks(snapshots)
        score = self._score(checks)
        overall = self._overall_status(checks, score)
        target_config_id = self._target_config_id(snapshots["device"])
        report_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + target_config_id[:8]

        report = HardwareValidationReport(
            id=report_id,
            label=(label or "hardware-validation").strip()[:80] or "hardware-validation",
            created_at=created_at,
            target_config_id=target_config_id,
            platform_name=snapshots["device"].get("platform", platform.system()),
            machine=snapshots["device"].get("machine", platform.machine()),
            overall_status=overall,
            score=score,
            checks=checks,
            snapshot_summary=self._snapshot_summary(snapshots),
            notes=notes.strip()[:500],
        )
        payload = self._report_payload(report)
        if save:
            self._save_report(payload)
        return payload

    def list_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent saved hardware validation report summaries."""
        reports = []
        if not self.report_dir.exists():
            return reports
        for path in sorted(self.report_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                reports.append({
                    "id": data.get("id", path.stem),
                    "label": data.get("label", path.stem),
                    "created_at": data.get("created_at"),
                    "target_config_id": data.get("target_config_id"),
                    "overall_status": data.get("overall_status"),
                    "score": data.get("score"),
                    "platform_name": data.get("platform_name"),
                    "machine": data.get("machine"),
                    "path": str(path.relative_to(self.workspace_root)),
                })
            except Exception:
                continue
            if len(reports) >= max(1, limit):
                break
        return reports

    def compatibility_matrix(self, limit: int = 20) -> Dict[str, Any]:
        """Summarize saved reports by target configuration."""
        reports = self.list_reports(limit=limit)
        targets: Dict[str, Dict[str, Any]] = {}
        for report in reports:
            target_id = report.get("target_config_id") or "unknown"
            existing = targets.get(target_id)
            if not existing or (report.get("created_at") or "") > (existing.get("latest_created_at") or ""):
                targets[target_id] = {
                    "target_config_id": target_id,
                    "latest_created_at": report.get("created_at"),
                    "latest_report_id": report.get("id"),
                    "overall_status": report.get("overall_status"),
                    "score": report.get("score"),
                    "platform_name": report.get("platform_name"),
                    "machine": report.get("machine"),
                }
        return {
            "target_count": len(targets),
            "report_count": len(reports),
            "targets": sorted(targets.values(), key=lambda item: item.get("latest_created_at") or "", reverse=True),
        }

    def _collect_snapshots(self) -> Dict[str, Any]:
        return {
            "device": self.device_manager.snapshot(),
            "audio": self.audio_manager.snapshot(),
            "camera_state": self.camera_manager.state(),
            "camera_devices": self.camera_manager.list_devices(),
            "network": self.network_manager.snapshot(),
            "power": self.power_manager.state(),
            "gpu_probe": self._gpu_probe_override or self._probe_gpu(),
            "bluetooth_probe": self._bluetooth_probe_override or self._probe_bluetooth(),
            "audio_latency_probe": self._audio_latency_probe_override or self._probe_audio_latency(),
            "audio_workload_probe": self._audio_workload_probe_override or self._probe_audio_workload(),
            "camera_workload_probe": self._camera_workload_probe_override or self._probe_camera_workload(),
        }

    def _build_checks(self, snapshots: Dict[str, Any]) -> List[HardwareValidationCheck]:
        device = snapshots["device"]
        audio = snapshots["audio"]
        camera_state = snapshots["camera_state"]
        camera_devices = snapshots["camera_devices"]
        network = snapshots["network"]
        power = snapshots["power"]
        gpu_probe = snapshots["gpu_probe"]
        bluetooth_probe = snapshots["bluetooth_probe"]
        audio_latency_probe = snapshots["audio_latency_probe"]
        audio_workload_probe = snapshots["audio_workload_probe"]
        camera_workload_probe = snapshots["camera_workload_probe"]

        checks = [
            self._threshold_check("system", "CPU cores", device.get("cpu_cores", 0), 2, 4, "logical cores"),
            self._threshold_check("system", "Memory", device.get("memory_total_gb", 0), 4, 8, "GB total RAM"),
            self._threshold_check("storage", "Disk free", device.get("disk_free_gb", 0), 10, 25, "GB free"),
            self._display_check(device),
            self._audio_check(audio),
            self._audio_workload_check(audio_workload_probe),
            self._audio_latency_check(audio_latency_probe),
            self._camera_check(camera_state, camera_devices),
            self._camera_workload_check(camera_workload_probe),
            self._network_check(network),
            self._battery_check(power),
            self._thermal_check(device),
            self._gpu_check(gpu_probe),
            self._bluetooth_check(bluetooth_probe),
        ]
        return checks

    def _threshold_check(self, category: str, name: str, value: float, warn_min: float, pass_min: float, unit: str) -> HardwareValidationCheck:
        if value >= pass_min:
            status = "pass"
            message = f"{name} meets production target."
            recommendation = ""
        elif value >= warn_min:
            status = "warn"
            message = f"{name} meets minimum target but is below preferred target."
            recommendation = f"Prefer at least {pass_min:g} {unit}."
        else:
            status = "fail"
            message = f"{name} is below minimum target."
            recommendation = f"Requires at least {warn_min:g} {unit}."
        return HardwareValidationCheck(category, name, status, message, {"value": value, "unit": unit, "minimum": warn_min, "preferred": pass_min}, recommendation)

    def _display_check(self, device: Dict[str, Any]) -> HardwareValidationCheck:
        width = device.get("display_width")
        height = device.get("display_height")
        available = width is not None and height is not None
        return HardwareValidationCheck(
            "display",
            "Display detection",
            "pass" if available else "warn",
            "Display geometry detected." if available else "Display geometry unavailable in this environment.",
            {"width": width, "height": height},
            "" if available else "Run validation from a graphical session.",
        )

    def _audio_check(self, audio: Any) -> HardwareValidationCheck:
        devices = getattr(audio, "devices", [])
        has_input = any(getattr(device, "is_input", False) for device in devices)
        has_output = any(getattr(device, "is_output", False) for device in devices)
        status = "pass" if has_input and has_output else "warn"
        return HardwareValidationCheck(
            "audio",
            "Audio input/output",
            status,
            "Audio input and output devices detected." if status == "pass" else "Audio devices are incomplete or using fallback detection.",
            {"device_count": len(devices), "has_input": has_input, "has_output": has_output},
            "" if status == "pass" else "Validate microphone and speaker drivers on target hardware.",
        )

    def _audio_workload_check(self, probe: Dict[str, Any]) -> HardwareValidationCheck:
        if not probe.get("available"):
            return HardwareValidationCheck(
                "audio",
                "Audio workload readiness",
                "unknown",
                probe.get("message", "Audio workload probe is unavailable."),
                probe,
                "Install/enable PyAudio and validate default input/output devices on target hardware.",
            )
        has_input = bool(probe.get("has_default_input"))
        has_output = bool(probe.get("has_default_output"))
        sample_rate = float(probe.get("default_sample_rate") or 0.0)
        if has_input and has_output and sample_rate >= 16000:
            status = "pass"
            message = "Default audio input/output devices are ready for voice workloads."
            recommendation = ""
        elif has_input or has_output:
            status = "warn"
            message = "Audio workload probe found only partial default device readiness."
            recommendation = "Validate default microphone and speaker routing before voice testing."
        else:
            status = "fail"
            message = "No default audio input/output devices are ready for voice workloads."
            recommendation = "Install or configure audio drivers and default devices."
        return HardwareValidationCheck("audio", "Audio workload readiness", status, message, probe, recommendation)

    def _audio_latency_check(self, probe: Dict[str, Any]) -> HardwareValidationCheck:
        if not probe.get("available"):
            return HardwareValidationCheck(
                "audio",
                "Audio latency probe",
                "unknown",
                probe.get("message", "Audio latency probe is unavailable."),
                probe,
                "Install/enable PyAudio or add an OS-specific loopback latency probe.",
            )
        latency_ms = probe.get("estimated_roundtrip_ms")
        if latency_ms is None:
            return HardwareValidationCheck("audio", "Audio latency probe", "unknown", "Audio latency could not be estimated.", probe, "Run a loopback latency test on target hardware.")
        if latency_ms <= 120:
            status = "pass"
            message = "Estimated audio latency is within target."
            recommendation = ""
        elif latency_ms <= 250:
            status = "warn"
            message = "Estimated audio latency is usable but above preferred target."
            recommendation = "Tune audio buffer size, sample rate, and driver backend."
        else:
            status = "fail"
            message = "Estimated audio latency is too high for responsive voice UX."
            recommendation = "Validate drivers and reduce audio buffer latency before production."
        return HardwareValidationCheck("audio", "Audio latency probe", status, message, probe, recommendation)

    def _camera_check(self, camera_state: Any, camera_devices: List[Dict[str, Any]]) -> HardwareValidationCheck:
        available = bool(getattr(camera_state, "available", False))
        status = "pass" if available and len(camera_devices) > 0 else "warn" if available else "fail"
        return HardwareValidationCheck(
            "camera",
            "Camera compatibility",
            status,
            "Camera stack is available." if available else "Camera stack is unavailable.",
            {"available": available, "device_count": len(camera_devices), "devices": camera_devices[:5]},
            "" if status == "pass" else "Run camera enumeration and snapshot test on target hardware.",
        )

    def _camera_workload_check(self, probe: Dict[str, Any]) -> HardwareValidationCheck:
        if not probe.get("available"):
            return HardwareValidationCheck(
                "camera",
                "Camera snapshot workload",
                "unknown",
                probe.get("message", "Camera snapshot probe is unavailable."),
                probe,
                "Run validation from a camera-capable target with camera permissions granted.",
            )
        captured = bool(probe.get("captured"))
        width = int(probe.get("width") or 0)
        height = int(probe.get("height") or 0)
        if captured and width >= 640 and height >= 480:
            status = "pass"
            message = "Camera captured a usable validation frame."
            recommendation = ""
        elif captured:
            status = "warn"
            message = "Camera captured a frame below preferred validation resolution."
            recommendation = "Validate camera resolution and driver configuration."
        else:
            status = "fail"
            message = "Camera did not capture a validation frame."
            recommendation = "Check camera permissions, driver availability, and exclusive access conflicts."
        return HardwareValidationCheck("camera", "Camera snapshot workload", status, message, probe, recommendation)

    def _network_check(self, network: Any) -> HardwareValidationCheck:
        connected = getattr(network, "connected_interfaces", [])
        wifi_present = any(getattr(iface, "connection_type", None) == ConnectionType.WIFI for iface in connected)
        status = "pass" if len(connected) > 0 else "fail"
        return HardwareValidationCheck(
            "network",
            "Network connectivity",
            status,
            "At least one network interface is connected." if status == "pass" else "No connected network interfaces detected.",
            {"connected_interfaces": len(connected), "wifi_enabled": getattr(network, "wifi_enabled", False), "wifi_present": wifi_present},
            "" if status == "pass" else "Validate Ethernet/WiFi drivers and network configuration.",
        )

    def _battery_check(self, power: Any) -> HardwareValidationCheck:
        percent = getattr(power, "battery_percent", None)
        if percent is None:
            status = "pass"
            message = "No battery detected; treating as desktop/AC configuration."
            recommendation = ""
        elif getattr(power, "critical_battery", False):
            status = "fail"
            message = "Battery is critically low."
            recommendation = "Charge before stress or thermal validation."
        elif getattr(power, "low_battery", False):
            status = "warn"
            message = "Battery is low."
            recommendation = "Charge before long validation runs."
        else:
            status = "pass"
            message = "Battery state is healthy for validation."
            recommendation = ""
        return HardwareValidationCheck("power", "Battery state", status, message, {"battery_percent": percent, "ac_powered": getattr(power, "ac_powered", None)}, recommendation)

    def _thermal_check(self, device: Dict[str, Any]) -> HardwareValidationCheck:
        supported = bool(device.get("sensor_support"))
        return HardwareValidationCheck(
            "thermal",
            "Thermal sensor support",
            "pass" if supported else "warn",
            "Thermal sensor API is available." if supported else "Thermal sensor API is not available.",
            {"sensor_support": supported},
            "" if supported else "Add platform-specific thermal probe for this target.",
        )

    def _gpu_check(self, probe: Dict[str, Any]) -> HardwareValidationCheck:
        if not probe.get("available"):
            return HardwareValidationCheck(
                "gpu",
                "GPU driver validation",
                "unknown",
                probe.get("message", "GPU probe is unavailable."),
                probe,
                "Install platform GPU probe tools or run a render smoke test.",
            )
        device_count = len(probe.get("devices") or [])
        status = "pass" if device_count > 0 else "warn"
        return HardwareValidationCheck(
            "gpu",
            "GPU driver validation",
            status,
            "GPU adapter information detected." if device_count else "GPU probe ran but no adapter details were found.",
            probe,
            "" if status == "pass" else "Validate GPU driver installation and render acceleration.",
        )

    def _bluetooth_check(self, probe: Dict[str, Any]) -> HardwareValidationCheck:
        if not probe.get("available"):
            return HardwareValidationCheck(
                "bluetooth",
                "Bluetooth driver validation",
                "unknown",
                probe.get("message", "Bluetooth probe is unavailable."),
                probe,
                "Install platform Bluetooth probe tools or validate adapter enumeration manually.",
            )
        adapter_count = len(probe.get("adapters") or [])
        status = "pass" if adapter_count > 0 else "warn"
        return HardwareValidationCheck(
            "bluetooth",
            "Bluetooth driver validation",
            status,
            "Bluetooth adapter information detected." if adapter_count else "Bluetooth probe ran but no adapters were found.",
            probe,
            "" if status == "pass" else "Validate Bluetooth driver and adapter availability on target hardware.",
        )

    def _unknown_check(self, category: str, name: str, evidence: Dict[str, Any], recommendation: str) -> HardwareValidationCheck:
        return HardwareValidationCheck(category, name, "unknown", "No automated validation probe is available yet.", evidence, recommendation)

    def _probe_gpu(self) -> Dict[str, Any]:
        system = platform.system()
        if system == "Windows":
            return self._probe_windows_gpu()
        if system == "Linux":
            return self._probe_linux_gpu()
        if system == "Darwin":
            return self._probe_macos_gpu()
        return {"available": False, "platform": system, "devices": [], "message": "No GPU probe exists for this platform."}

    def _probe_bluetooth(self) -> Dict[str, Any]:
        system = platform.system()
        if system == "Windows":
            return self._probe_windows_bluetooth()
        if system == "Linux":
            return self._probe_linux_bluetooth()
        if system == "Darwin":
            return self._probe_macos_bluetooth()
        return {"available": False, "platform": system, "adapters": [], "message": "No Bluetooth probe exists for this platform."}

    def _probe_audio_latency(self) -> Dict[str, Any]:
        pyaudio_obj = getattr(self.audio_manager, "_pyaudio", None)
        if not pyaudio_obj:
            return {"available": False, "message": "PyAudio is unavailable; latency cannot be estimated.", "estimated_roundtrip_ms": None}
        try:
            input_info = pyaudio_obj.get_default_input_device_info()
            output_info = pyaudio_obj.get_default_output_device_info()
            input_latency = float(input_info.get("defaultLowInputLatency", input_info.get("defaultHighInputLatency", 0.0)) or 0.0)
            output_latency = float(output_info.get("defaultLowOutputLatency", output_info.get("defaultHighOutputLatency", 0.0)) or 0.0)
            roundtrip_ms = round((input_latency + output_latency) * 1000, 2)
            return {
                "available": True,
                "estimated_roundtrip_ms": roundtrip_ms,
                "input_latency_ms": round(input_latency * 1000, 2),
                "output_latency_ms": round(output_latency * 1000, 2),
                "input_device": input_info.get("name"),
                "output_device": output_info.get("name"),
            }
        except Exception as exc:
            return {"available": False, "message": f"Audio latency probe failed: {exc}", "estimated_roundtrip_ms": None}

    def _probe_audio_workload(self) -> Dict[str, Any]:
        pyaudio_obj = getattr(self.audio_manager, "_pyaudio", None)
        if not pyaudio_obj:
            return {"available": False, "message": "PyAudio is unavailable; audio workload readiness cannot be probed."}
        try:
            input_info = pyaudio_obj.get_default_input_device_info()
            output_info = pyaudio_obj.get_default_output_device_info()
            input_rate = float(input_info.get("defaultSampleRate", 0.0) or 0.0)
            output_rate = float(output_info.get("defaultSampleRate", 0.0) or 0.0)
            return {
                "available": True,
                "has_default_input": bool(input_info),
                "has_default_output": bool(output_info),
                "input_device": input_info.get("name"),
                "output_device": output_info.get("name"),
                "input_channels": int(input_info.get("maxInputChannels", 0) or 0),
                "output_channels": int(output_info.get("maxOutputChannels", 0) or 0),
                "input_sample_rate": input_rate,
                "output_sample_rate": output_rate,
                "default_sample_rate": min(input_rate, output_rate) if input_rate and output_rate else max(input_rate, output_rate),
            }
        except Exception as exc:
            return {"available": False, "message": f"Audio workload probe failed: {exc}"}

    def _probe_camera_workload(self) -> Dict[str, Any]:
        state = self.camera_manager.state()
        if not getattr(state, "available", False):
            return {"available": False, "captured": False, "message": "Camera stack is unavailable."}
        was_enabled = bool(getattr(state, "enabled", False))
        try:
            if not was_enabled and not self.camera_manager.enable():
                return {"available": True, "captured": False, "message": "Camera could not be enabled for snapshot workload."}
            snapshot = self.camera_manager.capture_snapshot(detect_faces=False)
            if snapshot is None:
                return {"available": True, "captured": False, "message": "Camera snapshot capture returned no frame."}
            return {
                "available": True,
                "captured": True,
                "width": snapshot.width,
                "height": snapshot.height,
                "has_faces": snapshot.has_faces,
                "face_count": snapshot.face_count,
            }
        except Exception as exc:
            return {"available": True, "captured": False, "message": f"Camera workload probe failed: {exc}"}
        finally:
            if not was_enabled:
                try:
                    self.camera_manager.disable()
                except Exception:
                    pass

    def _probe_windows_gpu(self) -> Dict[str, Any]:
        command = [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,AdapterRAM | ConvertTo-Json -Compress",
        ]
        result = self._run_probe(command)
        devices = self._json_objects(result.get("stdout", ""))
        return {**result, "devices": devices, "message": "Windows GPU CIM probe completed." if result.get("available") else result.get("message", "")}

    def _probe_windows_bluetooth(self) -> Dict[str, Any]:
        command = [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Compress",
        ]
        result = self._run_probe(command)
        adapters = self._json_objects(result.get("stdout", ""))
        return {**result, "adapters": adapters, "message": "Windows Bluetooth PnP probe completed." if result.get("available") else result.get("message", "")}

    def _probe_linux_gpu(self) -> Dict[str, Any]:
        if shutil.which("lspci"):
            result = self._run_probe(["lspci"])
            devices = [
                {"name": line.strip()}
                for line in result.get("stdout", "").splitlines()
                if any(term in line.lower() for term in ["vga", "3d controller", "display controller"])
            ]
            return {**result, "devices": devices, "message": "Linux lspci GPU probe completed." if result.get("available") else result.get("message", "")}
        if shutil.which("nvidia-smi"):
            result = self._run_probe(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"])
            devices = [{"name": line.strip()} for line in result.get("stdout", "").splitlines() if line.strip()]
            return {**result, "devices": devices, "message": "Linux NVIDIA GPU probe completed." if result.get("available") else result.get("message", "")}
        return {"available": False, "platform": "Linux", "devices": [], "message": "No Linux GPU probe tool found (lspci or nvidia-smi)."}

    def _probe_linux_bluetooth(self) -> Dict[str, Any]:
        if shutil.which("bluetoothctl"):
            result = self._run_probe(["bluetoothctl", "list"])
            adapters = [{"name": line.strip()} for line in result.get("stdout", "").splitlines() if line.strip()]
            return {**result, "adapters": adapters, "message": "Linux bluetoothctl probe completed." if result.get("available") else result.get("message", "")}
        if shutil.which("hciconfig"):
            result = self._run_probe(["hciconfig", "-a"])
            adapters = [{"name": line.strip()} for line in result.get("stdout", "").splitlines() if line.strip().startswith("hci")]
            return {**result, "adapters": adapters, "message": "Linux hciconfig probe completed." if result.get("available") else result.get("message", "")}
        return {"available": False, "platform": "Linux", "adapters": [], "message": "No Linux Bluetooth probe tool found (bluetoothctl or hciconfig)."}

    def _probe_macos_gpu(self) -> Dict[str, Any]:
        if not shutil.which("system_profiler"):
            return {"available": False, "platform": "Darwin", "devices": [], "message": "system_profiler is unavailable."}
        result = self._run_probe(["system_profiler", "SPDisplaysDataType", "-json"])
        data = self._json_value(result.get("stdout", ""))
        devices = data.get("SPDisplaysDataType", []) if isinstance(data, dict) else []
        return {**result, "devices": devices, "message": "macOS display profiler probe completed." if result.get("available") else result.get("message", "")}

    def _probe_macos_bluetooth(self) -> Dict[str, Any]:
        if not shutil.which("system_profiler"):
            return {"available": False, "platform": "Darwin", "adapters": [], "message": "system_profiler is unavailable."}
        result = self._run_probe(["system_profiler", "SPBluetoothDataType", "-json"])
        data = self._json_value(result.get("stdout", ""))
        adapters = data.get("SPBluetoothDataType", []) if isinstance(data, dict) else []
        return {**result, "adapters": adapters, "message": "macOS Bluetooth profiler probe completed." if result.get("available") else result.get("message", "")}

    def _run_probe(self, command: List[str], timeout_seconds: int = 8) -> Dict[str, Any]:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                shell=False,
            )
            return {
                "available": completed.returncode == 0,
                "command": command,
                "returncode": completed.returncode,
                "stdout": (completed.stdout or "")[-5000:],
                "stderr": (completed.stderr or "")[-2000:],
                "message": "Probe completed." if completed.returncode == 0 else "Probe command failed.",
            }
        except Exception as exc:
            return {"available": False, "command": command, "devices": [], "adapters": [], "message": str(exc)}

    def _json_objects(self, text: str) -> List[Dict[str, Any]]:
        value = self._json_value(text)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
        return []

    def _json_value(self, text: str) -> Any:
        try:
            return json.loads(text)
        except Exception:
            return None

    def _score(self, checks: List[HardwareValidationCheck]) -> int:
        scored = [check for check in checks if check.status != "unknown"]
        if not scored:
            return 0
        weights = {"pass": 100, "warn": 60, "fail": 0}
        return round(sum(weights.get(check.status, 0) for check in scored) / len(scored))

    def _overall_status(self, checks: List[HardwareValidationCheck], score: int) -> str:
        if any(check.status == "fail" for check in checks):
            return "fail"
        if any(check.status in {"warn", "unknown"} for check in checks) or score < 85:
            return "warn"
        return "pass"

    def _target_config_id(self, device: Dict[str, Any]) -> str:
        raw = "|".join([
            str(device.get("platform", "")),
            str(device.get("machine", "")),
            str(device.get("cpu_cores", "")),
            str(device.get("memory_total_gb", "")),
            str(device.get("disk_total_gb", "")),
        ])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _snapshot_summary(self, snapshots: Dict[str, Any]) -> Dict[str, Any]:
        device = snapshots["device"]
        return {
            "platform": device.get("platform"),
            "machine": device.get("machine"),
            "cpu_cores": device.get("cpu_cores"),
            "memory_total_gb": device.get("memory_total_gb"),
            "disk_free_gb": device.get("disk_free_gb"),
            "network_interfaces": device.get("network_interfaces"),
            "camera_available": device.get("camera_available"),
            "microphone_available": device.get("microphone_available"),
            "battery_percent": device.get("battery_percent"),
        }

    def _report_payload(self, report: HardwareValidationReport) -> Dict[str, Any]:
        payload = asdict(report)
        payload["checks"] = [asdict(check) for check in report.checks]
        return payload

    def _save_report(self, payload: Dict[str, Any]) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        path = self.report_dir / f"{payload['id']}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
