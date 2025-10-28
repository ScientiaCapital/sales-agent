# Project Context Directory

This directory contains context files for maintaining continuity between Claude Code and Cursor sessions.

## Files:
- `context.md` - Current project state, tasks, and progress
- `architecture.md` - Technical decisions and system design

## Usage:
1. **Starting Claude Code**: Tell it to "Read CLAUDE_INIT.md"
2. **Ending a session**: Update context.md with your progress
3. **Switching projects**: Save state here before moving

## Quick Commands:
```bash
# Start session
cat .claude/context.md

# Save progress
echo "- [x] Completed task" >> .claude/context.md

# Check recent work
git log --oneline -5
```

This is part of the project-context-manager system.
