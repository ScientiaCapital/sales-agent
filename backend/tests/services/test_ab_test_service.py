"""
Unit Tests for A/B Test Analytics Service

Tests statistical calculations including chi-square tests, confidence intervals,
and sample size calculations.
"""

import pytest
import math
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta

from app.services.analytics.ab_test_service import ABTestAnalyticsService, ABTestAnalysis
from app.models.analytics_models import AnalyticsABTest


class TestChiSquareCalculations:
    """Test chi-square statistical significance calculations"""

    def test_significant_difference(self):
        """Test chi-square with statistically significant difference"""
        service = ABTestAnalyticsService(db=Mock())

        # Variant A: 50/100 conversions (50%)
        # Variant B: 70/100 conversions (70%)
        result = service.calculate_chi_square_test(
            conversions_a=50,
            participants_a=100,
            conversions_b=70,
            participants_b=100
        )

        assert result["is_significant"] is True
        assert result["p_value"] < 0.05
        assert result["chi_square_stat"] > 0
        assert result["confidence_level"] > 95.0

    def test_no_significant_difference(self):
        """Test chi-square with no significant difference"""
        service = ABTestAnalyticsService(db=Mock())

        # Variant A: 50/100 conversions (50%)
        # Variant B: 52/100 conversions (52%)
        result = service.calculate_chi_square_test(
            conversions_a=50,
            participants_a=100,
            conversions_b=52,
            participants_b=100
        )

        assert result["is_significant"] is False
        assert result["p_value"] >= 0.05

    def test_large_sample_size_significant(self):
        """Test with large sample sizes"""
        service = ABTestAnalyticsService(db=Mock())

        # Variant A: 500/1000 conversions (50%)
        # Variant B: 550/1000 conversions (55%)
        # Small difference but large sample should be significant
        result = service.calculate_chi_square_test(
            conversions_a=500,
            participants_a=1000,
            conversions_b=550,
            participants_b=1000
        )

        assert result["is_significant"] is True
        assert result["p_value"] < 0.05

    def test_zero_conversions(self):
        """Test handling of zero conversions"""
        service = ABTestAnalyticsService(db=Mock())

        result = service.calculate_chi_square_test(
            conversions_a=0,
            participants_a=100,
            conversions_b=10,
            participants_b=100
        )

        assert "p_value" in result
        assert "chi_square_stat" in result


class TestConfidenceIntervals:
    """Test Wilson score confidence interval calculations"""

    def test_confidence_interval_50_percent(self):
        """Test confidence interval for 50% conversion rate"""
        service = ABTestAnalyticsService(db=Mock())

        # 50/100 conversions
        lower, upper = service.calculate_confidence_interval(
            successes=50,
            trials=100,
            confidence=0.95
        )

        # 95% CI for 50% should be approximately [40%, 60%]
        assert 39.0 < lower < 41.0
        assert 59.0 < upper < 61.0

    def test_confidence_interval_small_sample(self):
        """Test confidence interval with small sample size (wide interval)"""
        service = ABTestAnalyticsService(db=Mock())

        # 5/10 conversions (50%)
        lower, upper = service.calculate_confidence_interval(
            successes=5,
            trials=10,
            confidence=0.95
        )

        # Small sample should have wider interval
        interval_width = upper - lower
        assert interval_width > 30.0  # Wide interval

    def test_confidence_interval_large_sample(self):
        """Test confidence interval with large sample size (narrow interval)"""
        service = ABTestAnalyticsService(db=Mock())

        # 500/1000 conversions (50%)
        lower, upper = service.calculate_confidence_interval(
            successes=500,
            trials=1000,
            confidence=0.95
        )

        # Large sample should have narrow interval
        interval_width = upper - lower
        assert interval_width < 10.0  # Narrow interval

    def test_confidence_interval_zero_trials(self):
        """Test handling of zero trials"""
        service = ABTestAnalyticsService(db=Mock())

        lower, upper = service.calculate_confidence_interval(
            successes=0,
            trials=0,
            confidence=0.95
        )

        assert lower == 0.0
        assert upper == 0.0

    def test_confidence_interval_100_percent(self):
        """Test confidence interval for 100% conversion rate"""
        service = ABTestAnalyticsService(db=Mock())

        # 100/100 conversions
        lower, upper = service.calculate_confidence_interval(
            successes=100,
            trials=100,
            confidence=0.95
        )

        # Upper bound should be 100%
        assert upper == 100.0
        assert lower > 90.0


