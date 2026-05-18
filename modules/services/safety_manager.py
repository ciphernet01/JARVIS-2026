"""
SafetyManager: recovery mode, safe mode, checkpoints, and safety gates.
"""
import json
import logging
import platform
import re
import shutil
import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SafetyCheckpoint:
    """Immutable recovery checkpoint metadata."""
    id: str
    label: str
    created_at: str
    manifest_path: str
    workspace_root: str
    notes: str


@dataclass(frozen=True)
class SafetyState:
    """Immutable safety and recovery state snapshot."""
    safe_mode: bool
    recovery_mode: bool
    maintenance_shell_available: bool
    fallback_desktop_available: bool
    backup_available: bool
    last_checkpoint_at: Optional[str]
    checkpoint_count: int
    permission_escalation_required: bool
    safety_gates: List[str]
    active_reasons: List[str]
    platform_name: str


@dataclass(frozen=True)
class SafetyActionResult:
    """Result of a safety operation."""
    success: bool
    action: str
    message: str
    state: SafetyState
    checkpoint: Optional[SafetyCheckpoint] = None
    data: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class MaintenanceCommandResult:
    """Result of an allowlisted offline maintenance command."""
    success: bool
    command: str
    message: str
    stdout: str = ""
    stderr: str = ""
    returncode: Optional[int] = None
    blocked: bool = False


@dataclass(frozen=True)
class SafetyGateDecision:
    """Decision from the command safety gate."""
    allowed: bool
    category: str
    requires_confirmation: bool
    reason: str
    command: str


class SafetyGate:
    """Classify shell-like commands before execution."""

    DESTRUCTIVE_PATTERNS = [
        r"\brm\s+(-[^\s]*[rf][^\s]*|/[sq]\b)",
        r"\bdel\s+(/s|/q|\*)",
        r"\berase\s+(/s|/q|\*)",
        r"\brmdir\s+(/s|/q|-r|/S|/Q)",
        r"\brd\s+(/s|/q|/S|/Q)",
        r"\bremove-item\b.*(-recurse|-force)\b",
        r"\bformat\b",
        r"\bdiskpart\b",
        r"\bmkfs(\.|\\b)",
        r"\bdd\s+.*\bof=",
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bpoweroff\b",
        r"\bgit\s+reset\s+--hard\b",
        r"\bgit\s+clean\b.*\b-f\b",
    ]

    MUTATING_PATTERNS = [
        r"\bnpm\s+(install|uninstall|update|audit\s+fix)\b",
        r"\byarn\s+(add|remove|install|upgrade)\b",
        r"\bpnpm\s+(add|remove|install|update)\b",
        r"\bpip\s+(install|uninstall)\b",
        r"\bpython\s+-m\s+pip\s+(install|uninstall)\b",
        r"\bwinget\s+(install|uninstall|upgrade)\b",
        r"\bchoco\s+(install|uninstall|upgrade)\b",
        r"\bapt(-get)?\s+(install|remove|upgrade|dist-upgrade|autoremove)\b",
        r"\bdnf\s+(install|remove|upgrade)\b",
        r"\bpacman\s+-(s|r|syu)\b",
        r"\bbrew\s+(install|uninstall|upgrade)\b",
        r"\bgit\s+(checkout|switch|merge|rebase|commit|push|pull|apply|restore)\b",
        r"\b(new-item|mkdir|md|touch|copy|copy-item|cp|move|move-item|mv|rename|rename-item)\b",
        r"\bset-service\b|\bstart-service\b|\bstop-service\b|\brestart-service\b",
        r"\bsc\s+(start|stop|delete|create)\b",
        r"\bsystemctl\s+(start|stop|restart|enable|disable)\b",
    ]

    def __init__(self, state: SafetyState):
        self.state = state

    def evaluate(self, command: str, *, confirmed: bool = False) -> SafetyGateDecision:
        clean_command = (command or "").strip()
        lowered = clean_command.lower()
        if not clean_command:
            return SafetyGateDecision(False, "blocked", False, "Command is empty.", clean_command)

        category = self._category(lowered)
        if category == "destructive":
            return SafetyGateDecision(
                False,
                category,
                True,
                "Destructive shell commands are blocked by JARVIS safety gates.",
                clean_command,
            )

        if category == "mutating":
            if self.state.recovery_mode:
                return SafetyGateDecision(
                    False,
                    category,
                    True,
                    "Recovery mode allows read-only diagnostics only.",
                    clean_command,
                )
            if not confirmed:
                return SafetyGateDecision(
                    False,
                    category,
                    True,
                    "Confirmation required before mutating shell commands.",
                    clean_command,
                )

        return SafetyGateDecision(True, category, category == "mutating", "Command allowed.", clean_command)

    def _category(self, lowered_command: str) -> str:
        for pattern in self.DESTRUCTIVE_PATTERNS:
            if re.search(pattern, lowered_command, re.IGNORECASE):
                return "destructive"
        for pattern in self.MUTATING_PATTERNS:
            if re.search(pattern, lowered_command, re.IGNORECASE):
                return "mutating"
        return "read_only"


