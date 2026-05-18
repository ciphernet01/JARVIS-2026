"""Phase 6 failover scenario drills for release hardening."""

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .manager import ServiceManager
from .safety_manager import SafetyManager


@dataclass(frozen=True)
class FailoverDrillCheck:
    key: str
    label: str
    status: str
    detail: str
    recommendation: Optional[str] = None
    severity: str = "medium"


@dataclass(frozen=True)
class FailoverDrillReport:
    id: str
    label: str
    created_at: str
    overall_status: str
    score: float
    summary: Dict[str, int]
    checks: List[FailoverDrillCheck]
    duration_ms: int
    notes: str = ""


class FailoverDrillManager:
    """Run non-mutating failover drills against local safety controls."""

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        *,
        safety_manager: Optional[SafetyManager] = None,
        service_manager: Optional[ServiceManager] = None,
    ):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.report_dir = self.workspace_root / "test_reports" / "failover_drills"
        self.safety_manager = safety_manager or SafetyManager(workspace_root=str(self.workspace_root))
        self.service_manager = service_manager or ServiceManager()

    def run_drill(self, label: Optional[str] = None, notes: str = "", *, save: bool = True) -> Dict[str, Any]:
        started = time.perf_counter()
        checks = [
            self._check_recovery_checkpoint(),
            self._check_fallback_controls(),
            self._check_destructive_command_gate(),
            self._check_mutating_confirmation_gate(),
            self._check_maintenance_shell(),
            self._check_service_inventory(),
        ]
        summary = {
            "pass": sum(1 for check in checks if check.status == "pass"),
            "warn": sum(1 for check in checks if check.status == "warn"),
            "fail": sum(1 for check in checks if check.status == "fail"),
        }
        overall = "fail" if summary["fail"] else "warn" if summary["warn"] else "pass"
        report = FailoverDrillReport(
            id=f"failover-drill-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            label=(label or "failover-drill").strip()[:80] or "failover-drill",
            created_at=datetime.now(timezone.utc).isoformat(),
            overall_status=overall,
            score=self._score(checks),
            summary=summary,
            checks=checks,
            duration_ms=int((time.perf_counter() - started) * 1000),
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
                    "overall_status": data.get("overall_status", "unknown"),
                    "score": data.get("score", 0),
                    "summary": data.get("summary", {}),
                    "path": str(path.relative_to(self.workspace_root)),
                })
            except Exception:
                continue
            if len(reports) >= max(1, limit):
                break
        return reports

    def _item(self, key: str, label: str, status: str, detail: str, recommendation: Optional[str] = None, severity: str = "medium") -> FailoverDrillCheck:
        return FailoverDrillCheck(key, label, status, detail, recommendation, severity)

    def _check_recovery_checkpoint(self) -> FailoverDrillCheck:
        state = self.safety_manager.state()
        if state.checkpoint_count <= 0:
            return self._item(
                "recovery_checkpoint",
                "Recovery Checkpoint",
                "warn",
                "No recovery checkpoint is available for rollback drills.",
                "Create a checkpoint before release validation.",
                "high",
            )
        return self._item("recovery_checkpoint", "Recovery Checkpoint", "pass", f"{state.checkpoint_count} checkpoint(s) available.", None, "high")

    def _check_fallback_controls(self) -> FailoverDrillCheck:
        state = self.safety_manager.state()
        missing = []
        if not state.maintenance_shell_available:
            missing.append("maintenance shell")
        if not state.fallback_desktop_available:
            missing.append("fallback desktop")
        if missing:
            return self._item("fallback_controls", "Fallback Controls", "fail", f"Unavailable control(s): {', '.join(missing)}.", "Enable fallback operator controls.", "critical")
        return self._item("fallback_controls", "Fallback Controls", "pass", "Maintenance shell and fallback desktop are available.", None, "critical")

    def _check_destructive_command_gate(self) -> FailoverDrillCheck:
        decision = self.safety_manager.evaluate_shell_command("Remove-Item -Path . -Recurse -Force")
        if not decision.allowed and decision.category == "destructive":
            return self._item("destructive_gate", "Destructive Command Gate", "pass", "Destructive command was blocked by safety gate.", None, "critical")
        return self._item("destructive_gate", "Destructive Command Gate", "fail", "Destructive command was not blocked.", "Tighten command safety gate patterns.", "critical")

    def _check_mutating_confirmation_gate(self) -> FailoverDrillCheck:
        decision = self.safety_manager.evaluate_shell_command("npm install left-pad", confirmed=False)
        if not decision.allowed and decision.requires_confirmation:
            return self._item("mutation_confirmation", "Mutation Confirmation", "pass", "Mutating command requires explicit confirmation.", None, "high")
        return self._item("mutation_confirmation", "Mutation Confirmation", "fail", "Mutating command did not require confirmation.", "Restore confirmation gates for mutating commands.", "high")

    def _check_maintenance_shell(self) -> FailoverDrillCheck:
        allowlist = self.safety_manager.maintenance_allowlist()
        if not allowlist:
            return self._item("maintenance_shell", "Maintenance Shell", "fail", "No maintenance diagnostics are allowlisted.", "Add read-only diagnostics to the maintenance allowlist.", "high")
        expected = {"pwd", "list-root"}
        missing = sorted(expected - set(allowlist))
        if missing:
            return self._item("maintenance_shell", "Maintenance Shell", "warn", f"Core diagnostic(s) missing: {', '.join(missing)}.", "Keep basic offline diagnostics allowlisted.", "medium")
        return self._item("maintenance_shell", "Maintenance Shell", "pass", f"{len(allowlist)} maintenance diagnostic(s) allowlisted.", None, "medium")

    def _check_service_inventory(self) -> FailoverDrillCheck:
        try:
            snapshot = self.service_manager.get_status_snapshot()
        except Exception as exc:
            return self._item("service_inventory", "Service Inventory", "fail", f"Service inventory failed: {exc}", "Repair service lifecycle status reporting.", "high")
        return self._item(
            "service_inventory",
            "Service Inventory",
            "pass",
            f"{snapshot.get('tracked_services', 0)} tracked service(s), {snapshot.get('running_processes', 0)} process(es) visible.",
            None,
            "medium",
        )

    def _score(self, checks: List[FailoverDrillCheck]) -> float:
        weights = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
        if not checks:
            return 0.0
        return round(sum(weights.get(check.status, 0.0) for check in checks) / len(checks), 2)

    def _report_payload(self, report: FailoverDrillReport) -> Dict[str, Any]:
        return {
            **asdict(report),
            "checks": [asdict(check) for check in report.checks],
        }

    def _save_report(self, payload: Dict[str, Any]) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        path = self.report_dir / f"{payload['id']}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
