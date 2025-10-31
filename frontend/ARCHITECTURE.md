# Frontend Architecture Guide

Comprehensive guide to the Sales Agent frontend architecture, refactoring patterns, and best practices.

## Architecture Overview

### Tech Stack
- **React 19**: Latest React with concurrent features
- **TypeScript**: Full type safety
- **Vite**: Fast build tool
- **React Query (TanStack Query)**: Data fetching and caching
- **React Router**: Client-side routing
- **Tailwind CSS**: Utility-first styling
- **Vitest**: Unit testing
- **Playwright**: E2E testing

## Project Structure

```
frontend/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── ui/              # Base UI components (buttons, cards, etc.)
│   │   ├── dashboard/       # Dashboard-specific components
│   │   └── providers/       # Context providers
│   ├── pages/               # Page components (routes)
│   ├── hooks/               # Custom React hooks
│   │   └── useApi.ts       # React Query hooks for API calls
│   ├── services/           # Service layer (API client)
│   ├── lib/                # Utilities and helpers
│   │   └── debug.ts        # Debugging and logging utilities
│   ├── types/              # TypeScript type definitions
│   └── test/               # Test setup and utilities
└── vitest.config.ts        # Test configuration
```

## Key Architectural Patterns

### 1. Data Fetching with React Query

**Before (Component State)**:
```typescript
const [leads, setLeads] = useState([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);

useEffect(() => {
  fetch('/api/leads')
    .then(res => res.json())
    .then(data => setLeads(data))
    .catch(err => setError(err))
    .finally(() => setLoading(false));
}, []);
```

**After (React Query Hook)**:
```typescript
const { data: leads, isLoading, error } = useLeads();
```

**Benefits**:
- Automatic caching and refetching
- Built-in loading and error states
- Optimistic updates
- Request deduplication

### 2. Component Composition

**Large Component**:
```typescript
// ❌ Dashboard.tsx (400+ lines, hard to test)
export function Dashboard() {
  // All logic in one component
}
```

**Composed Components**:
```typescript
// ✅ Dashboard.tsx (focused on composition)
export function Dashboard() {
  return (
    <>
      <DashboardSystemStatus />
      <DashboardMetrics />
      <DashboardCharts />
    </>
  );
}
```

**Benefits**:
- Easier to test individual pieces
- Better code organization
- Reusable components
- Easier to maintain

### 3. Custom Hooks for Business Logic

**Extract Logic to Hooks**:
```typescript
// hooks/useDashboardData.ts
export function useDashboardData() {
  const metrics = useMetricsSummary();
  const leads = useLeads();
  // ... combine and transform data
  return { metrics, leads, isLoading, error };
}

// pages/Dashboard.tsx
export function Dashboard() {
  const { metrics, leads, isLoading, error } = useDashboardData();
  // ... render UI
}
```

### 4. Error Handling Strategy

**Centralized Error Handling**:
```typescript
// lib/debug.ts
export class ErrorTracker {
  static captureException(error: Error, context?: LogContext): void {
    logger.error('Exception captured', error, context);
    // TODO: Send to error tracking service (Sentry, etc.)
  }
}

// hooks/useApi.ts
try {
  const result = await apiClient.getData();
  return result;
} catch (error) {
  ErrorTracker.captureException(error as Error, { endpoint: '/api/data' });
  throw error;
}
```

### 5. Performance Monitoring

**Component Performance**:
```typescript
import { usePerformanceMonitor } from '../lib/debug';

export function Dashboard() {
  usePerformanceMonitor('Dashboard');
  // ... component code
}
```

**API Performance**:
```typescript
const start = performance.now();
const result = await apiClient.getData();
const duration = performance.now() - start;
logger.apiCall('GET', '/api/data', duration);
```

## Refactoring Checklist

When refactoring components:

1. ✅ **Extract Data Fetching**: Move to React Query hooks
2. ✅ **Split Large Components**: Break into smaller, focused components
3. ✅ **Extract Custom Hooks**: Move business logic to hooks
4. ✅ **Add Error Handling**: Use ErrorTracker for error logging
5. ✅ **Add Tests**: Write unit tests for components and hooks
6. ✅ **Performance Monitoring**: Add performance tracking
7. ✅ **Type Safety**: Ensure all types are properly defined

