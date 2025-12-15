"""Scientia Capital Audit Infrastructure."""

from .schema import (
    ALL_MODELS,
    ANTHROPIC_MODELS,
    GEMINI_MODELS,
    OPENROUTER_MODELS,
    AccuracyMetrics,
    AuditMetadata,
    AuditRecord,
    CostMetrics,
    HashInfo,
    LatencyMetrics,
    ModelInfo,
    ModelTier,
    OperationalMetrics,
    Provider,
    TokenMetrics,
    calculate_margin_comparison,
    project_annual_costs,
)
from .logger import AuditLogger
from .exporters import AuditReportExporter, generate_audit_report

__all__ = [
    # Enums
    "Provider",
    "ModelTier",
    # Model registries
    "OPENROUTER_MODELS",
    "ANTHROPIC_MODELS",
    "GEMINI_MODELS",
    "ALL_MODELS",
    # Pydantic models
    "AuditMetadata",
    "ModelInfo",
    "TokenMetrics",
    "CostMetrics",
    "LatencyMetrics",
    "AccuracyMetrics",
    "OperationalMetrics",
    "HashInfo",
    "AuditRecord",
    # Logger
    "AuditLogger",
    # Helpers
    "calculate_margin_comparison",
    "project_annual_costs",
    # Exporters
    "AuditReportExporter",
    "generate_audit_report",
]
