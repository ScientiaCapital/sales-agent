"""
Workflow Automation Services

This package contains services for workflow rule evaluation and execution.
Part of Phase 4: Workflow Automation for the Close CRM Enhancements project.

Services:
    - WorkflowRuleEngine: Evaluates workflow rules against events and contexts
    - (Future) WorkflowActionExecutor: Executes actions for triggered rules
"""

from app.services.workflow.rule_engine import WorkflowRuleEngine

__all__ = ["WorkflowRuleEngine"]
