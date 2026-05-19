import sys
from pathlib import Path

# Add project root to path
workspace_root = Path("C:/JARVIS-2026").resolve()
sys.path.insert(0, str(workspace_root))

from modules.services.gesture_manager import GestureManager

print("Initializing GestureManager...")
mgr = GestureManager()
avail = mgr.is_available()
print(f"Is available? {avail}")

if not avail:
    print("Checking why it is not available...")
    try:
        from modules.vision.gesture_engine import GestureEngine
        engine = GestureEngine()
        print(f"Engine is_available(): {engine.is_available()}")
    except Exception as e:
        print(f"Engine Exception: {e}")
