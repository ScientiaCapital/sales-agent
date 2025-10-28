# Claude Code Initialization

Please initialize yourself with this project's context:

## 1. Load Project Context
```bash
cat .claude/context.md
cat .claude/architecture.md
cat .cursorrules
```

## 2. Check Recent Activity
```bash
git log --oneline -10
git status
git diff --cached
```

## 3. Find Active Work Areas
```bash
# Check for TODOs
grep -r "TODO\|FIXME\|XXX\|HACK" --include="*.py" --include="*.js" --include="*.ts" --include="*.jsx" --include="*.tsx" . 2>/dev/null | head -20

# Check for recent file modifications
find . -type f -name "*.py" -o -name "*.js" -o -name "*.ts" -mtime -1 2>/dev/null | head -10
```

## 4. After Loading Context

Summarize:
1. **Current Focus**: (from Current Sprint/Focus section)
2. **Last Session**: (from Recent Changes section)  
3. **Blockers**: (from Blockers section)
4. **Next Steps**: (from Next Steps section)

Then ask: "What would you like to work on today? Should I continue with the next steps or is there something specific?"
