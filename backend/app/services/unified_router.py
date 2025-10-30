"""
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
