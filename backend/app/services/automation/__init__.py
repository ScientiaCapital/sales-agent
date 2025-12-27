"""
Automation services for trigger rules and actions.

Provides:
- TriggerRuleEngine: Evaluates and executes automation rules
- ActionExecutor: Executes individual actions (Slack, email, CRM updates)
"""
from .trigger_engine import TriggerRuleEngine
from .action_executor import ActionExecutor

__all__ = ["TriggerRuleEngine", "ActionExecutor"]
