import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from modules.vision.gesture_engine import GestureEngine, GESTURE_NONE, GESTURE_OPEN_PALM, GESTURE_FIST

class TestGestureEngine(unittest.TestCase):
    def setUp(self):
        # Mocking MediaPipe submodules as they are imported in gesture_engine.py
        with patch('modules.vision.gesture_engine.mp_hands'), \
             patch('modules.vision.gesture_engine.mp_drawing'), \
             patch('cv2.VideoCapture'):
            self.engine = GestureEngine()

    def test_initialization(self):
        self.assertEqual(self.engine.max_hands, 2)
        self.assertEqual(self.engine.detection_confidence, 0.7)

    def test_is_available_returns_bool(self):
        # Mocking existence of dependencies
        with patch('modules.vision.gesture_engine.cv2', MagicMock()), \
             patch('modules.vision.gesture_engine.mp_hands', MagicMock()):
            self.engine._hands = MagicMock()
            self.assertTrue(self.engine.is_available())

    def test_finger_extension_logic(self):
        tip = MagicMock()
        tip.y = 0.1
        pip = MagicMock()
        pip.y = 0.5
        mcp = MagicMock()
        mcp.y = 0.7
        
        landmarks = {8: tip, 6: pip, 5: mcp} # INDEX_TIP, INDEX_PIP, INDEX_MCP
        self.assertTrue(self.engine._finger_is_extended(landmarks, 8, 6, 5))
        
        tip.y = 0.8
        self.assertFalse(self.engine._finger_is_extended(landmarks, 8, 6, 5))

    def test_classify_gesture_no_landmarks(self):
        gesture, confidence = self.engine.classify_gesture(None)
        self.assertEqual(gesture, GESTURE_NONE)
        self.assertEqual(confidence, 0.0)

    @patch('modules.vision.gesture_engine.GestureEngine._get_finger_states')
    def test_classify_open_palm(self, mock_states):
        mock_states.return_value = {
            "thumb": True, "index": True, "middle": True, "ring": True, "pinky": True
        }
        landmarks = [MagicMock()] * 21
        gesture, confidence = self.engine.classify_gesture(landmarks)
        self.assertEqual(gesture, GESTURE_OPEN_PALM)
        self.assertGreater(confidence, 0.9)

if __name__ == '__main__':
    unittest.main()
