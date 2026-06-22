import hashlib
import json

import pytest

from scripts.generate_wheelhouse_manifest import generate


def test_wheelhouse_manifest_hashes_sorted_artifacts(tmp_path):
    wheelhouse = tmp_path / "wheels"
    wheelhouse.mkdir()
    (wheelhouse / "z_package-1.0-py3-none-any.whl").write_bytes(b"z")
    (wheelhouse / "a_package-1.0-py3-none-any.whl").write_bytes(b"alpha")
    output = tmp_path / "manifest.json"

    generate(wheelhouse, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["artifact_count"] == 2
    assert [item["filename"] for item in payload["artifacts"]] == [
        "a_package-1.0-py3-none-any.whl",
        "z_package-1.0-py3-none-any.whl",
    ]
    assert payload["artifacts"][0]["sha256"] == hashlib.sha256(b"alpha").hexdigest()


def test_wheelhouse_manifest_rejects_empty_directory(tmp_path):
    with pytest.raises(ValueError, match="No wheels found"):
        generate(tmp_path, tmp_path / "manifest.json")
