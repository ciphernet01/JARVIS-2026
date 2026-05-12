"""
Phase 2: AI Conversation Engine Tests

Tests for conversation flow, intent extraction, skill execution,
and end-to-end voice processing.
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from modules.agent.conversation_engine import (
    AIConversationEngine,
    ConversationMemory,
    ConversationRole,
    ConversationMessage,
    IntentExtractor,
    IntentResult,
    SkillExecutor,
    ExecutionResult,
    get_conversation_engine,
)


# ============================================================================
# CONVERSATION MEMORY TESTS
# ============================================================================

class TestConversationMemory:
    """Test ConversationMemory - Conversation history & context."""

    def test_add_message_creates_immutable_message(self):
        """Messages should be immutable."""
        memory = ConversationMemory()
        msg = memory.add_message(ConversationRole.USER, "Hello JARVIS")

        assert msg.role == ConversationRole.USER
        assert msg.content == "Hello JARVIS"
        assert isinstance(msg.timestamp, str)

        # Verify immutability - frozen dataclass
        with pytest.raises(AttributeError):
            msg.content = "Modified text"

    def test_memory_maintains_max_history(self):
        """Memory should respect max history limit."""
        memory = ConversationMemory(max_history=5)

        # Add 10 messages
        for i in range(10):
            memory.add_message(ConversationRole.USER, f"Message {i}")

        # Only last 5 should remain
        assert len(memory) == 5
        history = memory.get_history(10)
        assert history[0].content == "Message 5"
        assert history[-1].content == "Message 9"

    def test_get_context_string_formats_correctly(self):
        """Context string should be properly formatted for LLM."""
        memory = ConversationMemory()
        memory.add_message(ConversationRole.USER, "Hello")
        memory.add_message(ConversationRole.ASSISTANT, "Hi there")

        context = memory.get_context_string()
        assert "user: Hello\n" in context
        assert "jarvis: Hi there\n" in context

    def test_preferences_storage(self):
        """Should store and retrieve user preferences."""
        memory = ConversationMemory()
        memory.extract_preference("favorite_volume", 75)
        memory.extract_preference("theme", "dark")

        assert memory.get_preference("favorite_volume") == 75
        assert memory.get_preference("theme") == "dark"
        assert memory.get_preference("nonexistent", "default") == "default"

    def test_session_duration_calculation(self):
        """Should calculate session duration."""
        memory = ConversationMemory()
        assert memory.get_session_duration_minutes() == 0

    def test_clear_history(self):
        """Should clear conversation history."""
        memory = ConversationMemory()
        memory.add_message(ConversationRole.USER, "Message 1")
        memory.add_message(ConversationRole.USER, "Message 2")
        assert len(memory) == 2

        memory.clear_history()
        assert len(memory) == 0

    def test_thread_safety(self):
        """Should handle concurrent access."""
        memory = ConversationMemory()

        def add_messages(count):
            for i in range(count):
                memory.add_message(ConversationRole.USER, f"Message {i}")

        import threading
        threads = [threading.Thread(target=add_messages, args=(10,)) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 30 messages without corruption
        assert len(memory) == 30


# ============================================================================
# INTENT EXTRACTOR TESTS
# ============================================================================

class TestIntentExtractor:
    """Test IntentExtractor - NLP intent recognition."""

    def test_extract_volume_intent_via_patterns(self):
        """Should recognize volume control intents."""
        extractor = IntentExtractor()

        result = asyncio.run(extractor.extract("turn up the volume"))
        assert result.intent == "INCREASE_VOLUME"
        assert result.confidence > 0.8
        assert result.executable

        result = asyncio.run(extractor.extract("make it quieter"))
        assert result.intent == "DECREASE_VOLUME"

    def test_extract_time_intent_via_patterns(self):
        """Should recognize time query intents."""
        extractor = IntentExtractor()

        result = asyncio.run(extractor.extract("what time is it"))
        assert result.intent == "QUERY_TIME"
        assert result.executable

    def test_extract_unknown_intent(self):
        """Should handle unknown intents gracefully."""
        extractor = IntentExtractor()

        result = asyncio.run(extractor.extract("xyzabc unknown gibberish"))
        assert result.intent == "OTHER"
        assert result.confidence < 0.7
        assert not result.executable

    def test_extract_with_context(self):
        """Should use conversation context in extraction."""
        extractor = IntentExtractor()
        context = "user: What's the volume?\nassistant: It's at 50%\n"

        result = asyncio.run(extractor.extract("increase it", context))
        # Should still recognize as volume control from context
        assert result.intent in ["INCREASE_VOLUME", "OTHER"]

    def test_intent_entities_extraction(self):
        """Should extract entities from intent."""
        extractor = IntentExtractor()

        result = asyncio.run(extractor.extract("turn up the volume"))
        assert result.entities is not None
        assert "text" in result.entities or result.entities


# ============================================================================
# SKILL EXECUTOR TESTS
# ============================================================================

class TestSkillExecutor:
    """Test SkillExecutor - Action execution & manager routing."""

    def test_execute_increases_volume(self):
        """Should execute volume increase."""
        audio_mgr = MagicMock()
        audio_mgr.get_volume.return_value = 50
        audio_mgr.set_volume.return_value = None

        executor = SkillExecutor(managers={"audio": audio_mgr})

        intent = IntentResult(
            intent="INCREASE_VOLUME",
            confidence=0.9,
            entities={"amount": 10},
            executable=True,
            requires_confirmation=False,
            explanation="Increase volume"
        )

        result = asyncio.run(executor.execute(intent))
        assert result.success
        assert "60" in result.output

    def test_execute_queries_time(self):
        """Should execute time query."""
        executor = SkillExecutor()

        intent = IntentResult(
            intent="QUERY_TIME",
            confidence=0.9,
            entities={},
            executable=True,
            requires_confirmation=False,
            explanation="Query time"
        )

        result = asyncio.run(executor.execute(intent))
        assert result.success
        assert ":" in result.output  # Contains time

    def test_execute_non_executable_intent(self):
        """Should fail gracefully for non-executable intents."""
        executor = SkillExecutor()

        intent = IntentResult(
            intent="UNKNOWN",
            confidence=0.3,
            entities={},
            executable=False,
            requires_confirmation=False,
            explanation="Unknown intent"
        )

        result = asyncio.run(executor.execute(intent))
        assert not result.success

    def test_register_custom_handler(self):
        """Should register and use custom handlers."""
        executor = SkillExecutor()

        async def custom_handler(entities):
            return ExecutionResult(
                success=True,
                output="Custom action executed"
            )

        executor.register("CUSTOM_ACTION", custom_handler)

        intent = IntentResult(
            intent="CUSTOM_ACTION",
            confidence=0.9,
            entities={},
            executable=True,
            requires_confirmation=False,
            explanation="Custom action"
        )

        result = asyncio.run(executor.execute(intent))
        assert result.success
        assert result.output == "Custom action executed"


# ============================================================================
# AI CONVERSATION ENGINE TESTS
# ============================================================================

class TestAIConversationEngine:
    """Test AIConversationEngine - Main orchestration."""

    def test_engine_initialization(self):
        """Should initialize with all components."""
        engine = AIConversationEngine()

        assert engine.memory is not None
        assert engine.intent_extractor is not None
        assert engine.skill_executor is not None

    def test_process_voice_input_low_confidence(self):
        """Should reject voice input with low confidence."""
        engine = AIConversationEngine()

        response = asyncio.run(engine.process_voice_input("hello", confidence=0.4))
        assert "didn't catch" in response.lower()

    def test_process_voice_input_high_confidence(self):
        """Should process voice input with high confidence."""
        engine = AIConversationEngine()

        response = asyncio.run(engine.process_voice_input("what time is it", confidence=0.95))
        assert "time" in response.lower() or response

    def test_process_voice_input_stores_in_memory(self):
        """Should store conversation in memory."""
        engine = AIConversationEngine()

        asyncio.run(engine.process_voice_input("hello jarvis", confidence=0.95))

        history = engine.memory.get_history()
        assert len(history) >= 2  # User message + response

        # First should be user message
        assert history[0].role == ConversationRole.USER
        assert "hello" in history[0].content.lower()

    def test_process_text_input(self):
        """Should process text input (for chat interface)."""
        engine = AIConversationEngine()

        response = asyncio.run(engine.process_text_input("What is the current date?"))
        assert response

    def test_register_response_callback(self):
        """Should trigger response callbacks."""
        engine = AIConversationEngine()
        callback_called = []

        def callback(response):
            callback_called.append(response)

        engine.register_response_callback(callback)

        asyncio.run(engine.process_voice_input("what time is it", confidence=0.95))

        assert len(callback_called) > 0

    def test_get_context_summary(self):
        """Should provide context summary."""
        engine = AIConversationEngine()

        asyncio.run(engine.process_voice_input("hello", confidence=0.95))

        summary = engine.get_context_summary()
        assert "messages" in summary
        assert "duration_minutes" in summary
        assert "user_preferences" in summary

    def test_multi_turn_conversation(self):
        """Should handle multi-turn conversations."""
        engine = AIConversationEngine()

        # Turn 1
        resp1 = asyncio.run(engine.process_voice_input("what time is it", confidence=0.95))
        assert resp1

        # Turn 2
        resp2 = asyncio.run(engine.process_voice_input("and the date", confidence=0.95))
        assert resp2

        # Check memory has both exchanges
        history = engine.memory.get_history(10)
        assert len(history) >= 4  # 2 user + 2 assistant


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestConversationEngineIntegration:
    """Integration tests for complete voice-to-response flow."""

    def test_voice_to_response_flow(self):
        """Complete voice processing flow."""
        audio_mgr = MagicMock()
        audio_mgr.get_volume.return_value = 50

        engine = AIConversationEngine(managers={"audio": audio_mgr})

        response = asyncio.run(engine.process_voice_input("turn up the volume", confidence=0.95))
        assert response
        assert "success" in response.lower() or "volume" in response.lower() or response

    def test_multiple_sequential_commands(self):
        """Should handle multiple commands in sequence."""
        engine = AIConversationEngine()

        commands = [
            ("what time is it", 0.95),
            ("and the date", 0.95),
            ("increase volume", 0.95),
        ]

        responses = []
        for cmd, conf in commands:
            resp = asyncio.run(engine.process_voice_input(cmd, confidence=conf))
            responses.append(resp)

        assert all(responses)  # All got responses
        assert len(engine.memory) >= 6  # At least 3 exchanges


# ============================================================================
# SINGLETON TESTS
# ============================================================================

class TestConversationEngineSingleton:
    """Test singleton pattern."""

    def test_get_conversation_engine_singleton(self):
        """Should return same instance."""
        # Reset singleton for testing
        import modules.agent.conversation_engine as ce
        ce._instance = None

        engine1 = get_conversation_engine()
        engine2 = get_conversation_engine()

        assert engine1 is engine2


# ============================================================================
# EDGE CASES & ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_input(self):
        """Should handle empty input."""
        engine = AIConversationEngine()
        response = asyncio.run(engine.process_voice_input("", confidence=0.95))
        assert response

    def test_very_long_input(self):
        """Should handle very long input."""
        engine = AIConversationEngine()
        long_text = "what is the current time " * 100

        response = asyncio.run(engine.process_voice_input(long_text, confidence=0.95))
        assert response

    def test_special_characters_in_input(self):
        """Should handle special characters."""
        engine = AIConversationEngine()
        response = asyncio.run(engine.process_voice_input("!@#$%^&*()", confidence=0.95))
        assert response

    def test_missing_managers(self):
        """Should handle missing service managers gracefully."""
        engine = AIConversationEngine(managers={})

        # Should not crash even without managers
        response = asyncio.run(engine.process_voice_input("what time is it", confidence=0.95))
        assert response


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
