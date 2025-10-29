# Feature Development Workflow

## Overview

The Feature Development Workflow provides an interactive, token-efficient way to implement new features in the sales-agent project. It supports both skill-based development (89% token reduction) and manual MCP workflows for complex scenarios.

## Purpose & When to Use

**Use this workflow when:**
- Adding new LangGraph agents (qualification, enrichment, growth, etc.)
- Creating FastAPI endpoints (CRUD, streaming, agent endpoints)
- Implementing database migrations (tables, columns, indexes)
- Setting up CRM sync operations (Close, Apollo, LinkedIn)
- Writing comprehensive test suites (unit, integration, streaming)
- Building any new feature that follows established patterns

**Don't use this workflow for:**
- One-off scripts or utilities
- Configuration changes
- Documentation updates only
- Bug fixes (use Debug Workflow instead)

## Prerequisites

### Environment Setup
- `.env` file with required API keys
- PostgreSQL and Redis running (via Docker)
- Python dependencies installed
- Git repository initialized

### Required Environment Variables
```bash
CEREBRAS_API_KEY=your_cerebras_key
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0
DEEPSEEK_API_KEY=your_deepseek_key
OPENROUTER_API_KEY=your_openrouter_key
```

### Project Structure
```
backend/
├── app/
│   ├── api/           # FastAPI endpoints
│   ├── models/        # SQLAlchemy models
│   ├── services/      # Business logic
│   └── schemas/       # Pydantic schemas
├── alembic/           # Database migrations
└── tests/             # Test suite
```

## Step-by-Step Guide

### 1. Start the Workflow

```bash
# Interactive mode
python commands/feature_workflow.py

# Non-interactive mode
python commands/feature_workflow.py --name "lead scoring" --type 1
```

### 2. Feature Requirements

The workflow will prompt you for:

#### Feature Name
```
What are you building? (e.g., 'lead scoring agent'): lead qualification
```

#### Feature Type
```
What type of feature is this?
1. LangGraph Agent (LCEL chain or StateGraph)
2. FastAPI Endpoint (CRUD or streaming)
3. Database Migration (table, column, index)
4. CRM Sync Operation (Close, Apollo, LinkedIn)
5. Test Suite (unit, integration, streaming)
6. Other (manual workflow)
```

#### Type-Specific Details

**For LangGraph Agents:**
- Workflow type: Linear (LCEL chain) or Multi-step (StateGraph)
- Agent description
- Required tools

**For FastAPI Endpoints:**
- Endpoint type: Standard, Streaming, or Agent
- Schema name
- Service name

**For Database Migrations:**
- Migration type: Add table, Add column, Add index, Modify column
- Table name
- Column name (if applicable)

**For CRM Sync:**
- Platform: close, apollo, linkedin
- Sync type: Bidirectional or Import only

**For Test Suites:**
- Test type: Unit, Integration, Streaming, or Agent
- Module name to test

### 3. Skill Selection

The workflow automatically determines the best skill to use:

| Feature Type | Skill Used | Token Cost | Savings |
|--------------|------------|------------|---------|
| LangGraph Agent | `langgraph_agent` | 1.7K | 90% |
| FastAPI Endpoint | `fastapi_endpoint` | 1.2K | 90% |
| Database Migration | `database_migration` | 800 | 90% |
| CRM Sync | `crm_sync` | 2K | 87% |
| Test Suite | `write_tests` | 1K | 90% |

### 4. Execution

#### Skill-Based Execution (Recommended)
- Uses pre-compiled patterns and templates
- Interactive decision trees
- Automatic file generation
- 89% average token reduction

#### Manual Workflow (Fallback)
- Full MCP workflow: Sequential Thinking → Serena → Context7
- 18K+ tokens for complex features
- Used when no skill is available

### 5. Results

The workflow provides:

#### Files Created
- Generated source code files
- Test files
- Migration files
- Configuration updates

#### Next Steps
- Specific actions to complete the feature
- Testing commands to run
- Documentation updates needed

#### Metrics
- Token usage (skill vs manual)
- Files created count
- Tests run count
- Execution time

## MCP Workflow Integration

### Mandatory Workflow (Manual Mode)

When skills are not available, the workflow follows the mandatory MCP pattern:

1. **Sequential Thinking**: Problem decomposition
   - Break down feature into components
   - Identify dependencies and challenges
   - Create implementation plan

2. **Serena**: Codebase navigation
   - Find existing patterns to follow
   - Identify integration points
   - Understand architecture constraints

3. **Context7**: Library documentation
   - Verify latest API patterns
   - Check for breaking changes
   - Confirm best practices

### Skills Integration

Skills encapsulate the MCP workflow results:

