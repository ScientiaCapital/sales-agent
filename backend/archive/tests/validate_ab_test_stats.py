"""
Simple validation script for A/B Test statistical functions.
Runs without pytest/conftest to avoid app initialization issues.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

# Set dummy DATABASE_URL to avoid import errors
import os
os.environ['DATABASE_URL'] = 'postgresql+psycopg://test:test@localhost:5432/test'
os.environ['RUNPOD_S3_BUCKET_NAME'] = 'test-bucket'

print("🧪 Validating A/B Test Statistical Functions\n")
print("=" * 60)

# Now import after environment is set
from unittest.mock import Mock
from app.services.analytics.ab_test_service import ABTestAnalyticsService

# Create service with mock database
service = ABTestAnalyticsService(db=Mock())

# Test 1: Chi-Square Test - Significant Difference
print("\n✓ Test 1: Chi-Square Test - Significant Difference")
result = service.calculate_chi_square_test(
    conversions_a=50,
    participants_a=100,
    conversions_b=70,
    participants_b=100
)
assert result["is_significant"] == True, f"Should be significant, got {result}"
assert result["p_value"] < 0.05, f"P-value should be < 0.05, got {result['p_value']}"
print(f"  P-value: {result['p_value']:.6f} (< 0.05 ✓)")
print(f"  Chi-square: {result['chi_square_stat']:.4f}")
print(f"  Confidence: {result['confidence_level']:.2f}%")

# Test 2: Chi-Square Test - No Significant Difference
print("\n✓ Test 2: Chi-Square Test - No Significant Difference")
result = service.calculate_chi_square_test(
    conversions_a=50,
    participants_a=100,
    conversions_b=52,
    participants_b=100
)
assert result["is_significant"] == False, "Should not be significant"
assert result["p_value"] >= 0.05, f"P-value should be >= 0.05, got {result['p_value']}"
print(f"  P-value: {result['p_value']:.6f} (>= 0.05 ✓)")

# Test 3: Confidence Interval - 50% Conversion Rate
print("\n✓ Test 3: Confidence Interval - 50% Conversion Rate")
lower, upper = service.calculate_confidence_interval(
    successes=50,
    trials=100,
    confidence=0.95
)
assert 39.0 < lower < 41.0, f"Lower bound should be ~40%, got {lower}%"
assert 59.0 < upper < 61.0, f"Upper bound should be ~60%, got {upper}%"
print(f"  95% CI: [{lower:.2f}%, {upper:.2f}%]")
print(f"  Interval width: {upper - lower:.2f}%")

# Test 4: Confidence Interval - Small vs Large Sample
print("\n✓ Test 4: Confidence Interval - Sample Size Effect")
# Small sample (wide interval)
lower_small, upper_small = service.calculate_confidence_interval(
    successes=5,
    trials=10,
    confidence=0.95
)
# Large sample (narrow interval)
lower_large, upper_large = service.calculate_confidence_interval(
    successes=500,
    trials=1000,
    confidence=0.95
)
width_small = upper_small - lower_small
width_large = upper_large - lower_large
assert width_small > width_large, "Small sample should have wider interval"
print(f"  Small sample (n=10): [{lower_small:.2f}%, {upper_small:.2f}%] (width: {width_small:.2f}%)")
print(f"  Large sample (n=1000): [{lower_large:.2f}%, {upper_large:.2f}%] (width: {width_large:.2f}%)")

# Test 5: Minimum Sample Size Calculation
print("\n✓ Test 5: Minimum Sample Size Calculation")
sample_size = service.calculate_minimum_sample_size(
    baseline_rate=0.10,
    minimum_detectable_effect=0.20,
    alpha=0.05,
    power=0.80
)
assert 2500 < sample_size < 5000, f"Sample size should be ~3000-4000, got {sample_size}"
print(f"  Baseline: 10%, MDE: 20%, α: 0.05, Power: 0.80")
print(f"  Required sample size per variant: {sample_size}")

# Test 6: Sample Size with Different MDE
print("\n✓ Test 6: Sample Size - Effect of MDE")
sample_20pct = service.calculate_minimum_sample_size(
    baseline_rate=0.10,
    minimum_detectable_effect=0.20
)
sample_10pct = service.calculate_minimum_sample_size(
    baseline_rate=0.10,
    minimum_detectable_effect=0.10
)
assert sample_10pct > sample_20pct, "Smaller MDE should require larger sample"
print(f"  20% MDE: {sample_20pct} samples per variant")
print(f"  10% MDE: {sample_10pct} samples per variant")
print(f"  Ratio: {sample_10pct / sample_20pct:.2f}x larger for smaller effect")

# Test 7: Large Sample Significance
print("\n✓ Test 7: Large Sample Statistical Power")
result = service.calculate_chi_square_test(
    conversions_a=500,
    participants_a=1000,
    conversions_b=550,
    participants_b=1000
)
assert result["is_significant"] == True, "5% difference with large sample should be significant"
print(f"  Variant A: 500/1000 (50.0%)")
print(f"  Variant B: 550/1000 (55.0%)")
print(f"  P-value: {result['p_value']:.6f} (significant ✓)")

# Test 8: Edge Cases
print("\n✓ Test 8: Edge Cases Handling")
# Zero conversions
result = service.calculate_chi_square_test(
    conversions_a=0,
    participants_a=100,
    conversions_b=10,
    participants_b=100
)
print(f"  Zero conversions handled: p-value = {result['p_value']:.6f}")

# Zero trials (confidence interval)
lower, upper = service.calculate_confidence_interval(0, 0)
assert lower == 0.0 and upper == 0.0, "Should return (0, 0) for zero trials"
print(f"  Zero trials handled: CI = [{lower}, {upper}]")

# 100% conversion rate
lower, upper = service.calculate_confidence_interval(100, 100)
assert upper == 100.0, "Upper bound should be 100% for perfect conversion"
print(f"  100% conversion handled: CI = [{lower:.2f}%, {upper:.2f}%]")

print("\n" + "=" * 60)
print("✅ All statistical function validations passed!")
print("\nCore functionality verified:")
print("  ✓ Chi-square significance testing")
print("  ✓ Wilson score confidence intervals")
print("  ✓ Power-based sample size calculations")
print("  ✓ Edge case handling")
print("\nReady for integration into FastAPI endpoints.")
