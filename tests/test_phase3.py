"""Phase 3 Tests: Voice history, conversation context, and performance monitoring."""

import time
import pytest

from modules.agent.voice_history import (
    VoiceHistoryManager,
    CommandStatus,
    get_voice_history_manager,
)
from modules.agent.conversation_context import (
    ConversationContextManager,
    ConversationSessionManager,
    get_session_manager,
)
from modules.agent.performance_monitor import (
    PerformanceMonitor,
    get_performance_monitor,
)


# ============================================================================
# VOICE HISTORY MANAGER TESTS
# ============================================================================

class TestVoiceHistoryManager:
    """Test voice history tracking."""

    def test_add_entry_creates_immutable_record(self):
        """Should create immutable history entry."""
        manager = VoiceHistoryManager()
        entry = manager.add_entry("hello", "hi there", 0.95)

        assert entry.command_text == "hello"
        assert entry.response_text == "hi there"
        assert entry.confidence == 0.95
        assert entry.status == CommandStatus.EXECUTED

    def test_history_maintains_max_size(self):
        """Should maintain maximum history size."""
        manager = VoiceHistoryManager(max_entries=10)

        for i in range(20):
            manager.add_entry(f"command {i}", f"response {i}", 0.85)

        assert len(manager) == 10

    def test_get_history_returns_snapshot(self):
        """Should return immutable history snapshot."""
        manager = VoiceHistoryManager()
        manager.add_entry("cmd1", "resp1", 0.9)
        manager.add_entry("cmd2", "resp2", 0.85)

        history = manager.get_history(num_entries=5)
        assert len(history) == 2
        assert history[0].command_text == "cmd1"

    def test_get_recent_commands_for_suggestions(self):
        """Should return recent commands for UI suggestions."""
        manager = VoiceHistoryManager()
        manager.add_entry("open notepad", "opening", 0.9)
        manager.add_entry("set timer", "setting", 0.85)
        manager.add_entry("what time", "time is", 0.95)

        recent = manager.get_recent_commands(2)
        assert "set timer" in recent
        assert "what time" in recent

    def test_success_rate_calculation(self):
        """Should calculate success rate correctly."""
        manager = VoiceHistoryManager()
        manager.add_entry("cmd1", "success", 0.9, CommandStatus.EXECUTED)
        manager.add_entry("cmd2", "fail", 0.5, CommandStatus.FAILED)
        manager.add_entry("cmd3", "success", 0.9, CommandStatus.EXECUTED)

        rate = manager.get_success_rate()
        assert abs(rate - 0.666) < 0.01  # ~67%

    def test_average_latency_calculation(self):
        """Should calculate average latency."""
        manager = VoiceHistoryManager()
        manager.add_entry("cmd1", "resp", 0.9, duration_ms=100)
        manager.add_entry("cmd2", "resp", 0.9, duration_ms=200)
        manager.add_entry("cmd3", "resp", 0.9, duration_ms=300)

        avg = manager.get_average_latency()
        assert avg == 200.0

    def test_average_confidence_calculation(self):
        """Should calculate average confidence."""
        manager = VoiceHistoryManager()
        manager.add_entry("cmd1", "resp", 0.8)
        manager.add_entry("cmd2", "resp", 0.9)
        manager.add_entry("cmd3", "resp", 1.0)

        avg = manager.get_average_confidence()
        assert abs(avg - 0.9) < 0.01

    def test_export_json(self):
        """Should export history as JSON."""
        manager = VoiceHistoryManager()
        manager.add_entry("hello", "hi", 0.95)

        json_str = manager.export_json()
        assert "hello" in json_str
        assert "hi" in json_str

    def test_get_stats_summary(self):
        """Should return comprehensive stats."""
        manager = VoiceHistoryManager()
        for i in range(5):
            manager.add_entry(f"cmd{i}", f"resp{i}", 0.9, CommandStatus.EXECUTED)

        stats = manager.get_stats()
        assert "total_entries" in stats
        assert "success_rate_overall" in stats
        assert "avg_latency_ms" in stats


# ============================================================================
# CONVERSATION CONTEXT TESTS
# ============================================================================

