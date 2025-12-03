---
description: "Save important context and insights to Memory MCP"
arguments:
  - name: context
    description: "What to save: decision, pattern, insight, or lesson"
---

# 💾 Team Memory - Context Persistence

Save important project knowledge for future sessions using Memory MCP.

## What to Save to Memory:

### 1. Architectural Decisions
Document why certain choices were made:
- Technology selections
- Design patterns chosen
- Trade-off considerations
- Future implications

### 2. Code Patterns
Store reusable patterns:
- Multi-tenant patterns
- Authentication flows
- API integration approaches
- Performance optimizations

### 3. Bug Solutions
Remember how issues were solved:
- Root cause analysis
- Solution approach
- Prevention strategies
- Testing methods

### 4. Team Knowledge
Preserve team insights:
- Development workflows
- Deployment procedures
- Troubleshooting guides
- Best practices

## Memory Structure:

### Entities (Key Concepts)
Create entities for important concepts:
```
mcp__memory__create_entities([{
  name: "Multi-Tenant Authentication",
  entityType: "Architecture Pattern",
  observations: [
    "Uses Supabase with RLS policies",
    "JWT tokens include tenant_id claim",
    "Middleware validates tenant access"
  ]
}])
```

### Relations (How Things Connect)
Link entities to show relationships:
```
mcp__memory__create_relations([{
  from: "Multi-Tenant Auth",
  to: "Row-Level Security",
  relationType: "implements"
}])
```

### Observations (Details & Context)
Add detailed notes to entities:
```
mcp__memory__add_observations({
  entityName: "Multi-Tenant Auth",
  contents: [
    "Performance: <100ms auth check",
    "Security: Automatic tenant isolation",
    "Tested across all 5 domains"
  ]
})
```

## Memory Usage Examples:

### Save Architecture Decision
```
Context: Chose Supabase over NextAuth for authentication

Entity: "Authentication System"
Type: "Technical Decision"
Observations:
- "Selected Supabase for multi-tenant RLS integration"
- "NextAuth lacked native PostgreSQL RLS support"
- "Supabase provides automatic tenant isolation"
- "Trade-off: Vendor lock-in vs. feature completeness"

Relations:
- Authentication System → implements → Row-Level Security
- Authentication System → requires → Neon Database
```

### Save Code Pattern
```
Context: Multi-tenant routing pattern in middleware

Entity: "Tenant Routing Pattern"
Type: "Code Pattern"
Observations:
- "Middleware detects hostname → extracts domain → maps to tenant"
- "Uses getDomainConfig() for domain-to-tenant mapping"
- "Rewrites URL to /[tenant]/path for Next.js routing"
- "Headers: x-tenant and x-domain for component access"

Relations:
- Tenant Routing → uses → Domain Configuration
- Tenant Routing → enables → Multi-Tenant Platform
```

### Save Bug Solution
```
Context: Fixed RLS policy for leads table

Entity: "Leads Table RLS Fix"
Type: "Bug Solution"
Observations:
- "Bug: Leads visible across tenants"
- "Root cause: RLS policy used wrong tenant_id reference"
- "Solution: Updated policy to use current_setting('app.current_tenant')"
- "Prevention: Always test RLS with multiple tenants"

Relations:
- Leads Table RLS Fix → fixes → Data Isolation Issue
- Leads Table RLS Fix → affects → Multi-Tenant Security
```

## Retrieval from Memory:

Later sessions can recall this knowledge:
```
mcp__memory__search_nodes({ query: "authentication" })
mcp__memory__open_nodes({ names: ["Authentication System"] })
mcp__memory__read_graph()  // Get all stored knowledge
```

## Integration with Team Workflow:

1. **After major decisions** → Save to Memory
2. **After solving complex bugs** → Save to Memory  
3. **After discovering patterns** → Save to Memory
4. **Next session** → Recall from Memory

Context to save: $ARGUMENTS

Perfect for: Knowledge retention, team onboarding, decision documentation, pattern library
