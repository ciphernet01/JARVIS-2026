"""
Tests for modules.tools
Mocks subprocess / httpx / duckduckgo-search.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from modules.tools.shell import run_shell
from modules.tools.files import write_file, read_file, list_directory
from modules.tools.code_runner import run_python, run_node
from modules.tools.web import search_web, fetch_url
from modules.services.safety_manager import SafetyManager


class TestShellTool:
    @patch("modules.tools.shell.subprocess.run")
    def test_run_shell_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="hello", stderr="")
        result = run_shell("echo hello", timeout=5)
        assert result["success"] is True
        assert result["output"] == "hello"
        assert result["error"] is None

    @patch("modules.tools.shell.subprocess.run")
    def test_run_shell_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = run_shell("badcmd", timeout=5)
        assert result["success"] is False
        assert result["error"] == "error"

    @patch("modules.tools.shell.subprocess.run", side_effect=Exception("crash"))
    def test_run_shell_exception(self, mock_run):
        result = run_shell("cmd", timeout=5)
        assert result["success"] is False
        assert "crash" in result["error"]

    @patch("modules.tools.shell.subprocess.run")
    def test_run_shell_blocks_destructive_commands(self, mock_run, tmp_path):
        SafetyManager._instance = None
        SafetyManager._initialized = False
        safety = SafetyManager(workspace_root=str(tmp_path))

        result = run_shell("rm -rf important", timeout=5, confirmed=True, safety_state=safety.state())

        assert result["success"] is False
        assert result["returncode"] == -2
        assert result["safety"]["category"] == "destructive"
        mock_run.assert_not_called()

    @patch("modules.tools.shell.subprocess.run")
    def test_run_shell_requires_confirmation_for_mutating_commands(self, mock_run, tmp_path):
        SafetyManager._instance = None
        SafetyManager._initialized = False
        safety = SafetyManager(workspace_root=str(tmp_path))

        result = run_shell("npm install", timeout=5, safety_state=safety.state())

        assert result["success"] is False
        assert result["safety"]["category"] == "mutating"
        assert result["safety"]["requires_confirmation"] is True
        mock_run.assert_not_called()


class TestFileTools:
    @patch("modules.tools.files._allow_path")
    def test_write_and_read_file(self, mock_allow):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            test_path = Path(tmp) / "test.txt"
            mock_allow.return_value = test_path

            write_result = write_file(str(test_path), "hello world")
            assert write_result["success"] is True

            read_result = read_file(str(test_path))
            assert read_result["success"] is True
            assert read_result["output"] == "hello world"

    @patch("modules.tools.files._allow_path")
    def test_list_directory(self, mock_allow):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            mock_allow.return_value = Path(tmp)
            (Path(tmp) / "a.txt").write_text("a")
            (Path(tmp) / "b").mkdir()

            result = list_directory(str(tmp))
            assert result["success"] is True
            names = {item["name"] for item in result["output"]}
            assert "a.txt" in names
            assert "b" in names


class TestCodeRunner:
    @patch("modules.tools.code_runner.subprocess.run")
    def test_run_python_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="42", stderr="")
        result = run_python("print(42)", timeout=5)
        assert result["success"] is True
        assert result["output"] == "42"

    @patch("modules.tools.code_runner.subprocess.run")
    def test_run_node_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="hello", stderr="")
        result = run_node("console.log('hello')", timeout=5)
        assert result["success"] is True
        assert result["output"] == "hello"


class TestWebTools:
    @patch("modules.tools.web.DDGS")
    def test_search_web_success(self, mock_ddgs_cls):
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs_cls.return_value.__exit__ = MagicMock(return_value=None)
        mock_ddgs.text.return_value = [
            {"title": "T", "href": "http://example.com", "body": "snippet"}
        ]
        result = search_web("python")
        assert result["success"] is True
        assert len(result["output"]) == 1
        assert result["output"][0]["title"] == "T"

    @patch("modules.tools.web.DDGS", None)
    def test_search_web_missing_package(self):
        result = search_web("python")
        assert result["success"] is False
        assert "duckduckgo_search" in result["error"]

    @patch("modules.tools.web.httpx.get")
    def test_fetch_url_success(self, mock_get):
        mock_get.return_value = MagicMock(text="<html>hi</html>", raise_for_status=lambda: None)
        result = fetch_url("http://example.com")
        assert result["success"] is True
        assert "hi" in result["output"]
