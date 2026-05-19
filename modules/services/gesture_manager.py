"""
JARVIS Gesture Manager Service
Manages hand gesture recognition lifecycle, action mapping, and event buffering.
"""

import base64
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

from modules.vision.gesture_engine import (
    GestureEngine,
    GestureResult,
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_FIST,
    GESTURE_POINTING,
    GESTURE_THUMBS_UP,
    GESTURE_THUMBS_DOWN,
    GESTURE_PEACE,
    GESTURE_SWIPE_LEFT,
    GESTURE_SWIPE_RIGHT,
    GESTURE_PINCH_HOLD,
    ALL_GESTURES,
)

from modules.vision.vision_bridge import VisionOSBridge

# Default gesture → action mapping
DEFAULT_ACTION_MAP: Dict[str, Dict[str, Any]] = {
    GESTURE_OPEN_PALM: {
        "action": "stop_recognition",
        "label": "Stop Gesture Control",
        "description": "Open palm halts gesture recognition session",
    },
    GESTURE_FIST: {
        "action": "toggle_terminal",
        "label": "Toggle Terminal",
        "description": "Closed fist switches to the command terminal panel",
    },
    GESTURE_POINTING: {
        "action": "select",
        "label": "Select / Click",
        "description": "Pointing index finger acts as a pointer/selector",
    },
    GESTURE_THUMBS_UP: {
        "action": "confirm",
        "label": "Confirm Action",
        "description": "Thumbs up confirms the current pending action",
    },
    GESTURE_THUMBS_DOWN: {
        "action": "cancel",
        "label": "Cancel Action",
        "description": "Thumbs down cancels the current pending action",
    },
    GESTURE_PEACE: {
        "action": "toggle_analytics",
        "label": "Toggle Analytics",
        "description": "Peace sign switches to the analytics panel",
    },
    GESTURE_SWIPE_LEFT: {
        "action": "prev_panel",
        "label": "Previous Panel",
        "description": "Swipe left navigates to the previous dashboard panel",
    },
    GESTURE_SWIPE_RIGHT: {
        "action": "next_panel",
        "label": "Next Panel",
        "description": "Swipe right navigates to the next dashboard panel",
    },
}


@dataclass
class GestureEvent:
    """A single gesture recognition event."""
    gesture: str
    confidence: float
    action: Optional[str]
    hand_count: int
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gesture": self.gesture,
            "confidence": round(self.confidence, 3),
            "action": self.action,
            "hand_count": self.hand_count,
            "timestamp": self.timestamp,
        }


