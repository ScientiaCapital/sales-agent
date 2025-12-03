---
description: "Initialize project with all MCP servers from scratch"
---

# 🎬 Fresh Project Initialization with MCP

Complete project setup using all MCP capabilities.

## Full Initialization Workflow:

### Phase 1: Serena Project Setup
Activate and onboard the codebase:
- Activate project at current directory
- Check if onboarding was performed
- If not, run comprehensive onboarding
- Create 6 core memory files

Tools:
```
mcp__serena__activate_project(projectPath)
mcp__serena__check_onboarding_performed()
mcp__serena__onboarding()
```

### Phase 2: Task Master AI Setup
Initialize task management:
- Check for existing .taskmaster/ directory
- Initialize if needed
- Set up task tracking
- Configure models (if available)

Tools:
```
mcp__taskmaster_ai__initialize_project(projectRoot)
mcp__taskmaster_ai__models(projectRoot)
```

### Phase 3: Import Existing Tasks (Optional)
If project has existing planning:
- Look for PRD documents in .taskmaster/docs/
- Parse and import tasks
- Set up initial task structure

Tools:
```
mcp__taskmaster_ai__parse_prd(projectRoot, input: ".taskmaster/docs/prd.txt")
```

### Phase 4: Shrimp Task Manager Setup
Initialize verification system:
- Set up task storage
- Initialize planning engine
- Configure verification criteria

### Phase 5: Memory MCP Setup
Create persistent context:
- Initialize knowledge graph
- Create project entities
- Set up relationships

Tools:
```
mcp__memory__create_entities([{name, entityType, observations}])
mcp__memory__create_relations([{from, to, relationType}])
```

### Phase 6: Neon Database Setup (if applicable)
Configure database access:
- List available projects
- Set connection strings
- Test connectivity

Tools:
```
mcp__neon__list_projects({limit: 10})
mcp__neon__get_connection_string({projectId})
```

### Phase 7: GitHub Integration (if applicable)
Connect repository:
- Verify repo access
- Set up issue/PR tracking
- Configure workflows

## Initialization Complete Report:

```
🎉 Project Fully Initialized!

✅ Serena: 6 memory files created
✅ Task Master AI: Ready with task tracking
✅ Shrimp Manager: Verification system active
✅ Memory MCP: Knowledge graph initialized
✅ Neon: Database connected (if configured)
✅ GitHub: Repository linked (if configured)

📚 Memory Files:
- project_overview.md
- tech_stack.md
- code_style_and_conventions.md
- project_structure.md
- suggested_commands.md
- task_completion_workflow.md

🚀 Ready for development!
Use /team-start-advanced to begin work.
```

Perfect for: New projects, team onboarding, fresh repository setup
