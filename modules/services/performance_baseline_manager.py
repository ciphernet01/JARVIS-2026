"""Phase 6 performance baseline and memory drift checks."""

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import psutil


@dataclass(frozen=True)
class PerformanceSample:
    timestamp: str
    elapsed_ms: int
    process_rss_mb: float
    system_memory_percent: float
    process_cpu_percent: float
    thread_count: int
    handle_count: Optional[int] = None
    operation_latency_ms: Optional[float] = None
    operation_success: Optional[bool] = None


@dataclass(frozen=True)
class PerformanceBaselineReport:
    id: str
    label: str
    created_at: str
    duration_seconds: float
    interval_seconds: float
    sample_count: int
    overall_status: str
    summary: Dict[str, Any]
    samples: List[PerformanceSample]
    notes: str = ""


class PerformanceBaselineManager:
    """Capture a lightweight production baseline for release validation."""

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        *,
        sampler: Optional[Callable[[], PerformanceSample]] = None,
        operation: Optional[Callable[[], bool]] = None,
        sleeper: Optional[Callable[[float], None]] = None,
        clock: Optional[Callable[[], float]] = None,
    ):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.report_dir = self.workspace_root / "test_reports" / "performance_baselines"
        self._process = psutil.Process()
        self._sampler = sampler
        self._operation = operation
        self._sleep = sleeper or time.sleep
        self._clock = clock or time.monotonic

    def run_baseline(
        self,
        label: Optional[str] = None,
        notes: str = "",
        *,
        duration_seconds: float = 30.0,
        interval_seconds: float = 2.0,
        save: bool = True,
    ) -> Dict[str, Any]:
        safe_duration = max(1.0, min(float(duration_seconds), 300.0))
        safe_interval = max(0.5, min(float(interval_seconds), 30.0))
        start = self._clock()
        created_at = datetime.now(timezone.utc).isoformat()
        samples: List[PerformanceSample] = []

        while True:
            samples.append(self._sample(start))
            elapsed = self._clock() - start
            if elapsed >= safe_duration:
                break
            self._sleep(min(safe_interval, max(0.0, safe_duration - elapsed)))

        actual_duration = max(0.0, self._clock() - start)
        summary = self._summarize(samples)
        overall_status = self._overall_status(summary)
        report = PerformanceBaselineReport(
            id=f"performance-baseline-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{len(samples):03d}",
            label=(label or "performance-baseline").strip()[:80] or "performance-baseline",
            created_at=created_at,
            duration_seconds=round(actual_duration, 2),
            interval_seconds=safe_interval,
            sample_count=len(samples),
            overall_status=overall_status,
            summary=summary,
            samples=samples,
            notes=notes.strip()[:500],
        )
        payload = self._report_payload(report)
        if save:
            self._save_report(payload)
        return payload

    def list_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
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
                    "duration_seconds": data.get("duration_seconds"),
                    "sample_count": data.get("sample_count"),
                    "overall_status": data.get("overall_status"),
                    "summary": data.get("summary", {}),
                    "path": str(path.relative_to(self.workspace_root)),
                })
            except Exception:
                continue
            if len(reports) >= max(1, limit):
                break
        return reports

    def _sample(self, start: float) -> PerformanceSample:
        if self._sampler:
            return self._sampler()

        operation_latency = None
        operation_success = None
        if self._operation:
            op_start = self._clock()
            try:
                operation_success = bool(self._operation())
            except Exception:
                operation_success = False
            operation_latency = round((self._clock() - op_start) * 1000, 2)

        memory = psutil.virtual_memory()
        info = self._process.memory_info()
        handle_count = None
        try:
            handle_count = self._process.num_handles()
        except Exception:
            handle_count = None

        return PerformanceSample(
            timestamp=datetime.now(timezone.utc).isoformat(),
            elapsed_ms=int((self._clock() - start) * 1000),
            process_rss_mb=round(info.rss / (1024 * 1024), 2),
            system_memory_percent=float(memory.percent),
            process_cpu_percent=float(self._process.cpu_percent(interval=None)),
            thread_count=int(self._process.num_threads()),
            handle_count=handle_count,
            operation_latency_ms=operation_latency,
            operation_success=operation_success,
        )

    def _summarize(self, samples: List[PerformanceSample]) -> Dict[str, Any]:
        def values(name: str) -> List[float]:
            return [float(getattr(sample, name)) for sample in samples if getattr(sample, name) is not None]

        rss = values("process_rss_mb")
        cpu = values("process_cpu_percent")
        latency = values("operation_latency_ms")
        first = samples[0]
        last = samples[-1]
        operation_results = [sample.operation_success for sample in samples if sample.operation_success is not None]
        successful_ops = sum(1 for result in operation_results if result)
        return {
            "rss_start_mb": first.process_rss_mb,
            "rss_end_mb": last.process_rss_mb,
            "rss_max_mb": round(max(rss), 2) if rss else 0.0,
            "rss_growth_mb": round(last.process_rss_mb - first.process_rss_mb, 2),
            "system_memory_max_percent": round(max(values("system_memory_percent")), 1),
            "cpu_avg_percent": round(sum(cpu) / len(cpu), 1) if cpu else 0.0,
            "cpu_max_percent": round(max(cpu), 1) if cpu else 0.0,
            "thread_start": first.thread_count,
            "thread_end": last.thread_count,
            "thread_growth": last.thread_count - first.thread_count,
            "handle_start": first.handle_count,
            "handle_end": last.handle_count,
            "handle_growth": (
                last.handle_count - first.handle_count
                if first.handle_count is not None and last.handle_count is not None
                else None
            ),
            "operation_count": len(operation_results),
            "operation_success_rate": round(successful_ops / len(operation_results), 2) if operation_results else None,
            "operation_latency_avg_ms": round(sum(latency) / len(latency), 2) if latency else None,
            "operation_latency_max_ms": round(max(latency), 2) if latency else None,
        }

    def _overall_status(self, summary: Dict[str, Any]) -> str:
        if summary.get("operation_success_rate") is not None and summary["operation_success_rate"] < 1.0:
            return "fail"
        if summary.get("rss_growth_mb", 0) >= 128 or summary.get("thread_growth", 0) >= 25:
            return "fail"
        if summary.get("cpu_max_percent", 0) >= 98 or summary.get("system_memory_max_percent", 0) >= 95:
            return "fail"
        if summary.get("rss_growth_mb", 0) >= 64 or summary.get("thread_growth", 0) >= 10:
            return "warn"
        if summary.get("operation_latency_max_ms") is not None and summary["operation_latency_max_ms"] >= 1000:
            return "warn"
        if summary.get("cpu_avg_percent", 0) >= 85 or summary.get("system_memory_max_percent", 0) >= 85:
            return "warn"
        return "pass"

    def _report_payload(self, report: PerformanceBaselineReport) -> Dict[str, Any]:
        payload = asdict(report)
        payload["samples"] = [asdict(sample) for sample in report.samples]
        return payload

    def _save_report(self, payload: Dict[str, Any]) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        path = self.report_dir / f"{payload['id']}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
