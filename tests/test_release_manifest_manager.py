"""Tests for Phase 7 release manifest and update planning."""

import json

from modules.services.release_manifest_manager import ReleaseManifestManager


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_release_manifest_generates_hashes_and_version(tmp_path):
    write(tmp_path / "os-distribution" / "VERSION.json", '{"name":"JARVIS OS","version":"test-1"}')
    write(tmp_path / "README.md", "hello")

    manager = ReleaseManifestManager(workspace_root=str(tmp_path))
    manifest = manager.generate_manifest(paths=["README.md", "missing.txt"], save=False)

    assert manifest["version"]["version"] == "test-1"
    assert manifest["file_count"] == 1
    assert manifest["files"][0]["path"] == "README.md"
    assert len(manifest["files"][0]["sha256"]) == 64


def test_release_manifest_saves_and_lists(tmp_path):
    write(tmp_path / "os-distribution" / "VERSION.json", '{"version":"test-1"}')
    write(tmp_path / "README.md", "hello")

    manager = ReleaseManifestManager(workspace_root=str(tmp_path))
    manifest = manager.generate_manifest(paths=["README.md"], save=True)
    manifests = manager.list_manifests()

    assert (tmp_path / "os-distribution" / "manifests" / f"{manifest['id']}.json").exists()
    assert manifests[0]["id"] == manifest["id"]


def test_update_plan_detects_added_changed_removed_and_critical(tmp_path):
    current = {
        "version": {"version": "old"},
        "files": [
            {"path": "README.md", "size": 1, "sha256": "a"},
            {"path": "backend/server.py", "size": 1, "sha256": "b"},
            {"path": "removed.txt", "size": 1, "sha256": "c"},
        ],
    }
    candidate = {
        "version": {"version": "new"},
        "files": [
            {"path": "README.md", "size": 1, "sha256": "a"},
            {"path": "backend/server.py", "size": 2, "sha256": "changed"},
            {"path": "added.txt", "size": 1, "sha256": "d"},
        ],
    }
    write(tmp_path / "current.json", json.dumps(current))
    write(tmp_path / "candidate.json", json.dumps(candidate))

    plan = ReleaseManifestManager(workspace_root=str(tmp_path)).plan_update("current.json", "candidate.json")

    assert plan["summary"] == {"added": 1, "changed": 1, "removed": 1, "critical": 1}
    assert plan["changed"] == ["backend/server.py"]
    assert plan["requires_checkpoint"] is True
    assert plan["requires_release_evidence"] is True


def test_update_plan_reports_no_changes(tmp_path):
    manifest = {"version": {"version": "same"}, "files": [{"path": "README.md", "size": 1, "sha256": "a"}]}
    write(tmp_path / "a.json", json.dumps(manifest))
    write(tmp_path / "b.json", json.dumps(manifest))

    plan = ReleaseManifestManager(workspace_root=str(tmp_path)).plan_update("a.json", "b.json")

    assert plan["summary"]["changed"] == 0
    assert plan["requires_checkpoint"] is False
    assert "No file changes" in plan["recommendation"]
