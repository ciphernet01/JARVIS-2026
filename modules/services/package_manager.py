"""
PackageManager: safety-gated app/package lifecycle operations.
"""
import logging
import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PackageProvider:
    """Detected package manager provider."""
    name: str
    executable: str
    platform_name: str
    requires_admin: bool
    supports_search: bool = True
    supports_install: bool = True
    supports_uninstall: bool = True
    supports_update: bool = True


@dataclass(frozen=True)
class PackagePlan:
    """Planned package operation."""
    action: str
    package: Optional[str]
    command: List[str]
    provider: Optional[str]
    requires_confirmation: bool
    blocked: bool
    reason: Optional[str] = None


@dataclass(frozen=True)
class PackageActionResult:
    """Result of package action execution or planning."""
    success: bool
    action: str
    dry_run: bool
    message: str
    plan: PackagePlan
    stdout: str = ""
    stderr: str = ""
    returncode: Optional[int] = None
    timestamp: str = ""


class PackageManager:
    """Detect and run package lifecycle operations through a safe interface."""

    def __init__(self, provider: Optional[PackageProvider] = None):
        self._provider = provider or self.detect_provider()

    def detect_provider(self) -> Optional[PackageProvider]:
        system = platform.system()
        candidates = []
        if system == "Windows":
            candidates = [("winget", False), ("choco", True)]
        elif system == "Linux":
            candidates = [("apt-get", True), ("dnf", True), ("pacman", True)]
        elif system == "Darwin":
            candidates = [("brew", False)]

        for name, requires_admin in candidates:
            executable = shutil.which(name)
            if executable:
                return PackageProvider(
                    name=name,
                    executable=executable,
                    platform_name=system,
                    requires_admin=requires_admin,
                )
        return None

    def provider_state(self) -> Dict[str, Any]:
        provider = self._provider
        if not provider:
            return {
                "available": False,
                "provider": None,
                "message": "No supported package manager detected.",
                "supported_providers": ["winget", "choco", "apt-get", "dnf", "pacman", "brew"],
            }
        return {
            "available": True,
            "provider": provider.__dict__,
            "message": f"{provider.name} package lifecycle provider ready.",
        }

    def plan(self, action: str, package: Optional[str] = None) -> PackagePlan:
        action = action.strip().lower()
        package = package.strip() if package else None
        provider = self._provider
        if not provider:
            return PackagePlan(action, package, [], None, True, True, "No supported package manager detected")
        if action in {"install", "uninstall", "search"} and not package:
            return PackagePlan(action, package, [], provider.name, True, True, "Package name is required")

        command = self._build_command(provider, action, package)
        if not command:
            return PackagePlan(action, package, [], provider.name, True, True, f"Unsupported package action: {action}")

        return PackagePlan(
            action=action,
            package=package,
            command=command,
            provider=provider.name,
            requires_confirmation=action in {"install", "uninstall", "update"},
            blocked=False,
        )

    def search(self, query: str, timeout_seconds: int = 20) -> PackageActionResult:
        return self.execute("search", query, dry_run=False, confirmed=True, timeout_seconds=timeout_seconds)

    def list_installed(self, timeout_seconds: int = 30) -> PackageActionResult:
        return self.execute("list", None, dry_run=False, confirmed=True, timeout_seconds=timeout_seconds)

    def execute(
        self,
        action: str,
        package: Optional[str] = None,
        *,
        dry_run: bool = True,
        confirmed: bool = False,
        safety_state: Optional[Any] = None,
        timeout_seconds: int = 120,
    ) -> PackageActionResult:
        plan = self.plan(action, package)
        timestamp = datetime.now(timezone.utc).isoformat()
        if plan.blocked:
            return PackageActionResult(False, action, dry_run, plan.reason or "Package operation blocked.", plan, timestamp=timestamp)

        if safety_state and getattr(safety_state, "recovery_mode", False) and action in {"install", "uninstall", "update"}:
            blocked = PackagePlan(action, package, plan.command, plan.provider, plan.requires_confirmation, True, "Recovery mode blocks package changes")
            return PackageActionResult(False, action, dry_run, blocked.reason or "Blocked", blocked, timestamp=timestamp)

        if safety_state and getattr(safety_state, "safe_mode", False) and action in {"install", "uninstall", "update"}:
            blocked = PackagePlan(action, package, plan.command, plan.provider, plan.requires_confirmation, True, "Safe mode blocks package changes")
            return PackageActionResult(False, action, dry_run, blocked.reason or "Blocked", blocked, timestamp=timestamp)

        if plan.requires_confirmation and not confirmed:
            return PackageActionResult(False, action, dry_run, "Confirmation required before package changes.", plan, timestamp=timestamp)

        if dry_run:
            return PackageActionResult(True, action, True, "Package operation plan ready.", plan, timestamp=timestamp)

        try:
            completed = subprocess.run(
                plan.command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            ok = completed.returncode == 0
            message = "Package operation completed." if ok else "Package operation failed."
            return PackageActionResult(
                ok,
                action,
                False,
                message,
                plan,
                stdout=completed.stdout[-6000:],
                stderr=completed.stderr[-3000:],
                returncode=completed.returncode,
                timestamp=timestamp,
            )
        except subprocess.TimeoutExpired as exc:
            return PackageActionResult(False, action, False, f"Package operation timed out after {timeout_seconds}s.", plan, stdout=exc.stdout or "", stderr=exc.stderr or "", timestamp=timestamp)
        except Exception as exc:
            logger.error(f"Package operation failed: {exc}")
            return PackageActionResult(False, action, False, str(exc), plan, timestamp=timestamp)

    def _build_command(self, provider: PackageProvider, action: str, package: Optional[str]) -> List[str]:
        exe = provider.executable
        name = provider.name
        if name == "winget":
            if action == "search":
                return [exe, "search", "--query", package or "", "--accept-source-agreements"]
            if action == "list":
                return [exe, "list"]
            if action == "install":
                return [exe, "install", "--id", package or "", "--silent", "--accept-package-agreements", "--accept-source-agreements"]
            if action == "uninstall":
                return [exe, "uninstall", "--id", package or ""]
            if action == "update":
                return [exe, "upgrade", "--id", package, "--accept-package-agreements", "--accept-source-agreements"] if package else [exe, "upgrade", "--all", "--accept-package-agreements", "--accept-source-agreements"]
        if name == "choco":
            if action == "search":
                return [exe, "search", package or ""]
            if action == "list":
                return [exe, "list", "--local-only"]
            if action == "install":
                return [exe, "install", package or "", "-y"]
            if action == "uninstall":
                return [exe, "uninstall", package or "", "-y"]
            if action == "update":
                return [exe, "upgrade", package or "all", "-y"]
        if name == "apt-get":
            apt_cache = shutil.which("apt-cache") or "apt-cache"
            if action == "search":
                return [apt_cache, "search", package or ""]
            if action == "list":
                return ["dpkg-query", "-W", "-f=${Package}\t${Version}\n"]
            if action == "install":
                return [exe, "install", "-y", package or ""]
            if action == "uninstall":
                return [exe, "remove", "-y", package or ""]
            if action == "update":
                return [exe, "upgrade", "-y"] if not package else [exe, "install", "--only-upgrade", "-y", package]
        if name == "dnf":
            if action in {"search", "install", "remove"}:
                return [exe, action, package or ""] if action == "search" else [exe, action, "-y", package or ""]
            if action == "uninstall":
                return [exe, "remove", "-y", package or ""]
            if action == "update":
                return [exe, "upgrade", "-y"] if not package else [exe, "upgrade", "-y", package]
            if action == "list":
                return [exe, "list", "installed"]
        if name == "pacman":
            if action == "search":
                return [exe, "-Ss", package or ""]
            if action == "list":
                return [exe, "-Q"]
            if action == "install":
                return [exe, "-S", "--noconfirm", package or ""]
            if action == "uninstall":
                return [exe, "-R", "--noconfirm", package or ""]
            if action == "update":
                return [exe, "-Syu", "--noconfirm"]
        if name == "brew":
            if action == "search":
                return [exe, "search", package or ""]
            if action == "list":
                return [exe, "list", "--versions"]
            if action == "install":
                return [exe, "install", package or ""]
            if action == "uninstall":
                return [exe, "uninstall", package or ""]
            if action == "update":
                return [exe, "upgrade", package] if package else [exe, "upgrade"]
        return []
