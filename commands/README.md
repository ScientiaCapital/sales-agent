# Sales Agent Commands & Skills System

## 🚀 Overview

This directory contains **11 executable commands** and a **skills system** for the sales-agent project, providing both basic development workflows and advanced MCP team orchestration with **89% average token reduction**.

## 📊 Quick Stats

- **11 Commands**: 4 basic workflows + 7 MCP orchestration
- **5 Core Skills**: Pre-compiled patterns for common tasks
- **89% Token Savings**: Skills vs manual MCP workflows
- **Production Ready**: Follows project patterns and best practices

## 🏗️ Architecture

```
/commands/
├── Basic Workflows (4 commands)     # Feature, Debug, Performance, Review
├── MCP Team Orchestration (7 commands)  # Advanced multi-agent coordination
├── Skills System (5 POC skills)     # Token-efficient reusable patterns
└── Common Utilities                 # Shared workflow infrastructure
```

## 🎯 Basic Workflows

### 1. Feature Development
**Purpose**: Create new features with 89% token reduction
**Command**: `python commands/feature_workflow.py`
**Skills**: LangGraph agents, FastAPI endpoints, DB migrations, CRM sync, tests

```bash
# Interactive mode
python commands/feature_workflow.py

# Quick mode
python commands/feature_workflow.py --name "lead scoring" --type 1
```

**Token Usage**:
- Skill-based: 1K-2K tokens (90% reduction)
- Manual MCP: 18K+ tokens (full workflow)

### 2. Debug Workflow
**Purpose**: Systematic troubleshooting and issue resolution
**Command**: `python commands/debug_workflow.py`
**Features**: Log analysis, LangSmith traces, circuit breaker status, Redis inspection

```bash
# Debug recent issues
python commands/debug_workflow.py

# Debug specific component
python commands/debug_workflow.py --component "cerebras"
```

### 3. Performance Workflow
**Purpose**: Identify and resolve performance bottlenecks
**Command**: `python commands/performance_workflow.py`
**Features**: Benchmarking, profiling, optimization suggestions

```bash
# Full performance analysis
python commands/performance_workflow.py

# Quick benchmark
python commands/performance_workflow.py --quick
```

### 4. Review Workflow
**Purpose**: Ensure code quality before merging
**Command**: `python commands/review_workflow.py`
**Features**: Linting, testing, security checks, architecture validation

```bash
# Full review
python commands/review_workflow.py

# Quick checks
python commands/review_workflow.py --quick
```

## 🤖 MCP Team Orchestration

### 5. Team Start Advanced
**Purpose**: Initialize all 5 MCP servers with full context
**Command**: `python commands/team_start_advanced.py`
**MCPs**: Sequential Thinking, Serena, Context7, Task Master, Desktop Commander

```bash
# Initialize all MCPs
python commands/team_start_advanced.py

# Check MCP status
python commands/team_start_advanced.py --status
```

### 6. Project Init MCP
**Purpose**: Complete project setup from scratch
**Command**: `python commands/project_init_mcp.py`
**Features**: Git init, .env setup, DB migrations, Docker containers, tests

```bash
# Full project initialization
python commands/project_init_mcp.py

# Skip Docker setup
python commands/project_init_mcp.py --no-docker
```

### 7. Daily Standup MCP
**Purpose**: Morning planning and task prioritization
**Command**: `python commands/daily_standup_mcp.py`
**Features**: Task review, commit analysis, LangSmith metrics, daily planning

```bash
# Morning standup
python commands/daily_standup_mcp.py

# Review yesterday's work
python commands/daily_standup_mcp.py --yesterday
```

### 8. Team Orchestrate
**Purpose**: Complex feature coordination with parallel agents
**Command**: `python commands/team_orchestrate.py`
**Features**: Dependency analysis, parallel execution, progress monitoring

```bash
# Orchestrate complex feature
python commands/team_orchestrate.py --feature "multi-agent system"

# Monitor progress
python commands/team_orchestrate.py --monitor
```

### 9. Team Architect MCP
**Purpose**: Architecture design with Serena + Sequential Thinking
**Command**: `python commands/team_architect_mcp.py`
**Features**: Requirements analysis, pattern discovery, architecture diagrams

```bash
# Design new architecture
python commands/team_architect_mcp.py --requirements "scalable microservices"

# Review existing patterns
python commands/team_architect_mcp.py --analyze
```

### 10. Team Research
**Purpose**: Research mode with planning and analysis
**Command**: `python commands/team_research.py`
**Features**: DeepSeek research, parallel agents, synthesis, reports

```bash
# Research new technology
python commands/team_research.py --topic "LangGraph optimization"

# Generate research report
python commands/team_research.py --report
```

## 🧠 Skills System

### Core Skills (5 POC)

| Skill | Token Cost | Use Case | Savings |
|-------|------------|----------|---------|
| `langgraph_agent` | 1.7K | Create LangGraph agents | 90% |
| `fastapi_endpoint` | 1.2K | Add FastAPI endpoints | 90% |
| `database_migration` | 800 | Database migrations | 90% |
| `crm_sync` | 2K | CRM sync operations | 87% |
| `write_tests` | 1K | Generate test suites | 90% |

### Using Skills

```python
from commands.skills.skill_manager import SkillManager

# Load skill
skill_mgr = SkillManager()
skill = skill_mgr.get_skill("langgraph_agent")

# Execute skill
result = skill_mgr.execute_skill("langgraph_agent", {
    "name": "qualification",
    "description": "Lead qualification agent",
    "tools": "qualification_tools"
})

# Check results
print(f"Files created: {result.files_created}")
print(f"Token cost: {result.token_cost}")
```

