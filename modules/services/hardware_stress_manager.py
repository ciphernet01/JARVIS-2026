"""
Hardware stress and thermal capture for Phase 4.

This module records repeatable system samples during a short validation window.
It does not create heavy load by default; operators can run it alongside a
known workload to capture thermal and performance behavior safely.
"""

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import psutil


@dataclass(frozen=True)
class HardwareStressSample:
    """A point-in-time stress/thermal sample."""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    disk_read_bytes: int
    disk_write_bytes: int
    net_sent_bytes: int
    net_recv_bytes: int
    max_temperature_c: Optional[float]
    battery_percent: Optional[float]
    ac_powered: Optional[bool]


@dataclass(frozen=True)
class HardwareStressReport:
    """A summarized stress/thermal capture report."""
    id: str
    label: str
    created_at: str
    duration_seconds: float
    interval_seconds: float
    sample_count: int
    overall_status: str
    summary: Dict[str, Any]
    samples: List[HardwareStressSample]
    notes: str = ""


class HardwareStressManager:
    """Collect and persist hardware stress/thermal samples."""

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        *,
        sampler: Optional[Callable[[], HardwareStressSample]] = None,
        sleeper: Optional[Callable[[float], None]] = None,
        clock: Optional[Callable[[], float]] = None,
    ):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.report_dir = self.workspace_root / "test_reports" / "hardware_stress"
        self._sampler = sampler or self._sample_system
        self._sleep = sleeper or time.sleep
        self._clock = clock or time.monotonic

    def run_capture(
        self,
        label: Optional[str] = None,
        notes: str = "",
        *,
        duration_seconds: float = 30.0,
        interval_seconds: float = 2.0,
        save: bool = True,
    ) -> Dict[str, Any]:
        """Capture hardware samples and optionally persist the report."""
        safe_duration = max(1.0, min(float(duration_seconds), 300.0))
        safe_interval = max(0.5, min(float(interval_seconds), 30.0))
        start = self._clock()
        created_at = datetime.now(timezone.utc).isoformat()
        samples: List[HardwareStressSample] = []

        while True:
            samples.append(self._sampler())
            elapsed = self._clock() - start
            if elapsed >= safe_duration:
                break
            self._sleep(min(safe_interval, max(0.0, safe_duration - elapsed)))

        actual_duration = max(0.0, self._clock() - start)
        summary = self._summarize(samples)
        overall_status = self._overall_status(summary)
        report_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{len(samples):03d}"
        report = HardwareStressReport(
            id=report_id,
            label=(label or "hardware-stress-capture").strip()[:80] or "hardware-stress-capture",
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
        """Return saved stress report summaries."""
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

    def _sample_system(self) -> HardwareStressSample:
        disk = psutil.disk_io_counters()
        net = psutil.net_io_counters()
        memory = psutil.virtual_memory()
        battery = psutil.sensors_battery()
        return HardwareStressSample(
            timestamp=datetime.now(timezone.utc).isoformat(),
            cpu_percent=float(psutil.cpu_percent(interval=None)),
            memory_percent=float(memory.percent),
            disk_read_bytes=int(getattr(disk, "read_bytes", 0) or 0),
            disk_write_bytes=int(getattr(disk, "write_bytes", 0) or 0),
            net_sent_bytes=int(getattr(net, "bytes_sent", 0) or 0),
            net_recv_bytes=int(getattr(net, "bytes_recv", 0) or 0),
            max_temperature_c=self._max_temperature(),
            battery_percent=battery.percent if battery else None,
            ac_powered=battery.power_plugged if battery else None,
        )

    def _max_temperature(self) -> Optional[float]:
        try:
            temps = psutil.sensors_temperatures(fahrenheit=False)
        except Exception:
            return None
        values = []
        for entries in (temps or {}).values():
            for item in entries:
                current = getattr(item, "current", None)
                if current is not None:
                    values.append(float(current))
        return round(max(values), 1) if values else None

    def _summarize(self, samples: List[HardwareStressSample]) -> Dict[str, Any]:
        def values(name: str) -> List[float]:
            return [float(getattr(sample, name)) for sample in samples if getattr(sample, name) is not None]

        cpu = values("cpu_percent")
        mem = values("memory_percent")
        temp = values("max_temperature_c")
        first = samples[0]
        last = samples[-1]
        return {
            "cpu_avg_percent": round(sum(cpu) / len(cpu), 1) if cpu else 0.0,
            "cpu_max_percent": round(max(cpu), 1) if cpu else 0.0,
            "memory_avg_percent": round(sum(mem) / len(mem), 1) if mem else 0.0,
            "memory_max_percent": round(max(mem), 1) if mem else 0.0,
            "max_temperature_c": round(max(temp), 1) if temp else None,
            "temperature_available": bool(temp),
            "disk_read_delta_bytes": max(0, last.disk_read_bytes - first.disk_read_bytes),
            "disk_write_delta_bytes": max(0, last.disk_write_bytes - first.disk_write_bytes),
            "net_sent_delta_bytes": max(0, last.net_sent_bytes - first.net_sent_bytes),
            "net_recv_delta_bytes": max(0, last.net_recv_bytes - first.net_recv_bytes),
            "battery_start_percent": first.battery_percent,
            "battery_end_percent": last.battery_percent,
            "ac_powered": last.ac_powered,
        }

    def _overall_status(self, summary: Dict[str, Any]) -> str:
        temp = summary.get("max_temperature_c")
        if summary.get("cpu_max_percent", 0) >= 98 or summary.get("memory_max_percent", 0) >= 95:
            return "fail"
        if temp is not None and temp >= 90:
            return "fail"
        if summary.get("cpu_max_percent", 0) >= 90 or summary.get("memory_max_percent", 0) >= 85:
            return "warn"
        if temp is not None and temp >= 80:
            return "warn"
        if not summary.get("temperature_available"):
            return "warn"
        return "pass"

    def _report_payload(self, report: HardwareStressReport) -> Dict[str, Any]:
        payload = asdict(report)
        payload["samples"] = [asdict(sample) for sample in report.samples]
        return payload

    def _save_report(self, payload: Dict[str, Any]) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        path = self.report_dir / f"{payload['id']}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
