"""
TDD tests for prompts module.

RED phase: These tests define the API we want.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add the services/analysis directory to path for imports
services_path = Path(__file__).parent.parent
if str(services_path) not in sys.path:
    sys.path.insert(0, str(services_path))

from prompts import (  # noqa: E402
    SYSTEM_PROMPT,
    TRADE_PROMPTS,
    get_analysis_prompt,
    get_trade_specific_prompt,
)

# =============================================================================
# CONSTANTS TESTS
# =============================================================================


class TestPromptConstants:
    """Test prompt constants exist and have valid structure."""

    def test_system_prompt_exists(self):
        """Should have a system prompt string."""
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 100  # Should be substantial

    def test_system_prompt_mentions_json(self):
        """System prompt should mention JSON output format."""
        assert "json" in SYSTEM_PROMPT.lower() or "JSON" in SYSTEM_PROMPT

    def test_trade_prompts_dict_exists(self):
        """Should have trade-specific prompts dictionary."""
        assert isinstance(TRADE_PROMPTS, dict)
        assert len(TRADE_PROMPTS) >= 5  # At least 5 trades

    def test_trade_prompts_covers_main_trades(self):
        """Should cover main construction trades."""
        expected_trades = ["solar", "electrical", "hvac", "plumbing", "roofing"]
        for trade in expected_trades:
            assert trade in TRADE_PROMPTS, f"Missing trade prompt: {trade}"


# =============================================================================
# GET ANALYSIS PROMPT TESTS
# =============================================================================


class TestGetAnalysisPrompt:
    """Test get_analysis_prompt function."""

    def test_returns_string(self):
        """Should return a prompt string."""
        result = get_analysis_prompt()
        assert isinstance(result, str)
        assert len(result) > 50

    def test_includes_json_instruction(self):
        """Should include instruction for JSON output."""
        result = get_analysis_prompt()
        assert "json" in result.lower() or "JSON" in result

    def test_includes_trade_field(self):
        """Should mention trade extraction."""
        result = get_analysis_prompt()
        assert "trade" in result.lower()


# =============================================================================
# TRADE-SPECIFIC PROMPT TESTS
# =============================================================================


class TestGetTradeSpecificPrompt:
    """Test trade-specific prompt retrieval."""

    def test_returns_prompt_for_known_trade(self):
        """Should return specific prompt for known trade."""
        result = get_trade_specific_prompt("solar")
        assert isinstance(result, str)
        assert "solar" in result.lower()

    def test_returns_generic_for_unknown_trade(self):
        """Should return generic prompt for unknown trade."""
        result = get_trade_specific_prompt("unknown_trade_xyz")
        assert isinstance(result, str)
        assert len(result) > 20  # Not empty

    def test_returns_generic_for_none(self):
        """Should return generic prompt for None trade."""
        result = get_trade_specific_prompt(None)
        assert isinstance(result, str)

    def test_case_insensitive(self):
        """Should handle case-insensitive trade names."""
        result_lower = get_trade_specific_prompt("solar")
        result_upper = get_trade_specific_prompt("SOLAR")
        result_mixed = get_trade_specific_prompt("Solar")
        # All should return the same prompt
        assert result_lower == result_upper == result_mixed