class SafetyManager:
    """Singleton safety manager for recovery and high-risk operation gates."""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, workspace_root: Optional[str] = None):
        if self._initialized:
            return

        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.state_dir = self.workspace_root / "memory" / "safety"
        self.checkpoint_dir = self.workspace_root / "backups" / "recovery"
        self.state_path = self.state_dir / "safety_state.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()
        SafetyManager._initialized = True

    def _load_state(self) -> Dict[str, Any]:
        defaults = {
            "safe_mode": False,
            "recovery_mode": False,
            "active_reasons": [],
            "permission_escalation_required": True,
            "last_checkpoint_at": None,
        }
        if not self.state_path.exists():
            return defaults
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return {**defaults, **data}
        except Exception as exc:
            logger.warning(f"Failed to load safety state: {exc}")
            return defaults

    def _save_state(self) -> None:
        payload = {**self._state, "updated_at": datetime.now(timezone.utc).isoformat()}
        self.state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def state(self) -> SafetyState:
        checkpoints = self.list_checkpoints(limit=1000)
        last_checkpoint_at = self._state.get("last_checkpoint_at")
        if checkpoints and not last_checkpoint_at:
            last_checkpoint_at = checkpoints[0].created_at

        gates = [
            "confirm_power_actions",
            "confirm_package_changes",
            "confirm_service_lifecycle",
            "workspace_path_boundary",
            "audit_sensitive_actions",
        ]
        if self._state.get("safe_mode"):
            gates.append("block_destructive_operations")
        if self._state.get("recovery_mode"):
            gates.append("recovery_read_only_default")

        return SafetyState(
            safe_mode=bool(self._state.get("safe_mode")),
            recovery_mode=bool(self._state.get("recovery_mode")),
            maintenance_shell_available=True,
            fallback_desktop_available=True,
            backup_available=bool(checkpoints),
            last_checkpoint_at=last_checkpoint_at,
            checkpoint_count=len(checkpoints),
            permission_escalation_required=bool(self._state.get("permission_escalation_required", True)),
            safety_gates=gates,
            active_reasons=list(self._state.get("active_reasons") or []),
            platform_name=platform.system(),
        )

    def set_safe_mode(self, enabled: bool, reason: Optional[str] = None) -> SafetyActionResult:
        self._state["safe_mode"] = bool(enabled)
        self._set_reason("safe_mode", enabled, reason)
        self._save_state()
        verb = "enabled" if enabled else "disabled"
        return SafetyActionResult(True, "safe_mode", f"Safe mode {verb}.", self.state())

    def set_recovery_mode(self, enabled: bool, reason: Optional[str] = None) -> SafetyActionResult:
        self._state["recovery_mode"] = bool(enabled)
        self._set_reason("recovery_mode", enabled, reason)
        self._save_state()
        verb = "enabled" if enabled else "disabled"
        return SafetyActionResult(True, "recovery_mode", f"Recovery mode {verb}.", self.state())

    def _set_reason(self, prefix: str, enabled: bool, reason: Optional[str]) -> None:
        reasons = [item for item in self._state.get("active_reasons", []) if not item.startswith(f"{prefix}:")]
        if enabled:
            clean_reason = (reason or "operator requested").strip()[:160]
            reasons.append(f"{prefix}: {clean_reason}")
        self._state["active_reasons"] = reasons

    def create_checkpoint(self, label: Optional[str] = None, notes: str = "") -> SafetyActionResult:
        checkpoint_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        safe_label = (label or "manual-checkpoint").strip()[:80] or "manual-checkpoint"
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        files_dir = self.checkpoint_dir / checkpoint_id / "files"
        tracked_files = self._tracked_file_manifest(files_dir)
        checkpoint = SafetyCheckpoint(
            id=checkpoint_id,
            label=safe_label,
            created_at=datetime.now(timezone.utc).isoformat(),
            manifest_path=str(checkpoint_path.relative_to(self.workspace_root)),
            workspace_root=str(self.workspace_root),
            notes=notes.strip()[:500],
        )
        manifest = {
            **asdict(checkpoint),
            "state": asdict(self.state()),
            "tracked_files": tracked_files,
        }
        checkpoint_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        self._state["last_checkpoint_at"] = checkpoint.created_at
        self._save_state()
        return SafetyActionResult(
            True,
            "checkpoint",
            "Recovery checkpoint created.",
            self.state(),
            checkpoint,
            {"tracked_file_count": len(tracked_files)},
        )

    def list_checkpoints(self, limit: int = 10) -> List[SafetyCheckpoint]:
        checkpoints: List[SafetyCheckpoint] = []
        for path in sorted(self.checkpoint_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                checkpoints.append(SafetyCheckpoint(
                    id=data.get("id", path.stem),
                    label=data.get("label", path.stem),
                    created_at=data.get("created_at", datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()),
                    manifest_path=str(path.relative_to(self.workspace_root)),
                    workspace_root=data.get("workspace_root", str(self.workspace_root)),
                    notes=data.get("notes", ""),
                ))
            except Exception as exc:
                logger.warning(f"Skipping invalid checkpoint {path}: {exc}")
            if len(checkpoints) >= limit:
                break
        return checkpoints

    def restore_checkpoint(self, checkpoint_id: str, *, dry_run: bool = True, confirmed: bool = False) -> SafetyActionResult:
        """Plan or restore tracked files from a checkpoint backup."""
        clean_id = (checkpoint_id or "").strip()
        if not clean_id:
            return SafetyActionResult(False, "restore", "Checkpoint id is required.", self.state())

        manifest_path = self.checkpoint_dir / f"{clean_id}.json"
        if not manifest_path.exists() or not manifest_path.is_file():
            return SafetyActionResult(False, "restore", "Checkpoint not found.", self.state())

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return SafetyActionResult(False, "restore", f"Checkpoint manifest is invalid: {exc}", self.state())

        plan = self._restore_plan(manifest)
        blocked = [item for item in plan if item.get("blocked")]
        if blocked:
            return SafetyActionResult(
                False,
                "restore",
                "Restore blocked because one or more files failed safety validation.",
                self.state(),
                data={"checkpoint_id": clean_id, "plan": plan},
            )

        if dry_run:
            return SafetyActionResult(
                True,
                "restore",
                "Restore plan ready.",
                self.state(),
                data={"checkpoint_id": clean_id, "plan": plan, "requires_confirmation": True},
            )

        if not confirmed:
            return SafetyActionResult(
                False,
                "restore",
                "Confirmation required before restoring checkpoint files.",
                self.state(),
                data={"checkpoint_id": clean_id, "plan": plan, "requires_confirmation": True},
            )

        restored = []
        for item in plan:
            source = Path(item["source_abs"])
            target = Path(item["target_abs"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            restored.append(item["path"])

        self._state["last_restore_at"] = datetime.now(timezone.utc).isoformat()
        self._state["last_restore_checkpoint"] = clean_id
        self._save_state()
        return SafetyActionResult(
            True,
            "restore",
            f"Restored {len(restored)} checkpoint file(s).",
            self.state(),
            data={"checkpoint_id": clean_id, "restored": restored, "plan": plan},
        )

    def run_maintenance_command(self, command: str, timeout_seconds: int = 20) -> MaintenanceCommandResult:
        """Run a read-only command from the offline maintenance allowlist."""
        tokens = self._maintenance_tokens(command)
        if not tokens:
            return MaintenanceCommandResult(False, command, "Maintenance command is not allowlisted.", blocked=True)

        try:
            completed = subprocess.run(
                tokens,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=max(1, min(timeout_seconds, 60)),
                check=False,
                shell=False,
            )
            return MaintenanceCommandResult(
                completed.returncode == 0,
                " ".join(tokens),
                "Maintenance command completed." if completed.returncode == 0 else "Maintenance command failed.",
                stdout=(completed.stdout or "")[-6000:],
                stderr=(completed.stderr or "")[-3000:],
                returncode=completed.returncode,
            )
        except subprocess.TimeoutExpired as exc:
            return MaintenanceCommandResult(
                False,
                " ".join(tokens),
                f"Maintenance command timed out after {timeout_seconds}s.",
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
            )
        except Exception as exc:
            logger.warning(f"Maintenance command failed: {exc}")
            return MaintenanceCommandResult(False, " ".join(tokens), str(exc), blocked=False)

    def maintenance_allowlist(self) -> List[str]:
        """Human-readable list of allowed maintenance diagnostics."""
        return sorted(self._maintenance_allowlist().keys())

    def evaluate_shell_command(self, command: str, *, confirmed: bool = False) -> SafetyGateDecision:
        """Classify a shell/developer command through the current safety state."""
        return SafetyGate(self.state()).evaluate(command, confirmed=confirmed)

    def audit_command_decision(self, decision: SafetyGateDecision, source: str) -> None:
        """Append command-gate decisions to a local audit log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "command": decision.command[:500],
            "category": decision.category,
            "allowed": decision.allowed,
            "requires_confirmation": decision.requires_confirmation,
            "reason": decision.reason,
        }
        audit_path = self.state_dir / "command_audit.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def _tracked_file_manifest(self, files_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
        tracked = []
        for relative in [".env", ".env.example", "backend/server.py", "frontend/package.json", "frontend/src/App.js"]:
            path = self.workspace_root / relative
            if not path.exists() or not path.is_file():
                continue
            stat = path.stat()
            backup_path = None
            if files_dir:
                backup = files_dir / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup)
                backup_path = str(backup.relative_to(self.workspace_root))
            tracked.append({
                "path": relative,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "backup_path": backup_path,
            })
        return tracked

    def _restore_plan(self, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
        plan = []
        for item in manifest.get("tracked_files") or []:
            relative = item.get("path")
            backup_path = item.get("backup_path")
            target = (self.workspace_root / relative).resolve() if relative else self.workspace_root
            source = (self.workspace_root / backup_path).resolve() if backup_path else self.workspace_root
            blocked_reason = None
            if not relative or not backup_path:
                blocked_reason = "Checkpoint does not include a restorable backup for this file"
            elif not self._is_inside_workspace(target) or not self._is_inside_workspace(source):
                blocked_reason = "Restore path escapes workspace boundary"
            elif not source.exists() or not source.is_file():
                blocked_reason = "Backup file is missing"

            plan.append({
                "path": relative,
                "source": backup_path,
                "target": relative,
                "source_abs": str(source),
                "target_abs": str(target),
                "blocked": blocked_reason is not None,
                "reason": blocked_reason,
                "will_overwrite": target.exists() and target.is_file(),
            })
        return plan

    def _is_inside_workspace(self, path: Path) -> bool:
        try:
            path.relative_to(self.workspace_root)
            return True
        except ValueError:
            return False

    def _maintenance_allowlist(self) -> Dict[str, List[str]]:
        python_exe = shutil.which("python") or shutil.which("python3")
        git_exe = shutil.which("git")
        node_exe = shutil.which("node")
        npm_exe = shutil.which("npm")
        commands = {
            "pwd": ["powershell.exe", "-NoProfile", "-Command", "Get-Location"] if platform.system() == "Windows" else ["pwd"],
            "list-root": ["powershell.exe", "-NoProfile", "-Command", "Get-ChildItem -Force"] if platform.system() == "Windows" else ["ls", "-la"],
        }
        if python_exe:
            commands["python-version"] = [python_exe, "--version"]
        if git_exe:
            commands["git-status"] = [git_exe, "status", "--short"]
            commands["git-diff-stat"] = [git_exe, "diff", "--stat"]
        if node_exe:
            commands["node-version"] = [node_exe, "--version"]
        if npm_exe:
            commands["npm-version"] = [npm_exe, "--version"]
        return commands

    def _maintenance_tokens(self, command: str) -> List[str]:
        normalized = (command or "").strip().lower()
        return self._maintenance_allowlist().get(normalized, [])

    def capability_matrix(self) -> Dict[str, Any]:
        state = self.state()
        return {
            "safe_mode": True,
            "recovery_mode": True,
            "offline_maintenance_shell": state.maintenance_shell_available,
            "fallback_desktop": state.fallback_desktop_available,
            "checkpoint_manifest": True,
            "restore_execution": True,
            "command_safety_gate": True,
            "maintenance_allowlist": self.maintenance_allowlist(),
            "audit_integration": True,
            "permission_escalation_gates": state.safety_gates,
        }
