import importlib.util
import sys
from pathlib import Path

import pytest

# Load module directly from file to avoid importing the full services package
spec_path = Path(__file__).resolve().parents[1] / "modules" / "services" / "simulated_device_manager.py"
spec = importlib.util.spec_from_file_location("simulated_device_manager", str(spec_path))
sim_mod = importlib.util.module_from_spec(spec)
sys.modules["simulated_device_manager"] = sim_mod
spec.loader.exec_module(sim_mod)
SimulatedDeviceManager = sim_mod.SimulatedDeviceManager


def test_list_and_get_device():
    mgr = SimulatedDeviceManager()
    devices = mgr.list_devices()
    assert isinstance(devices, list)
    assert len(devices) >= 1

    dev = devices[0]
    got = mgr.get_device(dev["id"]) or {}
    assert got.get("id") == dev["id"]


def test_add_remove_and_power_cycle():
    mgr = SimulatedDeviceManager()
    resp = mgr.add_device("test-device-1", "sensor", {"unit": "lux"})
    assert resp.get("success") is True
    dev = resp.get("device")
    assert dev["id"] == "test-device-1"

    status = mgr.get_device_status("test-device-1")
    assert status.get("success") is True

    pc = mgr.power_cycle_device("test-device-1", offline_seconds=0)
    assert pc.get("success") is True

    rem = mgr.remove_device("test-device-1")
    assert rem.get("success") is True
    assert mgr.get_device("test-device-1") is None