class GestureManager:
    """
    Manages the gesture recognition lifecycle, including camera capture,
    gesture classification, action mapping, event buffering, and frame streaming.
    """

    MAX_EVENT_BUFFER = 50
    CAPTURE_INTERVAL = 1.0 / 15.0  # ~15 FPS

    def __init__(
        self,
        workspace_root: str = ".",
        camera_index: int = 0,
        max_hands: int = 2,
    ):
        self.workspace_root = Path(workspace_root)
        self.camera_index = camera_index
        self.max_hands = max_hands

        self._engine: Optional[GestureEngine] = None
        self._bridge = VisionOSBridge()
        self._capture = None
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._spatial_callback: Optional[Callable] = None

        # Current state
        self._current_result = GestureResult()
        self._current_frame: Optional[bytes] = None  # JPEG bytes
        self._last_gesture = GESTURE_NONE
        self._gesture_stable_count = 0

        # Event buffer
        self._events: deque = deque(maxlen=self.MAX_EVENT_BUFFER)

        # Action mapping
        self._action_map_path = self.workspace_root / "memory" / "gesture" / "action_map.json"
        self._action_map: Dict[str, Dict[str, Any]] = self._load_action_map()

        # Callbacks for gesture actions
        self._action_callbacks: Dict[str, Callable] = {}

        logger.info("GestureManager initialized")

    # ── Action Map Persistence ────────────────────────────────────────────

    def _load_action_map(self) -> Dict[str, Dict[str, Any]]:
        """Load gesture→action mapping from file or use defaults."""
        try:
            if self._action_map_path.exists():
                data = json.loads(self._action_map_path.read_text(encoding="utf-8"))
                return data
        except Exception as exc:
            logger.warning(f"Failed to load gesture action map: {exc}")
        return dict(DEFAULT_ACTION_MAP)

    def _save_action_map(self):
        """Persist the current action map to disk."""
        try:
            self._action_map_path.parent.mkdir(parents=True, exist_ok=True)
            self._action_map_path.write_text(
                json.dumps(self._action_map, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"Failed to save gesture action map: {exc}")

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if gesture recognition dependencies are available."""
        if self._engine is None:
            try:
                self._engine = GestureEngine(
                    camera_index=self.camera_index,
                    max_hands=self.max_hands,
                )
            except Exception:
                return False
        return self._engine.is_available()

    def is_active(self) -> bool:
        """Check if gesture recognition is currently running."""
        return self._active

    def start(self) -> Dict[str, Any]:
        """Start the gesture recognition capture loop."""
        if self._active:
            return {"status": "already_active", "message": "Gesture recognition is already running"}

        if not self.is_available():
            return {"status": "unavailable", "message": "Gesture recognition dependencies not available (OpenCV + MediaPipe required)"}

        if not cv2:
            return {"status": "unavailable", "message": "OpenCV is not installed"}

        self._capture = cv2.VideoCapture(self.camera_index)
        if not self._capture.isOpened():
            self._capture = None
            return {"status": "error", "message": "Could not open camera"}

        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self._active = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

        logger.info("Gesture recognition started")
        return {"status": "started", "message": "Gesture recognition session active"}

    def stop(self) -> Dict[str, Any]:
        """Stop the gesture recognition capture loop."""
        if not self._active:
            return {"status": "already_inactive", "message": "Gesture recognition is not running"}

        self._active = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

        if self._capture:
            self._capture.release()
            self._capture = None

        self._current_result = GestureResult()
        self._current_frame = None

        logger.info("Gesture recognition stopped")
        return {"status": "stopped", "message": "Gesture recognition session ended"}

    def _capture_loop(self):
        """Main capture loop running in a background thread."""
        if not self._engine:
            return

        while self._active:
            try:
                if not self._capture or not self._capture.isOpened():
                    break

                ok, frame = self._capture.read()
                if not ok or frame is None:
                    continue

                # Flip frame horizontally for mirror effect
                frame = cv2.flip(frame, 1)

                # Process gesture recognition
                result = self._engine.process_frame(frame)

                # Annotate frame with HUD overlay
                annotated = self._engine.annotate_frame(frame, result)

                # Encode annotated frame as JPEG
                jpeg_bytes = self._engine.encode_frame_jpeg(annotated, quality=70)

                with self._lock:
                    self._current_result = result
                    self._current_frame = jpeg_bytes

                # Fire gesture event if gesture changed / stabilized
                self._process_gesture_event(result)

                time.sleep(self.CAPTURE_INTERVAL)

            except Exception as exc:
                logger.error(f"Gesture capture error: {exc}")
                time.sleep(0.1)

    def _process_gesture_event(self, result: GestureResult):
        """Track gesture stability and emit events."""
        # Vision-to-OS Bridge (Virtual Mouse)
        if self._bridge:
            self._bridge.process_gesture(result)

        # Continuous streaming for spatial computing (bypasses stability lock)
        if self._spatial_callback:
            try:
                self._spatial_callback(result)
            except Exception as exc:
                logger.error(f"Gesture spatial callback error: {exc}")

        if result.gesture == GESTURE_NONE:
            self._gesture_stable_count = 0
            self._last_gesture = GESTURE_NONE
            return

        if result.gesture == self._last_gesture:
            self._gesture_stable_count += 1
        else:
            self._last_gesture = result.gesture
            self._gesture_stable_count = 1

        # Require gesture to be stable for 3 consecutive frames
        if self._gesture_stable_count == 3:
            action_info = self._action_map.get(result.gesture, {})
            action = action_info.get("action")
            event = GestureEvent(
                gesture=result.gesture,
                confidence=result.confidence,
                action=action,
                hand_count=result.hand_count,
                timestamp=time.time(),
            )
            self._events.append(event)

            # Trigger callback if registered
            if action and action in self._action_callbacks:
                try:
                    self._action_callbacks[action](event)
                except Exception as exc:
                    logger.error(f"Gesture action callback error: {exc}")

    # ── State Queries ─────────────────────────────────────────────────────

    def state(self) -> Dict[str, Any]:
        """Return current gesture recognition state."""
        with self._lock:
            result = self._current_result

        return {
            "active": self._active,
            "available": self.is_available(),
            "gesture": result.gesture,
            "confidence": round(result.confidence, 3),
            "hand_count": result.hand_count,
            "frame_size": result.frame_size,
            "pointer_x": result.pointer_x,
            "pointer_y": result.pointer_y,
            "pinch_distance": round(result.pinch_distance, 4),
            "timestamp": result.timestamp,
        }

    def current_frame_base64(self) -> Optional[str]:
        """Return the latest annotated frame as a base64 JPEG string."""
        with self._lock:
            frame_bytes = self._current_frame
        if not frame_bytes:
            return None
        return base64.b64encode(frame_bytes).decode("ascii")

    def recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent gesture events."""
        events = list(self._events)[-limit:]
        return [e.to_dict() for e in reversed(events)]

    # ── Action Mapping ────────────────────────────────────────────────────

    def get_action_map(self) -> Dict[str, Dict[str, Any]]:
        """Return the current gesture→action mapping."""
        return dict(self._action_map)

    def update_action_map(self, updates: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Update the gesture→action mapping."""
        for gesture, action_info in updates.items():
            if gesture not in ALL_GESTURES:
                continue
            self._action_map[gesture] = action_info
        self._save_action_map()
        return {"status": "updated", "action_map": self._action_map}

    def reset_action_map(self) -> Dict[str, Any]:
        """Reset the action map to defaults."""
        self._action_map = dict(DEFAULT_ACTION_MAP)
        self._save_action_map()
        return {"status": "reset", "action_map": self._action_map}

    def register_action_callback(self, action: str, callback: Callable):
        """Register a callback for a specific action."""
        self._action_callbacks[action] = callback

    def register_spatial_callback(self, callback: Callable):
        """Register a callback for continuous raw gesture tracking."""
        self._spatial_callback = callback

    # ── Capability Matrix ─────────────────────────────────────────────────

    def capability_matrix(self) -> Dict[str, Any]:
        """Return what the gesture system can do."""
        return {
            "available": self.is_available(),
            "active": self._active,
            "supported_gestures": ALL_GESTURES,
            "max_hands": self.max_hands,
            "action_map": self._action_map,
            "camera_index": self.camera_index,
        }
