#!/usr/bin/env python3
"""
Simple test to verify LeadScorer implementation without full dependencies
"""

import sys
import os

# Add backend to path
sys.path.insert(0, 'backend')

# Remove numpy import from lead_scorer temporarily for testing
import importlib.util

def test_lead_scorer_logic():
    """Test the core logic of LeadScorer without numpy dependency"""

    print("=" * 60)
    print("LEAD SCORER LOGIC TEST")
    print("=" * 60)

    # Import without numpy
    spec = importlib.util.spec_from_file_location(
        "lead_scorer",
        "backend/app/services/lead_scorer.py"
    )
    module = importlib.util.module_from_spec(spec)

    # Patch numpy if imported
    sys.modules['numpy'] = type(sys)('numpy')

    try:
        spec.loader.exec_module(module)

        # Get the classes
        LeadScorer = module.LeadScorer
        SignalData = module.SignalData
        ScoringWeights = module.ScoringWeights

        print("\n✅ LeadScorer module loaded successfully")

        # Test 1: Default weights
        print("\nTest 1: Default Weights")
        weights = ScoringWeights()
        print(f"  Company Size: {weights.company_size}")
        print(f"  Industry: {weights.industry}")
        print(f"  Signals: {weights.signals}")
        assert abs((weights.company_size + weights.industry + weights.signals) - 1.0) < 0.01
        print("  ✅ Weights sum to 1.0")

        # Test 2: Initialize scorer
        print("\nTest 2: Initialize LeadScorer")
        scorer = LeadScorer()
        print("  ✅ LeadScorer initialized")

        # Test 3: Industry scoring
        print("\nTest 3: Industry Scoring")
        saas_score = scorer.get_industry_score("SaaS")
        print(f"  SaaS: {saas_score:.1f}")
        assert saas_score > 80, "SaaS should score high"

        nonprofit_score = scorer.get_industry_score("Non-profit")
        print(f"  Non-profit: {nonprofit_score:.1f}")
        assert nonprofit_score < 50, "Non-profit should score low"
        print("  ✅ Industry scoring works correctly")

        # Test 4: Company size scoring
        print("\nTest 4: Company Size Scoring")
        small_score = scorer.get_size_score("1-10")
        print(f"  1-10 employees: {small_score:.1f}")
        assert small_score == 40, "Small companies should score 40"

        large_score = scorer.get_size_score("1000+")
        print(f"  1000+ employees: {large_score:.1f}")
        assert large_score == 95, "Large companies should score 95"
        print("  ✅ Size scoring works correctly")

        # Test 5: Signal analysis
        print("\nTest 5: Signal Analysis")
        strong_signals = SignalData(
            recent_funding=True,
            funding_amount_millions=50,
            demo_requested=True,
            employee_growth_rate=0.5
        )
        strong_score = scorer.analyze_signals(strong_signals)
        print(f"  Strong signals: {strong_score:.1f}")
        assert strong_score > 85, "Strong signals should score high"

        weak_signals = SignalData(
            recent_funding=False,
            demo_requested=False,
            employee_growth_rate=-0.1
        )
        weak_score = scorer.analyze_signals(weak_signals)
        print(f"  Weak signals: {weak_score:.1f}")
        assert weak_score < 50, "Weak signals should score low"
        print("  ✅ Signal analysis works correctly")

        # Test 6: Full scoring calculation
        print("\nTest 6: Full Scoring Calculation")
        lead_data = {
            "company_size": "201-500",
            "industry": "SaaS"
        }
        signals = SignalData(
            recent_funding=True,
            demo_requested=True
        )

        result = scorer.calculate_score(lead_data, signals)

        print(f"  Final Score: {result.score:.1f}")
        print(f"  Confidence: {result.confidence * 100:.0f}%")
        print(f"  Tier: {result.tier}")
        print(f"  Factors:")
        print(f"    - Company Size: {result.factors['company_size']:.1f}")
        print(f"    - Industry: {result.factors['industry']:.1f}")
        print(f"    - Signals: {result.factors['signals']:.1f}")

        assert 0 <= result.score <= 100, "Score should be in range 0-100"
        assert 0 <= result.confidence <= 1.0, "Confidence should be in range 0-1"
        assert result.tier in ["A", "B", "C", "D"], "Tier should be A/B/C/D"
        assert len(result.recommendations) > 0, "Should have recommendations"
        print("  ✅ Full scoring calculation works correctly")

        # Test 7: Edge cases
        print("\nTest 7: Edge Cases")

        # Empty data
        empty_result = scorer.calculate_score({}, None)
        print(f"  Empty data score: {empty_result.score:.1f}")
        print(f"  Empty data confidence: {empty_result.confidence:.2f}")
        assert empty_result.confidence < 0.5, "Empty data should have low confidence"

        # Unknown industry
        unknown_industry_score = scorer.get_industry_score("Some Random Industry XYZ")
        print(f"  Unknown industry score: {unknown_industry_score:.1f}")
        assert unknown_industry_score == 70.0, "Unknown industry should get default score"

        print("  ✅ Edge cases handled correctly")

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_lead_scorer_logic()
    sys.exit(0 if success else 1)