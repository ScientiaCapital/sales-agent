---
description: "Performance optimization workflow"
---

# ⚡ Performance Optimization Workflow

Systematic approach to improving application performance.

## Optimization Process:

### Step 1: Identify Bottlenecks
**Agents**: Sequential Thinking + Serena
```
1. Define performance goals
2. Measure current performance
3. Find slow operations
4. Prioritize issues
```

### Step 2: Research Solutions
**Agents**: Web Search + Context7
```
1. Search optimization techniques
2. Check framework docs
3. Review best practices
4. Find benchmarks
```

### Step 3: Code Analysis
**Agent**: Serena
```
1. Find performance-critical code
2. Analyze database queries
3. Check render patterns
4. Identify N+1 problems
```

### Step 4: Design Optimizations
**Agent**: Sequential Thinking
```
1. Evaluate optimization strategies
2. Consider trade-offs
3. Plan implementation
4. Define success metrics
```

### Step 5: Implementation
**Agents**: Serena + Task Master
```
1. Apply optimizations
2. Add performance tests
3. Measure improvements
4. Verify no regressions
```

### Step 6: Documentation
**Agent**: Memory
```
1. Save optimization patterns
2. Document techniques
3. Record benchmarks
4. Create guidelines
```

## Common Optimizations:

### Database Performance
```
✅ Add indexes for frequent queries
✅ Use query batching
✅ Implement caching (Redis)
✅ Optimize RLS policies
```

### React Performance
```
✅ Use React.memo() for expensive components
✅ Implement virtualization for lists
✅ Optimize re-render triggers
✅ Code splitting with dynamic imports
```

### API Performance
```
✅ Enable compression
✅ Implement response caching
✅ Use Edge functions
✅ Batch API requests
```

### Bundle Optimization
```
✅ Tree shaking
✅ Code splitting
✅ Dynamic imports
✅ Lazy loading
```

## Example: Optimize Calculator Performance

```bash
# Step 1: Identify Issues
/team-think-sequential
# Goal: <200ms calculation time
# Current: 800ms average

# Step 2: Research
/team-research "React performance optimization 2025"
# Found: memoization, virtualization techniques

# Step 3: Analyze Code
/team-serena-analyze
# Found: Heavy re-renders in Calculator component

# Step 4: Design Solutions
/team-think-sequential
# Plan: Memoize calculations, optimize state

# Step 5: Implement
/team-orchestrate
# Apply React.memo, useMemo, useCallback

# Step 6: Document
/team-memory-save "calculator optimization patterns"
# Result: 150ms average (25% improvement)
```

## Performance Metrics:

Track improvements:
- Response time (API/component)
- Bundle size
- Time to Interactive (TTI)
- Largest Contentful Paint (LCP)
- Database query time

Perfect for: Performance tuning, optimization, speed improvements, scalability
