"""
Cost tracking services for sales agent.

Integrates with ai-cost-optimizer for real-time cost monitoring and optimization.
"""

from .optimizer_client import CostOptimizerClient, get_cost_optimizer

__all__ = [
    "CostOptimizerClient",
    "get_cost_optimizer",
]
