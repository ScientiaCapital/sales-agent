# Sales Agent - Claude Code Development Guidelines

## Project Overview

AI-powered sales automation platform leveraging Cerebras ultra-fast inference for real-time lead qualification and intelligent outreach.

## Architecture Principles

### Ultra-Fast Inference First
- **Primary**: Cerebras Inference API (<100ms latency)
- **Use Case**: Real-time conversation intelligence, lead qualification
- **Pattern**: Follow examples in `Cerebras-Inference-Cookbook/`

### Multi-Agent Coordination
- **Search Agent Pattern**: Automated research and report generation
- **Gist Memory Pattern**: Document summarization and search
- **Custom Agents**: Build on these foundations for sales workflows

### Cost-Effective AI Stack
```
Development: Claude Sonnet 4.5 (premium quality)
Research: DeepSeek v3 ($0.27/1M tokens)
Fallback: GPT-4o-mini
Local: Ollama for simple queries
```

## Development Workflow

### Daily Routine
1. `/team-start-advanced` - Initialize all MCP servers
2. `/daily-standup-mcp` - Morning planning
3. `task-master next` - Get next task
4. Implement following Task Master guidelines
5. `task-master set-status --id=<id> --status=done`

### Feature Development
1. **Plan** - `/team-orchestrate [feature description]`
2. **Research** - `/team-research [technical topic]` if needed
3. **Implement** - Use Cerebras patterns from cookbook
4. **Verify** - Test with real-time inference requirements
5. **Document** - Update tasks and memory

## Technical Stack

### Core Dependencies
- **Cerebras SDK** - Ultra-fast LLM inference
- **Python 3.8+** - For agent scripts
- **Node.js 18+** - For tooling and MCP servers
- **Task Master AI** - Project management

### Cerebras Integration Patterns

#### 1. Search Agent Pattern
```python
# Location: Cerebras-Inference-Cookbook/agents/search-agent/
# Use for: Lead research, company intelligence
# Key Feature: Multi-agent pipeline with <100ms responses
```

#### 2. Gist Memory Pattern
```python
# Location: Cerebras-Inference-Cookbook/agents/gist-memory/
# Use for: Document analysis, conversation history
# Key Feature: Efficient long-document processing
```

#### 3. Custom Agent Template
```python
from cerebras.cloud.sdk import Cerebras

client = Cerebras(api_key=os.environ.get("CEREBRAS_API_KEY"))

# Ultra-fast inference call
response = client.chat.completions.create(
    model="llama-3.3-70b",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=1000,
    temperature=0.7
)
```

## Code Organization

### Directory Structure
```
sales-agent/
├── agents/                  # Custom sales agents
│   ├── lead-qualifier/     # Lead qualification agent
│   ├── outreach/           # Outreach automation
│   └── conversation/       # Conversation intelligence
├── Cerebras-Inference-Cookbook/  # Reference examples
├── .taskmaster/            # Task management
├── .claude/                # Claude Code config
└── README.md
```

### File Naming Conventions
- Agents: `{purpose}_agent.py`
- Utilities: `{function}_utils.py`
- Tests: `test_{module}.py`
- Configs: `{service}_config.json`

## MCP Server Usage

### Task Master AI
```bash
# Always use for task management
task-master list
task-master next
task-master show <id>
task-master update-subtask --id=<id> --prompt="notes"
```

### Serena (Code Intelligence)
```bash
# Use for codebase navigation
# Let Claude Code invoke via MCP automatically
# Focus on symbolic tools for Python modules
```

### Sequential Thinking
```bash
# Use for complex problem solving
# Invoke when architectural decisions needed
# Break down multi-step implementations
```

### Memory MCP
```bash
# Save project knowledge
# Store architectural decisions
# Remember integration patterns
```

### Shrimp Task Manager
```bash
# Use for detailed planning
# Verify complex implementations
# Track multi-phase features
```

## Coding Standards

### Python (Cerebras Agents)
```python
# Follow Cerebras cookbook patterns
# Use type hints
# Document with docstrings
# Keep functions focused and testable

def qualify_lead(lead_data: dict) -> dict:
    """
    Qualify a lead using Cerebras inference.

    Args:
        lead_data: Dictionary containing lead information

    Returns:
        Qualification result with score and reasoning
    """
    # Implementation using Cerebras pattern
```

### Error Handling
```python
# Always handle API errors gracefully
try:
    response = client.chat.completions.create(...)
except Exception as e:
    logger.error(f"Cerebras API error: {e}")
    # Fallback to DeepSeek or GPT-4o-mini
```

