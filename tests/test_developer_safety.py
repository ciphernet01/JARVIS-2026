"""Tests for developer skill safety gates."""

from unittest.mock import MagicMock, patch

from modules.services.safety_manager import SafetyManager
from modules.skills.developer import ExecuteCommandSkill, FileManagementSkill


def reset_safety_singleton():
    SafetyManager._instance = None
    SafetyManager._initialized = False


def test_execute_command_skill_blocks_destructive_command(tmp_path, monkeypatch):
    reset_safety_singleton()
    monkeypatch.setenv("JARVIS_WORKSPACE", str(tmp_path))
    skill = ExecuteCommandSkill()

    with patch("modules.skills.developer.subprocess.run") as mock_run:
        result = skill.execute("execute: Remove-Item . -Recurse -Force", {"confirmed": True})

    assert "Command blocked" in result
    mock_run.assert_not_called()


def test_execute_command_skill_requires_confirmation_for_mutating_command(tmp_path, monkeypatch):
    reset_safety_singleton()
    monkeypatch.setenv("JARVIS_WORKSPACE", str(tmp_path))
    skill = ExecuteCommandSkill()

    with patch("modules.skills.developer.subprocess.run") as mock_run:
        result = skill.execute("execute: npm install")

    assert "Confirmation required" in result
    mock_run.assert_not_called()


def test_execute_command_skill_runs_confirmed_mutating_command(tmp_path, monkeypatch):
    reset_safety_singleton()
    monkeypatch.setenv("JARVIS_WORKSPACE", str(tmp_path))
    skill = ExecuteCommandSkill()

    with patch("modules.skills.developer.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        result = skill.execute("execute: npm install", {"confirmed": True})

    assert "Output" in result
    mock_run.assert_called_once()


def test_file_management_skill_blocks_workspace_escape(tmp_path, monkeypatch):
    reset_safety_singleton()
    monkeypatch.setenv("JARVIS_WORKSPACE", str(tmp_path))
    skill = FileManagementSkill()

    result = skill.execute("write: ..\\outside.txt | no")

    assert "escapes the workspace boundary" in result
