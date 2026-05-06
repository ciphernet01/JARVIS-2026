import requests
import os

from pathlib import Path

# Load Session Token
token_path = Path("e:/JARVIS/jarvis-core/.session_token")
if not token_path.exists():
    print("Error: Session token not found.")
    exit(1)

token = token_path.read_text().strip()

# Test Command
url = "http://127.0.0.1:5000/api/command"
headers = {"X-JARVIS-TOKEN": token}
payload = {"command": "test gemini: what is the core mission of JARVIS? Be brief."}

try:
    print(f"Sending request to {url}...")
    resp = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"JARVIS Response: {data.get('response')}")
    else:
        print(f"Error Response: {resp.text}")
except Exception as e:
    print(f"Connection Failed: {e}")
