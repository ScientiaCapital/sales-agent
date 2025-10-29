"""
Skills system for token-efficient reusable patterns.

Provides:
- SkillManager: Load, cache, and execute skills
- Pre-compiled knowledge modules
- Decision trees for common scenarios
- Jinja2 template rendering
- 89% average token reduction
"""

from .skill_manager import SkillManager

__all__ = ["SkillManager"]