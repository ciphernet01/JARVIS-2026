"""Tests for Phase 4 hardware stress/thermal capture."""

from modules.services.hardware_stress_manager import HardwareStressManager, HardwareStressSample


def sample(cpu, memory, temp, disk_read=100, disk_write=200, net_sent=300, net_recv=400):
    return HardwareStressSample(
        timestamp="2026-05-13T00:00:00+00:00",
        cpu_percent=cpu,
        memory_percent=memory,
        disk_read_bytes=disk_read,
        disk_write_bytes=disk_write,
        net_sent_bytes=net_sent,
        net_recv_bytes=net_recv,
        max_temperature_c=temp,
        battery_percent=80,
        ac_powered=True,
    )


def make_manager(tmp_path, samples):
    queue = list(samples)
    now = {"value": 0.0}

    def sampler():
        if len(queue) > 1:
            return queue.pop(0)
        return queue[0]

    def sleeper(seconds):
        now["value"] += seconds

    return HardwareStressManager(
        workspace_root=str(tmp_path),
        sampler=sampler,
        sleeper=sleeper,
        clock=lambda: now["value"],
    )


def test_stress_capture_report_structure(tmp_path):
    manager = make_manager(tmp_path, [
        sample(20, 40, 50, disk_read=100, disk_write=200, net_sent=300, net_recv=400),
        sample(30, 45, 55, disk_read=150, disk_write=260, net_sent=330, net_recv=460),
    ])

    report = manager.run_capture(label="short-run", duration_seconds=1, interval_seconds=1, save=False)

    assert report["label"] == "short-run"
    assert report["sample_count"] >= 2
    assert report["overall_status"] == "pass"
    assert report["summary"]["cpu_max_percent"] == 30.0
    assert report["summary"]["disk_read_delta_bytes"] == 50
    assert report["summary"]["net_recv_delta_bytes"] == 60


def test_stress_capture_warns_when_thermal_unavailable(tmp_path):
    manager = make_manager(tmp_path, [
        sample(20, 40, None),
        sample(25, 42, None),
    ])

    report = manager.run_capture(duration_seconds=1, interval_seconds=1, save=False)

    assert report["overall_status"] == "warn"
    assert report["summary"]["temperature_available"] is False


def test_stress_capture_fails_on_high_temperature(tmp_path):
    manager = make_manager(tmp_path, [
        sample(40, 50, 72),
        sample(50, 55, 93),
    ])

    report = manager.run_capture(duration_seconds=1, interval_seconds=1, save=False)

    assert report["overall_status"] == "fail"
    assert report["summary"]["max_temperature_c"] == 93.0


def test_stress_capture_saves_and_lists_reports(tmp_path):
    manager = make_manager(tmp_path, [
        sample(20, 40, 50),
        sample(25, 42, 52),
    ])

    report = manager.run_capture(label="saved-stress", duration_seconds=1, interval_seconds=1, save=True)
    reports = manager.list_reports()

    assert (tmp_path / "test_reports" / "hardware_stress" / f"{report['id']}.json").exists()
    assert reports[0]["id"] == report["id"]
    assert reports[0]["overall_status"] == "pass"
