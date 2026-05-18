"""Tests for Phase 6 failover drill checks."""

from dataclasses import dataclass

from modules.services.failover_drill_manager import FailoverDrillManager


@dataclass(frozen=True)
class Decision:
    allowed: bool
    category: str
    requires_confirmation: bool


@dataclass(frozen=True)
class State:
    checkpoint_count: int = 1
    maintenance_shell_available: bool = True
    fallback_desktop_available: bool = True


class SafetyStub:
    def __init__(self, state=None, allowlist=None, destructive_allowed=False, mutation_requires_confirmation=True):
        self._state = state or State()
        self._allowlist = allowlist or ["list-root", "pwd", "git-status"]
        self.destructive_allowed = destructive_allowed
        self.mutation_requires_confirmation = mutation_requires_confirmation

    def state(self):
        return self._state

    def maintenance_allowlist(self):
        return self._allowlist

    def evaluate_shell_command(self, command, confirmed=False):
        if "remove-item" in command.lower():
            return Decision(self.destructive_allowed, "destructive", True)
        return Decision(False, "mutating", self.mutation_requires_confirmation)


class ServiceStub:
    def __init__(self, fail=False):
        self.fail = fail

    def get_status_snapshot(self):
        if self.fail:
            raise RuntimeError("inventory unavailable")
        return {"tracked_services": 2, "running_processes": 12}


def test_failover_drill_report_structure(tmp_path):
    manager = FailoverDrillManager(
        workspace_root=str(tmp_path),
        safety_manager=SafetyStub(),
        service_manager=ServiceStub(),
    )

    report = manager.run_drill(label="short-drill", save=False)

    assert report["id"].startswith("failover-drill-")
    assert report["label"] == "short-drill"
    assert report["overall_status"] == "pass"
    assert report["score"] == 1.0
    assert len(report["checks"]) == 6


def test_failover_drill_warns_without_checkpoint(tmp_path):
    manager = FailoverDrillManager(
        workspace_root=str(tmp_path),
        safety_manager=SafetyStub(state=State(checkpoint_count=0)),
        service_manager=ServiceStub(),
    )

    report = manager.run_drill(save=False)
    checkpoint = next(check for check in report["checks"] if check["key"] == "recovery_checkpoint")

    assert report["overall_status"] == "warn"
    assert checkpoint["status"] == "warn"


def test_failover_drill_fails_when_destructive_gate_allows_command(tmp_path):
    manager = FailoverDrillManager(
        workspace_root=str(tmp_path),
        safety_manager=SafetyStub(destructive_allowed=True),
        service_manager=ServiceStub(),
    )

    report = manager.run_drill(save=False)
    gate = next(check for check in report["checks"] if check["key"] == "destructive_gate")

    assert report["overall_status"] == "fail"
    assert gate["status"] == "fail"


def test_failover_drill_fails_when_service_inventory_breaks(tmp_path):
    manager = FailoverDrillManager(
        workspace_root=str(tmp_path),
        safety_manager=SafetyStub(),
        service_manager=ServiceStub(fail=True),
    )

    report = manager.run_drill(save=False)
    inventory = next(check for check in report["checks"] if check["key"] == "service_inventory")

    assert report["overall_status"] == "fail"
    assert inventory["status"] == "fail"


def test_failover_drill_saves_and_lists_reports(tmp_path):
    manager = FailoverDrillManager(
        workspace_root=str(tmp_path),
        safety_manager=SafetyStub(),
        service_manager=ServiceStub(),
    )

    report = manager.run_drill(label="saved-drill", save=True)
    reports = manager.list_reports()

    assert (tmp_path / "test_reports" / "failover_drills" / f"{report['id']}.json").exists()
    assert reports[0]["id"] == report["id"]
    assert reports[0]["overall_status"] == "pass"
