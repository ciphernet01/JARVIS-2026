"""Release-candidate evidence bundle for Phase 6 to Phase 7 handoff."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .failover_drill_manager import FailoverDrillManager
from .hardware_stress_manager import HardwareStressManager
from .hardware_validation_manager import HardwareValidationManager
from .performance_baseline_manager import PerformanceBaselineManager
from .security_audit_manager import SecurityAuditManager


@dataclass(frozen=True)
class ReleaseEvidenceItem:
    key: str
    label: str
    status: str
    required: bool
    detail: str
    report_id: Optional[str] = None
    report_path: Optional[str] = None
    recommendation: Optional[str] = None


@dataclass(frozen=True)
class ReleaseEvidenceBundle:
    id: str
    label: str
    created_at: str
    release_status: str
    score: float
    summary: Dict[str, int]
    items: List[ReleaseEvidenceItem]
    notes: str = ""


class ReleaseEvidenceManager:
    """Collect latest validation artifacts into one release-candidate bundle."""

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        *,
        security_manager: Optional[SecurityAuditManager] = None,
        performance_manager: Optional[PerformanceBaselineManager] = None,
        failover_manager: Optional[FailoverDrillManager] = None,
        hardware_validation_manager: Optional[HardwareValidationManager] = None,
        hardware_stress_manager: Optional[HardwareStressManager] = None,
    ):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.report_dir = self.workspace_root / "test_reports" / "release_evidence"
        self.security_manager = security_manager or SecurityAuditManager(workspace_root=str(self.workspace_root))
        self.performance_manager = performance_manager or PerformanceBaselineManager(workspace_root=str(self.workspace_root))
        self.failover_manager = failover_manager or FailoverDrillManager(workspace_root=str(self.workspace_root))
        self.hardware_validation_manager = hardware_validation_manager or HardwareValidationManager(workspace_root=str(self.workspace_root))
        self.hardware_stress_manager = hardware_stress_manager or HardwareStressManager(workspace_root=str(self.workspace_root))

    def create_bundle(self, label: Optional[str] = None, notes: str = "", *, save: bool = True) -> Dict[str, Any]:
        items = [
            self._from_latest(
                "security_audit",
                "Security Audit",
                self.security_manager.list_reports(limit=1),
                required=True,
                missing_recommendation="Run a security hardening audit before release.",
            ),
            self._from_latest(
                "performance_baseline",
                "Performance Baseline",
                self.performance_manager.list_reports(limit=1),
                required=True,
                missing_recommendation="Capture a production performance baseline before release.",
            ),
            self._from_latest(
                "failover_drill",
                "Failover Drill",
                self.failover_manager.list_reports(limit=1),
                required=True,
                missing_recommendation="Run a failover drill before release.",
            ),
            self._from_latest(
                "hardware_validation",
                "Hardware Validation",
                self.hardware_validation_manager.list_reports(limit=1),
                required=False,
                missing_recommendation="Capture hardware validation on target devices.",
            ),
            self._from_latest(
                "hardware_stress",
                "Hardware Stress",
                self.hardware_stress_manager.list_reports(limit=1),
                required=False,
                missing_recommendation="Capture stress and thermal evidence on target devices.",
            ),
        ]
        summary = {
            "pass": sum(1 for item in items if item.status == "pass"),
            "warn": sum(1 for item in items if item.status == "warn"),
            "fail": sum(1 for item in items if item.status == "fail"),
            "missing": sum(1 for item in items if item.status == "missing"),
            "required_missing": sum(1 for item in items if item.required and item.status == "missing"),
            "required_failed": sum(1 for item in items if item.required and item.status == "fail"),
        }
        release_status = self._release_status(items)
        bundle = ReleaseEvidenceBundle(
            id=f"release-evidence-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            label=(label or "release-candidate-evidence").strip()[:80] or "release-candidate-evidence",
            created_at=datetime.now(timezone.utc).isoformat(),
            release_status=release_status,
            score=self._score(items),
            summary=summary,
            items=items,
            notes=notes.strip()[:500],
        )
        payload = self._bundle_payload(bundle)
        if save:
            self._save_bundle(payload)
        return payload

    def list_bundles(self, limit: int = 10) -> List[Dict[str, Any]]:
        bundles = []
        if not self.report_dir.exists():
            return bundles
        for path in sorted(self.report_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                bundles.append({
                    "id": data.get("id", path.stem),
                    "label": data.get("label", path.stem),
                    "created_at": data.get("created_at"),
                    "release_status": data.get("release_status", "unknown"),
                    "score": data.get("score", 0),
                    "summary": data.get("summary", {}),
                    "path": str(path.relative_to(self.workspace_root)),
                })
            except Exception:
                continue
            if len(bundles) >= max(1, limit):
                break
        return bundles

    def _from_latest(
        self,
        key: str,
        label: str,
        reports: List[Dict[str, Any]],
        *,
        required: bool,
        missing_recommendation: str,
    ) -> ReleaseEvidenceItem:
        if not reports:
            return ReleaseEvidenceItem(
                key=key,
                label=label,
                status="missing",
                required=required,
                detail="No saved evidence found.",
                recommendation=missing_recommendation,
            )
        report = reports[0]
        raw_status = report.get("overall_status") or report.get("release_status") or "unknown"
        status = raw_status if raw_status in {"pass", "warn", "fail"} else "warn"
        score = report.get("score")
        detail = f"Latest report {raw_status}"
        if score is not None:
            detail += f" / score {score}"
        return ReleaseEvidenceItem(
            key=key,
            label=label,
            status=status,
            required=required,
            detail=detail,
            report_id=report.get("id"),
            report_path=report.get("path"),
            recommendation=None if status == "pass" else f"Review latest {label.lower()} findings.",
        )

    def _release_status(self, items: List[ReleaseEvidenceItem]) -> str:
        required = [item for item in items if item.required]
        if any(item.status in {"fail", "missing"} for item in required):
            return "blocked"
        if any(item.status in {"warn", "missing"} for item in items):
            return "ready_with_warnings"
        return "ready"

    def _score(self, items: List[ReleaseEvidenceItem]) -> float:
        weights = {"pass": 1.0, "warn": 0.5, "missing": 0.0, "fail": 0.0}
        if not items:
            return 0.0
        total = 0.0
        possible = 0.0
        for item in items:
            multiplier = 2.0 if item.required else 1.0
            total += weights.get(item.status, 0.0) * multiplier
            possible += multiplier
        return round(total / possible, 2)

    def _bundle_payload(self, bundle: ReleaseEvidenceBundle) -> Dict[str, Any]:
        return {
            **asdict(bundle),
            "items": [asdict(item) for item in bundle.items],
        }

    def _save_bundle(self, payload: Dict[str, Any]) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        path = self.report_dir / f"{payload['id']}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