```json
{
  "skill_id": "langgraph_agent",
  "token_cost": 1700,
  "decision_tree": {
    "question": "Linear or multi-step workflow?",
    "options": {
      "linear": {"template": "lcel_chain.py.jinja2"},
      "multi_step": {"template": "state_graph.py.jinja2"}
    }
  }
}
```

## Project-Specific Considerations

### LangGraph Agents

**LCEL Chains** (Simple workflows):
- Lead qualification
- Data enrichment
- Simple transformations

**StateGraphs** (Complex workflows):
- Multi-step research
- Human-in-loop processes
- Cyclic validation

### FastAPI Endpoints

**Standard Endpoints**:
- CRUD operations
- Business logic
- Data validation

**Streaming Endpoints**:
- Real-time processing
- WebSocket connections
- Server-sent events

**Agent Endpoints**:
- LangGraph integration
- Redis checkpointing
- State management

### Database Migrations

**Alembic Integration**:
- Automatic revision generation
- Upgrade/downgrade support
- Dependency management

**Indexing Strategy**:
- Performance optimization
- Query pattern analysis
- Composite indexes

### CRM Sync Operations

**Close CRM** (Bidirectional):
- Lead management
- Contact synchronization
- Conflict resolution

**Apollo.io** (Import only):
- Contact enrichment
- Company data
- Technology stack

**LinkedIn** (Import only):
- Profile scraping
- Professional data
- Network analysis

## Examples

### Example 1: Create Lead Qualification Agent

```bash
$ python commands/feature_workflow.py

What are you building? lead qualification agent
What type of feature is this? 1
Linear workflow (1) or Multi-step (2)? 1
Agent description: Qualify leads using Cerebras AI
Required tools: qualification_tools

✅ Using skill: langgraph_agent (1.7K tokens)
✅ Feature created successfully

📁 Files created (1):
  - backend/app/services/langgraph/agents/lead_qualification_agent.py

📋 Next steps:
  - Add agent to FastAPI router
  - Create test file for the agent
  - Update documentation
  - Test agent execution
```

### Example 2: Create CRM Sync Service

```bash
$ python commands/feature_workflow.py

What are you building? apollo enrichment sync
What type of feature is this? 4
Platform (close/apollo/linkedin): apollo
Bidirectional (1) or Import only (2)? 2

✅ Using skill: crm_sync (2K tokens)
✅ Feature created successfully

📁 Files created (1):
  - backend/app/services/crm/apollo_sync.py

📋 Next steps:
  - Configure CRM credentials
  - Test sync operation
  - Set up monitoring
  - Schedule periodic syncs
```

### Example 3: Manual Workflow (No Skill Available)

```bash
$ python commands/feature_workflow.py

What are you building? custom analytics dashboard
What type of feature is this? 6

ℹ️ Using manual workflow (18K tokens)
ℹ️ Phase 1: Sequential Thinking analysis
ℹ️ Phase 2: Serena codebase analysis
ℹ️ Phase 3: Context7 library research
✅ MCP workflow completed successfully (18,500 tokens, 2.3s)

📁 Files created (2):
  - backend/app/api/analytics.py
  - backend/app/services/analytics_service.py
```

## Common Pitfalls

### 1. Missing Prerequisites
**Problem**: Environment variables not set
**Solution**: Run `python commands/common/checks.py` first

### 2. Skill Not Available
**Problem**: No skill for custom feature type
**Solution**: Use manual workflow or create new skill

### 3. File Generation Errors
**Problem**: Permission issues or invalid paths
**Solution**: Check file permissions and directory structure

### 4. Test Failures
**Problem**: Generated tests don't pass
**Solution**: Review test patterns and update as needed

## Success Criteria

A successful feature development workflow should:

✅ **Generate working code** that follows project patterns
✅ **Create appropriate tests** with good coverage
✅ **Use minimal tokens** (prefer skills over manual)
✅ **Provide clear next steps** for completion
✅ **Integrate with existing architecture** seamlessly

## Token Usage Comparison

| Approach | Token Cost | Use Case |
|----------|------------|----------|
| Skill-based | 1K-2K | Common patterns |
| Manual MCP | 18K+ | Custom features |
| **Savings** | **89%** | **Average reduction** |

## Troubleshooting

### Check Prerequisites
```bash
python commands/common/checks.py
```

### Verify Skills
```bash
python -c "from commands.skills.skill_manager import SkillManager; print(SkillManager().list_skills())"
```

### Test Generated Code
```bash
pytest backend/tests/ -v
```

### Manual Override
```bash
python commands/feature_workflow.py --type 6  # Force manual workflow
```

## Related Workflows

- **Debug Workflow**: For fixing issues in generated features
- **Performance Workflow**: For optimizing feature performance
- **Review Workflow**: For validating feature quality
- **Team Orchestrate**: For complex multi-agent features