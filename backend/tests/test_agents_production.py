"""
Production-ready test suite for LangGraph agents.

Tests performance, cost, and functionality of all agents.
"""

import pytest
import asyncio
import time
from typing import Dict, Any

from app.services.langgraph.agents.qualification_agent import QualificationAgent
from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent
from app.services.langgraph.agents.conversation_agent import ConversationAgent


class TestQualificationAgentProduction:
    """Production tests for QualificationAgent."""

    @pytest.mark.asyncio
    async def test_qualification_agent_performance(self):
        """Test QualificationAgent meets performance targets."""
        agent = QualificationAgent()
        
        result, latency_ms, metadata = await agent.qualify(
            company_name="Acme Corp",
            industry="SaaS",
            company_size="50-200"
        )
        
        # Performance assertions
        assert latency_ms < 1000, f"Latency {latency_ms}ms exceeds 1000ms target"
        assert metadata['estimated_cost_usd'] < 0.0001, f"Cost ${metadata['estimated_cost_usd']:.6f} exceeds budget"
        
        # Output validation
        assert 0 <= result.qualification_score <= 100
        assert result.tier in ["hot", "warm", "cold", "unqualified"]
        assert len(result.recommendations) > 0
        assert len(result.qualification_reasoning) > 10  # Non-empty reasoning

    @pytest.mark.asyncio
    async def test_qualification_agent_batch_performance(self):
        """Test batch qualification performance."""
        agent = QualificationAgent()
        
        leads = [
            {"company_name": "TechCorp", "industry": "SaaS", "company_size": "100-500"},
            {"company_name": "StartupInc", "industry": "FinTech", "company_size": "10-50"},
            {"company_name": "EnterpriseCo", "industry": "Manufacturing", "company_size": "1000+"}
        ]
        
        start_time = time.time()
        results = await agent.qualify_batch(leads, max_concurrency=3)
        total_time = time.time() - start_time
        
        # Should complete in reasonable time (3x single request + overhead)
        assert total_time < 5.0, f"Batch processing took {total_time:.2f}s, too slow"
        assert len(results) == 3
        
        # Validate all results
        for result, latency_ms, metadata in results:
            assert latency_ms < 1000
            assert metadata['estimated_cost_usd'] < 0.0001

    @pytest.mark.asyncio
    async def test_qualification_agent_edge_cases(self):
        """Test edge cases and error handling."""
        agent = QualificationAgent()
        
        # Empty company name should raise error
        with pytest.raises(ValueError):
            await agent.qualify(company_name="")
        
        # Very long company name should work
        long_name = "A" * 1000
        result, latency_ms, metadata = await agent.qualify(company_name=long_name)
        assert result.qualification_score >= 0


class TestEnrichmentAgentProduction:
    """Production tests for EnrichmentAgent."""

    @pytest.mark.asyncio
    async def test_enrichment_agent_tool_calling(self):
        """Test EnrichmentAgent tool calling and data merging."""
        agent = EnrichmentAgent()
        
        # Test with email (most common case)
        result = await agent.enrich(email="test@example.com")
        
        # Validate tool execution
        assert len(result.tools_called) > 0, "No tools were called"
        assert len(result.data_sources) > 0, "No data sources found"
        assert result.confidence_score > 0, "Confidence score should be positive"
        
        # Performance check
        assert result.latency_ms < 3000, f"Enrichment too slow: {result.latency_ms}ms"
        
        # Cost check (should be reasonable)
        assert result.total_cost_usd < 0.01, f"Cost too high: ${result.total_cost_usd:.6f}"

    @pytest.mark.asyncio
    async def test_enrichment_agent_linkedin_only(self):
        """Test enrichment with LinkedIn URL only."""
        agent = EnrichmentAgent()
        
        result = await agent.enrich(linkedin_url="https://linkedin.com/in/testuser")
        
        # Should still work with just LinkedIn
        assert result.latency_ms < 3000
        assert result.confidence_score >= 0  # May be 0 if no data found

    @pytest.mark.asyncio
    async def test_enrichment_agent_error_handling(self):
        """Test error handling for invalid inputs."""
        agent = EnrichmentAgent()
        
        # No identifiers should raise error
        with pytest.raises(Exception):  # ValidationError from the agent
            await agent.enrich()
        
        # Invalid email format should still attempt enrichment
        result = await agent.enrich(email="invalid-email")
        assert result.latency_ms < 3000  # Should complete even if tools fail

    @pytest.mark.asyncio
    async def test_enrichment_agent_batch_processing(self):
        """Test batch enrichment performance."""
        agent = EnrichmentAgent()
        
        contacts = [
            {"email": "user1@example.com"},
            {"email": "user2@example.com"},
            {"linkedin_url": "https://linkedin.com/in/user3"}
        ]
        
        start_time = time.time()
        results = await agent.enrich_batch(contacts, max_concurrency=2)
        total_time = time.time() - start_time
        
        # Should complete in reasonable time
        assert total_time < 10.0, f"Batch enrichment took {total_time:.2f}s, too slow"
        assert len(results) == 3
        
        # All results should have reasonable latency
        for result in results:
            assert result.latency_ms < 3000


