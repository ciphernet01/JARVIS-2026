import unittest
from unittest.mock import MagicMock, patch
import json
import os
from pathlib import Path
from modules.services.gesture_manager import GestureManager, GESTURE_OPEN_PALM, GESTURE_FIST

class TestGestureManager(unittest.TestCase):
    def setUp(self):
        self.workspace = Path("/tmp/jarvis_test_workspace")
        self.workspace.mkdir(parents=True, exist_ok=True)
        # Mock GestureEngine to avoid MP/CV dependency
        with patch('modules.services.gesture_manager.GestureEngine'):
            self.manager = GestureManager(workspace_root=str(self.workspace))

    def tearDown(self):
        # Cleanup test workspace
        import shutil
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def test_initialization(self):
        self.assertFalse(self.manager.is_active())
        self.assertEqual(len(self.manager.get_action_map()), 8)

    def test_load_save_action_map(self):
        # Update a mapping
        update = {
            GESTURE_FIST: {
                "action": "test_action",
                "label": "Test Label",
                "description": "Test Desc"
            }
        }
        self.manager.update_action_map(update)
        
        # Verify it persisted
        map_path = self.workspace / "memory" / "gesture" / "action_map.json"
        self.assertTrue(map_path.exists())
        
        # Load in new manager
        with patch('modules.services.gesture_manager.GestureEngine'):
            new_manager = GestureManager(workspace_root=str(self.workspace))
            self.assertEqual(new_manager.get_action_map()[GESTURE_FIST]["action"], "test_action")

    @patch('cv2.VideoCapture')
    def test_start_stop_lifecycle(self, mock_vc):
        mock_vc.return_value.isOpened.return_value = True
        
        with patch('modules.services.gesture_manager.GestureEngine.is_available', return_value=True):
            # Start
            result = self.manager.start()
            self.assertEqual(result["status"], "started")
            self.assertTrue(self.manager.is_active())
            
            # Stop
            result = self.manager.stop()
            self.assertEqual(result["status"], "stopped")
            self.assertFalse(self.manager.is_active())

    def test_process_gesture_event_trigger(self):
        # Setup callback
        mock_callback = MagicMock()
        self.manager.register_action_callback("toggle_terminal", mock_callback)
        
        # Simulate gist gesture result for 3 frames
        from modules.vision.gesture_engine import GestureResult
        res = GestureResult(gesture=GESTURE_FIST, confidence=0.9, hand_count=1)
        
        self.manager._process_gesture_event(res) # Frame 1
        self.manager._process_gesture_event(res) # Frame 2
        self.manager._process_gesture_event(res) # Frame 3 (Should trigger)
        
        mock_callback.assert_called_once()
        self.assertEqual(len(self.manager.recent_events()), 1)

if __name__ == '__main__':
    unittest.main()
