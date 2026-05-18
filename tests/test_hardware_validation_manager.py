"""Tests for Phase 4 hardware validation reports."""

from types import SimpleNamespace

from modules.services.hardware_validation_manager import HardwareValidationManager
from modules.services.network_manager import ConnectionType


class FakeDeviceManager:
    def snapshot(self):
        return {
            "platform": "TestOS 1.0",
            "kernel": "test-kernel",
            "machine": "x86_64",
            "cpu_cores": 8,
            "cpu_freq_mhz": 3200,
            "memory_total_gb": 16,
            "memory_available_gb": 8,
            "disk_total_gb": 256,
            "disk_free_gb": 120,
            "battery_percent": 80,
            "power_plugged": True,
            "display_width": 1920,
            "display_height": 1080,
            "camera_available": True,
            "microphone_available": True,
            "tts_available": True,
            "sensor_support": True,
            "network_interfaces": 2,
            "timestamp": "2026-05-13T00:00:00+00:00",
        }


class FakeAudioManager:
    def snapshot(self):
        return SimpleNamespace(
            devices=[
                SimpleNamespace(is_input=True, is_output=False),
                SimpleNamespace(is_input=False, is_output=True),
            ],
            volume=50.0,
            microphone_enabled=True,
            speakers_enabled=True,
        )


class FakeCameraManager:
    def state(self):
        return SimpleNamespace(available=True)

    def list_devices(self):
        return [{"id": 0, "name": "Integrated Camera", "available": True}]


class FakeNetworkManager:
    def snapshot(self):
        return SimpleNamespace(
            connected_interfaces=[
                SimpleNamespace(name="Wi-Fi", connection_type=ConnectionType.WIFI, is_connected=True),
            ],
            wifi_enabled=True,
        )


class FakePowerManager:
    def state(self):
        return SimpleNamespace(
            battery_percent=80,
            ac_powered=True,
            low_battery=False,
            critical_battery=False,
        )


def make_manager(tmp_path):
    return HardwareValidationManager(
        workspace_root=str(tmp_path),
        device_manager=FakeDeviceManager(),
        audio_manager=FakeAudioManager(),
        camera_manager=FakeCameraManager(),
        network_manager=FakeNetworkManager(),
        power_manager=FakePowerManager(),
        gpu_probe={"available": True, "devices": [{"name": "Test GPU", "driver": "1.0"}]},
        bluetooth_probe={"available": True, "adapters": [{"name": "Test Bluetooth", "status": "OK"}]},
        audio_latency_probe={"available": True, "estimated_roundtrip_ms": 45.0},
        audio_workload_probe={
            "available": True,
            "has_default_input": True,
            "has_default_output": True,
            "default_sample_rate": 44100.0,
        },
        camera_workload_probe={
            "available": True,
            "captured": True,
            "width": 1280,
            "height": 720,
        },
    )


def test_hardware_validation_report_structure(tmp_path):
    manager = make_manager(tmp_path)

    report = manager.run_validation(label="lab-machine", save=False)

    assert report["label"] == "lab-machine"
    assert report["target_config_id"]
    assert report["score"] == 100
    assert report["overall_status"] == "pass"
    assert any(check["category"] == "gpu" and check["status"] == "pass" for check in report["checks"])
    assert any(check["name"] == "Audio latency probe" and check["status"] == "pass" for check in report["checks"])
    assert any(check["name"] == "Audio workload readiness" and check["status"] == "pass" for check in report["checks"])
    assert any(check["name"] == "Camera snapshot workload" and check["status"] == "pass" for check in report["checks"])
    assert any(check["category"] == "audio" and check["status"] == "pass" for check in report["checks"])


def test_hardware_validation_saves_and_lists_reports(tmp_path):
    manager = make_manager(tmp_path)

    report = manager.run_validation(label="saved-target", save=True)
    reports = manager.list_reports()
    matrix = manager.compatibility_matrix()

    assert (tmp_path / "test_reports" / "hardware_validation" / f"{report['id']}.json").exists()
    assert reports[0]["id"] == report["id"]
    assert matrix["target_count"] == 1
    assert matrix["targets"][0]["latest_report_id"] == report["id"]


def test_low_resource_machine_fails_core_checks(tmp_path):
    class LowDeviceManager(FakeDeviceManager):
        def snapshot(self):
            data = super().snapshot()
            data["cpu_cores"] = 1
            data["memory_total_gb"] = 1
            data["disk_free_gb"] = 1
            return data

    manager = HardwareValidationManager(
        workspace_root=str(tmp_path),
        device_manager=LowDeviceManager(),
        audio_manager=FakeAudioManager(),
        camera_manager=FakeCameraManager(),
        network_manager=FakeNetworkManager(),
        power_manager=FakePowerManager(),
        gpu_probe={"available": True, "devices": [{"name": "Test GPU"}]},
        bluetooth_probe={"available": True, "adapters": [{"name": "Test Bluetooth"}]},
        audio_latency_probe={"available": True, "estimated_roundtrip_ms": 45.0},
        audio_workload_probe={
            "available": True,
            "has_default_input": True,
            "has_default_output": True,
            "default_sample_rate": 44100.0,
        },
        camera_workload_probe={"available": True, "captured": True, "width": 1280, "height": 720},
    )

    report = manager.run_validation(save=False)

    assert report["overall_status"] == "fail"
    assert any(check["status"] == "fail" for check in report["checks"])


