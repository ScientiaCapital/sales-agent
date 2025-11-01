"""Interactive CLI for testing Claude Agent SDK agents."""
import asyncio
from typing import Optional
import sys

from app.agents_sdk.agents import SRBDRAgent, PipelineManagerAgent, CustomerSuccessAgent
from app.agents_sdk.sessions import RedisSessionStore
from app.agents_sdk.schemas.chat import ChatMessage
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class AgentCLI:
    """
    Interactive CLI for testing agents during development.

    Usage:
        python -m app.agents_sdk.cli sr_bdr
        python -m app.agents_sdk.cli pipeline_manager
        python -m app.agents_sdk.cli cs_agent
    """

    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        self.agent = self._create_agent(agent_type)
        self.session_id: Optional[str] = None

    def _create_agent(self, agent_type: str):
        """Create agent instance."""
        agents = {
            "sr_bdr": SRBDRAgent,
            "pipeline_manager": PipelineManagerAgent,
            "cs_agent": CustomerSuccessAgent
        }

        if agent_type not in agents:
            raise ValueError(
                f"Unknown agent type: {agent_type}. "
                f"Available: {', '.join(agents.keys())}"
            )

        return agents[agent_type]()

    async def start_session(self):
        """Initialize session."""
        redis_store = await RedisSessionStore.create()
        self.session_id = await redis_store.create_session(
            user_id="cli_test_user",
            agent_type=self.agent_type
        )
        logger.info(f"Started session: {self.session_id}")

    async def chat(self, message: str):
        """Send message to agent and stream response."""
        if not self.session_id:
            await self.start_session()

        print(f"\n🧑 You: {message}")
        print(f"🤖 {self.agent.name.replace('_', ' ').title()}: ", end="", flush=True)

        # Stream agent response
        full_response = ""
        async for chunk in self.agent.chat(self.session_id, message):
            # Extract text from SSE format
            if isinstance(chunk, dict) and "text" in chunk:
                text = chunk["text"]
            else:
                text = chunk

            print(text, end="", flush=True)
            full_response += text

        print()  # Newline after response
        return full_response

    async def run(self):
        """Run interactive CLI loop."""
        print(f"\n{'='*60}")
        print(f"Claude Agent SDK - Interactive CLI")
        print(f"Agent: {self.agent.name.replace('_', ' ').title()}")
        print(f"{'='*60}\n")
        print("Commands:")
        print("  - Type your message and press Enter")
        print("  - /quit or /exit: Exit CLI")
        print("  - /clear: Start new session")
        print("  - /help: Show agent capabilities")
        print(f"{'='*60}\n")

        try:
            await self.start_session()

            while True:
                try:
                    # Get user input
                    user_input = input("\n🧑 You: ").strip()

                    if not user_input:
                        continue

                    # Handle commands
                    if user_input.lower() in ["/quit", "/exit"]:
                        print("\n👋 Goodbye!")
                        break

                    if user_input.lower() == "/clear":
                        await self.start_session()
                        print(f"✅ New session started: {self.session_id}")
                        continue

                    if user_input.lower() == "/help":
                        self._show_help()
                        continue

                    # Send message to agent
                    await self.chat(user_input)

                except KeyboardInterrupt:
                    print("\n\n👋 Goodbye!")
                    break

                except Exception as e:
                    logger.error(f"Error during chat: {e}", exc_info=True)
                    print(f"\n❌ Error: {e}")
                    print("Type /clear to start a new session or /quit to exit")

        finally:
            print("\n" + "="*60)
            print("Session ended. Check logs for details.")
            print("="*60 + "\n")

    def _show_help(self):
        """Show agent-specific help."""
        help_text = {
            "sr_bdr": """
SR/BDR Agent - Sales Rep Assistant

Example queries:
- "What are my top 5 leads today?"
- "Tell me about Acme Corp"
- "Show me all PLATINUM tier leads in Texas"
- "Qualify this lead: TechCorp, Construction industry, 50 employees"

Available tools:
- qualify_lead_tool: Score and tier leads
- search_leads_tool: Find leads by filters
- enrich_company_tool: Get detailed company data
""",
            "pipeline_manager": """
Pipeline Manager Agent - License Import Orchestration

Example queries:
- "I have 5 new license lists to import: CA, TX, FL, AZ, NV"
- "Validate these files before I start"
- "Run Phase 1 cross-reference for California"
- "Show me the quality report for the last import"
- "What's the status of my import pipeline?"

Available tools:
- validate_files_tool: Check CSV quality
- cross_reference_tool: State license matching
- multi_state_detection_tool: Find multi-state contractors
- icp_scoring_tool: Qualify and tier leads
""",
            "cs_agent": """
Customer Success Agent - Onboarding & Support

Example queries:
- "How do I import my first lead list?"
- "My Close CRM integration isn't working"
- "What features are available in my plan?"
- "Show me how to set up the pipeline import"
- "What's the best way to qualify leads?"

Available tools:
- qualify_lead_tool: Help customers test qualification
- search_documentation_tool: Find help articles
- check_integration_status_tool: Verify API connections
"""
        }

        print("\n" + "="*60)
        print(help_text.get(self.agent_type, "No help available"))
        print("="*60)


async def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("\nUsage: python -m app.agents_sdk.cli <agent_type>\n")
        print("Available agents:")
        print("  - sr_bdr: Sales Rep/BDR conversational assistant")
        print("  - pipeline_manager: License import orchestration")
        print("  - cs_agent: Customer success and onboarding\n")
        sys.exit(1)

    agent_type = sys.argv[1]

    try:
        cli = AgentCLI(agent_type)
        await cli.run()
    except ValueError as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)
    except Exception as e:
        logger.error(f"CLI error: {e}", exc_info=True)
        print(f"\n❌ Unexpected error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
