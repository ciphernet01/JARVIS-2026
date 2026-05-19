import sys
from pathlib import Path
import asyncio

# Setup paths
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.vision.gesture_engine import GestureResult, GESTURE_FIST
from backend.server import _get_gesture_manager, broadcast_gesture_event

async def mock_fist():
    print("Simulating GESTURE_FIST...")
    manager = _get_gesture_manager()
    
    # Mock a stable gesture manually
    result = GestureResult()
    result.gesture = GESTURE_FIST
    result.confidence = 0.99
    result.hand_count = 1
    
    # Mocking the event dict that the manager would normally emit
    event_dict = {
        "gesture": GESTURE_FIST,
        "confidence": 0.99,
        "action": "toggle_launcher",
        "hand_count": 1,
        "timestamp": 123456789.0
    }
    
    print("Broadcasting to WebSockets...")
    await broadcast_gesture_event(event_dict)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(mock_fist())