class TestConversationContextManager:
    """Test conversation context management."""

    def test_add_turn_creates_record(self):
        """Should record conversation turn."""
        ctx = ConversationContextManager("session_1")
        turn = ctx.add_turn("what time", "It's 3pm", intent="query_time")

        assert turn.user_input == "what time"
        assert turn.assistant_response == "It's 3pm"
        assert turn.intent == "query_time"

    def test_maintains_max_turns(self):
        """Should maintain max turn history."""
        ctx = ConversationContextManager("session_1", max_turns=5)

        for i in range(10):
            ctx.add_turn(f"cmd{i}", f"resp{i}")

        assert len(ctx) == 5

    def test_get_context_string_for_llm(self):
        """Should format context for LLM."""
        ctx = ConversationContextManager("session_1")
        ctx.add_turn("hello", "hi")
        ctx.add_turn("how are you", "I'm good")

        context = ctx.get_context_string(2)
        assert "User: hello" in context
        assert "Assistant: hi" in context

    def test_user_preferences_storage(self):
        """Should store discovered preferences."""
        ctx = ConversationContextManager("session_1")
        ctx.set_preference("language", "python")
        ctx.set_preference("theme", "dark")

        assert ctx.get_preference("language") == "python"
        assert ctx.get_preference("theme") == "dark"

    def test_session_duration_tracking(self):
        """Should calculate session duration."""
        ctx = ConversationContextManager("session_1")
        assert ctx.get_session_duration_minutes() == 0

    def test_get_summary(self):
        """Should return session summary."""
        ctx = ConversationContextManager("session_1")
        ctx.add_turn("cmd1", "resp1", intent="action")
        ctx.set_preference("user_name", "Alice")

        summary = ctx.get_summary()
        assert summary["session_id"] == "session_1"
        assert summary["turn_count"] == 1
        assert summary["user_preferences"]["user_name"] == "Alice"

    def test_clear_session(self):
        """Should clear session state."""
        ctx = ConversationContextManager("session_1")
        ctx.add_turn("cmd", "resp")
        ctx.set_preference("pref", "value")

        ctx.clear()
        assert len(ctx) == 0
        assert ctx.get_preference("pref") is None


class TestConversationSessionManager:
    """Test multi-session management."""

    def test_get_context_creates_session(self):
        """Should create context if not exists."""
        mgr = ConversationSessionManager()
        ctx1 = mgr.get_context("session_1")
        ctx2 = mgr.get_context("session_1")

        assert ctx1 is ctx2  # Same instance

    def test_manage_multiple_sessions(self):
        """Should manage multiple concurrent sessions."""
        mgr = ConversationSessionManager()
        ctx1 = mgr.get_context("session_1")
        ctx2 = mgr.get_context("session_2")

        ctx1.add_turn("cmd1", "resp1")
        ctx2.add_turn("cmd2", "resp2")

        assert len(ctx1) == 1
        assert len(ctx2) == 1

    def test_end_session(self):
        """Should end session and return summary."""
        mgr = ConversationSessionManager()
        ctx = mgr.get_context("session_1")
        ctx.add_turn("cmd", "resp")

        summary = mgr.end_session("session_1")
        assert summary["session_id"] == "session_1"
        assert summary["turn_count"] == 1

    def test_get_active_sessions(self):
        """Should list active sessions."""
        mgr = ConversationSessionManager()
        mgr.get_context("session_1")
        mgr.get_context("session_2")

        active = mgr.get_active_sessions()
        assert "session_1" in active
        assert "session_2" in active


# ============================================================================
# PERFORMANCE MONITOR TESTS
# ============================================================================

class TestPerformanceMonitor:
    """Test performance monitoring."""

    def test_measure_operation_duration(self):
        """Should measure operation duration."""
        monitor = PerformanceMonitor()
        monitor.start_operation("op_1")
        time.sleep(0.05)  # 50ms
        metric = monitor.end_operation("op_1", "test_op")

        assert metric is not None
        assert metric.duration_ms >= 50
        assert metric.operation == "test_op"
        assert metric.success

    def test_get_metrics_returns_snapshot(self):
        """Should return immutable metrics snapshot."""
        monitor = PerformanceMonitor()
        monitor.start_operation("op_1")
        time.sleep(0.01)
        monitor.end_operation("op_1", "op1")

        metrics = monitor.get_metrics()
        assert len(metrics) == 1

    def test_get_stats_aggregation(self):
        """Should aggregate stats correctly."""
        monitor = PerformanceMonitor()

        for i in range(5):
            monitor.start_operation(f"op_{i}")
            time.sleep(0.01)
            monitor.end_operation(f"op_{i}", "test_op", success=i < 4)

        stats = monitor.get_stats("test_op")
        assert stats["count"] == 5
        assert stats["success_rate"] == 0.8  # 4/5

    def test_operation_names_list(self):
        """Should list tracked operation names."""
        monitor = PerformanceMonitor()
        monitor.start_operation("op_1")
        monitor.end_operation("op_1", "voice_stt")
        monitor.start_operation("op_2")
        monitor.end_operation("op_2", "voice_tts")

        names = monitor.get_operation_names()
        assert "voice_stt" in names
        assert "voice_tts" in names

    def test_clear_metrics(self):
        """Should clear all metrics."""
        monitor = PerformanceMonitor()
        monitor.start_operation("op_1")
        monitor.end_operation("op_1", "test")

        assert len(monitor) == 1
        monitor.clear()
        assert len(monitor) == 0


# ============================================================================
# SINGLETON TESTS
# ============================================================================

class TestSingletons:
    """Test singleton pattern for managers."""

    def test_voice_history_singleton(self):
        """Should return same instance."""
        mgr1 = get_voice_history_manager()
        mgr2 = get_voice_history_manager()

        assert mgr1 is mgr2

    def test_session_manager_singleton(self):
        """Should return same instance."""
        mgr1 = get_session_manager()
        mgr2 = get_session_manager()

        assert mgr1 is mgr2

    def test_performance_monitor_singleton(self):
        """Should return same instance."""
        mon1 = get_performance_monitor()
        mon2 = get_performance_monitor()

        assert mon1 is mon2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
