import requests
import os
from pathlib import Path

token_path = Path("e:/JARVIS/jarvis-core/.session_token")
token = token_path.read_text().strip()

url = "http://127.0.0.1:5000/api/command"
headers = {"X-JARVIS-TOKEN": token}

def test_command(cmd):
    print(f"\nTesting: '{cmd}'")
    resp = requests.post(url, json={"command": cmd}, headers=headers)
    if resp.status_code == 200:
        print(f"JARVIS: {resp.json().get('response')}")
    else:
        print(f"Error: {resp.text}")

test_command("Hello JARVIS, how are you today?")
test_command("What is the current time?")
