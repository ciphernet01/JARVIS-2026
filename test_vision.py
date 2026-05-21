import requests
import os
from pathlib import Path
import pytest

token_path = Path(os.environ.get("JARVIS_SESSION_TOKEN_PATH", "./.session_token"))
if not token_path.exists():
    pytest.skip("Session token not found; skipping vision integration test", allow_module_level=True)

token = token_path.read_text().strip()
url = os.environ.get("JARVIS_TEST_URL", "http://127.0.0.1:5000/api/command")
headers = {"X-JARVIS-TOKEN": token}


def test_vision_scene():
    resp = requests.post(url, json={"command": "JARVIS, what do you see through your neural sensors right now?"}, headers=headers, timeout=5)
    assert resp.status_code == 200