def test_missing_probe_tools_are_unknown(tmp_path):
    manager = HardwareValidationManager(
        workspace_root=str(tmp_path),
        device_manager=FakeDeviceManager(),
        audio_manager=FakeAudioManager(),
        camera_manager=FakeCameraManager(),
        network_manager=FakeNetworkManager(),
        power_manager=FakePowerManager(),
        gpu_probe={"available": False, "devices": [], "message": "No probe tool."},
        bluetooth_probe={"available": False, "adapters": [], "message": "No probe tool."},
        audio_latency_probe={"available": False, "message": "No latency probe.", "estimated_roundtrip_ms": None},
        audio_workload_probe={"available": False, "message": "No audio workload probe."},
        camera_workload_probe={"available": False, "captured": False, "message": "No camera workload probe."},
    )

    report = manager.run_validation(save=False)

    assert report["overall_status"] == "warn"
    assert any(check["category"] == "gpu" and check["status"] == "unknown" for check in report["checks"])
    assert any(check["category"] == "bluetooth" and check["status"] == "unknown" for check in report["checks"])
    assert any(check["name"] == "Audio latency probe" and check["status"] == "unknown" for check in report["checks"])
    assert any(check["name"] == "Audio workload readiness" and check["status"] == "unknown" for check in report["checks"])
    assert any(check["name"] == "Camera snapshot workload" and check["status"] == "unknown" for check in report["checks"])


def test_high_audio_latency_fails(tmp_path):
    manager = HardwareValidationManager(
        workspace_root=str(tmp_path),
        device_manager=FakeDeviceManager(),
        audio_manager=FakeAudioManager(),
        camera_manager=FakeCameraManager(),
        network_manager=FakeNetworkManager(),
        power_manager=FakePowerManager(),
        gpu_probe={"available": True, "devices": [{"name": "Test GPU"}]},
        bluetooth_probe={"available": True, "adapters": [{"name": "Test Bluetooth"}]},
        audio_latency_probe={"available": True, "estimated_roundtrip_ms": 320.0},
        audio_workload_probe={
            "available": True,
            "has_default_input": True,
            "has_default_output": True,
            "default_sample_rate": 44100.0,
        },
        camera_workload_probe={"available": True, "captured": True, "width": 1280, "height": 720},
    )

    report = manager.run_validation(save=False)

    assert report["overall_status"] == "fail"
    assert any(check["name"] == "Audio latency probe" and check["status"] == "fail" for check in report["checks"])


def test_camera_workload_failure_fails_report(tmp_path):
    manager = HardwareValidationManager(
        workspace_root=str(tmp_path),
        device_manager=FakeDeviceManager(),
        audio_manager=FakeAudioManager(),
        camera_manager=FakeCameraManager(),
        network_manager=FakeNetworkManager(),
        power_manager=FakePowerManager(),
        gpu_probe={"available": True, "devices": [{"name": "Test GPU"}]},
        bluetooth_probe={"available": True, "adapters": [{"name": "Test Bluetooth"}]},
        audio_latency_probe={"available": True, "estimated_roundtrip_ms": 45.0},
        audio_workload_probe={
            "available": True,
            "has_default_input": True,
            "has_default_output": True,
            "default_sample_rate": 44100.0,
        },
        camera_workload_probe={"available": True, "captured": False, "message": "No frame."},
    )

    report = manager.run_validation(save=False)

    assert report["overall_status"] == "fail"
    assert any(check["name"] == "Camera snapshot workload" and check["status"] == "fail" for check in report["checks"])


def test_audio_workload_partial_readiness_warns(tmp_path):
    manager = HardwareValidationManager(
        workspace_root=str(tmp_path),
        device_manager=FakeDeviceManager(),
        audio_manager=FakeAudioManager(),
        camera_manager=FakeCameraManager(),
        network_manager=FakeNetworkManager(),
        power_manager=FakePowerManager(),
        gpu_probe={"available": True, "devices": [{"name": "Test GPU"}]},
        bluetooth_probe={"available": True, "adapters": [{"name": "Test Bluetooth"}]},
        audio_latency_probe={"available": True, "estimated_roundtrip_ms": 45.0},
        audio_workload_probe={
            "available": True,
            "has_default_input": True,
            "has_default_output": False,
            "default_sample_rate": 44100.0,
        },
        camera_workload_probe={"available": True, "captured": True, "width": 1280, "height": 720},
    )

    report = manager.run_validation(save=False)

    assert report["overall_status"] == "warn"
    assert any(check["name"] == "Audio workload readiness" and check["status"] == "warn" for check in report["checks"])
