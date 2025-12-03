---
description: "Architecture design combining Serena + Sequential Thinking"
---

# 🏛️ MCP-Powered Architecture Design

Design robust system architecture using Serena's code intelligence and Sequential Thinking.

## Architecture Design Process:

### Phase 1: Requirements Analysis (Sequential Thinking)
Define what the system needs to do:
- Functional requirements
- Non-functional requirements (performance, security, scalability)
- Constraints and limitations
- Success criteria

### Phase 2: Current State Analysis (Serena)
Understand existing architecture:
- Map current codebase structure
- Identify integration points
- Find similar patterns
- Assess technical debt

### Phase 3: Design Exploration (Sequential Thinking)
Explore architectural options:
- Evaluate multiple approaches
- Consider trade-offs
- Assess risks and benefits
- Choose optimal solution

### Phase 4: Integration Planning (Serena + Sequential Thinking)
Plan how new architecture fits:
- Identify code modifications needed
- Plan migration strategy
- Define testing approach
- Create rollout plan

### Phase 5: Documentation (Memory)
Capture architecture decisions:
- Save design rationale
- Document patterns used
- Store trade-off analysis
- Create implementation guide

## Design Workflows:

### New Feature Architecture
```
1. Sequential Thinking: Define feature requirements
   - User stories
   - Technical constraints
   - Success metrics

2. Serena: Analyze codebase
   - Find related features
   - Identify reusable code
   - Check architectural patterns

3. Sequential Thinking: Design solution
   - Component architecture
   - Data flow design
   - API contracts

4. Serena: Validate integration
   - Check for conflicts
   - Verify compatibility
   - Plan refactoring

5. Memory: Save design
   - Architecture decisions
   - Pattern choices
   - Future considerations
```

### System Refactoring
```
1. Serena: Map current system
   - Get symbols overview
   - Find all references
   - Understand dependencies

2. Sequential Thinking: Identify issues
   - Performance bottlenecks
   - Coupling problems
   - Scalability limits

3. Sequential Thinking: Design new architecture
   - Improved structure
   - Better separation of concerns
   - Scalability improvements

4. Serena: Plan migration
   - Incremental refactoring steps
   - Testing strategy
   - Rollback plan
```

### Multi-Tenant Feature Design
```
1. Sequential Thinking: Analyze tenant requirements
   - Shared vs tenant-specific features
   - Data isolation needs
   - Performance requirements

2. Serena: Review current multi-tenant patterns
   - Middleware routing
   - RLS policies
   - Tenant context handling

3. Sequential Thinking: Design tenant-aware feature
   - Component structure
   - Data model with tenant_id
   - Access control

4. Memory: Document tenant pattern
   - Save for future features
   - Create reusable template
```

## Example Architecture Design:

```
Task: "Design real-time chat system for voice AI platform"

Phase 1: Requirements (Sequential Thinking)
- Support 1000+ concurrent users
- Sub-100ms message delivery
- Multi-tenant isolation
- Voice + text integration
- Mobile and web support

Phase 2: Current Analysis (Serena)
- Find existing WebSocket code
- Check LiveKit integration
- Review tenant isolation patterns
- Assess database schema

Phase 3: Design Options (Sequential Thinking)
Option A: WebSocket with Redis pub/sub
- Pros: Real-time, scalable
- Cons: Complex setup

Option B: LiveKit rooms + custom signaling
- Pros: Built-in voice integration
- Cons: Vendor dependency

Option C: Supabase Realtime
- Pros: Easy RLS integration
- Cons: Cost at scale

Decision: Option C + Option B hybrid
- Supabase for text chat (RLS)
- LiveKit for voice rooms
- Best of both worlds

Phase 4: Integration Plan (Serena)
- Extend current LiveKit setup
- Add Supabase Realtime client
- Create unified chat component
- Implement tenant-aware rooms

Phase 5: Documentation (Memory)
- Save architecture decision
- Document integration pattern
- Store performance benchmarks
- Create implementation guide
```

## Tools Orchestration:

```
// Requirements
mcp__sequential_thinking__sequentialthinking({
  thought: "Define functional requirements",
  ...
})

// Code Analysis
mcp__serena__find_symbol("WebSocketProvider")
mcp__serena__search_for_pattern("LiveKit")

// Design
mcp__sequential_thinking__sequentialthinking({
  thought: "Evaluate architectural options",
  ...
})

// Documentation
mcp__memory__create_entities([{
  name: "Chat Architecture",
  entityType: "System Design",
  observations: ["Uses Supabase + LiveKit hybrid", ...]
}])
```

Perfect for: Feature architecture, system design, refactoring planning, technical decisions
