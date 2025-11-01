"""Tests for CostOptimizedLLMProvider."""
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from app.core.cost_optimized_llm import LLMConfig, CostOptimizedLLMProvider


def test_llm_config_defaults():
    """Test LLMConfig with defaults."""
    config = LLMConfig(agent_type="test")

    assert config.agent_type == "test"
    assert config.lead_id is None
    assert config.session_id is None
    assert config.user_id is None
    assert config.mode == "passthrough"
    assert config.provider is None
    assert config.model is None


def test_llm_config_passthrough():
    """Test LLMConfig for passthrough mode."""
    config = LLMConfig(
        agent_type="qualification",
        lead_id=123,
        mode="passthrough",
        provider="cerebras",
        model="llama3.1-8b"
    )

    assert config.mode == "passthrough"
    assert config.provider == "cerebras"
    assert config.model == "llama3.1-8b"


def test_llm_config_smart_router():
    """Test LLMConfig for smart_router mode."""
    config = LLMConfig(
        agent_type="sr_bdr",
        session_id="sess_123",
        mode="smart_router"
    )

    assert config.mode == "smart_router"
    assert config.provider is None  # Router decides
    assert config.model is None


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_provider_initialization(mock_db_session):
    """Test CostOptimizedLLMProvider initialization."""
    provider = CostOptimizedLLMProvider(mock_db_session)

    assert provider.db == mock_db_session
    assert provider.router is not None
    assert hasattr(provider, 'score_complexity')


@pytest.mark.asyncio
async def test_passthrough_validation_missing_provider(mock_db_session):
    """Test that passthrough mode validates provider parameter."""
    provider = CostOptimizedLLMProvider(mock_db_session)
    config = LLMConfig(
        agent_type="test",
        mode="passthrough",
        model="llama3.1-8b"
        # Missing provider!
    )

    with pytest.raises(ValueError, match="Passthrough mode requires provider and model"):
        await provider.complete("Test prompt", config)


@pytest.mark.asyncio
async def test_passthrough_validation_missing_model(mock_db_session):
    """Test that passthrough mode validates model parameter."""
    provider = CostOptimizedLLMProvider(mock_db_session)
    config = LLMConfig(
        agent_type="test",
        mode="passthrough",
        provider="cerebras"
        # Missing model!
    )

    with pytest.raises(ValueError, match="Passthrough mode requires provider and model"):
        await provider.complete("Test prompt", config)


@pytest.mark.asyncio
async def test_passthrough_cerebras(mock_db_session):
    """Test passthrough mode routes to Cerebras correctly."""
    provider = CostOptimizedLLMProvider(mock_db_session)
    config = LLMConfig(
        agent_type="qualification",
        lead_id=123,
        mode="passthrough",
        provider="cerebras",
        model="llama3.1-8b"
    )

    # Mock the LangChain provider call
    with patch('langchain_cerebras.ChatCerebras') as mock_cerebras:
        mock_response = Mock()
        mock_response.content = "Test response from Cerebras"
        mock_response.response_metadata = {
            "usage": {"prompt_tokens": 50, "completion_tokens": 100}
        }
        mock_cerebras.return_value.ainvoke = AsyncMock(return_value=mock_response)

        result = await provider.complete("Test prompt", config)

        assert result["provider"] == "cerebras"
        assert result["model"] == "llama3.1-8b"
        assert result["tokens_in"] == 50
        assert result["tokens_out"] == 100
        assert result["cost_usd"] > 0
        assert result["response"] == "Test response from Cerebras"
        assert "latency_ms" in result


@pytest.mark.asyncio
async def test_passthrough_claude(mock_db_session):
    """Test passthrough mode routes to Claude correctly."""
    provider = CostOptimizedLLMProvider(mock_db_session)
    config = LLMConfig(
        agent_type="enrichment",
        lead_id=456,
        mode="passthrough",
        provider="claude",
        model="claude-3-haiku-20240307"
    )

    # Mock the LangChain provider call
    with patch('langchain_anthropic.ChatAnthropic') as mock_claude:
        mock_response = Mock()
        mock_response.content = "Test response from Claude"
        mock_response.response_metadata = {
            "usage": {"input_tokens": 30, "output_tokens": 80}
        }
        mock_claude.return_value.ainvoke = AsyncMock(return_value=mock_response)

        result = await provider.complete("Analyze this lead", config)

        assert result["provider"] == "claude"
        assert result["model"] == "claude-3-haiku-20240307"
        assert result["tokens_in"] == 30
        assert result["tokens_out"] == 80
        assert result["cost_usd"] > 0


@pytest.mark.asyncio
async def test_passthrough_deepseek(mock_db_session):
    """Test passthrough mode routes to DeepSeek correctly."""
    provider = CostOptimizedLLMProvider(mock_db_session)
    config = LLMConfig(
        agent_type="growth",
        mode="passthrough",
        provider="deepseek",
        model="deepseek/deepseek-chat"
    )

    # Mock the LangChain provider call
    with patch('langchain_openai.ChatOpenAI') as mock_openai:
        mock_response = Mock()
        mock_response.content = "Test response from DeepSeek"
        mock_response.response_metadata = {
            "usage": {"prompt_tokens": 40, "completion_tokens": 90}
        }
        mock_openai.return_value.ainvoke = AsyncMock(return_value=mock_response)

        result = await provider.complete("Market analysis", config)

        assert result["provider"] == "deepseek"
        assert result["tokens_in"] == 40
        assert result["tokens_out"] == 90


