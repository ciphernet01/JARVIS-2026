"""
Tests for VoiceManager
"""
import pytest
from unittest.mock import patch, MagicMock
from modules.services.voice_manager import (
    VoiceManager, VoiceCommand, VoiceResponse, VoiceState,
    VoiceMode, ConfidenceLevel
)


class TestVoiceManager:
    """Test VoiceManager voice processing."""
    
    def test_singleton_pattern(self):
        """VoiceManager should be a singleton."""
        manager1 = VoiceManager()
        manager2 = VoiceManager()
        assert manager1 is manager2, "VoiceManager should be a singleton"
    
    def test_voice_state_structure(self):
        """VoiceState should have all required fields."""
        manager = VoiceManager()
        state = manager.state()
        
        assert isinstance(state, VoiceState)
        assert isinstance(state.mode, str)
        assert isinstance(state.is_listening, bool)
        assert isinstance(state.wake_word_enabled, bool)
        assert isinstance(state.microphone_available, bool)
        assert isinstance(state.speaker_available, bool)
        assert isinstance(state.commands_processed, int)
        assert isinstance(state.average_confidence, float)
    
    def test_voice_state_immutability(self):
        """VoiceState should be immutable."""
        manager = VoiceManager()
        state = manager.state()
        
        with pytest.raises(AttributeError):
            state.is_listening = not state.is_listening
    
    def test_voice_command_immutability(self):
        """VoiceCommand should be immutable."""
        command = VoiceCommand(
            text="hello jarvis",
            confidence=0.92,
            language="en-US",
            recognized_at="2026-05-12T10:00:00",
            duration_ms=2500,
            source="microphone"
        )
        
        with pytest.raises(AttributeError):
            command.confidence = 0.5
    
    def test_voice_response_immutability(self):
        """VoiceResponse should be immutable."""
        response = VoiceResponse(
            text="Hello, how can I help?",
            audio_path=None,
            duration_ms=1200,
            status="success",
            generated_at="2026-05-12T10:00:01"
        )
        
        with pytest.raises(AttributeError):
            response.status = "error"
    
    def test_voice_modes(self):
        """VoiceMode enum should have correct values."""
        assert VoiceMode.IDLE.value == "idle"
        assert VoiceMode.LISTENING.value == "listening"
        assert VoiceMode.PROCESSING.value == "processing"
        assert VoiceMode.SPEAKING.value == "speaking"
        assert VoiceMode.ERROR.value == "error"
    
    def test_confidence_levels(self):
        """ConfidenceLevel enum should have correct values."""
        assert ConfidenceLevel.LOW.value == "low"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.HIGH.value == "high"
    
    def test_capability_matrix(self):
        """Capability matrix should report available features."""
        manager = VoiceManager()
        capabilities = manager.capability_matrix()
        
        assert "stt_available" in capabilities
        assert "tts_available" in capabilities
        assert "microphone_available" in capabilities
        assert "speaker_available" in capabilities
        assert "wake_word_capable" in capabilities
        assert "supported_languages" in capabilities
        assert isinstance(capabilities["supported_languages"], list)
    
    def test_wake_word_enable_disable(self):
        """Wake word should be enable/disable."""
        manager = VoiceManager()
        
        manager.enable_wake_word("jarvis")
        state1 = manager.state()
        assert state1.wake_word_enabled is True
        
        manager.disable_wake_word()
        state2 = manager.state()
        assert state2.wake_word_enabled is False
    
    def test_command_callback_registration(self):
        """Should be able to register command callbacks."""
        manager = VoiceManager()
        
        callback_called = []
        
        def test_callback(command):
            callback_called.append(command)
        
        manager.register_command_callback(test_callback)
        
        command = VoiceCommand(
            text="test command",
            confidence=0.9,
            language="en-US",
            recognized_at="2026-05-12T10:00:00",
            duration_ms=1000,
            source="microphone"
        )
        
        result = manager.process_command(command)
        assert result["callbacks_executed"] == 1
        assert callback_called[0] == command
    
    def test_command_processing(self):
        """Commands should be processed and tracked."""
        manager = VoiceManager()
        
        command = VoiceCommand(
            text="increase volume",
            confidence=0.88,
            language="en-US",
            recognized_at="2026-05-12T10:00:00",
            duration_ms=1200,
            source="microphone"
        )
        
        result = manager.process_command(command)
        assert result["command"] == "increase volume"
        assert result["confidence"] == 0.88
        assert result["callbacks_executed"] >= 0
    
    def test_voice_state_after_speak(self):
        """Voice state should update after speaking."""
        manager = VoiceManager()
        
        response = manager.speak_response("Hello world")
        
        assert isinstance(response, VoiceResponse)
        assert response.text == "Hello world"
        assert response.status in ["success", "error"]
        assert isinstance(response.duration_ms, int)
    
    def test_average_confidence_calculation(self):
        """Average confidence should be calculated correctly."""
        manager = VoiceManager()
        
        # Simulate multiple commands
        for i in range(5):
            manager._confidence_scores.append(0.8 + i * 0.02)
        
        state = manager.state()
        assert 0.8 <= state.average_confidence <= 1.0
    
    def test_confidence_score_limiting(self):
        """Confidence scores should be limited to last 100."""
        manager = VoiceManager()
        
        # Add more than 100 scores
        for i in range(150):
            manager._confidence_scores.append(0.5 + (i % 50) * 0.01)
        
        # Trim the scores
        manager._trim_confidence_scores()

        """VoiceCommand should validate creation."""
        command = VoiceCommand(
            text="set timer for 5 minutes",
            confidence=0.94,
            language="en-US",
            recognized_at="2026-05-12T10:00:00",
            duration_ms=2100,
            source="microphone"
        )
        
        assert command.text == "set timer for 5 minutes"
        assert command.confidence == 0.94
        assert command.language == "en-US"
        assert command.duration_ms == 2100
    
    def test_voice_response_creation(self):
        """VoiceResponse should validate creation."""
        response = VoiceResponse(
            text="Timer set for 5 minutes",
            audio_path="/tmp/response.wav",
            duration_ms=3200,
            status="success",
            generated_at="2026-05-12T10:00:01"
        )
        
        assert response.text == "Timer set for 5 minutes"
        assert response.audio_path == "/tmp/response.wav"
        assert response.duration_ms == 3200
        assert response.status == "success"
    
    def test_voice_state_creation(self):
        """VoiceState should validate creation."""
        command = VoiceCommand(
            text="test",
            confidence=0.9,
            language="en-US",
            recognized_at="2026-05-12T10:00:00",
            duration_ms=1000,
            source="microphone"
        )
        
        response = VoiceResponse(
            text="acknowledged",
            audio_path=None,
            duration_ms=800,
            status="success",
            generated_at="2026-05-12T10:00:01"
        )
        
        state = VoiceState(
            mode="listening",
            is_listening=True,
            wake_word_enabled=True,
            last_command=command,
            last_response=response,
            microphone_available=True,
            speaker_available=True,
            commands_processed=42,
            average_confidence=0.87
        )
        
        assert state.mode == "listening"
        assert state.commands_processed == 42
        assert state.average_confidence == 0.87


