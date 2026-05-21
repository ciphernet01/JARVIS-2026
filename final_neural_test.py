import requests
import os

from pathlib import Path


def main():
    # Load Session Token - prefer env override, fall back to local .session_token
    token_path = Path(os.environ.get("JARVIS_SESSION_TOKEN_PATH", "./.session_token"))
    if not token_path.exists():
        print("Warning: Session token not found; skipping live neural test.")
        return 0

    token = token_path.read_text().strip()

    # Test Command
    url = os.environ.get("JARVIS_TEST_URL", "http://127.0.0.1:5000/api/command")
    headers = {"X-JARVIS-TOKEN": token}
    payload = {"command": "test gemini: what is the core mission of JARVIS? Be brief."}

    try:
        print(f"Sending request to {url}...")
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"JARVIS Response: {data.get('response')}")
        else:
            print(f"Error Response: {resp.text}")
    except Exception as e:
        print(f"Connection Failed: {e}")


if __name__ == "__main__":
    raise SystemExit(main())