class TestConversationAgentProduction:
    """Production tests for ConversationAgent."""

    @pytest.mark.asyncio
    async def test_conversation_agent_single_turn(self):
        """Test single-turn conversation performance."""
        agent = ConversationAgent()
        
        result = await agent.send_message(text="Hello, what's your name?")
        
        # Performance assertions
        assert result.latency_breakdown['total_ms'] < 1000, f"Too slow: {result.latency_breakdown['total_ms']}ms"
        assert result.latency_breakdown['llm_ms'] < 800, f"LLM too slow: {result.latency_breakdown['llm_ms']}ms"
        assert result.latency_breakdown['tts_ms'] < 200, f"TTS too slow: {result.latency_breakdown['tts_ms']}ms"
        
        # Output validation
        assert len(result.assistant_response) > 0
        assert len(result.audio_output) > 0  # Should generate audio
        assert result.turn_number == 1
        assert result.total_cost_usd < 0.01  # Should be cheap

    @pytest.mark.asyncio
    async def test_conversation_agent_multi_turn(self):
        """Test multi-turn conversation with context."""
        agent = ConversationAgent()
        config = {"configurable": {"thread_id": "test_123"}}
        
        # Turn 1
        result1 = await agent.continue_conversation(
            text="Hello, what's your name?",
            config=config
        )
        assert result1.turn_number == 1
        assert result1.latency_breakdown['total_ms'] < 1000
        assert len(result1.conversation_history) == 2  # 1 user + 1 assistant
        
        # Turn 2 (should remember context)
        result2 = await agent.continue_conversation(
            text="What did I just ask?",
            config=config
        )
        assert result2.turn_number == 2
        assert len(result2.conversation_history) == 4  # 2 user + 2 assistant
        assert result2.latency_breakdown['total_ms'] < 1000

    @pytest.mark.asyncio
    async def test_conversation_agent_voice_config(self):
        """Test voice configuration options."""
        from app.services.cartesia_service import VoiceConfig, VoiceSpeed, VoiceEmotion
        
        agent = ConversationAgent()
        
        # Test with custom voice config
        voice_config = VoiceConfig(
            voice_id="a0e99841-438c-4a64-b679-ae501e7d6091",
            speed=VoiceSpeed.FAST,
            emotion=VoiceEmotion.POSITIVITY
        )
        
        result = await agent.send_message(
            text="Test voice configuration",
            voice_config=voice_config
        )
        
        assert result.latency_breakdown['total_ms'] < 1000
        assert len(result.audio_output) > 0
        assert result.audio_metadata['voice_id'] == voice_config.voice_id

    @pytest.mark.asyncio
    async def test_conversation_agent_error_handling(self):
        """Test error handling for invalid inputs."""
        agent = ConversationAgent()
        
        # Empty text should raise error
        with pytest.raises(Exception):  # ValidationError from the agent
            await agent.send_message(text="")
        
        # Very long text should work
        long_text = "Tell me about " + "AI " * 1000
        result = await agent.send_message(text=long_text)
        assert result.latency_breakdown['total_ms'] < 2000  # May take longer for long text


