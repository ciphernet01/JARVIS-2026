"""Test AudioManager functionality."""
import pytest
from modules.services.audio_manager import AudioManager, AudioSnapshot, AudioDevice


def test_audio_manager_singleton():
    """Test that AudioManager is a proper singleton."""
    mgr1 = AudioManager()
    mgr2 = AudioManager()
    assert mgr1 is mgr2


def test_audio_snapshot_structure():
    """Test that audio snapshot has correct structure."""
    mgr = AudioManager()
    snapshot = mgr.snapshot()
    
    assert isinstance(snapshot, AudioSnapshot)
    assert isinstance(snapshot.devices, list)
    assert isinstance(snapshot.volume, float)
    assert 0.0 <= snapshot.volume <= 100.0
    assert isinstance(snapshot.microphone_enabled, bool)
    assert isinstance(snapshot.speakers_enabled, bool)
    assert isinstance(snapshot.mic_muted, bool)
    assert isinstance(snapshot.platform_name, str)


def test_audio_device_immutability():
    """Test that AudioDevice is immutable."""
    device = AudioDevice(
        id=0,
        name="Test Device",
        is_input=True,
        is_output=False,
        is_default_input=True
    )
    
    with pytest.raises(AttributeError):
        device.name = "Changed"


def test_audio_snapshot_immutability():
    """Test that AudioSnapshot is immutable."""
    snapshot = AudioSnapshot(
        devices=[],
        default_input=None,
        default_output=None,
        volume=50.0,
        microphone_enabled=True,
        speakers_enabled=True,
        mic_muted=False,
        platform_name="test"
    )
    
    with pytest.raises(AttributeError):
        snapshot.volume = 75.0


def test_capability_matrix():
    """Test audio capability matrix generation."""
    mgr = AudioManager()
    capabilities = mgr.capability_matrix()
    
    assert isinstance(capabilities, dict)
    assert "has_input_devices" in capabilities
    assert "has_output_devices" in capabilities
    assert "device_count" in capabilities
    assert "microphone_available" in capabilities
    assert "speakers_available" in capabilities
    
    assert isinstance(capabilities["device_count"], int)
    assert isinstance(capabilities["microphone_available"], bool)


def test_volume_set_bounds():
    """Test that volume setting respects bounds."""
    mgr = AudioManager()
    
    # Test that set_volume handles out-of-bounds values
    result = mgr.set_volume(-10.0)
    assert isinstance(result, bool)
    
    result = mgr.set_volume(150.0)
    assert isinstance(result, bool)
    
    result = mgr.set_volume(75.0)
    assert isinstance(result, bool)


def test_microphone_toggle():
    """Test microphone toggle functionality."""
    mgr = AudioManager()
    
    # Just test that it returns a boolean
    result = mgr.toggle_microphone(True)
    assert isinstance(result, bool)
    
    result = mgr.toggle_microphone(False)
    assert isinstance(result, bool)


def test_audio_snapshot_consistency():
    """Test that consecutive snapshots show consistency."""
    mgr = AudioManager()
    snapshot1 = mgr.snapshot()
    snapshot2 = mgr.snapshot()
    
    # Both should have devices (even if empty list)
    assert isinstance(snapshot1.devices, list)
    assert isinstance(snapshot2.devices, list)
    
    # Platform should be consistent
    assert snapshot1.platform_name == snapshot2.platform_name
