from unittest.mock import Mock, patch

from modules.llm.local_runtime import OpenAICompatibleManager


def test_capabilities_reports_models_from_openai_compatible_endpoint():
    manager = OpenAICompatibleManager(
        base_url="http://inference.local/v1",
        model="model-a",
        provider="vllm",
        api_key="test-token",
    )
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"data": [{"id": "model-a"}, {"id": "model-b"}]}

    with patch("modules.llm.local_runtime.requests.get", return_value=response) as get:
        capabilities = manager.capabilities()

    assert capabilities.reachable is True
    assert capabilities.available_models == ["model-a", "model-b"]
    assert capabilities.configured_model_available is True
    assert capabilities.tool_calling is None
    assert capabilities.provider == "vllm"
    assert get.call_args.args[0] == "http://inference.local/v1/models"
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer test-token"


def test_capabilities_degrades_cleanly_when_runtime_is_offline():
    manager = OpenAICompatibleManager()
    with patch("modules.llm.local_runtime.requests.get", side_effect=OSError("offline")):
        capabilities = manager.capabilities()
    assert capabilities.reachable is False
    assert capabilities.available_models == []
    assert capabilities.configured_model_available is False


def test_chat_uses_openai_compatible_completion_shape():
    manager = OpenAICompatibleManager(model="model-a", provider="ollama")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Systems nominal."}}]
    }

    with patch("modules.llm.local_runtime.requests.post", return_value=response) as post:
        result = manager.chat("status")

    assert result == "Systems nominal."
    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "model-a"
    assert payload["stream"] is False


def test_chat_returns_empty_string_instead_of_crashing_when_offline():
    manager = OpenAICompatibleManager()
    with patch("modules.llm.local_runtime.requests.post", side_effect=OSError("offline")):
        assert manager.chat("status") == ""


def test_decide_action_parses_json_plan():
    manager = OpenAICompatibleManager()
    with patch.object(
        manager,
        "_completion",
        return_value={"content": '{"type":"skill","skill_name":"weather","skill_query":"today"}'},
    ):
        result = manager.decide_action(
            "weather",
            {"available_skills": [{"name": "weather", "description": "Forecast"}]},
        )
    assert result["type"] == "skill"
    assert result["skill_name"] == "weather"
    assert result["confidence"] == 0.0
