#!/usr/bin/env python3
"""
Migration script to replace monolithic unified_router.py with modular architecture.

This script:
1. Backs up the original unified_router.py
2. Updates imports to use the new modular routing
3. Provides a compatibility layer for existing code
"""

import os
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def backup_original_file():
    """Backup the original unified_router.py file."""
    original_path = "app/services/unified_router.py"
    backup_path = f"app/services/unified_router_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    
    if os.path.exists(original_path):
        shutil.copy2(original_path, backup_path)
        logger.info(f"Backed up original file to: {backup_path}")
        return backup_path
    else:
        logger.warning(f"Original file not found: {original_path}")
        return None


def create_compatibility_layer():
    """Create a compatibility layer for existing imports."""
    compatibility_code = '''"""
Compatibility layer for unified_router.py migration.

This module provides backward compatibility for existing code that imports
from the old unified_router.py. It redirects to the new modular implementation.
"""

import warnings
from typing import Dict, List, Optional, Any, AsyncIterator

# Import the new modular implementation
from app.services.routing.unified_router import UnifiedRouter
from app.services.routing.base_router import RoutingRequest, RoutingResponse, TaskType, ProviderType, ProviderConfig

# Re-export the main classes for backward compatibility
__all__ = [
    "UnifiedRouter",
    "RoutingRequest", 
    "RoutingResponse",
    "TaskType",
    "ProviderType",
    "ProviderConfig"
]

# Issue deprecation warning
warnings.warn(
    "Importing from app.services.unified_router is deprecated. "
    "Please use app.services.routing.unified_router instead.",
    DeprecationWarning,
    stacklevel=2
)

# For backward compatibility, create an alias
UnifiedLLMRouter = UnifiedRouter
'''
    
    with open("app/services/unified_router.py", "w") as f:
        f.write(compatibility_code)
    
    logger.info("Created compatibility layer for unified_router.py")


def update_imports():
    """Update imports in files that use the old unified_router."""
    files_to_update = [
        "app/api/langgraph_agents.py",
        "app/services/lead_scorer.py",
        "app/services/research_pipeline.py",
        # Add more files as needed
    ]
    
    for file_path in files_to_update:
        if os.path.exists(file_path):
            update_file_imports(file_path)


def update_file_imports(file_path: str):
    """Update imports in a specific file."""
    try:
        with open(file_path, "r") as f:
            content = f.read()
        
        # Replace old imports with new ones
        old_imports = [
            "from app.services.unified_router import",
            "from app.services.unified_router import UnifiedLLMRouter",
            "from app.services.unified_router import RoutingRequest, RoutingResponse",
        ]
        
        new_imports = [
            "from app.services.routing.unified_router import",
            "from app.services.routing.unified_router import UnifiedRouter as UnifiedLLMRouter",
            "from app.services.routing.unified_router import RoutingRequest, RoutingResponse",
        ]
        
        updated = False
        for old, new in zip(old_imports, new_imports):
            if old in content:
                content = content.replace(old, new)
                updated = True
        
        if updated:
            with open(file_path, "w") as f:
                f.write(content)
            logger.info(f"Updated imports in: {file_path}")
        else:
            logger.info(f"No imports to update in: {file_path}")
            
    except Exception as e:
        logger.error(f"Failed to update {file_path}: {e}")


def create_migration_guide():
    """Create a migration guide for developers."""
    guide_content = """# Routing Migration Guide

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
"""
    
    with open("ROUTING_MIGRATION_GUIDE.md", "w") as f:
        f.write(guide_content)
    
    logger.info("Created migration guide: ROUTING_MIGRATION_GUIDE.md")


def main():
    """Run the migration process."""
    logger.info("Starting routing migration...")
    
    try:
        # Step 1: Backup original file
        backup_path = backup_original_file()
        
        # Step 2: Create compatibility layer
        create_compatibility_layer()
        
        # Step 3: Update imports in dependent files
        update_imports()
        
        # Step 4: Create migration guide
        create_migration_guide()
        
        logger.info("Migration completed successfully!")
        logger.info("Next steps:")
        logger.info("1. Test the application to ensure everything works")
        logger.info("2. Update imports in your code to use the new structure")
        logger.info("3. Remove the compatibility layer when ready")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
