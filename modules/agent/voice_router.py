"""Voice routing layer for JARVIS Phase 2-3.

Connects VoiceManager output to the JARVIS assistant runtime.
Integrates voice history tracking, conversation context, and performance monitoring.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, TYPE_CHECKING

from modules.services import VoiceManager, VoiceCommand
from modules.agent.voice_history import (
    CommandStatus,
    get_voice_history_manager,
)
from modules.agent.conversation_context import get_session_manager
from modules.agent.performance_monitor import get_performance_monitor

if TYPE_CHECKING:
    from core.assistant import Assistant

logger = logging.getLogger(__name__)


@dataclass
class VoiceCommandResult:
    """Processed voice command result."""

    command: str
    response: str
    routed: bool
    spoken: bool


class VoiceCommandRouter:
    """Routes voice commands through the JARVIS assistant with Phase 3 tracking."""

    def __init__(self, assistant: Optional["Assistant"], voice_manager: Optional[VoiceManager] = None):
        self.assistant = assistant
        self.voice_manager = voice_manager or VoiceManager()
        
        # Phase 3: Initialize managers
        self.history_manager = get_voice_history_manager()
        self.session_manager = get_session_manager()
        self.performance_monitor = get_performance_monitor()
        
        # Track current session
        self.current_session_id = "default_session"
        self.session_context = self.session_manager.get_context(self.current_session_id)

    async def handle_voice_command(self, command_text: str, speak: bool = True, confidence: float = 0.0) -> str:
        """Process a voice command with full Phase 3 tracking."""
        text = (command_text or "").strip()
        start_time = time.time()
        op_id = f"voice_cmd_{int(start_time * 1000)}"
        self.performance_monitor.start_operation(op_id)
        
        # Track in history
        if not text:
            response = "I didn't catch that. Please repeat the command."
            duration_ms = (time.time() - start_time) * 1000
            self.history_manager.add_entry(
                text or "[empty]",
                response,
                confidence,
                CommandStatus.FAILED,
                duration_ms=int(duration_ms),
            )
            self.performance_monitor.end_operation(op_id, "voice_command", success=False)
            if speak:
                self.voice_manager.speak_response(response)
            return response

        response = await self._run_assistant(text)
        success = response and len(response) > 0
        duration_ms = (time.time() - start_time) * 1000
        
        # Add to history with success status
        self.history_manager.add_entry(
            text,
            response,
            confidence if confidence > 0 else 0.95,
            CommandStatus.EXECUTED if success else CommandStatus.FAILED,
            duration_ms=int(duration_ms),
        )
        
        # Track in conversation context
        self.session_context.add_turn(text, response)
        
        # Record performance metrics
        self.performance_monitor.end_operation(op_id, "voice_command", success=success)
        
        if speak:
            self.voice_manager.speak_response(response)
        return response

    async def _run_assistant(self, command_text: str) -> str:
        if self.assistant and getattr(self.assistant, "react_agent", None):
            try:
                return await self.assistant.process_query_async(command_text)
            except Exception as exc:
                logger.warning(f"Voice command routing failed via assistant: {exc}")

        logger.info("Voice command routing fallback used")
        return f"I heard: {command_text}"
    
    def get_history(self, num_entries: int = 10) -> list:
        """Get recent command history."""
        return self.history_manager.get_history(num_entries)
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics."""
        return self.performance_monitor.get_stats("voice_command")
    
    def get_session_summary(self) -> dict:
        """Get current session summary."""
        return self.session_context.get_summary()


class VoiceCallbacks:
    """Keyword-based voice callback dispatcher."""

    def __init__(self, assistant: Optional["Assistant"], voice_manager: Optional[VoiceManager] = None):
        self.assistant = assistant
        self.voice_manager = voice_manager or VoiceManager()
        self.router = VoiceCommandRouter(assistant, self.voice_manager)

    def register_all(self, voice_manager: Optional[VoiceManager] = None) -> None:
        """Register the dispatcher callback with the voice manager."""
        manager = voice_manager or self.voice_manager
        manager.register_command_callback(self.handle_voice_command)

    def handle_voice_command(self, command: VoiceCommand) -> None:
        """Sync callback entry point for VoiceManager."""
        try:
            coro = self.router.handle_voice_command(command.text, speak=True)
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(coro)
            except RuntimeError:
                asyncio.run(coro)
        except Exception as exc:
            logger.error(f"Voice callback failed: {exc}")

    async def process_text(self, command_text: str) -> str:
        """Async helper for tests and direct routing."""
        return await self.router.handle_voice_command(command_text, speak=False)
