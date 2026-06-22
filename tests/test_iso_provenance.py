import hashlib
import json
from pathlib import Path

from scripts.generate_iso_provenance import generate


def test_generate_iso_provenance_records_hash_and_reproducible_time(tmp_path, monkeypatch):
    iso = tmp_path / "astra-test.iso"
    iso.write_bytes(b"astra-iso-test")
    output = tmp_path / "provenance.json"
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")

    destination = generate(iso, output)
    payload = json.loads(destination.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["artifact"]["name"] == "astra-test.iso"
    assert payload["artifact"]["size_bytes"] == len(b"astra-iso-test")
    assert payload["artifact"]["sha256"] == hashlib.sha256(b"astra-iso-test").hexdigest()
    assert payload["build"]["timestamp"] == "1970-01-01T00:00:00+00:00"
    assert "os-distribution/config/live-build.conf" in payload["inputs"]