class TestAgentIntegration:
    """Integration tests across multiple agents."""

    @pytest.mark.asyncio
    async def test_qualification_to_enrichment_workflow(self):
        """Test workflow: qualify lead, then enrich contact."""
        # Step 1: Qualify a lead
        qual_agent = QualificationAgent()
        qual_result, qual_latency, qual_metadata = await qual_agent.qualify(
            company_name="TestCorp",
            industry="SaaS",
            company_size="50-200"
        )
        
        assert qual_latency < 1000
        assert qual_result.qualification_score > 0
        
        # Step 2: Enrich contact (if qualified)
        if qual_result.tier in ["hot", "warm"]:
            enrich_agent = EnrichmentAgent()
            enrich_result = await enrich_agent.enrich(email="contact@testcorp.com")
            
            assert enrich_result.latency_ms < 3000
            assert enrich_result.confidence_score >= 0

    @pytest.mark.asyncio
    async def test_conversation_with_context(self):
        """Test conversation agent with lead context."""
        agent = ConversationAgent()
        
        # Simulate conversation about a qualified lead
        context = {
            "lead_id": 123,
            "purpose": "lead_qualification",
            "company_name": "TestCorp",
            "qualification_score": 85
        }
        
        result = await agent.send_message(
            text="Tell me about this lead",
            context=context
        )
        
        assert result.latency_breakdown['total_ms'] < 1000
        assert len(result.assistant_response) > 0


class TestPerformanceBenchmarks:
    """Performance benchmark tests."""

    @pytest.mark.asyncio
    async def test_qualification_agent_benchmark(self):
        """Benchmark QualificationAgent performance."""
        agent = QualificationAgent()
        
        # Test multiple runs for average performance
        latencies = []
        costs = []
        
        for i in range(5):
            result, latency_ms, metadata = await agent.qualify(
                company_name=f"TestCorp{i}",
                industry="SaaS",
                company_size="50-200"
            )
            latencies.append(latency_ms)
            costs.append(metadata['estimated_cost_usd'])
        
        avg_latency = sum(latencies) / len(latencies)
        avg_cost = sum(costs) / len(costs)
        
        # Performance targets
        assert avg_latency < 1000, f"Average latency {avg_latency:.1f}ms exceeds 1000ms target"
        assert avg_cost < 0.0001, f"Average cost ${avg_cost:.6f} exceeds budget"
        
        # Consistency check (no outliers)
        max_latency = max(latencies)
        assert max_latency < 1500, f"Max latency {max_latency}ms is too high"

    @pytest.mark.asyncio
    async def test_enrichment_agent_benchmark(self):
        """Benchmark EnrichmentAgent performance."""
        agent = EnrichmentAgent()
        
        # Test with different input types
        test_cases = [
            {"email": "test1@example.com"},
            {"email": "test2@example.com"},
            {"linkedin_url": "https://linkedin.com/in/test3"},
        ]
        
        latencies = []
        costs = []
        
        for case in test_cases:
            result = await agent.enrich(**case)
            latencies.append(result.latency_ms)
            costs.append(result.total_cost_usd)
        
        avg_latency = sum(latencies) / len(latencies)
        avg_cost = sum(costs) / len(costs)
        
        # Performance targets
        assert avg_latency < 3000, f"Average latency {avg_latency:.1f}ms exceeds 3000ms target"
        assert avg_cost < 0.01, f"Average cost ${avg_cost:.6f} exceeds budget"

    @pytest.mark.asyncio
    async def test_conversation_agent_benchmark(self):
        """Benchmark ConversationAgent performance."""
        agent = ConversationAgent()
        
        # Test multiple conversation turns
        latencies = []
        costs = []
        
        messages = [
            "Hello, what's your name?",
            "What do you do?",
            "Tell me about your services",
            "How can you help me?",
            "Thank you for your time"
        ]
        
        for message in messages:
            result = await agent.send_message(text=message)
            latencies.append(result.latency_breakdown['total_ms'])
            costs.append(result.total_cost_usd)
        
        avg_latency = sum(latencies) / len(latencies)
        avg_cost = sum(costs) / len(costs)
        
        # Performance targets
        assert avg_latency < 1000, f"Average latency {avg_latency:.1f}ms exceeds 1000ms target"
        assert avg_cost < 0.01, f"Average cost ${avg_cost:.6f} exceeds budget"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