@pytest.mark.asyncio
async def test_passthrough_gemini(mock_db_session):
    """Test passthrough mode routes to Gemini correctly."""
    provider = CostOptimizedLLMProvider(mock_db_session)
    config = LLMConfig(
        agent_type="marketing",
        mode="passthrough",
        provider="gemini",
        model="gemini-1.5-flash"
    )

    # Mock the LangChain provider call
    with patch('langchain_google_genai.ChatGoogleGenerativeAI') as mock_gemini:
        mock_response = Mock()
        mock_response.content = "Test response from Gemini"
        mock_response.response_metadata = {
            "usage": {"prompt_token_count": 20, "candidates_token_count": 60}
        }
        mock_gemini.return_value.ainvoke = AsyncMock(return_value=mock_response)

        result = await provider.complete("Generate campaign", config)

        assert result["provider"] == "gemini"
        assert result["tokens_in"] == 20
        assert result["tokens_out"] == 60


@pytest.mark.asyncio
async def test_smart_router_simple_prompt(mock_db_session):
    """Test smart router routes simple prompts correctly."""
    provider = CostOptimizedLLMProvider(mock_db_session)
    config = LLMConfig(
        agent_type="sr_bdr",
        mode="smart_router"
    )

    # Mock the Router's route_and_complete method
    with patch.object(provider.router, 'route_and_complete') as mock_route:
        mock_route.return_value = {
            "response": "Simple answer",
            "provider": "cerebras",
            "model": "llama3.1-8b",
            "tokens_in": 20,
            "tokens_out": 30,
            "cost": 0.000001,
            "complexity": "simple"
        }

        result = await provider.complete("What time is it?", config)

        assert result["provider"] == "cerebras"
        assert result["complexity"] == "simple"
        assert result["cost_usd"] == 0.000001


@pytest.mark.asyncio
async def test_smart_router_complex_prompt(mock_db_session):
    """Test smart router routes complex prompts correctly."""
    provider = CostOptimizedLLMProvider(mock_db_session)
    config = LLMConfig(
        agent_type="enrichment",
        mode="smart_router"
    )

    # Mock the Router's route_and_complete method
    with patch.object(provider.router, 'route_and_complete') as mock_route:
        mock_route.return_value = {
            "response": "Detailed analysis...",
            "provider": "claude",
            "model": "claude-3-haiku-20240307",
            "tokens_in": 150,
            "tokens_out": 300,
            "cost": 0.000425,
            "complexity": "complex"
        }

        complex_prompt = "Analyze this company's business model, identify key decision makers, and recommend personalized outreach strategies"

        result = await provider.complete(complex_prompt, config)

        assert result["provider"] == "claude"
        assert result["complexity"] == "complex"
        assert result["tokens_in"] == 150
        assert result["tokens_out"] == 300


@pytest.mark.asyncio
async def test_cost_calculation_cerebras():
    """Test cost calculation for Cerebras."""
    provider = CostOptimizedLLMProvider(AsyncMock())
    cost = provider._calculate_cost("cerebras", "llama3.1-8b", 1000, 2000)

    # Cerebras: $0.000006 per token for both input and output
    expected = (1000 + 2000) * 0.000006 / 1000
    assert abs(cost - expected) < 0.000001


@pytest.mark.asyncio
async def test_cost_calculation_claude():
    """Test cost calculation for Claude Haiku."""
    provider = CostOptimizedLLMProvider(AsyncMock())
    cost = provider._calculate_cost("claude", "claude-3-haiku-20240307", 1000, 2000)

    # Claude Haiku: $0.00025 input, $0.00125 output per 1K tokens
    expected = (1000 * 0.00025 + 2000 * 0.00125) / 1000
    assert abs(cost - expected) < 0.000001


@pytest.mark.asyncio
async def test_cost_tracking_database_error_handling(mock_db_session):
    """Test that database errors in tracking don't break LLM calls."""
    # Setup mock to fail on commit
    mock_db_session.commit = AsyncMock(side_effect=Exception("Database error"))

    provider = CostOptimizedLLMProvider(mock_db_session)
    config = LLMConfig(
        agent_type="test",
        mode="passthrough",
        provider="cerebras",
        model="llama3.1-8b"
    )

    # Mock successful LLM call
    with patch('langchain_cerebras.ChatCerebras') as mock_cerebras:
        mock_response = Mock()
        mock_response.content = "Test"
        mock_response.response_metadata = {
            "usage": {"prompt_tokens": 10, "completion_tokens": 20}
        }
        mock_cerebras.return_value.ainvoke = AsyncMock(return_value=mock_response)

        # Should not raise even though DB commit fails
        result = await provider.complete("Test", config)

        assert result["response"] == "Test"
        # Verify rollback was called
        mock_db_session.rollback.assert_called_once()
