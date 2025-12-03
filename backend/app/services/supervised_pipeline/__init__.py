"""
Supervised Enrichment Pipeline

Interactive terminal-based enrichment with manual checkpoints.
Processes 2 companies in parallel through 4 sequential stages:
1. Apollo Free - Company enrichment (free tier)
2. LinkedIn - Company page scraping via Browserbase
3. Hunter.io - Email finding ($0.01/lookup)
4. Apollo Paid - Additional contacts if needed ($0.05/credit)

Usage:
    python run_supervised_enrichment.py --budget 5.00 --batch-size 2

Claude Code Commands:
    /enrich-supervised - Start pipeline with guidance
    /enrich-status - Check progress
    /enrich-retry-failed - Retry failures
"""

from .orchestrator import SupervisedOrchestrator
from .state_manager import StateManager
from .budget_tracker import BudgetTracker
from .stages import (
    BaseStage,
    StageResult,
    ApolloFreeStage,
    LinkedInStage,
    HunterStage,
    ApolloPaidStage,
)

__all__ = [
    # Core components
    "SupervisedOrchestrator",
    "StateManager",
    "BudgetTracker",
    # Stage classes
    "BaseStage",
    "StageResult",
    "ApolloFreeStage",
    "LinkedInStage",
    "HunterStage",
    "ApolloPaidStage",
]
