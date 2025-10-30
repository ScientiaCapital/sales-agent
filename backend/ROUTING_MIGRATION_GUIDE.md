# Routing Migration Guide

## Overview
The monolithic `unified_router.py` has been replaced with a modular architecture for better maintainability and testability.

## New Structure
```
app/services/routing/
├── __init__.py
├── base_router.py          # Core routing interface
├── task_router.py          # Task-specific routing
├── cost_router.py          # Cost optimization routing
├── unified_router.py       # Unified interface
└── providers/
    ├── __init__.py
    ├── base_provider.py    # Provider interface
    ├── cerebras_provider.py
    ├── claude_provider.py
    ├── deepseek_provider.py
    └── ollama_provider.py
```

## Migration Steps

### 1. Update Imports
```python
# Old
from app.services.unified_router import UnifiedLLMRouter

# New
from app.services.routing.unified_router import UnifiedRouter
```

### 2. Update Class Names
```python
# Old
router = UnifiedLLMRouter(providers)

# New
router = UnifiedRouter(providers)
```

### 3. Use New Features
```python
# Task-specific routing
from app.services.routing.task_router import TaskRouter
task_router = TaskRouter(providers)

# Cost optimization
from app.services.routing.cost_router import CostRouter
cost_router = CostRouter(providers)

# Individual providers
from app.services.routing.providers.cerebras_provider import CerebrasProvider
cerebras = CerebrasProvider(config)
```

## Benefits
- **Maintainability**: Smaller, focused files
- **Testability**: Individual components can be tested
- **Extensibility**: Easy to add new providers or strategies
- **Performance**: Better error handling and monitoring

## Backward Compatibility
The old import path still works but shows a deprecation warning. Update your imports when convenient.

## Testing
Run the test suite to ensure everything works:
```bash
pytest tests/test_routing.py
```
