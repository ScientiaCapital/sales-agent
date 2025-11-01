"""Tests for CostOptimizedLLMProvider."""
import pytest
from app.core.cost_optimized_llm import LLMConfig


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
