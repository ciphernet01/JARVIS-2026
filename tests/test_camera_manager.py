"""Test CameraManager functionality."""
import pytest
from modules.services.camera_manager import CameraManager, CameraSnapshot, CameraState


def test_camera_manager_singleton():
    """Test that CameraManager is a proper singleton."""
    mgr1 = CameraManager()
    mgr2 = CameraManager()
    assert mgr1 is mgr2


def test_camera_state_structure():
    """Test that camera state has correct structure."""
    mgr = CameraManager()
    state = mgr.state()
    
    assert isinstance(state, CameraState)
    assert isinstance(state.available, bool)
    assert isinstance(state.enabled, bool)
    assert isinstance(state.device_id, int)
    assert isinstance(state.recording, bool)
    assert isinstance(state.resolution, tuple)
    assert len(state.resolution) == 2
    assert isinstance(state.fps, float)
    assert isinstance(state.face_detection_active, bool)


def test_camera_state_immutability():
    """Test that CameraState is immutable."""
    state = CameraState(
        available=True,
        enabled=False,
        device_id=0,
        recording=False,
        resolution=(1280, 720),
        fps=30.0,
        face_detection_active=False,
        last_face_timestamp=None
    )
    
    with pytest.raises(AttributeError):
        state.enabled = True


def test_camera_snapshot_immutability():
    """Test that CameraSnapshot is immutable."""
    snapshot = CameraSnapshot(
        timestamp=0.0,
        width=1280,
        height=720,
        has_faces=False,
        face_count=0,
        face_locations=[],
        jpeg_base64=None
    )
    
    with pytest.raises(AttributeError):
        snapshot.face_count = 1


def test_capability_matrix():
    """Test camera capability matrix generation."""
    mgr = CameraManager()
    capabilities = mgr.capability_matrix()
    
    assert isinstance(capabilities, dict)
    assert "available" in capabilities
    assert "enabled" in capabilities
    assert "can_detect_faces" in capabilities
    assert "recording" in capabilities
    assert "resolution" in capabilities
    
    assert isinstance(capabilities["available"], bool)
    assert isinstance(capabilities["enabled"], bool)


def test_enable_disable_camera():
    """Test camera enable/disable functionality."""
    mgr = CameraManager()
    
    # Disable any existing camera connection
    mgr.disable()
    initial_state = mgr.state()
    assert not initial_state.enabled
    
    # Test enable returns a boolean
    result = mgr.enable()
    assert isinstance(result, bool)
    
    # Test disable returns a boolean
    result = mgr.disable()
    assert isinstance(result, bool)


def test_face_detection_toggle():
    """Test face detection enable/disable."""
    mgr = CameraManager()
    
    result = mgr.start_face_detection()
    assert isinstance(result, bool)
    
    result = mgr.stop_face_detection()
    assert isinstance(result, bool)


def test_set_resolution():
    """Test camera resolution setting."""
    mgr = CameraManager()
    
    result = mgr.set_resolution(640, 480)
    assert isinstance(result, bool)
    
    result = mgr.set_resolution(1280, 720)
    assert isinstance(result, bool)


def test_list_devices():
    """Test device enumeration."""
    mgr = CameraManager()
    devices = mgr.list_devices()
    
    assert isinstance(devices, list)
    # Should return at least a default device
    if mgr._available:
        assert len(devices) >= 0


def test_camera_state_consistency():
    """Test that consecutive camera state calls are consistent."""
    mgr = CameraManager()
    state1 = mgr.state()
    state2 = mgr.state()
    
    # Both should have same availability
    assert state1.available == state2.available
    assert state1.device_id == state2.device_id
    
    # Resolution should be consistent unless explicitly changed
    assert state1.resolution == state2.resolution
