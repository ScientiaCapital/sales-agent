"""
Workflow Automation Services

This package contains services for workflow rule evaluation and execution.
Part of Phase 4: Workflow Automation for the Close CRM Enhancements project.

Services:
    - WorkflowRuleEngine: Evaluates workflow rules against events and contexts
    - ActionExecutor: Executes actions for triggered rules
    - Default Rules: Pre-configured workflow rules that ship with the system
"""

from app.services.workflow.rule_engine import WorkflowRuleEngine
from app.services.workflow.action_executor import ActionExecutor, get_action_executor
from app.services.workflow.default_rules import (
    DEFAULT_RULES,
    seed_default_rules,
    seed_default_rules_sync,
    get_default_rule_names,
    is_default_rule,
)

__all__ = [
    "WorkflowRuleEngine",
    "ActionExecutor",
    "get_action_executor",
    "DEFAULT_RULES",
    "seed_default_rules",
    "seed_default_rules_sync",
    "get_default_rule_names",
    "is_default_rule",
]
