"""
JARVIS Vision-to-OS Bridge
Maps hand gestures to system-level mouse and keyboard actions.
"""

import logging
import threading
from typing import Dict, Any, Optional

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

from modules.vision.gesture_engine import (
    GestureResult,
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_FIST,
    GESTURE_POINTING,
    GESTURE_THUMBS_UP,
    GESTURE_THUMBS_DOWN,
    GESTURE_PEACE,
    GESTURE_PINCH_HOLD
)

logger = logging.getLogger(__name__)

class VisionOSBridge:
    """Bridges gesture recognition with OS-level automation."""

    def __init__(self):
        self.screen_width, self.screen_height = (1920, 1080)
        if PYAUTOGUI_AVAILABLE:
            self.screen_width, self.screen_height = pyautogui.size()
            # Disable pause and failsafe to make it feel "zero-delay" and avoid accidental stops
            pyautogui.PAUSE = 0
            pyautogui.FAILSAFE = False

        self.last_pointer_x = 0.5
        self.last_pointer_y = 0.5
        self.is_dragging = False
        self._lock = threading.Lock()

        logger.info(f"VisionOSBridge initialized (Screen: {self.screen_width}x{self.screen_height})")

    def process_gesture(self, result: GestureResult):
        """Map a gesture result to an OS action."""
        if not PYAUTOGUI_AVAILABLE:
            return

        with self._lock:
            # 1. Update Pointer Position (Virtual Mouse)
            # Use exponential smoothing for jitter reduction
            alpha = 0.3
            self.last_pointer_x = (alpha * result.pointer_x) + ((1 - alpha) * self.last_pointer_x)
            self.last_pointer_y = (alpha * result.pointer_y) + ((1 - alpha) * self.last_pointer_y)

            target_x = int(self.last_pointer_x * self.screen_width)
            target_y = int(self.last_pointer_y * self.screen_height)

            # 2. Map Gestures to Actions
            gesture = result.gesture

            # PINCH = Drag / Mouse Down
            if gesture == GESTURE_PINCH_HOLD:
                if not self.is_dragging:
                    pyautogui.mouseDown(target_x, target_y)
                    self.is_dragging = True
                    logger.debug("Gesture: Drag Start")
                else:
                    pyautogui.moveTo(target_x, target_y)
            else:
                if self.is_dragging:
                    pyautogui.mouseUp(target_x, target_y)
                    self.is_dragging = False
                    logger.debug("Gesture: Drag End")

                # POINTING = Move Mouse
                if gesture == GESTURE_POINTING:
                    pyautogui.moveTo(target_x, target_y)

                # FIST = Left Click (only trigger if it was pointing before or just transitioned)
                # For simplicity, let's say FIST always clicks at current location
                elif gesture == GESTURE_FIST:
                    pyautogui.click(target_x, target_y)
                    logger.debug("Gesture: Click")

                # PEACE = Right Click
                elif gesture == GESTURE_PEACE:
                    pyautogui.rightClick(target_x, target_y)
                    logger.debug("Gesture: Right Click")

                # THUMBS_UP = Confirm (Enter key)
                elif gesture == GESTURE_THUMBS_UP:
                    pyautogui.press('enter')
                    logger.debug("Gesture: Enter")

                # THUMBS_DOWN = Cancel (Escape key)
                elif gesture == GESTURE_THUMBS_DOWN:
                    pyautogui.press('esc')
                    logger.debug("Gesture: Escape")
