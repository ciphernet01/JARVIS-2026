"""
JARVIS Gesture Recognition Engine (Neural Core)
Updated to use modern MediaPipe Tasks API for Python 3.14+ compatibility.
"""

import cv2
import logging
import time
import os
from typing import Tuple, List, Dict, Any, Optional

try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    TASKS_AVAILABLE = True
except (ImportError, AttributeError):
    TASKS_AVAILABLE = False

logger = logging.getLogger(__name__)

from dataclasses import dataclass, field

# ── Gesture Constants ────────────────────────────────────────────────────────
GESTURE_NONE = "NONE"
GESTURE_OPEN_PALM = "OPEN_PALM"
GESTURE_FIST = "CLOSED_FIST"
GESTURE_POINTING = "POINTING"
GESTURE_THUMBS_UP = "THUMBS_UP"
GESTURE_THUMBS_DOWN = "THUMBS_DOWN"
GESTURE_PEACE = "PEACE_SIGN"
GESTURE_SWIPE_LEFT = "SWIPE_LEFT"
GESTURE_SWIPE_RIGHT = "SWIPE_RIGHT"
GESTURE_PINCH_HOLD = "PINCH_HOLD"

ALL_GESTURES = [
    GESTURE_NONE, GESTURE_OPEN_PALM, GESTURE_FIST, GESTURE_POINTING,
    GESTURE_THUMBS_UP, GESTURE_THUMBS_DOWN, GESTURE_PEACE,
    GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT, GESTURE_PINCH_HOLD
]

@dataclass
class GestureResult:
    """Standardized result from gesture recognition."""
    gesture: str = GESTURE_NONE
    confidence: float = 0.0
    hand_count: int = 0
    landmarks: List[Any] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    frame_size: Tuple[int, int] = (0, 0)
    pointer_x: float = 0.5
    pointer_y: float = 0.5
    pinch_distance: float = 1.0

# ── MediaPipe Landmark Mapping ──────────────────────────────────────────────
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

