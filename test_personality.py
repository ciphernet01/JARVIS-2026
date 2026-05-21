import requests
import os
from pathlib import Path
import pytest

# Integration test that requires a running backend and a session token.
token_path = Path(os.environ.get("JARVIS_SESSION_TOKEN_PATH", "./.session_token"))
if not token_path.exists():
    pytest.skip("Session token not found; skipping personality integration tests", allow_module_level=True)

token = token_path.read_text().strip()
url = os.environ.get("JARVIS_TEST_URL", "http://127.0.0.1:5000/api/command")
headers = {"X-JARVIS-TOKEN": token}


def _call(cmd):
    resp = requests.post(url, json={"command": cmd}, headers=headers, timeout=5)
    return resp


def test_personality_greeting():
    resp = _call("Hello JARVIS, how are you today?")
    assert resp.status_code == 200


def test_personality_time():
    resp = _call("What is the current time?")
    assert resp.status_code == 200
