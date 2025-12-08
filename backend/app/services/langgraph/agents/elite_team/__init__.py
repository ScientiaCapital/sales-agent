"""
Elite Team - Trifecta Hunter Squad

Three specialized agents for emerging vertical domination:
1. SignalScoutAgent - Detects market opportunities from inbound patterns
2. DeepHunterAgent - Orchestrates 30 OEM scrapers for contractor discovery
3. IntakeCommanderAgent - Quality gate, deduplication, Trifecta scoring, BDR routing

Philosophy: Quality over quantity. Focus on high-signal verticals.

Architecture:
    Signal Scout → Deep Hunter → Intake Commander
         ↓              ↓              ↓
    (Market)      (Contractor)   (Quality Gate)
    (Signals)      (Networks)     (BDR Queue)
"""

from .signal_scout_agent import (
    SignalScoutAgent,
    VerticalSignal,
    ScrapingOrder as SignalScoutScrapingOrder,
    SignalScoutResult,
)

from .deep_hunter_agent import (
    DeepHunterAgent,
    ScrapingOrder,
    ContractorMatch,
    HuntResult,
    DeepHunterState,
    OEM_MAPPING,
    ALL_OEMS,
)

from .intake_commander_agent import (
    IntakeCommanderAgent,
    IntakeResult,
    TrifectaScore,
    calculate_trifecta_score,
    is_garbage_contact,
)

__all__ = [
    # Signal Scout
    "SignalScoutAgent",
    "VerticalSignal",
    "SignalScoutScrapingOrder",
    "SignalScoutResult",
    # Deep Hunter
    "DeepHunterAgent",
    "ScrapingOrder",
    "ContractorMatch",
    "HuntResult",
    "DeepHunterState",
    "OEM_MAPPING",
    "ALL_OEMS",
    # Intake Commander
    "IntakeCommanderAgent",
    "IntakeResult",
    "TrifectaScore",
    "calculate_trifecta_score",
    "is_garbage_contact",
]