class TestSampleSizeCalculations:
    """Test minimum sample size calculations"""

    def test_sample_size_20_percent_mde(self):
        """Test sample size with 20% MDE"""
        service = ABTestAnalyticsService(db=Mock())

        # Baseline 10% conversion rate, 20% MDE (to 12%)
        sample_size = service.calculate_minimum_sample_size(
            baseline_rate=0.10,
            minimum_detectable_effect=0.20,
            alpha=0.05,
            power=0.80
        )

        # Should require approximately 3,000-4,000 per variant
        assert 2500 < sample_size < 5000

    def test_sample_size_10_percent_mde(self):
        """Test sample size with smaller 10% MDE (requires larger sample)"""
        service = ABTestAnalyticsService(db=Mock())

        # Baseline 10% conversion rate, 10% MDE (to 11%)
        sample_size = service.calculate_minimum_sample_size(
            baseline_rate=0.10,
            minimum_detectable_effect=0.10,
            alpha=0.05,
            power=0.80
        )

        # Smaller MDE requires larger sample
        assert sample_size > 10000

    def test_sample_size_high_baseline(self):
        """Test sample size with high baseline conversion rate"""
        service = ABTestAnalyticsService(db=Mock())

        # Baseline 50% conversion rate, 20% MDE (to 60%)
        sample_size = service.calculate_minimum_sample_size(
            baseline_rate=0.50,
            minimum_detectable_effect=0.20,
            alpha=0.05,
            power=0.80
        )

        # Higher baseline requires smaller sample
        assert 500 < sample_size < 1500

    def test_sample_size_edge_cases(self):
        """Test sample size with edge case baseline rates"""
        service = ABTestAnalyticsService(db=Mock())

        # Very low baseline (should be capped internally)
        sample_size_low = service.calculate_minimum_sample_size(
            baseline_rate=0.001,
            minimum_detectable_effect=0.20
        )
        assert sample_size_low > 0

        # Very high baseline (should be capped internally)
        sample_size_high = service.calculate_minimum_sample_size(
            baseline_rate=0.999,
            minimum_detectable_effect=0.20
        )
        assert sample_size_high > 0


class TestABTestAnalysis:
    """Test comprehensive A/B test analysis"""

    def setup_method(self):
        """Setup mock database and test data"""
        self.mock_db = Mock()
        self.service = ABTestAnalyticsService(db=self.mock_db)

    def test_analyze_significant_test(self):
        """Test analysis of statistically significant test"""
        # Mock test data
        mock_test = AnalyticsABTest(
            test_id="test_001",
            test_name="Email Subject Line Test",
            variant_a_name="Short Subject",
            variant_b_name="Long Subject",
            participants_a=1000,
            participants_b=1000,
            conversions_a=100,  # 10% conversion
            conversions_b=150,  # 15% conversion
            status="running",
            start_date=datetime.utcnow() - timedelta(days=7)
        )

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_test
        self.mock_db.query.return_value = mock_query

        # Analyze test
        analysis = self.service.analyze_ab_test("test_001")

        assert analysis.test_id == "test_001"
        assert analysis.is_significant is True
        assert analysis.winner == "B"
        assert analysis.lift_percentage > 0
        assert len(analysis.recommendations) > 0

    def test_analyze_inconclusive_test(self):
        """Test analysis of inconclusive test"""
        # Mock test data with no significant difference
        mock_test = AnalyticsABTest(
            test_id="test_002",
            test_name="CTA Button Color Test",
            variant_a_name="Blue Button",
            variant_b_name="Green Button",
            participants_a=100,
            participants_b=100,
            conversions_a=10,  # 10% conversion
            conversions_b=11,  # 11% conversion
            status="running",
            start_date=datetime.utcnow() - timedelta(days=2)
        )

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_test
        self.mock_db.query.return_value = mock_query

        # Analyze test
        analysis = self.service.analyze_ab_test("test_002")

        assert analysis.test_id == "test_002"
        assert analysis.is_significant is False
        assert analysis.winner is None
        assert analysis.sample_adequacy < 100.0

    def test_analyze_test_not_found(self):
        """Test error handling for non-existent test"""
        # Setup mock to return None
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        self.mock_db.query.return_value = mock_query

        # Should raise ValueError
        with pytest.raises(ValueError, match="not found"):
            self.service.analyze_ab_test("nonexistent_test")

    def test_early_stopping_detection(self):
        """Test early stopping opportunity detection"""
        # Mock test with early significance
        mock_test = AnalyticsABTest(
            test_id="test_003",
            test_name="Email Timing Test",
            variant_a_name="Morning",
            variant_b_name="Evening",
            participants_a=500,
            participants_b=500,
            conversions_a=50,   # 10% conversion
            conversions_b=100,  # 20% conversion (clear winner)
            status="running",
            start_date=datetime.utcnow() - timedelta(days=3)
        )

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_test
        self.mock_db.query.return_value = mock_query

        # Check early stopping
        result = self.service.detect_early_stopping_opportunity("test_003")

        assert result["is_significant"] is True
        assert result["winner"] is not None
        assert "recommendation" in result


