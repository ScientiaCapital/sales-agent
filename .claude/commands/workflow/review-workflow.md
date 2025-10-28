---
description: "Code review and refactoring workflow"
---

# 👀 Code Review & Refactoring Workflow

Comprehensive code review using MCP intelligence.

## Review Process:

### Step 1: Code Analysis
**Agent**: Serena
```
1. Get file/symbol overview
2. Find all references
3. Analyze dependencies
4. Check for patterns
```

### Step 2: Quality Assessment
**Agent**: Sequential Thinking
```
1. Evaluate code structure
2. Check for anti-patterns
3. Assess performance
4. Review security
```

### Step 3: Pattern Recognition
**Agent**: Memory + Serena
```
1. Compare with known patterns
2. Identify improvements
3. Find duplication
4. Suggest refactoring
```

### Step 4: Refactoring Plan
**Agents**: Sequential Thinking + Shrimp
```
1. Prioritize changes
2. Plan safe refactoring
3. Create subtasks
4. Define test strategy
```

### Step 5: Implementation
**Agents**: Serena + Task Master
```
1. Execute refactoring
2. Run tests continuously
3. Verify no regressions
4. Update documentation
```

### Step 6: Knowledge Capture
**Agent**: Memory
```
1. Save refactoring patterns
2. Document improvements
3. Create guidelines
4. Update best practices
```

## Review Checklist:

### Code Quality
- ✅ Follows TypeScript strict mode
- ✅ No `any` types used
- ✅ Proper error handling
- ✅ Clear naming conventions

### Multi-Tenant Compliance
- ✅ Respects tenant isolation
- ✅ Uses RLS policies correctly
- ✅ Tenant-aware components
- ✅ Cross-tenant testing

### Performance
- ✅ Optimized queries
- ✅ Proper caching
- ✅ No unnecessary re-renders
- ✅ Bundle size acceptable

### Security
- ✅ No hardcoded secrets
- ✅ Input validation
- ✅ SQL injection prevention
- ✅ XSS protection

## Example: Review Multi-Tenant Middleware

```bash
# Step 1: Analyze
/team-serena-analyze
# Review middleware.ts structure

# Step 2: Assess Quality
/team-think-sequential
# Evaluation: Good separation, minor improvements

# Step 3: Find Patterns
/team-memory-save "middleware review insights"

# Step 4: Plan Improvements
/team-shrimp-plan
# Tasks: Add caching, improve error handling

# Step 5: Refactor
/team-orchestrate
# Implement improvements

# Step 6: Document
/team-memory-save "optimized middleware pattern"
```

Perfect for: Code review, refactoring, quality improvement, pattern extraction
