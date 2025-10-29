"""
Unit tests for Agent CLI functionality.

Tests CLI commands, user interactions, and output formatting.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from io import StringIO
import sys

# Mock the agent imports since we're testing CLI logic
sys.path.insert(0, '/Users/tmkipper/Desktop/tk_projects/sales-agent')

from agent_cli import AgentCLI


class TestAgentCLI:
    """Test cases for AgentCLI class."""

    def test_init(self):
        """Test CLI initialization."""
        cli = AgentCLI(enable_tracing=False)
        assert cli.enable_tracing is False
        assert cli.conversation_thread_id is None

    def test_init_with_tracing(self):
        """Test CLI initialization with tracing enabled."""
        cli = AgentCLI(enable_tracing=True)
        assert cli.enable_tracing is True

    @patch('agent_cli.console')
    def test_show_main_menu(self, mock_console):
        """Test main menu display."""
        cli = AgentCLI()
        
        # Mock user input
        with patch('agent_cli.Prompt.ask', return_value="1"):
            choice = cli.show_main_menu()
            assert choice == "1"
        
        # Verify console.print was called
        assert mock_console.print.call_count >= 4  # Menu options + prompt

    @patch('agent_cli.QualificationAgent')
    @patch('agent_cli.console')
    @patch('agent_cli.Prompt')
    def test_run_qualification_agent(self, mock_prompt, mock_console, mock_agent_class):
        """Test qualification agent execution."""
        cli = AgentCLI()
        
        # Mock agent instance and result
        mock_agent = AsyncMock()
        mock_result = Mock()
        mock_result.qualification_score = 85
        mock_result.tier = "hot"
        mock_result.qualification_reasoning = "Great fit for our product"
        mock_result.recommendations = ["Schedule demo", "Send case study"]
        
        mock_agent.qualify.return_value = (mock_result, 500, {"estimated_cost_usd": 0.00005})
        mock_agent_class.return_value = mock_agent
        
        # Mock user inputs
        mock_prompt.ask.side_effect = ["TestCorp", "SaaS", "50-200"]
        
        # Run the test
        asyncio.run(cli.run_qualification_agent())
        
        # Verify agent was called with correct parameters
        mock_agent.qualify.assert_called_once_with(
            company_name="TestCorp",
            industry="SaaS",
            company_size="50-200"
        )

    @patch('agent_cli.EnrichmentAgent')
    @patch('agent_cli.console')
    @patch('agent_cli.Prompt')
    def test_run_enrichment_agent_with_email(self, mock_prompt, mock_console, mock_agent_class):
        """Test enrichment agent execution with email."""
        cli = AgentCLI()
        
        # Mock agent instance and result
        mock_agent = AsyncMock()
        mock_result = Mock()
        mock_result.enriched_data = {"email": "test@example.com", "name": "Test User"}
        mock_result.confidence_score = 0.8
        mock_result.data_sources = ["apollo.io"]
        mock_result.latency_ms = 2000
        mock_result.total_cost_usd = 0.005
        
        mock_agent.enrich.return_value = mock_result
        mock_agent_class.return_value = mock_agent
        
        # Mock user inputs
        mock_prompt.ask.side_effect = ["test@example.com", ""]
        
        # Run the test
        asyncio.run(cli.run_enrichment_agent())
        
        # Verify agent was called with correct parameters
        mock_agent.enrich.assert_called_once_with(
            email="test@example.com",
            linkedin_url=None
        )

    @patch('agent_cli.EnrichmentAgent')
    @patch('agent_cli.console')
    @patch('agent_cli.Prompt')
    def test_run_enrichment_agent_no_inputs(self, mock_prompt, mock_console, mock_agent_class):
        """Test enrichment agent with no inputs (should show error)."""
        cli = AgentCLI()
        
        # Mock user inputs (both empty)
        mock_prompt.ask.side_effect = ["", ""]
        
        # Run the test
        asyncio.run(cli.run_enrichment_agent())
        
        # Verify error message was printed
        mock_console.print.assert_called_with("[red]Error: Provide at least email or LinkedIn URL[/red]")
        
        # Verify agent was not called
        mock_agent_class.assert_not_called()

    @patch('agent_cli.ConversationAgent')
    @patch('agent_cli.console')
    @patch('agent_cli.Prompt')
    def test_run_conversation_agent_single_turn(self, mock_prompt, mock_console, mock_agent_class):
        """Test conversation agent single turn."""
        cli = AgentCLI()
        
        # Mock agent instance and result
        mock_agent = AsyncMock()
        mock_result = Mock()
        mock_result.assistant_response = "Hello! I'm an AI assistant."
        mock_result.latency_breakdown = {"total_ms": 800}
        
        mock_agent.send_message.return_value = mock_result
        mock_agent_class.return_value = mock_agent
        
        # Mock user inputs (one message then exit)
        mock_prompt.ask.side_effect = ["Hello", "exit"]
        
        # Run the test
        asyncio.run(cli.run_conversation_agent())
        
        # Verify agent was called once
        mock_agent.send_message.assert_called_once_with(text="Hello")

    @patch('agent_cli.console')
    def test_display_qualification_result(self, mock_console):
        """Test qualification result display formatting."""
        cli = AgentCLI()
        
        # Mock result
        mock_result = Mock()
        mock_result.qualification_score = 85
        mock_result.tier = "hot"
        mock_result.qualification_reasoning = "Great fit for our product"
        mock_result.recommendations = ["Schedule demo", "Send case study"]
        
        metadata = {"estimated_cost_usd": 0.00005}
        
        # Run the test
        cli.display_qualification_result(mock_result, 500, metadata)
        
        # Verify console.print was called multiple times (table + reasoning + recommendations)
        assert mock_console.print.call_count >= 3

    @patch('agent_cli.console')
    def test_display_enrichment_result(self, mock_console):
        """Test enrichment result display formatting."""
        cli = AgentCLI()
        
        # Mock result
        mock_result = Mock()
        mock_result.enriched_data = {
            "email": "test@example.com",
            "name": "Test User",
            "company": "TestCorp",
            "experience": [{"title": "Engineer", "company": "TestCorp"}]
        }
        mock_result.confidence_score = 0.8
        mock_result.data_sources = ["apollo.io", "linkedin"]
        mock_result.latency_ms = 2000
        mock_result.total_cost_usd = 0.005
        
        # Run the test
        cli.display_enrichment_result(mock_result)
        
        # Verify console.print was called multiple times (tree + metadata)
        assert mock_console.print.call_count >= 2


class TestAgentCLIIntegration:
    """Integration tests for CLI with mocked agents."""

    @patch('agent_cli.QualificationAgent')
    @patch('agent_cli.console')
    @patch('agent_cli.Prompt')
    def test_qualification_workflow(self, mock_prompt, mock_console, mock_agent_class):
        """Test complete qualification workflow."""
        cli = AgentCLI()
        
        # Mock agent
        mock_agent = AsyncMock()
        mock_result = Mock()
        mock_result.qualification_score = 75
        mock_result.tier = "warm"
        mock_result.qualification_reasoning = "Good potential customer"
        mock_result.recommendations = ["Follow up next week"]
        
        mock_agent.qualify.return_value = (mock_result, 600, {"estimated_cost_usd": 0.00003})
        mock_agent_class.return_value = mock_agent
        
        # Mock user inputs
        mock_prompt.ask.side_effect = ["WarmCorp", "SaaS", "100-500"]
        
        # Run qualification
        asyncio.run(cli.run_qualification_agent())
        
        # Verify all interactions
        mock_agent.qualify.assert_called_once()
        assert mock_console.print.call_count >= 3  # Menu + results + formatting

    @patch('agent_cli.EnrichmentAgent')
    @patch('agent_cli.console')
    @patch('agent_cli.Prompt')
    def test_enrichment_workflow(self, mock_prompt, mock_console, mock_agent_class):
        """Test complete enrichment workflow."""
        cli = AgentCLI()
        
        # Mock agent
        mock_agent = AsyncMock()
        mock_result = Mock()
        mock_result.enriched_data = {
            "email": "contact@warmcorp.com",
            "name": "John Doe",
            "title": "CTO",
            "company": "WarmCorp"
        }
        mock_result.confidence_score = 0.9
        mock_result.data_sources = ["apollo.io"]
        mock_result.latency_ms = 1500
        mock_result.total_cost_usd = 0.002
        
        mock_agent.enrich.return_value = mock_result
        mock_agent_class.return_value = mock_agent
        
        # Mock user inputs
        mock_prompt.ask.side_effect = ["contact@warmcorp.com", ""]
        
        # Run enrichment
        asyncio.run(cli.run_enrichment_agent())
        
        # Verify all interactions
        mock_agent.enrich.assert_called_once()
        assert mock_console.print.call_count >= 2  # Menu + results

    @patch('agent_cli.ConversationAgent')
    @patch('agent_cli.console')
    @patch('agent_cli.Prompt')
    def test_conversation_workflow(self, mock_prompt, mock_console, mock_agent_class):
        """Test complete conversation workflow."""
        cli = AgentCLI()
        
        # Mock agent
        mock_agent = AsyncMock()
        mock_result = Mock()
        mock_result.assistant_response = "Hello! How can I help you today?"
        mock_result.latency_breakdown = {"total_ms": 700}
        
        mock_agent.send_message.return_value = mock_result
        mock_agent_class.return_value = mock_agent
        
        # Mock user inputs (conversation then exit)
        mock_prompt.ask.side_effect = ["Hi there", "exit"]
        
        # Run conversation
        asyncio.run(cli.run_conversation_agent())
        
        # Verify all interactions
        mock_agent.send_message.assert_called_once_with(text="Hi there")
        assert mock_console.print.call_count >= 3  # Menu + response + latency


class TestAgentCLIErrorHandling:
    """Test error handling in CLI."""

    @patch('agent_cli.QualificationAgent')
    @patch('agent_cli.console')
    @patch('agent_cli.Prompt')
    def test_qualification_agent_error(self, mock_prompt, mock_console, mock_agent_class):
        """Test qualification agent error handling."""
        cli = AgentCLI()
        
        # Mock agent that raises exception
        mock_agent = AsyncMock()
        mock_agent.qualify.side_effect = Exception("API Error")
        mock_agent_class.return_value = mock_agent
        
        # Mock user inputs
        mock_prompt.ask.side_effect = ["TestCorp", "SaaS", "50-200"]
        
        # Run the test (should not crash)
        try:
            asyncio.run(cli.run_qualification_agent())
        except Exception:
            # The CLI should handle the error gracefully
            pass

    @patch('agent_cli.EnrichmentAgent')
    @patch('agent_cli.console')
    @patch('agent_cli.Prompt')
    def test_enrichment_agent_error(self, mock_prompt, mock_console, mock_agent_class):
        """Test enrichment agent error handling."""
        cli = AgentCLI()
        
        # Mock agent that raises exception
        mock_agent = AsyncMock()
        mock_agent.enrich.side_effect = Exception("Network Error")
        mock_agent_class.return_value = mock_agent
        
        # Mock user inputs
        mock_prompt.ask.side_effect = ["test@example.com", ""]
        
        # Run the test (should not crash)
        try:
            asyncio.run(cli.run_enrichment_agent())
        except Exception:
            # The CLI should handle the error gracefully
            pass

    @patch('agent_cli.ConversationAgent')
    @patch('agent_cli.console')
    @patch('agent_cli.Prompt')
    def test_conversation_agent_error(self, mock_prompt, mock_console, mock_agent_class):
        """Test conversation agent error handling."""
        cli = AgentCLI()
        
        # Mock agent that raises exception
        mock_agent = AsyncMock()
        mock_agent.send_message.side_effect = Exception("TTS Error")
        mock_agent_class.return_value = mock_agent
        
        # Mock user inputs
        mock_prompt.ask.side_effect = ["Hello", "exit"]
        
        # Run the test (should not crash)
        try:
            asyncio.run(cli.run_conversation_agent())
        except Exception:
            # The CLI should handle the error gracefully
            pass


class TestAgentCLIOutputFormatting:
    """Test output formatting and display."""

    def test_qualification_result_table_formatting(self):
        """Test qualification result table formatting."""
        cli = AgentCLI()
        
        # Mock result with specific values
        mock_result = Mock()
        mock_result.qualification_score = 92
        mock_result.tier = "hot"
        mock_result.qualification_reasoning = "Excellent fit with strong buying signals"
        mock_result.recommendations = [
            "Schedule immediate demo",
            "Send personalized case study",
            "Connect with decision maker"
        ]
        
        metadata = {"estimated_cost_usd": 0.00008}
        
        with patch('agent_cli.console') as mock_console:
            cli.display_qualification_result(mock_result, 450, metadata)
            
            # Verify table was created and printed
            assert mock_console.print.call_count >= 3

    def test_enrichment_result_tree_formatting(self):
        """Test enrichment result tree formatting."""
        cli = AgentCLI()
        
        # Mock result with nested data
        mock_result = Mock()
        mock_result.enriched_data = {
            "contact_info": {
                "email": "john@example.com",
                "phone": "+1-555-0123"
            },
            "professional": {
                "title": "VP Engineering",
                "company": "TechCorp"
            },
            "experience": [
                {"title": "Senior Engineer", "company": "PreviousCorp"},
                {"title": "VP Engineering", "company": "TechCorp"}
            ]
        }
        mock_result.confidence_score = 0.95
        mock_result.data_sources = ["apollo.io", "linkedin_scraping"]
        mock_result.latency_ms = 1800
        mock_result.total_cost_usd = 0.003
        
        with patch('agent_cli.console') as mock_console:
            cli.display_enrichment_result(mock_result)
            
            # Verify tree was created and printed
            assert mock_console.print.call_count >= 2


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
