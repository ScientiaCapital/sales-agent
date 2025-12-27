"""
Backward compatibility shim for pipeline_orchestrator.

This module re-exports PipelineOrchestrator from its new location.
Import from app.services.pipeline instead.
"""
from app.services.pipeline import PipelineOrchestrator

__all__ = ["PipelineOrchestrator"]
