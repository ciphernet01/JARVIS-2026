from scripts.inspect_iso_payload import REQUIRED_PATHS, inspect_entries


def test_iso_payload_contract_accepts_required_clean_image():
    report = inspect_entries(REQUIRED_PATHS | {"etc/os-release", "boot/vmlinuz"})
    assert report["ok"] is True
    assert report["missing"] == []
    assert report["forbidden"] == []


def test_iso_payload_contract_reports_missing_runtime_files():
    entries = REQUIRED_PATHS - {"opt/astra/venv/bin/python"}
    report = inspect_entries(entries)
    assert report["ok"] is False
    assert report["missing"] == ["opt/astra/venv/bin/python"]


def test_iso_payload_contract_rejects_secrets_and_development_artifacts():
    entries = set(REQUIRED_PATHS) | {
        "opt/jarvis/.env",
        "opt/jarvis/frontend/node_modules/react/index.js",
        "opt/jarvis/.git/config",
        "opt/jarvis/jarvis.db",
    }
    report = inspect_entries(entries)
    assert report["ok"] is False
    assert report["forbidden"] == [
        "opt/jarvis/.env",
        "opt/jarvis/.git/config",
        "opt/jarvis/frontend/node_modules/react/index.js",
        "opt/jarvis/jarvis.db",
    ]
