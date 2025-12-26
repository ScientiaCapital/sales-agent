"""TDD tests for VLM audit infrastructure - 504 test matrix.

This test suite validates the audit infrastructure setup for comprehensive
VLM provider testing across 12 models and 42 MEP blueprint/field images.

Test Matrix:
- 6 trades (solar, electrical, hvac, roofing, plumbing, edge_cases)
- 42 total images (blueprints + field photos)
- 12 VLM models (4 OpenRouter + 3 Anthropic + 5 Gemini)
- 504 total test combinations (12 × 42)

RED phase: These tests WILL FAIL until test_providers.py is fully implemented.
"""

import pytest
from pathlib import Path


def test_all_trades_defined():
    """Verify all 6 trades are defined."""
    from tests.test_providers import TRADES

    expected_trades = ["solar", "electrical", "hvac", "roofing", "plumbing", "edge_cases"]
    for trade in expected_trades:
        assert trade in TRADES, f"Missing trade: {trade}"


def test_solar_has_8_images():
    """Solar: 4 blueprints + 4 field photos = 8."""
    from tests.test_providers import TRADES

    solar = TRADES["solar"]
    total = len(solar.get("blueprints", [])) + len(solar.get("field_photos", []))
    assert total == 8, f"Solar should have 8 images, got {total}"


def test_electrical_has_8_images():
    """Electrical: 4 blueprints + 4 field photos = 8."""
    from tests.test_providers import TRADES

    electrical = TRADES["electrical"]
    total = len(electrical.get("blueprints", [])) + len(electrical.get("field_photos", []))
    assert total == 8, f"Electrical should have 8 images, got {total}"


def test_hvac_has_7_images():
    """HVAC: 4 blueprints + 3 field photos = 7."""
    from tests.test_providers import TRADES

    hvac = TRADES["hvac"]
    total = len(hvac.get("blueprints", [])) + len(hvac.get("field_photos", []))
    assert total == 7, f"HVAC should have 7 images, got {total}"


def test_roofing_has_8_images():
    """Roofing: 4 blueprints + 4 field photos = 8."""
    from tests.test_providers import TRADES

    roofing = TRADES["roofing"]
    total = len(roofing.get("blueprints", [])) + len(roofing.get("field_photos", []))
    assert total == 8, f"Roofing should have 8 images, got {total}"


def test_plumbing_has_8_images():
    """Plumbing: 4 blueprints + 4 field photos = 8."""
    from tests.test_providers import TRADES

    plumbing = TRADES["plumbing"]
    total = len(plumbing.get("blueprints", [])) + len(plumbing.get("field_photos", []))
    assert total == 8, f"Plumbing should have 8 images, got {total}"


def test_edge_cases_has_3_images():
    """Edge cases: 3 blueprints + 0 field photos = 3."""
    from tests.test_providers import TRADES

    edge = TRADES["edge_cases"]
    total = len(edge.get("blueprints", [])) + len(edge.get("field_photos", []))
    assert total == 3, f"Edge cases should have 3 images, got {total}"


def test_total_42_images():
    """Total across all trades = 42."""
    from tests.test_providers import TRADES

    total = 0
    for trade_data in TRADES.values():
        total += len(trade_data.get("blueprints", []))
        total += len(trade_data.get("field_photos", []))
    assert total == 42, f"Total should be 42 images, got {total}"


def test_openrouter_has_4_models():
    """OpenRouter: 4 Chinese VLMs."""
    from tests.test_providers import OPENROUTER_MODELS

    assert len(OPENROUTER_MODELS) == 4, f"OpenRouter should have 4 models, got {len(OPENROUTER_MODELS)}"


def test_openrouter_includes_glm():
    """GLM-4.6v must be in OpenRouter models."""
    from tests.test_providers import OPENROUTER_MODELS

    assert "z-ai/glm-4.6v" in OPENROUTER_MODELS, "GLM-4.6v missing from OpenRouter"


def test_anthropic_has_3_models():
    """Anthropic: 3 Claude 4.5 models."""
    from tests.test_providers import ANTHROPIC_MODELS

    assert len(ANTHROPIC_MODELS) == 3, f"Anthropic should have 3 models, got {len(ANTHROPIC_MODELS)}"


def test_anthropic_all_claude_4_or_35():
    """All Anthropic models must be Claude 4.x or 3.5 family."""
    from tests.test_providers import ANTHROPIC_MODELS

    for model in ANTHROPIC_MODELS:
        assert "4-" in model or "3-5" in model, f"Model {model} is not Claude 4.x or 3.5 family"


def test_gemini_has_5_models():
    """Gemini: 5 models across 2.0, 2.5, 3.0."""
    from tests.test_providers import GEMINI_MODELS

    assert len(GEMINI_MODELS) == 5, f"Gemini should have 5 models, got {len(GEMINI_MODELS)}"


def test_total_12_models():
    """Total models = 12."""
    from tests.test_providers import ALL_MODELS

    total = sum(len(models) for models in ALL_MODELS.values())
    assert total == 12, f"Total should be 12 models, got {total}"


def test_504_total_tests():
    """12 models × 42 images = 504 tests."""
    from tests.test_providers import ALL_MODELS, TRADES

    total_models = sum(len(models) for models in ALL_MODELS.values())
    total_images = sum(
        len(t.get("blueprints", [])) + len(t.get("field_photos", []))
        for t in TRADES.values()
    )
    total_tests = total_models * total_images
    assert total_tests == 504, f"Should be 504 tests, got {total_tests}"
