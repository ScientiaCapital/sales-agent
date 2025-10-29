# 🤖 Sales Agent CLI Guide

Interactive terminal interface for testing and interacting with LangGraph agents in the Sales-Agent platform.

## Quick Start

```bash
# Interactive mode (recommended)
python agent_cli.py

# Direct agent invocation
python agent_cli.py --agent qualify
python agent_cli.py --agent enrich
python agent_cli.py --agent converse

# With LangSmith tracing
python agent_cli.py --trace
```

## Features

### 🎯 **3 Core Agents Available**
- **Qualification Agent** - Score leads with Cerebras AI (<1000ms)
- **Enrichment Agent** - Enrich contacts with Apollo/LinkedIn (<3000ms)  
- **Conversation Agent** - Voice-enabled chat (<1000ms/turn)

### 🎨 **Rich Terminal UI**
- Beautiful color-coded output
- Progress spinners during execution
- Formatted tables and trees for results
- Real-time streaming responses

### 🔍 **Production Ready**
- Comprehensive error handling
- Performance monitoring
- Cost tracking
- LangSmith observability

## Installation

### Prerequisites
```bash
# 1. Install Python dependencies
pip install -r backend/requirements.txt

# 2. Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# 3. Start required services
docker-compose up -d postgres redis
```

### Quick Setup
```bash
# Use the production launcher (handles everything)
./scripts/run_agent_cli.sh
```

## Usage Examples

### 1. Qualification Agent

**Interactive Mode:**
```bash
python agent_cli.py
# Select option 1: Qualification Agent
# Enter: Company name: "Acme Corp"
# Enter: Industry: "SaaS" 
# Enter: Company size: "50-200"
```

**Direct Mode:**
```bash
python agent_cli.py --agent qualify
```

**Expected Output:**
```
┌─────────────────────────────────┐
│        Qualification Results    │
├─────────────┬───────────────────┤
│ Score       │ 85/100            │
│ Tier        │ HOT               │
│ Latency     │ 450ms             │
│ Cost        │ $0.000045         │
└─────────────┴───────────────────┘

Reasoning:
Strong SaaS alignment with mid-market size. 
Decision-maker contact available with recent 
funding signals indicating buying readiness.

Recommendations:
  1. Schedule immediate demo
  2. Send personalized case study
  3. Connect with decision maker
```

### 2. Enrichment Agent

**Interactive Mode:**
```bash
python agent_cli.py
# Select option 2: Enrichment Agent
# Enter: Email address: "john@acme.com"
# Enter: LinkedIn URL: (optional)
```

**Direct Mode:**
```bash
python agent_cli.py --agent enrich
```

**Expected Output:**
```
Enriched Data
├── contact_info
│   ├── email: john@acme.com
│   ├── phone: +1-555-0123
│   └── first_name: John
├── professional
│   ├── title: VP Engineering
│   ├── company: Acme Corp
│   └── linkedin_url: https://linkedin.com/in/johndoe
└── experience
    ├── Senior Engineer at PreviousCorp (2020-2022)
    └── VP Engineering at Acme Corp (2022-present)

Confidence: 0.92
Sources: apollo.io, linkedin_scraping
Latency: 1800ms
Cost: $0.003
```

### 3. Conversation Agent

**Interactive Mode:**
```bash
python agent_cli.py
# Select option 3: Conversation Agent
# Type: "Hello, what's your name?"
# Type: "Tell me about your services"
# Type: "exit" to return to main menu
```

**Direct Mode:**
```bash
python agent_cli.py --agent converse
```

**Expected Output:**
```
You: Hello, what's your name?
Agent: Hello! I'm an AI assistant designed to help with sales and lead qualification. How can I assist you today?
(700ms)

You: Tell me about your services
Agent: I can help you qualify leads, enrich contact data, and have voice conversations. I specialize in B2B sales automation with ultra-fast response times.
(650ms)

You: exit
```

## Command Line Options

### Basic Usage
```bash
python agent_cli.py [OPTIONS]

Options:
  --agent [qualify|enrich|converse]  Direct agent invocation
  --trace / --no-trace               Enable LangSmith tracing
  --help                            Show help message
```

### Examples
```bash
# Interactive mode with tracing
python agent_cli.py --trace

# Direct qualification with tracing
python agent_cli.py --agent qualify --trace

# Direct enrichment
python agent_cli.py --agent enrich

# Direct conversation
python agent_cli.py --agent converse
```

