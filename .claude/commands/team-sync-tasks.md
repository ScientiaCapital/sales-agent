---
description: "Synchronize tasks across Task Master AI and Shrimp Task Manager"
---

# 🔄 Cross-Agent Task Synchronization

Keep Task Master AI and Shrimp Task Manager in perfect sync.

## Why Sync is Important:

Task Master AI and Shrimp serve different purposes:
- **Task Master**: Project-level coordination and tracking
- **Shrimp**: Detailed execution and verification

Both systems track tasks independently, so periodic sync prevents:
- ❌ Duplicate work
- ❌ Status conflicts
- ❌ Lost task updates
- ❌ Inconsistent priorities

## Synchronization Process:

### Step 1: List All Tasks
Get current state from both systems:
```
Task Master: mcp__taskmaster_ai__get_tasks(projectRoot, withSubtasks: true)
Shrimp: mcp__shrimp_task_manager__list_tasks(status: "all")
```

### Step 2: Compare Task States
Identify discrepancies:
- Tasks in Task Master but not in Shrimp
- Tasks in Shrimp but not in Task Master
- Status conflicts (completed vs pending)
- Priority mismatches

### Step 3: Resolve Conflicts
Apply resolution strategy:
- **Completed tasks**: Trust verification system (Shrimp)
- **In-progress tasks**: Trust execution system (Task Master)
- **New tasks**: Add to both systems
- **Deleted tasks**: Remove from both

### Step 4: Update Both Systems
Sync the changes:
- Update Task Master status where needed
- Update Shrimp task list
- Create missing tasks in both systems

### Step 5: Verify Sync
Confirm synchronization:
- Compare task counts
- Verify status alignment
- Check priority consistency

## Sync Report Format:

```
🔄 Task Synchronization Complete

📊 Summary:
- Total tasks: 15
- Synced successfully: 15
- Conflicts resolved: 2
- New tasks added: 1

✅ Systems in sync!

Next: Use /team-task-master next to continue work
```

Run this sync before major milestones or when switching between task systems!
