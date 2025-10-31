# Frontend Testing Guide

Comprehensive testing infrastructure for the Sales Agent frontend, following best practices for React applications.

## Test Infrastructure

### Tools
- **Vitest**: Fast unit test runner (Vite-native)
- **React Testing Library**: Component testing with user-centric approach
- **Playwright**: E2E testing (already configured)
- **@testing-library/jest-dom**: Custom matchers for DOM assertions

### Setup

```bash
cd frontend
npm install
npm test                 # Run tests in watch mode
npm run test:ui          # Run tests with UI
npm run test:coverage    # Run tests with coverage report
npm run test:e2e         # Run E2E tests
```

## Test Structure

```
frontend/
├── src/
│   ├── test/
│   │   ├── setup.ts              # Test configuration
│   │   ├── hooks/                # Hook tests
│   │   │   └── useApi.test.ts
│   │   └── components/           # Component tests
│   │       └── DashboardMetrics.test.tsx
│   └── ...
└── vitest.config.ts              # Vitest configuration
```

## Writing Tests

### Component Tests

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MyComponent } from '../components/MyComponent';

describe('MyComponent', () => {
  it('should render correctly', () => {
    render(<MyComponent prop="value" />);
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });
});
```

### Hook Tests

```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { useMyHook } from '../hooks/useMyHook';

describe('useMyHook', () => {
  it('should return expected data', async () => {
    const { result } = renderHook(() => useMyHook());
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    
    expect(result.current.data).toBeDefined();
  });
});
```

### API Mocking

```typescript
import { vi } from 'vitest';
import { apiClient } from '../services/api';

vi.mock('../services/api', () => ({
  apiClient: {
    getData: vi.fn(),
  },
}));

// In test
vi.mocked(apiClient.getData).mockResolvedValue({ data: 'value' });
```

## Testing Patterns

### 1. Query by Role (Preferred)

```typescript
screen.getByRole('button', { name: /submit/i });
screen.getByRole('heading', { name: /dashboard/i });
```

### 2. Query by Text Content

```typescript
screen.getByText('Hello World');
screen.getByText(/hello world/i); // Case-insensitive
```

### 3. Query by Test ID (Last Resort)

```typescript
// Component
<div data-testid="dashboard-metrics">...</div>

// Test
screen.getByTestId('dashboard-metrics');
```

### 4. Async Testing

```typescript
// Wait for element
await waitFor(() => {
  expect(screen.getByText('Loaded')).toBeInTheDocument();
});

// Wait for query hook
await waitFor(() => {
  expect(result.current.isSuccess).toBe(true);
});
```

## Coverage Goals

- **Components**: 80%+ coverage
- **Hooks**: 90%+ coverage
- **Utilities**: 95%+ coverage
- **Critical paths**: 100% coverage

## Running Tests

### Development Mode
```bash
npm test              # Watch mode - reruns on file changes
```

### Single Run
```bash
npm test -- --run     # Single run, no watch
```

### Specific File
```bash
npm test -- useApi.test.ts
```

### Coverage Report
```bash
npm run test:coverage
# Open coverage/index.html in browser
```

## Debugging Tests

### VS Code Debug Configuration

```json
{
  "type": "node",
  "request": "launch",
  "name": "Debug Tests",
  "runtimeExecutable": "npm",
  "runtimeArgs": ["test", "--", "--no-coverage"],
  "console": "integratedTerminal"
}
```

### Debugging in Tests

```typescript
import { screen, debug } from '@testing-library/react';

// Print current DOM
debug();

// Print specific element
debug(screen.getByRole('button'));
```

## Best Practices

1. **Test Behavior, Not Implementation**
   - ❌ Don't test internal state
   - ✅ Test user-visible behavior

2. **Use Accessibility Queries**
   - Prefer `getByRole` > `getByLabelText` > `getByText` > `getByTestId`

3. **Clean Up**
   - Vitest automatically cleans up after each test
   - Use `afterEach` if needed for custom cleanup

4. **Mock External Dependencies**
   - Mock API calls
   - Mock environment variables
   - Don't mock React or testing utilities

5. **Keep Tests Isolated**
   - Each test should be independent
   - Use `beforeEach` for setup, not shared state

6. **Write Descriptive Test Names**
   ```typescript
   it('should display error message when API call fails', () => {
     // ...
   });
   ```

## Common Patterns

### Testing Loading States

```typescript
it('should show loading state', () => {
  render(<Component isLoading={true} />);
  expect(screen.getByText(/loading/i)).toBeInTheDocument();
});
```

### Testing Error States

```typescript
it('should display error message', () => {
  render(<Component error="Something went wrong" />);
  expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
});
```

### Testing User Interactions

```typescript
import userEvent from '@testing-library/user-event';

it('should handle button click', async () => {
  const user = userEvent.setup();
  const handleClick = vi.fn();
  
  render(<Button onClick={handleClick}>Click me</Button>);
  await user.click(screen.getByRole('button'));
  
  expect(handleClick).toHaveBeenCalledTimes(1);
});
```

## Integration with CI/CD

Tests run automatically in CI/CD pipelines. See `.github/workflows/ci.yml` for configuration.

### Pre-commit Hooks (Optional)

```bash
# Install husky (if needed)
npm install --save-dev husky

# Add pre-commit hook
npx husky add .husky/pre-commit "npm test -- --run"
```

## Troubleshooting

### Tests Not Running
- Check `vitest.config.ts` for correct configuration
- Ensure test files match `*.test.*` pattern
- Check `src/test/setup.ts` exists

### Import Errors
- Verify path aliases in `vitest.config.ts`
- Check TypeScript configuration

### Mock Issues
- Ensure mocks are hoisted (use `vi.mock` at top level)
- Check mock return values match expected types

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Library Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)

