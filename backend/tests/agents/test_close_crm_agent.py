"""
Tests for Close CRM Agent

Tests agent workflows, deduplication integration, cost tracking, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.services.langgraph.agents.close_crm_agent import (
    CloseCRMAgent,
    get_close_crm_agent
)
from app.services.langgraph.agents.base_agent import OptimizationTarget


# ========== Fixtures ==========

@pytest.fixture
def mock_cost_optimizer():
    """Mock cost optimizer for testing"""
    optimizer = AsyncMock()
    optimizer.log_llm_call = AsyncMock()
    optimizer.log_agent_execution = AsyncMock()
    optimizer.log_cache_hit = AsyncMock()
    return optimizer


@pytest.fixture
def agent():
    """Create Close CRM agent for testing"""
    return CloseCRMAgent(
        provider="deepseek",
        temperature=0.2,
        use_cache=True,
        track_costs=True
    )


# ========== Initialization Tests ==========

def test_agent_initialization():
    """Test agent initializes with correct configuration"""
    agent = CloseCRMAgent(
        provider="deepseek",
        model="deepseek-chat",
        temperature=0.2
    )

    assert agent.name == "close_crm"
    assert agent.provider.value == "deepseek"
    assert agent.model == "deepseek-chat"
    assert agent.config.optimize_for == OptimizationTarget.COST
    assert agent.config.use_cache is True
    assert agent.config.grounding_strategy == "strict"


def test_agent_has_required_tools(agent):
    """Test agent has all required CRM tools"""
    tools = agent.get_tools()
    tool_names = [tool.name for tool in tools]

    assert "create_lead_tool" in tool_names
    assert "update_contact_tool" in tool_names
    assert "search_leads_tool" in tool_names
    assert "get_lead_tool" in tool_names
    assert "check_duplicate_leads_tool" in tool_names


def test_system_prompt_includes_deduplication_rules(agent):
    """Test system prompt enforces deduplication"""
    prompt = agent.get_system_prompt()

    assert "PREVENT DUPLICATES" in prompt
    assert "check for duplicates before creating" in prompt
    assert "confidence >= 85%" in prompt
    assert "check_duplicate_leads_tool" in prompt


# ========== Workflow Tests ==========

@pytest.mark.asyncio
@patch('app.services.langgraph.agents.close_crm_agent.create_react_agent')
async def test_create_lead_workflow(mock_create_agent, agent):
    """Test create lead workflow with deduplication"""
    # Mock ReAct agent response
    mock_agent_instance = AsyncMock()
    mock_agent_instance.ainvoke = AsyncMock(return_value={
        "messages": [
            Mock(content="✅ No duplicates found. Lead created successfully.")
        ]
    })
    mock_create_agent.return_value = mock_agent_instance

    # Test create lead
    result = await agent.process({
        "action": "create_lead",
        "company_name": "Test Corp",
        "contact_email": "test@testcorp.com",
        "contact_name": "Test User"
    })

    assert result["success"] is True
    assert "latency_ms" in result
    assert result["action"] == "create_lead"
    assert result["provider"] == "deepseek"


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.close_crm_agent.create_react_agent')
async def test_search_leads_workflow(mock_create_agent, agent):
    """Test search leads workflow"""
    mock_agent_instance = AsyncMock()
    mock_agent_instance.ainvoke = AsyncMock(return_value={
        "messages": [
            Mock(content="Found 3 leads matching 'Acme'")
        ]
    })
    mock_create_agent.return_value = mock_agent_instance

    result = await agent.process({
        "action": "search",
        "query": "Acme",
        "limit": 10
    })

    assert result["success"] is True
    assert result["action"] == "search"


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.close_crm_agent.create_react_agent')
async def test_update_contact_workflow(mock_create_agent, agent):
    """Test update contact workflow"""
    mock_agent_instance = AsyncMock()
    mock_agent_instance.ainvoke = AsyncMock(return_value={
        "messages": [
            Mock(content="Contact updated successfully")
        ]
    })
    mock_create_agent.return_value = mock_agent_instance

    result = await agent.process({
        "action": "update",
        "external_id": "contact_123",
        "title": "Senior VP"
    })

    assert result["success"] is True
    assert result["action"] == "update"


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.close_crm_agent.create_react_agent')
async def test_get_lead_workflow(mock_create_agent, agent):
    """Test get lead details workflow"""
    mock_agent_instance = AsyncMock()
    mock_agent_instance.ainvoke = AsyncMock(return_value={
        "messages": [
            Mock(content="Lead Details: John Doe @ Acme Corp")
        ]
    })
    mock_create_agent.return_value = mock_agent_instance

    result = await agent.process({
        "action": "get",
        "lead_id": "lead_abc123"
    })

    assert result["success"] is True
    assert result["action"] == "get"


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.close_crm_agent.create_react_agent')
async def test_check_duplicates_workflow(mock_create_agent, agent):
    """Test check duplicates workflow"""
    mock_agent_instance = AsyncMock()
    mock_agent_instance.ainvoke = AsyncMock(return_value={
        "messages": [
            Mock(content="✅ No duplicates found!")
        ]
    })
    mock_create_agent.return_value = mock_agent_instance

    result = await agent.process({
        "action": "check_duplicates",
        "email": "test@example.com",
        "company": "Test Corp",
        "threshold": 85.0
    })

    assert result["success"] is True
    assert result["action"] == "check_duplicates"


# ========== Prompt Builder Tests ==========

def test_build_create_lead_prompt(agent):
    """Test create lead prompt includes all fields"""
    prompt = agent._build_create_lead_prompt({
        "company_name": "Acme Corp",
        "contact_email": "john@acme.com",
        "contact_name": "John Doe",
        "contact_title": "VP",
        "contact_phone": "555-1234",
        "industry": "SaaS"
    })

    assert "Acme Corp" in prompt
    assert "john@acme.com" in prompt
    assert "John Doe" in prompt
    assert "VP" in prompt
    assert "555-1234" in prompt
    assert "SaaS" in prompt
    assert "check for duplicates" in prompt.lower()


def test_build_search_prompt(agent):
    """Test search prompt formatting"""
    prompt = agent._build_search_prompt({
        "query": "Acme Corp",
        "limit": 5
    })

    assert "Acme Corp" in prompt
    assert "5" in prompt or "5" in str(prompt)
    assert "search_leads_tool" in prompt.lower()


def test_build_update_prompt(agent):
    """Test update prompt includes fields"""
    prompt = agent._build_update_prompt({
        "external_id": "contact_123",
        "first_name": "John",
        "title": "VP of Sales"
    })

    assert "contact_123" in prompt
    assert "John" in prompt
    assert "VP of Sales" in prompt


def test_build_get_prompt(agent):
    """Test get lead prompt formatting"""
    prompt = agent._build_get_prompt({
        "lead_id": "lead_abc123"
    })

    assert "lead_abc123" in prompt
    assert "get_lead_tool" in prompt.lower()


def test_build_check_duplicates_prompt(agent):
    """Test check duplicates prompt includes all fields"""
    prompt = agent._build_check_duplicates_prompt({
        "email": "test@example.com",
        "company": "Test Corp",
        "phone": "555-1234",
        "threshold": 90.0
    })

    assert "test@example.com" in prompt
    assert "Test Corp" in prompt
    assert "555-1234" in prompt
    assert "90" in prompt or "90.0" in prompt


# ========== Cost Tracking Tests ==========

@pytest.mark.asyncio
@patch('app.services.langgraph.agents.close_crm_agent.create_react_agent')
@patch('app.services.langgraph.agents.base_agent.get_cost_optimizer')
async def test_cost_tracking_on_success(mock_get_optimizer, mock_create_agent, agent):
    """Test cost tracking logs successful execution"""
    # Mock cost optimizer
    mock_optimizer = AsyncMock()
    mock_optimizer.log_agent_execution = AsyncMock()
    mock_get_optimizer.return_value = mock_optimizer

    # Mock agent response
    mock_agent_instance = AsyncMock()
    mock_agent_instance.ainvoke = AsyncMock(return_value={
        "messages": [Mock(content="Success")]
    })
    mock_create_agent.return_value = mock_agent_instance

    # Enable cost tracking
    agent.config.track_costs = True
    agent.cost_optimizer = mock_optimizer

    result = await agent.process({
        "action": "search",
        "query": "test"
    })

    # Verify cost tracking was called
    assert mock_optimizer.log_agent_execution.called


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.close_crm_agent.create_react_agent')
@patch('app.services.langgraph.agents.base_agent.get_cost_optimizer')
async def test_cost_tracking_on_failure(mock_get_optimizer, mock_create_agent, agent):
    """Test cost tracking logs failed execution"""
    # Mock cost optimizer
    mock_optimizer = AsyncMock()
    mock_optimizer.log_agent_execution = AsyncMock()
    mock_get_optimizer.return_value = mock_optimizer

    # Mock agent to raise error
    mock_agent_instance = AsyncMock()
    mock_agent_instance.ainvoke = AsyncMock(side_effect=Exception("API Error"))
    mock_create_agent.return_value = mock_agent_instance

    # Enable cost tracking
    agent.config.track_costs = True
    agent.cost_optimizer = mock_optimizer

    result = await agent.process({
        "action": "create_lead"
    })

    assert result["success"] is False
    assert "error" in result


# ========== Error Handling Tests ==========

@pytest.mark.asyncio
@patch('app.services.langgraph.agents.close_crm_agent.create_react_agent')
async def test_handle_agent_exception(mock_create_agent, agent):
    """Test agent handles exceptions gracefully"""
    # Mock agent to raise exception
    mock_agent_instance = AsyncMock()
    mock_agent_instance.ainvoke = AsyncMock(side_effect=Exception("Network error"))
    mock_create_agent.return_value = mock_agent_instance

    result = await agent.process({
        "action": "search",
        "query": "test"
    })

    assert result["success"] is False
    assert "error" in result
    assert "Network error" in result["error"]
    assert "latency_ms" in result


# ========== Factory Function Tests ==========

def test_factory_function_creates_agent():
    """Test factory function creates agent correctly"""
    agent = get_close_crm_agent(
        provider="deepseek",
        model="deepseek-chat",
        use_cache=True,
        track_costs=True
    )

    assert isinstance(agent, CloseCRMAgent)
    assert agent.provider.value == "deepseek"
    assert agent.model == "deepseek-chat"
    assert agent.config.use_cache is True
    assert agent.config.track_costs is True


def test_factory_function_defaults():
    """Test factory function uses correct defaults"""
    agent = get_close_crm_agent()

    assert agent.provider.value == "deepseek"
    assert agent.config.optimize_for == OptimizationTarget.COST
    assert agent.config.use_cache is True
    assert agent.config.track_costs is True


# ========== Integration Tests (with mocks) ==========

@pytest.mark.asyncio
@patch('app.services.langgraph.agents.close_crm_agent.create_react_agent')
async def test_duplicate_prevention_workflow(mock_create_agent, agent):
    """Test agent prevents duplicate creation"""
    # Mock agent response indicating duplicate found
    mock_agent_instance = AsyncMock()
    mock_agent_instance.ainvoke = AsyncMock(return_value={
        "messages": [
            Mock(content="⚠️ DUPLICATE DETECTED (confidence: 95.0%)\nCannot create lead")
        ]
    })
    mock_create_agent.return_value = mock_agent_instance

    result = await agent.process({
        "action": "create_lead",
        "company_name": "Existing Corp",
        "contact_email": "existing@corp.com"
    })

    assert result["success"] is True
    assert "DUPLICATE" in result["response"] or "duplicate" in result["response"].lower()


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.close_crm_agent.create_react_agent')
async def test_performance_tracking(mock_create_agent, agent):
    """Test agent tracks performance metrics"""
    mock_agent_instance = AsyncMock()
    mock_agent_instance.ainvoke = AsyncMock(return_value={
        "messages": [Mock(content="Success")]
    })
    mock_create_agent.return_value = mock_agent_instance

    result = await agent.process({
        "action": "search",
        "query": "test"
    })

    # Verify performance metrics are tracked
    assert "latency_ms" in result
    assert isinstance(result["latency_ms"], int)
    assert result["latency_ms"] > 0


# ========== Edge Cases ==========

@pytest.mark.asyncio
@patch('app.services.langgraph.agents.close_crm_agent.create_react_agent')
async def test_unknown_action_defaults_to_prompt(mock_create_agent, agent):
    """Test unknown action uses raw prompt"""
    mock_agent_instance = AsyncMock()
    mock_agent_instance.ainvoke = AsyncMock(return_value={
        "messages": [Mock(content="Processed")]
    })
    mock_create_agent.return_value = mock_agent_instance

    result = await agent.process({
        "action": "unknown_action",
        "prompt": "Do something custom"
    })

    assert result["success"] is True


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.close_crm_agent.create_react_agent')
async def test_empty_response_handled(mock_create_agent, agent):
    """Test agent handles empty response gracefully"""
    mock_agent_instance = AsyncMock()
    mock_agent_instance.ainvoke = AsyncMock(return_value={
        "messages": []  # Empty messages
    })
    mock_create_agent.return_value = mock_agent_instance

    result = await agent.process({
        "action": "search",
        "query": "test"
    })

    assert result["success"] is True
    assert result["response"] == "No response"
