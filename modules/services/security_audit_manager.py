"""Production hardening audit checks for JARVIS OS."""

import json
import os
import stat
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SecurityAuditCheck:
    key: str
    label: str
    status: str
    detail: str
    recommendation: Optional[str] = None
    severity: str = "medium"


@dataclass(frozen=True)
class SecurityAuditReport:
    id: str
    generated_at: str
    overall_status: str
    score: float
    checks: List[SecurityAuditCheck]
    summary: Dict[str, int]
    duration_ms: int


class SecurityAuditManager:
    """Run lightweight local security checks without mutating system state."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.report_dir = self.workspace_root / "test_reports" / "security_audit"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run_audit(
        self,
        *,
        cors_origins: Optional[List[str]] = None,
        session_tokens: Optional[Dict[str, Any]] = None,
        safety_state: Optional[Any] = None,
        save: bool = True,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        checks = [
            self._check_env_file(),
            self._check_cors(cors_origins or []),
            self._check_session_tokens(session_tokens or {}),
            self._check_safety_state(safety_state),
            self._check_audit_logs(),
            self._check_dependency_lockfiles(),
            self._check_runtime_artifacts(),
            self._check_sensitive_file_permissions(),
        ]
        score = self._score(checks)
        summary = {
            "pass": sum(1 for check in checks if check.status == "pass"),
            "warn": sum(1 for check in checks if check.status == "warn"),
            "fail": sum(1 for check in checks if check.status == "fail"),
        }
        overall = "fail" if summary["fail"] else "warn" if summary["warn"] else "pass"
        report = SecurityAuditReport(
            id=f"security-audit-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            overall_status=overall,
            score=score,
            checks=checks,
            summary=summary,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        payload = self._report_payload(report)
        if save:
            self._save_report(payload)
        return payload

    def list_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        reports = []
        for path in sorted(self.report_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                reports.append({
                    "id": data.get("id", path.stem),
                    "generated_at": data.get("generated_at"),
                    "overall_status": data.get("overall_status", "unknown"),
                    "score": data.get("score", 0),
                    "summary": data.get("summary", {}),
                    "path": str(path),
                })
            except Exception:
                continue
            if len(reports) >= limit:
                break
        return reports

    def _item(self, key: str, label: str, status: str, detail: str, recommendation: Optional[str] = None, severity: str = "medium") -> SecurityAuditCheck:
        return SecurityAuditCheck(key, label, status, detail, recommendation, severity)

    def _check_env_file(self) -> SecurityAuditCheck:
        env_path = self.workspace_root / ".env"
        if not env_path.exists():
            return self._item("env_file", "Environment File", "warn", ".env not found; runtime may rely on host defaults.", "Create a production .env from documented secrets.", "low")
        text = env_path.read_text(encoding="utf-8", errors="ignore")
        weak_values = []
        empty_optional = []
        for line in text.splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if any(marker in key.upper() for marker in ["KEY", "TOKEN", "SECRET", "PASSWORD"]):
                clean = value.strip().strip('"').strip("'")
                if not clean:
                    empty_optional.append(key.strip())
                elif clean.lower() in {"changeme", "your_key_here", "password", "secret", "test"} or len(clean) < 12:
                    weak_values.append(key.strip())
        if weak_values:
            return self._item("env_file", "Environment File", "fail", f"Weak placeholder secret(s): {', '.join(weak_values[:4])}.", "Replace placeholders with high-entropy production secrets.", "high")
        if empty_optional:
            return self._item("env_file", "Environment File", "warn", f"Empty optional secret value(s): {', '.join(empty_optional[:4])}.", "Set production provider keys or remove unused providers from release env.", "medium")
        return self._item("env_file", "Environment File", "pass", ".env present and no obvious weak secret placeholders found.", None, "medium")

    def _check_cors(self, cors_origins: List[str]) -> SecurityAuditCheck:
        if "*" in cors_origins:
            return self._item("cors_policy", "CORS Policy", "warn", "API currently allows wildcard origins.", "Restrict CORS origins for production builds.", "high")
        if not cors_origins:
            return self._item("cors_policy", "CORS Policy", "warn", "No explicit CORS origin metadata provided.", "Declare allowed production origins.", "medium")
        return self._item("cors_policy", "CORS Policy", "pass", f"{len(cors_origins)} explicit origin(s) configured.", None, "medium")

    def _check_session_tokens(self, session_tokens: Dict[str, Any]) -> SecurityAuditCheck:
        if not session_tokens:
            return self._item("session_tokens", "Session Tokens", "pass", "No active in-memory session tokens at audit time.", None, "medium")
        short = [token for token in session_tokens if len(str(token)) < 24]
        if short:
            return self._item("session_tokens", "Session Tokens", "fail", f"{len(short)} active token(s) are too short.", "Use high-entropy token generation only.", "high")
        return self._item("session_tokens", "Session Tokens", "pass", f"{len(session_tokens)} active token(s) meet minimum length checks.", None, "medium")

    def _check_safety_state(self, safety_state: Optional[Any]) -> SecurityAuditCheck:
        if safety_state is None:
            return self._item("safety_gates", "Safety Gates", "fail", "Safety state unavailable during audit.", "Initialize SafetyManager before production boot.", "high")
        gates = set(getattr(safety_state, "safety_gates", []) or [])
        required = {"confirm_power_actions", "confirm_package_changes", "confirm_service_lifecycle", "workspace_path_boundary", "audit_sensitive_actions"}
        missing = sorted(required - gates)
        if missing:
            return self._item("safety_gates", "Safety Gates", "fail", f"Missing gate(s): {', '.join(missing)}.", "Enable all required safety gates.", "critical")
        return self._item("safety_gates", "Safety Gates", "pass", f"{len(gates)} safety gate(s) active.", None, "high")

    def _check_audit_logs(self) -> SecurityAuditCheck:
        candidates = [
            self.workspace_root / "memory" / "safety" / "command_audit.jsonl",
            self.workspace_root / "jarvis.db",
        ]
        existing = [path for path in candidates if path.exists()]
        if not existing:
            return self._item("audit_logging", "Audit Logging", "warn", "No local audit artifact found yet.", "Trigger one audited action before release validation.", "medium")
        return self._item("audit_logging", "Audit Logging", "pass", f"{len(existing)} audit artifact(s) found.", None, "medium")

    def _check_dependency_lockfiles(self) -> SecurityAuditCheck:
        expected = [self.workspace_root / "frontend" / "package-lock.json"]
        missing = [str(path.relative_to(self.workspace_root)) for path in expected if not path.exists()]
        if missing:
            return self._item("dependency_lockfiles", "Dependency Lockfiles", "warn", f"Missing lockfile(s): {', '.join(missing)}.", "Commit lockfiles for reproducible builds.", "medium")
        return self._item("dependency_lockfiles", "Dependency Lockfiles", "pass", "Frontend dependency lockfile is present.", None, "medium")

    def _check_runtime_artifacts(self) -> SecurityAuditCheck:
        risky_dirs = [self.workspace_root / ".tmp", self.workspace_root / "test_reports"]
        present = [path.name for path in risky_dirs if path.exists()]
        if present:
            return self._item("runtime_artifacts", "Runtime Artifacts", "warn", f"Runtime artifact directorie(s) present: {', '.join(present)}.", "Clean or exclude runtime artifacts from production images.", "low")
        return self._item("runtime_artifacts", "Runtime Artifacts", "pass", "No local runtime artifact directories detected.", None, "low")

    def _check_sensitive_file_permissions(self) -> SecurityAuditCheck:
        sensitive = [self.workspace_root / ".env", self.workspace_root / "memory" / "preferences" / "os_preferences.json"]
        world_readable = []
        for path in sensitive:
            if not path.exists():
                continue
            mode = path.stat().st_mode
            if os.name != "nt" and mode & stat.S_IROTH:
                world_readable.append(str(path.relative_to(self.workspace_root)))
        if world_readable:
            return self._item("file_permissions", "Sensitive File Permissions", "warn", f"World-readable file(s): {', '.join(world_readable)}.", "Restrict sensitive file permissions.", "medium")
        return self._item("file_permissions", "Sensitive File Permissions", "pass", "No insecure sensitive file permissions detected.", None, "medium")

    def _score(self, checks: List[SecurityAuditCheck]) -> float:
        weights = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
        if not checks:
            return 0.0
        return round(sum(weights.get(check.status, 0.0) for check in checks) / len(checks), 2)

    def _report_payload(self, report: SecurityAuditReport) -> Dict[str, Any]:
        return {
            **asdict(report),
            "checks": [asdict(check) for check in report.checks],
        }

    def _save_report(self, report: Dict[str, Any]) -> None:
        path = self.report_dir / f"{report['id']}.json"
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
