---
description: "Systematic debugging workflow with MCP agents"
---

# 🐛 Debugging Workflow

Systematic approach to finding and fixing bugs using MCP intelligence.

## Debug Process:

### Step 1: Problem Definition
**Agent**: Sequential Thinking
```
1. Describe the bug clearly
2. Identify symptoms
3. Determine impact
4. Set investigation scope
```

### Step 2: Code Investigation
**Agent**: Serena
```
1. Find buggy code location
2. Search for error patterns
3. Trace code execution
4. Map dependencies
```

### Step 3: Research Similar Issues
**Agent**: Web Search + Context7
```
1. Search for similar bugs
2. Check library documentation
3. Review known issues
4. Find community solutions
```

### Step 4: Root Cause Analysis
**Agent**: Sequential Thinking
```
1. Analyze collected evidence
2. Form hypotheses
3. Test assumptions
4. Identify root cause
```

### Step 5: Solution Implementation
**Agents**: Serena + Task Master
```
1. Design fix
2. Implement changes
3. Add regression tests
4. Verify fix works
```

### Step 6: Documentation
**Agent**: Memory
```
1. Save bug solution
2. Document prevention
3. Create test cases
4. Update patterns
```

## Example: Debug Multi-Tenant Data Leak

```bash
# Step 1: Define Problem
/team-think-sequential
# Bug: Users see other tenants' data

# Step 2: Find Bug Location  
/team-serena-analyze
# Found: RLS policy missing tenant_id check

# Step 3: Research
/team-research "PostgreSQL RLS multi-tenant"
# Best practice: use current_setting() for tenant

# Step 4: Root Cause
/team-think-sequential
# Cause: Policy uses wrong tenant reference

# Step 5: Fix
# Update RLS policy, add tests

# Step 6: Save Solution
/team-memory-save "RLS tenant isolation fix"
# Documented for future reference
```

Perfect for: Bug investigation, root cause analysis, systematic fixes