## Code Quality Standards

### TypeScript
- **Strict Mode**: Enabled in `tsconfig.json`
- **No `any` Types**: Use proper types or `unknown`
- **Type Imports**: Use `import type` for type-only imports

### React
- **Functional Components**: Use function components (not classes)
- **Hooks**: Custom hooks start with `use`
- **Memoization**: Use `React.memo` for expensive components
- **Props**: Destructure props in component signature

### Testing
- **Test Coverage**: Aim for 80%+ coverage
- **Test Naming**: `describe('Component', () => { it('should do X', () => {}) })`
- **Accessibility**: Test with accessibility in mind

## Debugging Workflow

### 1. Enable Debug Logging

```typescript
import { logger } from '../lib/debug';

logger.debug('Debug message', { context: 'value' });
logger.info('Info message');
logger.warn('Warning message');
logger.error('Error message', error);
```

### 2. Monitor Performance

```typescript
import { PerformanceMonitor } from '../lib/debug';

const endMeasurement = PerformanceMonitor.start('my-operation');
// ... do work
endMeasurement();

// Check stats
const stats = PerformanceMonitor.getStats('my-operation');
console.log(stats); // { count, avg, min, max }
```

### 3. Use React DevTools

- Install React DevTools browser extension
- Use Profiler to identify slow renders
- Check component tree and props

### 4. Network Debugging

- Use browser DevTools Network tab
- Check React Query DevTools (if installed)
- Verify API responses match expected types

## Common Patterns

### Loading States

```typescript
const { data, isLoading, error } = useLeads();

if (isLoading) return <LoadingSpinner />;
if (error) return <ErrorMessage error={error} />;
return <LeadsList leads={data} />;
```

### Error Boundaries

```typescript
// Wrap app in ErrorBoundary
<ErrorBoundary>
  <App />
</ErrorBoundary>
```

### Optimistic Updates

```typescript
const mutation = useMutation({
  mutationFn: updateLead,
  onMutate: async (newData) => {
    // Cancel outgoing refetches
    await queryClient.cancelQueries({ queryKey: ['leads'] });
    
    // Snapshot previous value
    const previous = queryClient.getQueryData(['leads']);
    
    // Optimistically update
    queryClient.setQueryData(['leads'], (old) => [...old, newData]);
    
    return { previous };
  },
  onError: (err, variables, context) => {
    // Rollback on error
    queryClient.setQueryData(['leads'], context.previous);
  },
});
```

## Migration Guide

### Migrating from Mock Data

1. **Create React Query Hook**:
   ```typescript
   export function useMetricsSummary() {
     return useQuery({
       queryKey: ['metrics', 'summary'],
       queryFn: () => apiClient.getMetricsSummary(),
     });
   }
   ```

2. **Replace Mock Data**:
   ```typescript
   // Before
   const data = mockDashboardData;
   
   // After
   const { data } = useMetricsSummary();
   ```

3. **Handle Loading/Error States**:
   ```typescript
   const { data, isLoading, error } = useMetricsSummary();
   
   if (isLoading) return <LoadingSpinner />;
   if (error) return <ErrorMessage />;
   ```

4. **Update Components**:
   ```typescript
   // Pass real data instead of mock
   <DashboardMetrics metrics={data} isLoading={isLoading} />
   ```

## Best Practices

1. **Component Size**: Keep components under 300 lines
2. **Hook Reusability**: Extract reusable logic to custom hooks
3. **Type Safety**: Use TypeScript types for all data
4. **Error Handling**: Always handle errors gracefully
5. **Performance**: Monitor and optimize slow components
6. **Testing**: Write tests for critical paths
7. **Documentation**: Document complex logic and decisions

## Resources

- [React Query Documentation](https://tanstack.com/query/latest)
- [React Best Practices](https://react.dev/learn)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Testing Library Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)

