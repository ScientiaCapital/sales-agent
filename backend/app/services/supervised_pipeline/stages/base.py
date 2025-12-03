"""Base class for enrichment stages."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class StageResult:
    """Result from an enrichment stage."""
    success: bool
    data: Dict[str, Any]
    cost_usd: float = 0.0
    error: Optional[str] = None
    latency_ms: int = 0


class BaseStage(ABC):
    """Abstract base class for enrichment stages."""

    name: str = "base"
    cost_per_call: float = 0.0

    @abstractmethod
    async def execute(self, company: Dict[str, Any]) -> StageResult:
        """
        Execute the enrichment stage for a company.

        Args:
            company: Company data from Supabase

        Returns:
            StageResult with enrichment data
        """
        pass
