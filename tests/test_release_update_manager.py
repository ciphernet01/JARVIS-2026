"""Tests for Phase 7 manifest-backed update execution."""

import hashlib
import json

from modules.services.release_update_manager import ReleaseUpdateManager


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest(files, version="test"):
    return {"version": {"version": version}, "files": files}


def test_update_dry_run_plans_changed_file_without_writing(tmp_path):
    write(tmp_path / "app.txt", "old")
    write(tmp_path / "candidate" / "app.txt", "new")
    write(tmp_path / "current.json", json.dumps(manifest([{"path": "app.txt", "size": 3, "sha256": sha("old")}], "old")))
    write(tmp_path / "candidate.json", json.dumps(manifest([{"path": "app.txt", "size": 3, "sha256": sha("new")}], "new")))

    result = ReleaseUpdateManager(workspace_root=str(tmp_path)).apply_update("current.json", "candidate.json", "candidate")

    assert result["status"] == "planned"
    assert result["actions"][0]["status"] == "planned"
    assert (tmp_path / "app.txt").read_text(encoding="utf-8") == "old"


def test_update_blocks_execution_without_confirmation(tmp_path):
    write(tmp_path / "app.txt", "old")
    write(tmp_path / "candidate" / "app.txt", "new")
    write(tmp_path / "current.json", json.dumps(manifest([{"path": "app.txt", "size": 3, "sha256": sha("old")}], "old")))
    write(tmp_path / "candidate.json", json.dumps(manifest([{"path": "app.txt", "size": 3, "sha256": sha("new")}], "new")))

    result = ReleaseUpdateManager(workspace_root=str(tmp_path)).apply_update(
        "current.json",
        "candidate.json",
        "candidate",
        dry_run=False,
        confirmed=False,
    )

    assert result["status"] == "blocked"
    assert result["actions"][0]["status"] == "blocked"
    assert (tmp_path / "app.txt").read_text(encoding="utf-8") == "old"


def test_update_applies_changed_file_and_creates_backup(tmp_path):
    write(tmp_path / "app.txt", "old")
    write(tmp_path / "candidate" / "app.txt", "new")
    write(tmp_path / "current.json", json.dumps(manifest([{"path": "app.txt", "size": 3, "sha256": sha("old")}], "old")))
    write(tmp_path / "candidate.json", json.dumps(manifest([{"path": "app.txt", "size": 3, "sha256": sha("new")}], "new")))

    result = ReleaseUpdateManager(workspace_root=str(tmp_path)).apply_update(
        "current.json",
        "candidate.json",
        "candidate",
        dry_run=False,
        confirmed=True,
    )

    assert result["status"] == "applied"
    assert (tmp_path / "app.txt").read_text(encoding="utf-8") == "new"
    backup = tmp_path / result["actions"][0]["backup_path"]
    assert backup.read_text(encoding="utf-8") == "old"


def test_update_blocks_hash_mismatch(tmp_path):
    write(tmp_path / "app.txt", "old")
    write(tmp_path / "candidate" / "app.txt", "tampered")
    write(tmp_path / "current.json", json.dumps(manifest([{"path": "app.txt", "size": 3, "sha256": sha("old")}], "old")))
    write(tmp_path / "candidate.json", json.dumps(manifest([{"path": "app.txt", "size": 3, "sha256": sha("new")}], "new")))

    result = ReleaseUpdateManager(workspace_root=str(tmp_path)).apply_update(
        "current.json",
        "candidate.json",
        "candidate",
        dry_run=False,
        confirmed=True,
    )

    assert result["status"] == "blocked"
    assert "hash" in result["actions"][0]["detail"].lower()
    assert (tmp_path / "app.txt").read_text(encoding="utf-8") == "old"


def test_update_skips_removals_by_default(tmp_path):
    write(tmp_path / "remove.txt", "bye")
    write(tmp_path / "current.json", json.dumps(manifest([{"path": "remove.txt", "size": 3, "sha256": sha("bye")}], "old")))
    write(tmp_path / "candidate.json", json.dumps(manifest([], "new")))
    write(tmp_path / "candidate" / ".keep", "")

    result = ReleaseUpdateManager(workspace_root=str(tmp_path)).apply_update(
        "current.json",
        "candidate.json",
        "candidate",
        dry_run=False,
        confirmed=True,
    )

    assert result["status"] == "applied"
    assert result["actions"][0]["status"] == "skipped"
    assert (tmp_path / "remove.txt").exists()


def test_update_reports_no_changes_for_identical_manifests(tmp_path):
    write(tmp_path / "same.json", json.dumps(manifest([{"path": "app.txt", "size": 3, "sha256": sha("old")}], "same")))
    write(tmp_path / "candidate" / "app.txt", "old")

    result = ReleaseUpdateManager(workspace_root=str(tmp_path)).apply_update("same.json", "same.json", "candidate")

    assert result["status"] == "no_changes"
    assert result["actions"] == []
