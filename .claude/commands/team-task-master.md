---
description: "Task Master AI workflow launcher with variants"
arguments:
  - name: action
    description: "Action to perform: next, list, show <id>, or status"
---

# 📋 Task Master AI Workflow

Direct access to Task Master AI for project task management.

## Available Actions:

### `/team-task-master next`
Get the next available task to work on:
- Respects task dependencies
- Considers priority levels
- Returns task with full context

Tool: `mcp__taskmaster_ai__next_task(projectRoot)`

### `/team-task-master list`
Show all tasks with current status:
- Filter by status (pending, in_progress, completed)
- Include subtasks for detailed view
- Display with complexity scores

Tool: `mcp__taskmaster_ai__get_tasks(projectRoot, withSubtasks: true)`

### `/team-task-master show <id>`
View detailed task information:
- Complete task description
- Implementation guide
- Verification criteria
- Dependencies and blockers

Tool: `mcp__taskmaster_ai__get_task(projectRoot, id)`

### `/team-task-master status`
Update task status:
- Mark as in_progress, completed, blocked, etc.
- Automatically updates dependent tasks
- Syncs with Shrimp Task Manager

Tool: `mcp__taskmaster_ai__set_task_status(projectRoot, id, status)`

## Usage Examples:

```bash
/team-task-master next              # Get next task
/team-task-master list              # All tasks
/team-task-master show 5            # Task details for ID 5
/team-task-master status            # Update task status
```

## Integration Notes:

Task Master AI coordinates with:
- Shrimp Task Manager for verification
- Serena for code context
- Memory MCP for persistence

Project root is automatically detected from current workspace.

Action: $ARGUMENTS