## Performance Targets

| Agent | Target Latency | Cost/Request | Use Case |
|-------|----------------|--------------|----------|
| **Qualification** | <1000ms | <$0.0001 | Ultra-fast lead scoring |
| **Enrichment** | <3000ms | <$0.01 | Contact data enrichment |
| **Conversation** | <1000ms/turn | <$0.01 | Voice-enabled chat |

## Troubleshooting

### Common Issues

**1. Import Errors**
```bash
# Error: ModuleNotFoundError: No module named 'app'
# Solution: Run from project root directory
cd /path/to/sales-agent
python agent_cli.py
```

**2. Missing Dependencies**
```bash
# Error: ModuleNotFoundError: No module named 'rich'
# Solution: Install requirements
pip install -r backend/requirements.txt
```

**3. API Key Errors**
```bash
# Error: CEREBRAS_API_KEY environment variable not set
# Solution: Check .env file
cat .env | grep CEREBRAS_API_KEY
```

**4. Service Connection Issues**
```bash
# Error: Connection refused to PostgreSQL/Redis
# Solution: Start services
docker-compose up -d postgres redis
```

**5. Agent Execution Errors**
```bash
# Error: Agent execution failed
# Solution: Check logs and try with --trace for debugging
python agent_cli.py --trace
```

### Debug Mode

Enable detailed logging and tracing:

```bash
# Set environment variables
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=your_langsmith_key
export LANGCHAIN_PROJECT=sales-agent-cli

# Run with tracing
python agent_cli.py --trace
```

### Performance Debugging

```bash
# Run production tests
cd backend
pytest tests/test_agents_production.py -v

# Run CLI tests
pytest tests/test_agent_cli.py -v

# Check agent performance
python -c "
import asyncio
from app.services.langgraph.agents.qualification_agent import QualificationAgent
async def test():
    agent = QualificationAgent()
    result, latency, meta = await agent.qualify('TestCorp', 'SaaS', '50-200')
    print(f'Latency: {latency}ms, Cost: ${meta[\"estimated_cost_usd\"]:.6f}')
asyncio.run(test())
"
```

## Advanced Usage

### Custom Voice Configuration

For the Conversation Agent, you can customize voice settings:

```python
# In agent_cli.py, modify the voice_config
from app.services.cartesia_service import VoiceConfig, VoiceSpeed, VoiceEmotion

voice_config = VoiceConfig(
    voice_id="a0e99841-438c-4a64-b679-ae501e7d6091",  # Professional voice
    speed=VoiceSpeed.FAST,  # NORMAL, FAST, SLOW
    emotion=VoiceEmotion.POSITIVITY  # POSITIVITY, NEUTRAL, ENERGY
)
```

### Batch Processing

For testing multiple leads or contacts:

```python
# Qualification batch
from app.services.langgraph.agents.qualification_agent import QualificationAgent

agent = QualificationAgent()
leads = [
    {"company_name": "Corp1", "industry": "SaaS"},
    {"company_name": "Corp2", "industry": "FinTech"}
]
results = await agent.qualify_batch(leads)
```

### Integration with Workflows

The CLI integrates with the workflow commands:

```bash
# Use feature workflow to create new agents
python commands/feature_workflow.py

# Debug agent issues
python commands/debug_workflow.py

# Optimize agent performance
python commands/performance_workflow.py
```

## Development

### Adding New Agents

1. Create agent in `backend/app/services/langgraph/agents/`
2. Add import to `agent_cli.py`
3. Add menu option in `show_main_menu()`
4. Add execution method (e.g., `run_new_agent()`)
5. Add display method (e.g., `display_new_agent_result()`)

### Testing

```bash
# Run all tests
cd backend
pytest tests/ -v

# Run specific test files
pytest tests/test_agent_cli.py -v
pytest tests/test_agents_production.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Contributing

1. Follow existing code patterns
2. Add tests for new features
3. Update documentation
4. Test with all 3 agents
5. Validate performance targets

## Support

- **Documentation**: See `README.md` for project overview
- **Issues**: Check troubleshooting section above
- **Performance**: Run production tests to validate
- **Debugging**: Use `--trace` flag for detailed logs

---

**Ready to test your agents! 🚀**

```bash
# Start the CLI
python agent_cli.py

# Or use the production launcher
./scripts/run_agent_cli.sh
```