### Skill Catalog

```bash
# List available skills
python -c "from commands.skills.skill_manager import SkillManager; print(SkillManager().list_skills())"

# Get skill info
python -c "from commands.skills.skill_manager import SkillManager; print(SkillManager().get_skill_info('langgraph_agent'))"
```

## 🛠️ Common Utilities

### WorkflowBase
Base class for all workflows with common functionality:
- Environment validation
- Database/Redis connection checks
- Test execution helpers
- Progress indicators

### Checks
Comprehensive validation system:
- Environment variables
- Service health checks
- File existence validation
- Configuration validation

### MCPManager
MCP server coordination:
- Server initialization
- Mandatory workflow execution
- Token usage tracking
- Status monitoring

### SubagentOrchestrator
Specialized agent management:
- 13 agent types available
- Parallel execution coordination
- Dependency analysis
- Progress monitoring

## 📈 Token Usage Comparison

### Before (Manual MCP Workflow)
```
Sequential Thinking: 2K tokens
Serena Analysis: 3K tokens  
Context7 Research: 4K tokens
Implementation: 9K tokens
Total: 18K tokens
```

### After (Skills System)
```
Skill Loading: 100 tokens
Decision Tree: 200 tokens
Template Rendering: 400 tokens
File Generation: 1K tokens
Total: 1.7K tokens (90% reduction)
```

## 🚀 Quick Start

### 1. Prerequisites
```bash
# Check environment
python commands/common/checks.py

# Start services
docker-compose up -d
```

### 2. Create Your First Feature
```bash
# Interactive feature creation
python commands/feature_workflow.py

# Follow prompts to create:
# - LangGraph agent
# - FastAPI endpoint  
# - Database migration
# - CRM sync operation
# - Test suite
```

### 3. Debug Issues
```bash
# Debug recent problems
python commands/debug_workflow.py

# Check performance
python commands/performance_workflow.py
```

### 4. Review Before Merge
```bash
# Full code review
python commands/review_workflow.py

# Quick checks
python commands/review_workflow.py --quick
```

## 🔧 Advanced Usage

### Custom Skills
Create new skills by adding `.skill.json` files:

```json
{
  "skill_id": "custom_skill",
  "version": "1.0.0",
  "description": "Custom skill description",
  "token_cost": 1500,
  "decision_tree": {
    "question": "What do you need?",
    "options": {
      "option1": {"template": "template1.py.jinja2"},
      "option2": {"template": "template2.py.jinja2"}
    }
  },
  "prerequisites": {
    "files_exist": ["backend/app/"],
    "env_vars": ["DATABASE_URL"]
  },
  "code_templates": {
    "option1": "// Template content here",
    "option2": "// Template content here"
  }
}
```

### MCP Workflow Integration
All workflows follow the mandatory pattern:

1. **Sequential Thinking** → Problem decomposition
2. **Serena** → Codebase navigation  
3. **Context7** → Library documentation
4. **Implementation** → Code generation
5. **Verification** → Testing and validation

### Parallel Agent Execution
For complex features:

```bash
# Orchestrate multiple agents
python commands/team_orchestrate.py --agents "architect,developer,tester"

# Monitor progress
python commands/team_orchestrate.py --monitor --agents "architect,developer"
```

## 📚 Documentation

Each command has comprehensive documentation:

- **Feature Workflow**: `commands/feature_workflow.md`
- **Debug Workflow**: `commands/debug_workflow.md`
- **Performance Workflow**: `commands/performance_workflow.md`
- **Review Workflow**: `commands/review_workflow.md`
- **Skills System**: `commands/skills/README.md`

## 🐛 Troubleshooting

### Common Issues

**1. MCP Servers Not Available**
```bash
# Check MCP status
python commands/team_start_advanced.py --status

# Initialize MCPs
python commands/team_start_advanced.py
```

**2. Skills Not Loading**
```bash
# Check skill files
ls commands/skills/*.skill.json

# Test skill manager
python -c "from commands.skills.skill_manager import SkillManager; print(SkillManager().list_skills())"
```

**3. Environment Issues**
```bash
# Run comprehensive checks
python commands/common/checks.py

# Check specific service
python commands/common/checks.py --service database
```

**4. Token Usage High**
```bash
# Use skills instead of manual workflow
python commands/feature_workflow.py --use-skills

# Check skill availability
python -c "from commands.skills.skill_manager import SkillManager; print(SkillManager().get_skill_catalog())"
```

## 🎯 Best Practices

### 1. Use Skills First
Always try skills before manual workflows for 89% token reduction.

### 2. Follow MCP Workflow
When manual workflow is needed, follow the mandatory pattern:
Sequential Thinking → Serena → Context7 → Implementation

### 3. Validate Early
Run checks before starting any workflow:
```bash
python commands/common/checks.py
```

### 4. Monitor Token Usage
Track token consumption across workflows:
```bash
python commands/team_start_advanced.py --metrics
```

### 5. Test Generated Code
Always run tests after feature creation:
```bash
python commands/review_workflow.py --test-only
```

## 🔮 Future Enhancements

- **More Skills**: Expand skill library to 20+ patterns
- **Auto-Skill Creation**: AI-assisted skill generation
- **Workflow Chaining**: Combine multiple workflows
- **Real-time Monitoring**: Live token usage tracking
- **Custom Templates**: User-defined code templates

## 📞 Support

For issues or questions:

1. Check troubleshooting section above
2. Review command-specific documentation
3. Run diagnostic checks: `python commands/common/checks.py`
4. Check MCP status: `python commands/team_start_advanced.py --status`

---

**Ready to build?** Start with: `python commands/feature_workflow.py` 🚀