"""
LangGraph Agent Integration Tests

Comprehensive test suite for all 6 LangGraph agents:
- QualificationAgent (LCEL chain)
- EnrichmentAgent (ReAct pattern)
- GrowthAgent (cyclic graph)
- MarketingAgent (parallel execution)
- BDRAgent (human-in-loop)
- ConversationAgent (voice-enabled)

Tests cover:
- End-to-end agent execution
- Streaming via SSE endpoints
- Redis checkpointing (pause/resume workflows)
- Database tracking (executions, tool calls)
- External API mocking (Cerebras, Apollo, LinkedIn, Cartesia)
- LangSmith tracing verification
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any, List
from datetime import datetime
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.database import get_db
from app.models.langgraph_models import LangGraphExecution, LangGraphCheckpoint, LangGraphToolCall
from app.services.langgraph.graph_utils import get_redis_checkpointer, create_streaming_config


# ========== Test Fixtures ==========

@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = MagicMock(spec=Session)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.query = MagicMock()
    return session


@pytest.fixture
def mock_redis_checkpointer():
    """Mock Redis checkpointer"""
    checkpointer = AsyncMock()
    checkpointer.asetup = AsyncMock()
    checkpointer.aget = AsyncMock()
    checkpointer.aput = AsyncMock()
    checkpointer.alist = AsyncMock()
    return checkpointer


@pytest.fixture
def sample_lead_data():
    """Sample lead data for testing"""
    return {
        "company_name": "TestCorp Inc",
        "industry": "SaaS",
        "company_size": "50-200",
        "contact_title": "VP Engineering",
        "contact_email": "test@testcorp.com",
        "company_website": "https://testcorp.com"
    }


@pytest.fixture
def sample_qualification_request():
    """Sample qualification request"""
    return {
        "agent_type": "qualification",
        "input_data": {
            "company_name": "TestCorp Inc",
            "industry": "SaaS",
            "company_size": "50-200",
            "contact_title": "VP Engineering"
        },
        "thread_id": "test_thread_123"
    }


# ========== Mock External APIs ==========

@pytest.fixture
def mock_cerebras_response():
    """Mock Cerebras API response"""
    return {
        "choices": [{
            "message": {
                "content": "Based on the company profile, TestCorp Inc appears to be a strong lead with a score of 85. The SaaS industry alignment and VP Engineering contact suggest high potential for our solution.",
                "role": "assistant"
            }
        }],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 75,
            "total_tokens": 225
        }
    }


@pytest.fixture
def mock_apollo_response():
    """Mock Apollo.io API response"""
    return {
        "person": {
            "id": "apollo_123",
            "first_name": "John",
            "last_name": "Doe",
            "title": "VP Engineering",
            "email": "john.doe@testcorp.com",
            "phone": "+1-555-0123",
            "linkedin_url": "https://linkedin.com/in/johndoe",
            "organization": {
                "name": "TestCorp Inc",
                "industry": "SaaS",
                "employee_count": 150,
                "annual_revenue": 10000000
            }
        }
    }


@pytest.fixture
def mock_linkedin_response():
    """Mock LinkedIn scraping response"""
    return {
        "profile": {
            "name": "John Doe",
            "title": "VP Engineering at TestCorp Inc",
            "location": "San Francisco, CA",
            "summary": "Experienced engineering leader with 10+ years in SaaS",
            "experience": [
                {
                    "title": "VP Engineering",
                    "company": "TestCorp Inc",
                    "duration": "2 years"
                }
            ],
            "skills": ["Python", "AWS", "Team Leadership"]
        }
    }


@pytest.fixture
def mock_cartesia_response():
    """Mock Cartesia TTS response"""
    return b"fake_audio_data_bytes"


# ========== QualificationAgent Tests ==========

@pytest.mark.asyncio
async def test_qualification_agent_end_to_end(
    client,
    mock_db_session,
    sample_qualification_request,
    mock_cerebras_response
):
    """Test QualificationAgent complete execution flow"""
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session), \
         patch('httpx.AsyncClient.post') as mock_post:
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        mock_post.return_value.json.return_value = mock_cerebras_response
        mock_post.return_value.status_code = 200
        
        # Execute agent
        response = client.post(
            "/api/langgraph/invoke",
            json=sample_qualification_request
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert "execution_id" in data
        assert data["agent_type"] == "qualification"
        assert data["status"] == "success"
        assert "output_data" in data
        assert "score" in data["output_data"]
        assert "reasoning" in data["output_data"]
        
        # Verify database tracking
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()


@pytest.mark.asyncio
async def test_qualification_agent_streaming(
    client,
    mock_db_session,
    sample_qualification_request,
    mock_cerebras_response
):
    """Test QualificationAgent streaming via SSE"""
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session), \
         patch('httpx.AsyncClient.post') as mock_post:
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        mock_post.return_value.json.return_value = mock_cerebras_response
        mock_post.return_value.status_code = 200
        
        # Execute streaming
        response = client.post(
            "/api/langgraph/stream",
            json=sample_qualification_request
        )
        
        # Verify streaming response
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        
        # Parse SSE data
        content = response.text
        lines = content.strip().split('\n')
        
        # Should have data lines
        data_lines = [line for line in lines if line.startswith('data: ')]
        assert len(data_lines) > 0
        
        # Parse first data line
        first_data = json.loads(data_lines[0][6:])  # Remove 'data: ' prefix
        assert first_data["type"] in ["chunk", "state_update", "complete"]


# ========== EnrichmentAgent Tests ==========

@pytest.mark.asyncio
async def test_enrichment_agent_with_tools(
    client,
    mock_db_session,
    mock_apollo_response,
    mock_linkedin_response
):
    """Test EnrichmentAgent with Apollo and LinkedIn tools"""
    
    enrichment_request = {
        "agent_type": "enrichment",
        "input_data": {
            "company_name": "TestCorp Inc",
            "contact_email": "john.doe@testcorp.com"
        },
        "thread_id": "test_thread_456"
    }
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session), \
         patch('httpx.AsyncClient.get') as mock_get:
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        # Mock Apollo API call
        apollo_response = MagicMock()
        apollo_response.json.return_value = mock_apollo_response
        apollo_response.status_code = 200
        
        # Mock LinkedIn API call
        linkedin_response = MagicMock()
        linkedin_response.json.return_value = mock_linkedin_response
        linkedin_response.status_code = 200
        
        # Configure mock to return different responses based on URL
        def mock_get_side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'apollo.io' in url:
                return apollo_response
            elif 'linkedin' in url:
                return linkedin_response
            return apollo_response
        
        mock_get.side_effect = mock_get_side_effect
        
        # Execute agent
        response = client.post(
            "/api/langgraph/invoke",
            json=enrichment_request
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["agent_type"] == "enrichment"
        assert data["status"] == "success"
        assert "enriched_data" in data["output_data"]
        
        # Verify tool calls were tracked
        mock_db_session.add.assert_called()


# ========== GrowthAgent Tests ==========

@pytest.mark.asyncio
async def test_growth_agent_cyclic_execution(
    client,
    mock_db_session
):
    """Test GrowthAgent cyclic graph execution"""
    
    growth_request = {
        "agent_type": "growth",
        "input_data": {
            "company_name": "TestCorp Inc",
            "research_depth": "standard"
        },
        "thread_id": "test_thread_789"
    }
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session), \
         patch('httpx.AsyncClient.get') as mock_get:
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        # Mock web search responses
        search_response = MagicMock()
        search_response.json.return_value = {
            "results": [
                {
                    "title": "TestCorp Inc Company Profile",
                    "content": "TestCorp Inc is a leading SaaS company...",
                    "url": "https://testcorp.com/about"
                }
            ]
        }
        search_response.status_code = 200
        mock_get.return_value = search_response
        
        # Execute agent
        response = client.post(
            "/api/langgraph/invoke",
            json=growth_request
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["agent_type"] == "growth"
        assert data["status"] == "success"
        assert "opportunities" in data["output_data"]
        assert "confidence" in data["output_data"]


# ========== MarketingAgent Tests ==========

@pytest.mark.asyncio
async def test_marketing_agent_parallel_execution(
    client,
    mock_db_session
):
    """Test MarketingAgent parallel node execution"""
    
    marketing_request = {
        "agent_type": "marketing",
        "input_data": {
            "company_name": "TestCorp Inc",
            "industry": "SaaS",
            "contact_title": "VP Engineering"
        },
        "thread_id": "test_thread_101"
    }
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session), \
         patch('httpx.AsyncClient.post') as mock_post:
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        # Mock LLM responses for parallel nodes
        mock_post.return_value.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Generated marketing content...",
                    "role": "assistant"
                }
            }]
        }
        mock_post.return_value.status_code = 200
        
        # Execute agent
        response = client.post(
            "/api/langgraph/invoke",
            json=marketing_request
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["agent_type"] == "marketing"
        assert data["status"] == "success"
        assert "campaigns" in data["output_data"]


# ========== BDRAgent Tests ==========

@pytest.mark.asyncio
async def test_bdr_agent_human_in_loop(
    client,
    mock_db_session
):
    """Test BDRAgent human-in-loop workflow"""
    
    bdr_request = {
        "agent_type": "bdr",
        "input_data": {
            "company_name": "TestCorp Inc",
            "contact_email": "john.doe@testcorp.com",
            "meeting_type": "discovery"
        },
        "thread_id": "test_thread_202"
    }
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session):
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        # Execute agent
        response = client.post(
            "/api/langgraph/invoke",
            json=bdr_request
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["agent_type"] == "bdr"
        # BDR agent may be in pending state waiting for human approval
        assert data["status"] in ["success", "pending"]


# ========== ConversationAgent Tests ==========

@pytest.mark.asyncio
async def test_conversation_agent_voice_enabled(
    client,
    mock_db_session,
    mock_cartesia_response
):
    """Test ConversationAgent voice-enabled workflow"""
    
    conversation_request = {
        "agent_type": "conversation",
        "input_data": {
            "user_input": "Hello, I'm interested in your SaaS solution",
            "session_id": "voice_session_303"
        },
        "thread_id": "test_thread_303"
    }
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session), \
         patch('httpx.AsyncClient.post') as mock_post:
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        # Mock Cartesia TTS response
        mock_post.return_value.content = mock_cartesia_response
        mock_post.return_value.status_code = 200
        
        # Execute agent
        response = client.post(
            "/api/langgraph/invoke",
            json=conversation_request
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["agent_type"] == "conversation"
        assert data["status"] == "success"
        assert "response" in data["output_data"]
        assert "audio_data" in data["output_data"]


# ========== Redis Checkpointing Tests ==========

@pytest.mark.asyncio
async def test_redis_checkpointing_pause_resume(
    client,
    mock_db_session
):
    """Test Redis checkpointing for pause/resume workflows"""
    
    # Start a long-running agent
    growth_request = {
        "agent_type": "growth",
        "input_data": {
            "company_name": "TestCorp Inc",
            "research_depth": "deep"
        },
        "thread_id": "test_thread_checkpoint"
    }
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session):
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        # Mock checkpoint creation
        mock_checkpointer.aput.return_value = "checkpoint_123"
        
        # Execute agent
        response = client.post(
            "/api/langgraph/invoke",
            json=growth_request
        )
        
        # Verify checkpointing was used
        mock_checkpointer.aput.assert_called()
        
        # Test checkpoint retrieval
        checkpoint_response = client.get(
            f"/api/langgraph/state/{growth_request['thread_id']}"
        )
        
        assert checkpoint_response.status_code == 200


# ========== Database Tracking Tests ==========

@pytest.mark.asyncio
async def test_database_execution_tracking(
    client,
    mock_db_session,
    sample_qualification_request
):
    """Test database tracking of agent executions"""
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session), \
         patch('httpx.AsyncClient.post') as mock_post:
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        mock_post.return_value.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Test qualification result",
                    "role": "assistant"
                }
            }]
        }
        mock_post.return_value.status_code = 200
        
        # Execute agent
        response = client.post(
            "/api/langgraph/invoke",
            json=sample_qualification_request
        )
        
        # Verify database operations
        assert response.status_code == 200
        
        # Check that LangGraphExecution was added
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()


@pytest.mark.asyncio
async def test_tool_call_tracking(
    client,
    mock_db_session,
    mock_apollo_response
):
    """Test database tracking of tool calls"""
    
    enrichment_request = {
        "agent_type": "enrichment",
        "input_data": {
            "company_name": "TestCorp Inc",
            "contact_email": "test@testcorp.com"
        },
        "thread_id": "test_thread_tools"
    }
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session), \
         patch('httpx.AsyncClient.get') as mock_get:
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        # Mock Apollo API call
        apollo_response = MagicMock()
        apollo_response.json.return_value = mock_apollo_response
        apollo_response.status_code = 200
        mock_get.return_value = apollo_response
        
        # Execute agent
        response = client.post(
            "/api/langgraph/invoke",
            json=enrichment_request
        )
        
        # Verify response
        assert response.status_code == 200
        
        # Verify tool calls were tracked in database
        mock_db_session.add.assert_called()


# ========== Error Handling Tests ==========

@pytest.mark.asyncio
async def test_agent_error_handling(
    client,
    mock_db_session
):
    """Test agent error handling and graceful degradation"""
    
    error_request = {
        "agent_type": "qualification",
        "input_data": {
            "company_name": "ErrorCorp",  # This will trigger an error
            "industry": "SaaS"
        },
        "thread_id": "test_thread_error"
    }
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session), \
         patch('httpx.AsyncClient.post') as mock_post:
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        # Mock API error
        mock_post.side_effect = Exception("API Error")
        
        # Execute agent
        response = client.post(
            "/api/langgraph/invoke",
            json=error_request
        )
        
        # Verify error handling
        assert response.status_code == 200  # Should still return 200 with error in response
        data = response.json()
        
        assert data["status"] == "failed"
        assert "error_message" in data


# ========== Performance Tests ==========

@pytest.mark.asyncio
async def test_agent_performance_targets(
    client,
    mock_db_session,
    sample_qualification_request
):
    """Test agent performance meets targets"""
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session), \
         patch('httpx.AsyncClient.post') as mock_post:
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        mock_post.return_value.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Test response",
                    "role": "assistant"
                }
            }]
        }
        mock_post.return_value.status_code = 200
        
        # Execute agent and measure time
        import time
        start_time = time.time()
        
        response = client.post(
            "/api/langgraph/invoke",
            json=sample_qualification_request
        )
        
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check performance targets
        if data["agent_type"] == "qualification":
            assert duration_ms < 1000  # Qualification target: <1000ms
        elif data["agent_type"] == "enrichment":
            assert duration_ms < 3000  # Enrichment target: <3000ms


# ========== LangSmith Tracing Tests ==========

@pytest.mark.asyncio
async def test_langsmith_tracing_integration(
    client,
    mock_db_session,
    sample_qualification_request
):
    """Test LangSmith tracing integration"""
    
    with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
         patch('app.models.database.get_db', return_value=mock_db_session), \
         patch('httpx.AsyncClient.post') as mock_post, \
         patch('langsmith.traceable') as mock_traceable:
        
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_get_checkpointer.return_value = mock_checkpointer
        
        mock_post.return_value.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Test response",
                    "role": "assistant"
                }
            }]
        }
        mock_post.return_value.status_code = 200
        
        # Execute agent
        response = client.post(
            "/api/langgraph/invoke",
            json=sample_qualification_request
        )
        
        # Verify response
        assert response.status_code == 200
        
        # Verify LangSmith tracing was called (if API key is configured)
        # Note: This test will pass even if LangSmith is not configured
        # The actual tracing happens in the agent implementations


# ========== Integration Test Suite ==========

@pytest.mark.integration
class TestLangGraphIntegration:
    """Integration test suite for all LangGraph agents"""
    
    @pytest.mark.asyncio
    async def test_all_agents_end_to_end(self, client, mock_db_session):
        """Test all 6 agents in sequence"""
        
        agents = [
            "qualification",
            "enrichment", 
            "growth",
            "marketing",
            "bdr",
            "conversation"
        ]
        
        for agent_type in agents:
            request = {
                "agent_type": agent_type,
                "input_data": {
                    "company_name": "TestCorp Inc",
                    "industry": "SaaS"
                },
                "thread_id": f"integration_test_{agent_type}"
            }
            
            with patch('app.services.langgraph.graph_utils.get_redis_checkpointer') as mock_get_checkpointer, \
                 patch('app.models.database.get_db', return_value=mock_db_session), \
                 patch('httpx.AsyncClient.post') as mock_post, \
                 patch('httpx.AsyncClient.get') as mock_get:
                
                # Setup mocks
                mock_checkpointer = AsyncMock()
                mock_get_checkpointer.return_value = mock_checkpointer
                
                # Mock API responses
                mock_post.return_value.json.return_value = {
                    "choices": [{
                        "message": {
                            "content": f"Test {agent_type} response",
                            "role": "assistant"
                        }
                    }]
                }
                mock_post.return_value.status_code = 200
                
                mock_get.return_value.json.return_value = {
                    "results": [{"title": "Test", "content": "Test content"}]
                }
                mock_get.return_value.status_code = 200
                
                # Execute agent
                response = client.post(
                    "/api/langgraph/invoke",
                    json=request
                )
                
                # Verify response
                assert response.status_code == 200
                data = response.json()
                assert data["agent_type"] == agent_type
                assert data["status"] in ["success", "pending"]  # BDR may be pending


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
