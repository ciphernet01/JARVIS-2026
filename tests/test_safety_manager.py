"""Test SafetyManager recovery and safety state."""
from modules.services.safety_manager import SafetyManager, SafetyActionResult, SafetyCheckpoint, SafetyState


def reset_safety_singleton():
    SafetyManager._instance = None
    SafetyManager._initialized = False


def test_safety_manager_state_structure(tmp_path):
    reset_safety_singleton()
    manager = SafetyManager(workspace_root=str(tmp_path))
    state = manager.state()

    assert isinstance(state, SafetyState)
    assert state.safe_mode is False
    assert state.recovery_mode is False
    assert state.permission_escalation_required is True
    assert "confirm_power_actions" in state.safety_gates


def test_safe_mode_toggle_persists(tmp_path):
    reset_safety_singleton()
    manager = SafetyManager(workspace_root=str(tmp_path))
    result = manager.set_safe_mode(True, "test")

    assert isinstance(result, SafetyActionResult)
    assert result.success is True
    assert result.state.safe_mode is True
    assert any("safe_mode" in reason for reason in result.state.active_reasons)

    reset_safety_singleton()
    manager2 = SafetyManager(workspace_root=str(tmp_path))
    assert manager2.state().safe_mode is True


def test_recovery_checkpoint_manifest(tmp_path):
    reset_safety_singleton()
    (tmp_path / ".env.example").write_text("TOKEN=before\n", encoding="utf-8")
    manager = SafetyManager(workspace_root=str(tmp_path))
    result = manager.create_checkpoint("unit-test", "checkpoint notes")

    assert result.success is True
    assert isinstance(result.checkpoint, SafetyCheckpoint)
    assert result.state.backup_available is True
    assert result.state.checkpoint_count == 1
    assert result.data["tracked_file_count"] == 1

    checkpoints = manager.list_checkpoints()
    assert len(checkpoints) == 1
    assert checkpoints[0].label == "unit-test"


def test_restore_checkpoint_requires_confirmation_and_restores_tracked_file(tmp_path):
    reset_safety_singleton()
    env_example = tmp_path / ".env.example"
    env_example.write_text("TOKEN=before\n", encoding="utf-8")
    manager = SafetyManager(workspace_root=str(tmp_path))
    checkpoint = manager.create_checkpoint("restore-test").checkpoint
    env_example.write_text("TOKEN=after\n", encoding="utf-8")

    plan = manager.restore_checkpoint(checkpoint.id, dry_run=True)
    assert plan.success is True
    assert plan.data["requires_confirmation"] is True
    assert plan.data["plan"][0]["will_overwrite"] is True

    blocked = manager.restore_checkpoint(checkpoint.id, dry_run=False, confirmed=False)
    assert blocked.success is False
    assert "Confirmation required" in blocked.message

    restored = manager.restore_checkpoint(checkpoint.id, dry_run=False, confirmed=True)
    assert restored.success is True
    assert env_example.read_text(encoding="utf-8") == "TOKEN=before\n"


def test_maintenance_shell_blocks_unknown_commands(tmp_path):
    reset_safety_singleton()
    manager = SafetyManager(workspace_root=str(tmp_path))

    result = manager.run_maintenance_command("format-drive")

    assert result.success is False
    assert result.blocked is True
    assert "allowlisted" in result.message


def test_shell_safety_gate_blocks_destructive_commands(tmp_path):
    reset_safety_singleton()
    manager = SafetyManager(workspace_root=str(tmp_path))

    decision = manager.evaluate_shell_command("Remove-Item . -Recurse -Force", confirmed=True)

    assert decision.allowed is False
    assert decision.category == "destructive"
    assert "blocked" in decision.reason


def test_shell_safety_gate_requires_confirmation_for_mutating_commands(tmp_path):
    reset_safety_singleton()
    manager = SafetyManager(workspace_root=str(tmp_path))

    blocked = manager.evaluate_shell_command("npm install", confirmed=False)
    allowed = manager.evaluate_shell_command("npm install", confirmed=True)

    assert blocked.allowed is False
    assert blocked.category == "mutating"
    assert blocked.requires_confirmation is True
    assert allowed.allowed is True
    assert allowed.requires_confirmation is True


def test_recovery_mode_blocks_mutating_shell_commands(tmp_path):
    reset_safety_singleton()
    manager = SafetyManager(workspace_root=str(tmp_path))
    manager.set_recovery_mode(True, "unit test")

    decision = manager.evaluate_shell_command("pip install requests", confirmed=True)

    assert decision.allowed is False
    assert decision.category == "mutating"
    assert "Recovery mode" in decision.reason


def test_capability_matrix(tmp_path):
    reset_safety_singleton()
    manager = SafetyManager(workspace_root=str(tmp_path))
    capabilities = manager.capability_matrix()

    assert capabilities["safe_mode"] is True
    assert capabilities["recovery_mode"] is True
    assert capabilities["checkpoint_manifest"] is True
    assert capabilities["restore_execution"] is True
    assert capabilities["command_safety_gate"] is True
    assert "list-root" in capabilities["maintenance_allowlist"]
