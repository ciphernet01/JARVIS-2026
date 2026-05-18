"""Tests for Phase 6 performance baseline and memory drift checks."""

from modules.services.performance_baseline_manager import PerformanceBaselineManager, PerformanceSample


def sample(rss, cpu=10, memory=40, threads=8, handles=None, latency=50, success=True):
    return PerformanceSample(
        timestamp="2026-05-17T00:00:00+00:00",
        elapsed_ms=0,
        process_rss_mb=rss,
        system_memory_percent=memory,
        process_cpu_percent=cpu,
        thread_count=threads,
        handle_count=handles,
        operation_latency_ms=latency,
        operation_success=success,
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

    return PerformanceBaselineManager(
        workspace_root=str(tmp_path),
        sampler=sampler,
        sleeper=sleeper,
        clock=lambda: now["value"],
    )


def test_performance_baseline_report_structure(tmp_path):
    manager = make_manager(tmp_path, [
        sample(100, cpu=5, threads=4, latency=25),
        sample(104, cpu=8, threads=4, latency=30),
    ])

    report = manager.run_baseline(label="short-baseline", duration_seconds=1, interval_seconds=1, save=False)

    assert report["id"].startswith("performance-baseline-")
    assert report["label"] == "short-baseline"
    assert report["sample_count"] >= 2
    assert report["overall_status"] == "pass"
    assert report["summary"]["rss_growth_mb"] == 4
    assert report["summary"]["operation_success_rate"] == 1.0


def test_performance_baseline_warns_on_memory_growth(tmp_path):
    manager = make_manager(tmp_path, [
        sample(100, cpu=20, threads=5),
        sample(170, cpu=25, threads=5),
    ])

    report = manager.run_baseline(duration_seconds=1, interval_seconds=1, save=False)

    assert report["overall_status"] == "warn"
    assert report["summary"]["rss_growth_mb"] == 70


def test_performance_baseline_fails_on_operation_failure(tmp_path):
    manager = make_manager(tmp_path, [
        sample(100, success=True),
        sample(101, success=False),
    ])

    report = manager.run_baseline(duration_seconds=1, interval_seconds=1, save=False)

    assert report["overall_status"] == "fail"
    assert report["summary"]["operation_success_rate"] == 0.5


def test_performance_baseline_saves_and_lists_reports(tmp_path):
    manager = make_manager(tmp_path, [
        sample(100),
        sample(102),
    ])

    report = manager.run_baseline(label="saved-baseline", duration_seconds=1, interval_seconds=1, save=True)
    reports = manager.list_reports()

    assert (tmp_path / "test_reports" / "performance_baselines" / f"{report['id']}.json").exists()
    assert reports[0]["id"] == report["id"]
    assert reports[0]["overall_status"] == "pass"