class GestureEngine:
    def __init__(self, max_hands=2, detection_confidence=0.5, tracking_confidence=0.5, **kwargs):
        self.max_hands = max_hands
        self.detection_confidence = detection_confidence
        self.tracking_confidence = tracking_confidence
        
        self._landmarker = None
        self._last_result = None
        self._init_mediapipe()
        
        logger.info("GestureEngine initialized with MediaPipe Tasks API")

    def _init_mediapipe(self):
        """Initialize MediaPipe Hand Landmarker."""
        if not TASKS_AVAILABLE:
            return
            
        try:
            # Resolve model path
            base_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(base_dir, "models", "hand_landmarker.task")
            
            if not os.path.exists(model_path):
                logger.error(f"Model file not found: {model_path}")
                return

            base_options = mp_python.BaseOptions(model_asset_path=model_path)
            options = mp_vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=mp_vision.RunningMode.VIDEO,
                num_hands=self.max_hands,
                min_hand_detection_confidence=self.detection_confidence,
                min_hand_presence_confidence=self.detection_confidence,
                min_tracking_confidence=self.tracking_confidence
            )
            self._landmarker = mp_vision.HandLandmarker.create_from_options(options)
        except Exception as e:
            logger.error(f"Failed to initialize MediaPipe Tasks: {e}")

    def is_available(self) -> bool:
        return self._landmarker is not None

    def process_frame(self, frame: Any) -> GestureResult:
        """
        Process a single BGR frame.
        Returns a GestureResult object.
        """
        if not self._landmarker:
            return GestureResult()

        try:
            h, w, _ = frame.shape
            # Convert OpenCV frame to MediaPipe Image
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            
            # Process in VIDEO mode (needs timestamp)
            timestamp_ms = int(time.time() * 1000)
            result = self._landmarker.detect_for_video(mp_image, timestamp_ms)
            
            if result.hand_landmarks:
                # For now, we simplify to the first hand detected to match single result expectation
                landmarks = result.hand_landmarks[0]
                gesture, confidence = self.classify_gesture(landmarks)
                
                # Spatial Computing pointer abstraction
                pointer_x = landmarks[INDEX_TIP].x
                pointer_y = landmarks[INDEX_TIP].y
                
                # Calculate grab/pinch state
                thumb_x, thumb_y = landmarks[THUMB_TIP].x, landmarks[THUMB_TIP].y
                import math
                pinch_dist = math.hypot(pointer_x - thumb_x, pointer_y - thumb_y)
                
                if pinch_dist < 0.05:
                    gesture = GESTURE_PINCH_HOLD
                    # Adjust cursor center for realistic drag feel
                    pointer_x = (pointer_x + thumb_x) / 2
                    pointer_y = (pointer_y + thumb_y) / 2
                
                return GestureResult(
                    gesture=gesture,
                    confidence=confidence,
                    hand_count=len(result.hand_landmarks),
                    landmarks=landmarks,
                    frame_size=(w, h),
                    pointer_x=pointer_x,
                    pointer_y=pointer_y,
                    pinch_distance=pinch_dist
                )
            
            return GestureResult(frame_size=(w, h))
            
        except Exception as e:
            logger.error(f"Gesture processing error: {e}")
            return GestureResult()

    def annotate_frame(self, frame: Any, result: GestureResult) -> Any:
        """Draw landmarks on the frame."""
        if not result.landmarks:
            return frame
            
        annotated = frame.copy()
        self._draw_landmarks(annotated, result.landmarks)
        
        # Add text overlay for gesture
        if result.gesture != GESTURE_NONE:
            cv2.putText(
                annotated, f"GESTURE: {result.gesture} ({int(result.confidence*100)}%)",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
            )
        
        return annotated

    def encode_frame_jpeg(self, frame: Any, quality: int = 70) -> Optional[bytes]:
        """Encode frame to JPEG for streaming."""
        try:
            _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            return buffer.tobytes()
        except Exception as e:
            logger.error(f"JPEG encoding error: {e}")
            return None

    def classify_gesture(self, landmarks) -> Tuple[str, float]:
        """Classify landmarks into a gesture."""
        if not landmarks:
            return GESTURE_NONE, 0.0

        # Create a simplified index-based lookup for readability
        l = {i: landmarks[i] for i in range(21)}
        
        # 1. Open Palm (All fingers extended)
        fingers = self._get_finger_states(l)
        if all(fingers.values()):
            return GESTURE_OPEN_PALM, 0.95
            
        # 2. Fist (All fingers closed)
        if not any(fingers.values()):
            return GESTURE_FIST, 0.95
            
        # 3. Pointing (Only index extended)
        if fingers["index"] and not fingers["middle"] and not fingers["ring"] and not fingers["pinky"]:
            return GESTURE_POINTING, 0.9
            
        # 4. Peace Sign (Index and Middle extended)
        if fingers["index"] and fingers["middle"] and not fingers["ring"] and not fingers["pinky"]:
            return GESTURE_PEACE, 0.9

        # 5. Thumbs Up (Only thumb extended, and higher than WRIST)
        if fingers["thumb"] and not any([fingers["index"], fingers["middle"], fingers["ring"], fingers["pinky"]]):
            if l[THUMB_TIP].y < l[WRIST].y:
                return GESTURE_THUMBS_UP, 0.85
            else:
                return GESTURE_THUMBS_DOWN, 0.85

        return GESTURE_NONE, 0.0

    def _get_finger_states(self, l) -> Dict[str, bool]:
        """Determine if fingers are extended."""
        return {
            "thumb": self._thumb_is_extended(l),
            "index": self._finger_is_extended(l, INDEX_TIP, INDEX_PIP, INDEX_MCP),
            "middle": self._finger_is_extended(l, MIDDLE_TIP, MIDDLE_PIP, MIDDLE_MCP),
            "ring": self._finger_is_extended(l, RING_TIP, RING_PIP, RING_MCP),
            "pinky": self._finger_is_extended(l, PINKY_TIP, PINKY_PIP, PINKY_MCP),
        }

    def _finger_is_extended(self, l, tip, pip, mcp) -> bool:
        """Check if a finger is extended by comparing Y coordinates."""
        # Simple Y check (top of image is 0)
        return l[tip].y < l[pip].y < l[mcp].y

    def _thumb_is_extended(self, l) -> bool:
        """Special check for thumb extension."""
        # Horizontal difference between tip and MCP
        return abs(l[THUMB_TIP].x - l[THUMB_MCP].x) > 0.05

    def _draw_landmarks(self, frame, landmarks):
        """Manual drawing of hand skeleton overlay."""
        h, w, _ = frame.shape
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4), # Thumb
            (0, 5), (5, 6), (6, 7), (7, 8), # Index
            (5, 9), (9, 10), (10, 11), (11, 12), # Middle
            (9, 13), (13, 14), (14, 15), (15, 16), # Ring
            (13, 17), (17, 18), (18, 19), (19, 20), (0, 17) # Pinky
        ]
        
        # Draw lines in Cyan
        for start_idx, end_idx in connections:
            start = landmarks[start_idx]
            end = landmarks[end_idx]
            pt1 = (int(start.x * w), int(start.y * h))
            pt2 = (int(end.x * w), int(end.y * h))
            cv2.line(frame, pt1, pt2, (212, 182, 6), 2, cv2.LINE_AA)
            
        # Draw dots in Glowing Cyan
        for lm in landmarks:
            pt = (int(lm.x * w), int(lm.y * h))
            cv2.circle(frame, pt, 4, (238, 211, 34), -1, cv2.LINE_AA)