### Performance Requirements
- **Cerebras calls**: Target <100ms latency
- **Batch operations**: Use async when possible
- **Caching**: Cache repeated queries
- **Monitoring**: Log inference times

## Testing Strategy

### Unit Tests
```python
# Test individual agent functions
# Mock Cerebras API calls
# Verify logic independently
```

### Integration Tests
```python
# Test multi-agent coordination
# Use Cerebras test environment
# Verify end-to-end workflows
```

### Performance Tests
```python
# Measure inference latency
# Test under load
# Verify <100ms target
```

## Task Master Integration

### Task Structure
- **Main tasks**: Feature-level (e.g., "Lead Qualification Engine")
- **Subtasks**: Implementation steps (e.g., "Implement scoring algorithm")
- **Sub-subtasks**: Specific code changes

### Implementation Logging
```bash
# Before coding
task-master update-subtask --id=1.2 --prompt="Planning to use Cerebras search agent pattern"

# During implementation
task-master update-subtask --id=1.2 --prompt="Integrated with lead database, added caching"

# After completion
task-master set-status --id=1.2 --status=done
```

## Common Patterns

### 1. Real-time Lead Scoring
```python
# Use Cerebras for ultra-fast scoring
# Pattern: Sync API call with <100ms target
# Location: agents/lead-qualifier/
```

### 2. Automated Outreach
```python
# Use multi-agent pattern from cookbook
# Pattern: Research → Personalize → Send
# Location: agents/outreach/
```

### 3. Conversation Intelligence
```python
# Use gist memory pattern for context
# Pattern: Summarize → Analyze → Respond
# Location: agents/conversation/
```

## Environment Variables

Required in `.env`:
```bash
# Cerebras (primary)
CEREBRAS_API_KEY=your_cerebras_key

# Claude (development)
ANTHROPIC_API_KEY=your_anthropic_key

# DeepSeek (research) - NEVER hardcode!
DEEPSEEK_API_KEY=your_deepseek_key
OPENROUTER_API_KEY=your_deepseek_key

# Optional fallbacks
OPENAI_API_KEY=your_openai_key
OLLAMA_API_KEY=your_ollama_key
```

## Best Practices

### DO
✅ Use Cerebras for real-time inference
✅ Follow cookbook patterns
✅ Log all agent decisions
✅ Cache repeated queries
✅ Test latency requirements
✅ Update tasks during development
✅ Use DeepSeek for research (cost-effective)

### DON'T
❌ Hardcode API keys anywhere
❌ Ignore latency requirements
❌ Skip error handling
❌ Commit `.env` files
❌ Use synchronous calls unnecessarily
❌ Forget to update task status
❌ Use expensive models for simple queries

## Debugging

### Cerebras Issues
```bash
# Check API key
echo $CEREBRAS_API_KEY

# Test connection
python Cerebras-Inference-Cookbook/agents/search-agent/test_connection.py

# Monitor latency
# Add timing to all Cerebras calls
```

### Task Master Issues
```bash
# Verify installation
task-master --version

# Check config
cat .taskmaster/config.json

# Regenerate tasks
task-master generate
```

### MCP Server Issues
```bash
# Restart Claude Code with debug
claude --mcp-debug

# Check MCP config
cat .mcp.json

# Verify API keys in environment
env | grep API_KEY
```

## Quick Reference

### Slash Commands
```bash
/team-start-advanced      # Initialize all MCPs
/daily-standup-mcp        # Morning planning
/project-init-mcp         # Full project setup
/team-orchestrate         # Complex feature workflow
/team-research            # Research mode
```

### Task Master Essentials
```bash
task-master list          # Show all tasks
task-master next          # Get next task
task-master show <id>     # Task details
task-master set-status    # Update status
task-master expand        # Break into subtasks
task-master analyze-complexity --research  # Analyze with DeepSeek
```

### Cerebras Resources
- [Inference Docs](https://inference-docs.cerebras.ai)
- [Cookbook](Cerebras-Inference-Cookbook/README.md)
- [Search Agent Example](Cerebras-Inference-Cookbook/agents/search-agent/)
- [Gist Memory Example](Cerebras-Inference-Cookbook/agents/gist-memory/)

---

**Remember**: This is a sales agent system focused on ultra-fast inference and intelligent automation. Every feature should leverage Cerebras's <100ms latency advantage.

## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines from the main CLAUDE.md file.**
@.taskmaster/CLAUDE.md
