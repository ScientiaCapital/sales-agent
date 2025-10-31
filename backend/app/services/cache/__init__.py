"""
Cache services for sales agent.

Provides Redis-based caching for:
- LinkedIn enrichment data (expensive scrapes)
- Qualification scores (repeated company lookups)
- Growth strategy templates (reusable patterns)
"""

from .base import CacheBase, get_redis_client
from .enrichment_cache import EnrichmentCache
from .qualification_cache import QualificationCache

__all__ = [
    "CacheBase",
    "get_redis_client",
    "EnrichmentCache",
    "QualificationCache",
]