class TestRecommendations:
    """Test recommendation generation logic"""

    def test_conclusive_test_recommendations(self):
        """Test recommendations for conclusive test"""
        service = ABTestAnalyticsService(db=Mock())

        recommendations = service._generate_recommendations(
            is_significant=True,
            sample_adequacy=100.0,
            winner="B",
            lift=25.0,
            participants_a=1000,
            participants_b=1000
        )

        assert len(recommendations) > 0
        assert any("conclusive" in rec.lower() for rec in recommendations)
        assert any("deploy" in rec.lower() for rec in recommendations)

    def test_early_significance_recommendations(self):
        """Test recommendations for early significance"""
        service = ABTestAnalyticsService(db=Mock())

        recommendations = service._generate_recommendations(
            is_significant=True,
            sample_adequacy=60.0,
            winner="A",
            lift=15.0,
            participants_a=300,
            participants_b=300
        )

        assert any("early" in rec.lower() for rec in recommendations)
        assert any("continue" in rec.lower() for rec in recommendations)

    def test_imbalanced_sample_warning(self):
        """Test warning for imbalanced samples"""
        service = ABTestAnalyticsService(db=Mock())

        recommendations = service._generate_recommendations(
            is_significant=False,
            sample_adequacy=50.0,
            winner=None,
            lift=0.0,
            participants_a=1000,
            participants_b=500  # 2:1 imbalance
        )

        assert any("imbalanced" in rec.lower() for rec in recommendations)


class TestDaysRemainingEstimation:
    """Test estimation of days remaining"""

    def test_estimate_days_remaining(self):
        """Test days remaining calculation"""
        service = ABTestAnalyticsService(db=Mock())

        mock_test = AnalyticsABTest(
            test_id="test_004",
            test_name="Test",
            status="running",
            start_date=datetime.utcnow() - timedelta(days=5)
        )

        # Current: 500 participants, Target: 2000, Velocity: 100/day
        # Should estimate 15 days remaining
        days = service._estimate_days_remaining(
            test=mock_test,
            current_participants=500,
            target_participants=2000
        )

        assert days is not None
        assert days > 0

    def test_estimate_no_start_date(self):
        """Test days remaining with no start date"""
        service = ABTestAnalyticsService(db=Mock())

        mock_test = AnalyticsABTest(
            test_id="test_005",
            test_name="Test",
            status="running",
            start_date=None
        )

        days = service._estimate_days_remaining(
            test=mock_test,
            current_participants=500,
            target_participants=2000
        )

        assert days is None

    def test_estimate_already_reached_target(self):
        """Test days remaining when target already reached"""
        service = ABTestAnalyticsService(db=Mock())

        mock_test = AnalyticsABTest(
            test_id="test_006",
            test_name="Test",
            status="running",
            start_date=datetime.utcnow() - timedelta(days=10)
        )

        days = service._estimate_days_remaining(
            test=mock_test,
            current_participants=2500,
            target_participants=2000
        )

        assert days is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
