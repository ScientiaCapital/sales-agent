"""
Routing Module

This module provides a clean, modular approach to LLM routing and task management.
It replaces the monolithic unified_router.py with focused, maintainable components.

Architecture:
- BaseRouter: Core routing interface and common functionality
- TaskRouter: Task-specific routing logic
- CostRouter: Cost optimization and budget management
- Providers: Individual LLM provider implementations
- Strategies: Task-specific optimization strategies
"""

from .base_router import BaseRouter
from .task_router import TaskRouter
from .cost_router import CostRouter
from .unified_router import UnifiedRouter

__all__ = [
    "BaseRouter",
    "TaskRouter", 
    "CostRouter",
    "UnifiedRouter"
]
