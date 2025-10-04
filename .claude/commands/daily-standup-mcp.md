# Daily Standup MCP - Morning Planning Workflow

Run a comprehensive morning standup using all available MCP servers.

## Steps

1. **Review Yesterday's Work** (via Task Master & Memory)
   - Get completed tasks from yesterday
   - Retrieve any saved context from Memory MCP
   - Summarize progress

2. **Check Current State** (via Task Master)
   - Run `task-master list --status=in-progress`
   - Run `task-master list --status=pending`
   - Identify blockers or dependencies

3. **Plan Today** (via Sequential Thinking + Task Master)
   - Find next available task: `task-master next`
   - Use Sequential Thinking to plan approach
   - Estimate time for top 3-5 tasks

4. **Code Intelligence Check** (via Serena)
   - Review any pending code reviews
   - Check for architectural concerns
   - Identify technical debt

5. **Generate Standup Report**
   - Yesterday: Completed tasks
   - Today: Planned tasks
   - Blockers: Any issues
   - Notes: Key decisions or insights

## Output Format

```markdown
# Daily Standup - [Date]

## ✅ Yesterday
- [Completed tasks list]

## 🎯 Today's Plan
1. [Next task with ID]
2. [Second priority task]
3. [Third priority task]

## ⚠️  Blockers
- [Any issues or dependencies]

## 💡 Notes
- [Key insights or decisions]
```