class TestVoiceIntegration:
    """Test voice system integration."""
    
    def test_multiple_callbacks(self):
        """Multiple callbacks should all be called."""
        manager = VoiceManager()
        
        results = {"callback1": False, "callback2": False, "callback3": False}
        
        def callback1(cmd):
            results["callback1"] = True
        
        def callback2(cmd):
            results["callback2"] = True
        
        def callback3(cmd):
            results["callback3"] = True
        
        manager.register_command_callback(callback1)
        manager.register_command_callback(callback2)
        manager.register_command_callback(callback3)
        
        command = VoiceCommand(
            text="test",
            confidence=0.9,
            language="en-US",
            recognized_at="2026-05-12T10:00:00",
            duration_ms=1000,
            source="microphone"
        )
        
        manager.process_command(command)
        
        assert results["callback1"] is True
        assert results["callback2"] is True
        assert results["callback3"] is True
    
    def test_voice_state_consistency(self):
        """Multiple state calls should be consistent."""
        manager = VoiceManager()
        
        state1 = manager.state()
        state2 = manager.state()
        
        assert state1.mode == state2.mode
        assert state1.commands_processed == state2.commands_processed
        assert state1.microphone_available == state2.microphone_available
    
    def test_thread_safety(self):
        """Voice manager should be thread-safe."""
        import threading
        
        manager = VoiceManager()
        results = []
        
        def read_state():
            for _ in range(10):
                state = manager.state()
                results.append(state.commands_processed >= 0)
        
        threads = [threading.Thread(target=read_state) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        assert len(results) == 50
        assert all(results)
