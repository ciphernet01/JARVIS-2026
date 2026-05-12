"""Phase 2 voice integration tests."""

import asyncio

from modules.agent.voice_router import VoiceCallbacks, VoiceCommandRouter
from modules.services import VoiceManager


class DummyAssistant:
    def __init__(self):
        self.react_agent = True
        self.calls = []

    async def process_query_async(self, text: str):
        self.calls.append(text)
        return f"processed: {text}"


def test_voice_command_router_processes_text():
    assistant = DummyAssistant()
    router = VoiceCommandRouter(assistant, VoiceManager())

    response = asyncio.run(router.handle_voice_command("what time is it", speak=False))

    assert response == "processed: what time is it"
    assert assistant.calls == ["what time is it"]


def test_voice_callbacks_route_command():
    assistant = DummyAssistant()
    voice = VoiceManager()
    callbacks = VoiceCallbacks(assistant, voice)

    result = asyncio.run(callbacks.process_text("open notepad"))

    assert result == "processed: open notepad"
