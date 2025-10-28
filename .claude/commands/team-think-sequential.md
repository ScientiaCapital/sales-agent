---
description: "Complex problem solving with Sequential Thinking MCP"
---

# 🧠 Sequential Thinking - Step-by-Step Problem Solving

Break down complex problems into manageable steps using advanced reasoning.

## When to Use Sequential Thinking:

### Perfect For:
- 🏗️ **Architecture Decisions** - Design complex systems
- 🐛 **Debugging Hard Issues** - Systematic problem investigation
- 🔄 **Refactoring Planning** - Safe code transformation
- 📊 **Performance Optimization** - Identify bottlenecks
- 🔐 **Security Analysis** - Threat modeling and mitigation

### Not Needed For:
- Simple bug fixes
- Straightforward feature additions
- Basic code changes

## Sequential Thinking Process:

### Phase 1: Problem Definition
Clearly articulate the challenge:
- What are we trying to solve?
- What constraints exist?
- What are success criteria?

### Phase 2: Information Gathering
Collect relevant data:
- Use Serena to explore codebase
- Use Context7 for library docs
- Use WebSearch for external research

### Phase 3: Hypothesis Generation
Create potential solutions:
- Brainstorm approaches
- Consider trade-offs
- Evaluate feasibility

### Phase 4: Analysis & Verification
Test hypotheses:
- Validate against requirements
- Check for edge cases
- Assess impact and risks

### Phase 5: Solution Synthesis
Formulate final approach:
- Combine best ideas
- Create implementation plan
- Document decision rationale

## Tool Usage:

```
mcp__sequential_thinking__sequentialthinking({
  thought: "Current reasoning step",
  thought_number: 1,
  total_thoughts: 5,
  next_thought_needed: true,
  is_revision: false
})
```

### Advanced Features:
- **Revisions** - Reconsider previous thoughts
- **Branching** - Explore alternative paths
- **Dynamic Scaling** - Adjust thought count as needed

## Example Problem:

```
Problem: "Design authentication system for 5-tenant platform"

Thought 1: Define requirements
- Multi-tenant isolation
- Shared SSO capability
- Secure token management
- Cross-domain support

Thought 2: Research patterns
- Review Supabase multi-tenant auth
- Check JWT best practices
- Analyze current middleware

Thought 3: Design architecture
- Centralized auth service
- Tenant-aware token claims
- RLS policy integration

Thought 4: Validate approach
- Security review
- Performance check
- Scalability assessment

Thought 5: Implementation plan
- Phase 1: Auth service
- Phase 2: Tenant integration
- Phase 3: Testing & rollout
```

## Integration with Other Agents:

- **Serena** - Provides code context for analysis
- **Shrimp** - Creates tasks from solution plan
- **Memory** - Saves decision rationale
- **Task Master** - Tracks implementation

Perfect for: Complex architectural decisions, systematic debugging, performance optimization
