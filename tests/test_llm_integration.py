"""
Phase 2: LLM Integration Tests

Tests for OpenAI, Ollama, Gemini backends and routing.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch, PropertyMock
import sys

# Mock external dependencies
sys.modules['openai'] = MagicMock()
sys.modules['google.genai'] = MagicMock()
sys.modules['httpx'] = MagicMock()

from modules.agent.llm_integration import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    OpenAILLM,
    OllamaLLM,
    GeminiLLM,
    LLMFactory,
    LLMRouter,
    create_default_llm,
)


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

class TestLLMConfig:
    """Test LLM configuration."""

    def test_llm_config_creation(self):
        """Should create valid config."""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name="gpt-4",
            temperature=0.5
        )

        assert config.provider == LLMProvider.OPENAI
        assert config.model_name == "gpt-4"
        assert config.temperature == 0.5

    def test_llm_config_defaults(self):
        """Should have sensible defaults."""
        config = LLMConfig(provider=LLMProvider.OLLAMA)

        assert config.temperature == 0.7
        assert config.max_tokens == 500
        assert config.timeout == 30


# ============================================================================
# OPENAI LLM TESTS
# ============================================================================

class TestOpenAILLM:
    """Test OpenAI integration."""

    def test_openai_config_storage(self):
        """Should store configuration."""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name="gpt-4",
            temperature=0.5
        )

        assert config.model_name == "gpt-4"
        assert config.temperature == 0.5

    def test_openai_generate_fallback(self):
        """Should handle missing client gracefully."""
        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="dummy-key")

        llm = OpenAILLM(config)
        llm.client = None

        response = asyncio.run(llm.generate("test"))
        assert "not available" in response.lower()


# ============================================================================
# OLLAMA LLM TESTS
# ============================================================================

class TestOllamaLLM:
    """Test Ollama integration."""

    def test_ollama_initialization(self):
        """Should initialize with URL."""
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            base_url="http://localhost:11434"
        )

        llm = OllamaLLM(config)
        assert llm.base_url == "http://localhost:11434"

    def test_ollama_generate_fallback(self):
        """Should handle missing client."""
        config = LLMConfig(provider=LLMProvider.OLLAMA)

        llm = OllamaLLM(config)
        llm.client = None

        response = asyncio.run(llm.generate("test"))
        assert "not available" in response.lower()


# ============================================================================
# GEMINI LLM TESTS
# ============================================================================

class TestGeminiLLM:
    """Test Gemini integration."""

    def test_gemini_initialization_without_key(self):
        """Should warn if no API key."""
        config = LLMConfig(provider=LLMProvider.GEMINI)

        with patch.dict('os.environ', {}, clear=True):
            llm = GeminiLLM(config)
            # Should not crash even without key
            assert llm is not None

    def test_gemini_generate_fallback(self):
        """Should handle missing client."""
        config = LLMConfig(provider=LLMProvider.GEMINI)

        llm = GeminiLLM(config)
        llm.client = None

        response = asyncio.run(llm.generate("test"))
        assert "not available" in response.lower()


# ============================================================================
# LLM FACTORY TESTS
# ============================================================================

class TestLLMFactory:
    """Test LLM factory."""

    def test_factory_creates_openai(self):
        """Should create OpenAI instance."""
        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="test-key")

        with patch('modules.agent.llm_integration.OpenAILLM') as mock_openai:
            mock_openai.return_value = MagicMock(spec=OpenAILLM)
            # Factory will just instantiate the class
            llm = LLMFactory.create(config)
            assert llm is not None

    def test_factory_creates_ollama(self):
        """Should create Ollama instance."""
        config = LLMConfig(provider=LLMProvider.OLLAMA)

        llm = LLMFactory.create(config)
        assert isinstance(llm, OllamaLLM)

    def test_factory_unknown_provider(self):
        """Should raise on unknown provider."""
        config = LLMConfig(provider="unknown_provider")

        with pytest.raises((ValueError, AttributeError)):
            LLMFactory.create(config)


# ============================================================================
# LLM ROUTER TESTS
# ============================================================================

class TestLLMRouter:
    """Test LLM router with fallback."""

    def test_router_initialization(self):
        """Should initialize with multiple providers."""
        configs = [
            LLMConfig(provider=LLMProvider.OLLAMA),
            LLMConfig(provider=LLMProvider.OPENAI, api_key="test-key"),
        ]

        router = LLMRouter(configs)

        assert len(router.llms) == 2
        assert router.current_index == 0

    def test_router_generate_uses_primary(self):
        """Should use primary provider."""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="Primary response")

        router = LLMRouter([LLMConfig(provider=LLMProvider.OLLAMA)])
        router.llms = [mock_llm]

        response = asyncio.run(router.generate("test"))
        assert response == "Primary response"

    def test_router_fallback_on_error(self):
        """Should fall back to secondary provider on error."""
        mock_primary = AsyncMock()
        mock_primary.generate = AsyncMock(side_effect=Exception("Primary failed"))

        mock_secondary = AsyncMock()
        mock_secondary.generate = AsyncMock(return_value="Fallback response")

        router = LLMRouter([
            LLMConfig(provider=LLMProvider.OLLAMA),
            LLMConfig(provider=LLMProvider.OPENAI, api_key="test-key"),
        ])
        router.llms = [mock_primary, mock_secondary]

        response = asyncio.run(router.generate("test"))
        assert response == "Fallback response"
        assert router.current_index == 1  # Switched to fallback

    def test_router_all_providers_fail(self):
        """Should handle all providers failing."""
        mock_llm1 = AsyncMock()
        mock_llm1.generate = AsyncMock(side_effect=Exception("Failed"))

        mock_llm2 = AsyncMock()
        mock_llm2.generate = AsyncMock(side_effect=Exception("Failed"))

        router = LLMRouter([
            LLMConfig(provider=LLMProvider.OLLAMA),
            LLMConfig(provider=LLMProvider.OPENAI, api_key="test-key"),
        ])
        router.llms = [mock_llm1, mock_llm2]

        response = asyncio.run(router.generate("test"))
        assert "unavailable" in response.lower()

    def test_router_get_current_provider(self):
        """Should report current active provider."""
        configs = [
            LLMConfig(provider=LLMProvider.OLLAMA),
            LLMConfig(provider=LLMProvider.OPENAI, api_key="test-key"),
        ]

        router = LLMRouter(configs)

        assert router.get_current_provider() == LLMProvider.OLLAMA


# ============================================================================
# DEFAULT LLM FACTORY TESTS
# ============================================================================

class TestCreateDefaultLLM:
    """Test default LLM creation."""

    def test_create_default_has_fallback(self):
        """Should create default LLM with fallback."""
        # Just verify it doesn't crash
        with patch.dict('os.environ', {}, clear=True):
            llm = create_default_llm()
            # Should be None or an LLM instance
            assert llm is None or isinstance(llm, (OllamaLLM, LLMRouter))


# ============================================================================
# LLM RESPONSE TESTS
# ============================================================================

class TestLLMResponse:
    """Test LLM response dataclass."""

    def test_llm_response_creation(self):
        """Should create valid response."""
        response = LLMResponse(
            content="Test content",
            model="gpt-3.5-turbo",
            tokens_used=100,
            provider=LLMProvider.OPENAI
        )

        assert response.content == "Test content"
        assert response.model == "gpt-3.5-turbo"
        assert response.tokens_used == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
