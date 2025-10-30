"""
A/B Test Analytics Service

Provides statistical significance testing and advanced A/B test analysis.
Uses scipy for chi-square tests, confidence intervals, and sample size calculations.
"""

from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from scipy import stats
from scipy.stats import chi2_contingency
import numpy as np

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.analytics_models import AnalyticsABTest
from app.models.campaign import MessageVariantAnalytics, Campaign


@dataclass
class ABTestAnalysis:
    """Statistical analysis results for an A/B test"""
    test_id: str
    test_name: str

    # Variant A metrics
    variant_a_name: str
    variant_a_conversions: int
    variant_a_participants: int
    variant_a_conversion_rate: float
    variant_a_confidence_interval: Tuple[float, float]

    # Variant B metrics
    variant_b_name: str
    variant_b_conversions: int
    variant_b_participants: int
    variant_b_conversion_rate: float
    variant_b_confidence_interval: Tuple[float, float]

    # Statistical significance
    p_value: float
    chi_square_statistic: float
    is_significant: bool
    confidence_level: float

    # Winner determination
    winner: Optional[str]  # "A", "B", or None
    lift_percentage: float  # % improvement of winner over loser

    # Sample adequacy
    minimum_sample_size: int
    sample_adequacy: float  # % of minimum sample size achieved
    can_stop_early: bool

    # Recommendations
    recommendations: List[str]
    days_remaining_estimate: Optional[int]


class ABTestAnalyticsService:
    """
    Statistical analysis service for A/B testing.

    Provides chi-square testing, confidence intervals, sample size calculations,
    and early stopping recommendations.
    """

    def __init__(self, db: Session):
        self.db = db

    def calculate_chi_square_test(
        self,
        conversions_a: int,
        participants_a: int,
        conversions_b: int,
        participants_b: int
    ) -> Dict[str, Any]:
        """
        Calculate chi-square test for two variants.

        Args:
            conversions_a: Number of conversions for variant A
            participants_a: Total participants for variant A
            conversions_b: Number of conversions for variant B
            participants_b: Total participants for variant B

        Returns:
            dict with p_value, chi_square_stat, is_significant, confidence_level
        """
        # Create contingency table
        # [[conversions_a, non_conversions_a],
        #  [conversions_b, non_conversions_b]]
        non_conversions_a = participants_a - conversions_a
        non_conversions_b = participants_b - conversions_b

        contingency_table = np.array([
            [conversions_a, non_conversions_a],
            [conversions_b, non_conversions_b]
        ])

        # Perform chi-square test
        chi2, p_value, dof, expected_freq = chi2_contingency(contingency_table)

        # Determine significance level (95% confidence = 0.05 alpha)
        is_significant = p_value < 0.05
        confidence_level = (1 - p_value) * 100 if p_value < 1 else 0.0

        return {
            "p_value": float(p_value),
            "chi_square_stat": float(chi2),
            "is_significant": is_significant,
            "confidence_level": confidence_level,
            "degrees_of_freedom": int(dof)
        }

    def calculate_confidence_interval(
        self,
        successes: int,
        trials: int,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """
        Calculate confidence interval for a conversion rate using Wilson score interval.

        Args:
            successes: Number of successful conversions
            trials: Total number of trials
            confidence: Confidence level (default 0.95 for 95%)

        Returns:
            Tuple of (lower_bound, upper_bound) as percentages
        """
        if trials == 0:
            return (0.0, 0.0)

        # Conversion rate
        p = successes / trials

        # Z-score for confidence level
        z = stats.norm.ppf(1 - (1 - confidence) / 2)

        # Wilson score interval (more accurate than normal approximation)
        denominator = 1 + z**2 / trials
        center = (p + z**2 / (2 * trials)) / denominator
        margin = z * math.sqrt((p * (1 - p) / trials) + (z**2 / (4 * trials**2))) / denominator

        lower_bound = max(0.0, center - margin) * 100
        upper_bound = min(1.0, center + margin) * 100

        return (lower_bound, upper_bound)

    def calculate_minimum_sample_size(
        self,
        baseline_rate: float,
        minimum_detectable_effect: float = 0.20,
        alpha: float = 0.05,
        power: float = 0.80
    ) -> int:
        """
        Calculate minimum sample size per variant for statistical power.

        Args:
            baseline_rate: Expected baseline conversion rate (0.0 to 1.0)
            minimum_detectable_effect: MDE as relative change (e.g., 0.20 = 20% improvement)
            alpha: Significance level (default 0.05 for 95% confidence)
            power: Statistical power (default 0.80 for 80% power)

        Returns:
            Minimum sample size per variant
        """
        # Ensure baseline_rate is valid
        if baseline_rate <= 0 or baseline_rate >= 1:
            baseline_rate = max(0.01, min(0.99, baseline_rate))

        # Calculate expected alternative conversion rate
        alternative_rate = baseline_rate * (1 + minimum_detectable_effect)
        alternative_rate = min(0.99, alternative_rate)  # Cap at 99%

        # Z-scores for alpha and power
        z_alpha = stats.norm.ppf(1 - alpha / 2)  # Two-tailed test
        z_beta = stats.norm.ppf(power)

        # Pooled probability
        p_pooled = (baseline_rate + alternative_rate) / 2

        # Sample size calculation (simplified formula)
        numerator = (z_alpha * math.sqrt(2 * p_pooled * (1 - p_pooled)) +
                    z_beta * math.sqrt(baseline_rate * (1 - baseline_rate) +
                                     alternative_rate * (1 - alternative_rate)))
        denominator = abs(alternative_rate - baseline_rate)

        sample_size = (numerator / denominator) ** 2

        return int(math.ceil(sample_size))

    def analyze_ab_test(self, test_id: str) -> ABTestAnalysis:
        """
        Comprehensive statistical analysis of an A/B test.

        Args:
            test_id: Unique identifier for the A/B test

        Returns:
            ABTestAnalysis object with complete statistical analysis

        Raises:
            ValueError: If test_id not found
        """
        # Fetch test from database
        test = self.db.query(AnalyticsABTest).filter(
            AnalyticsABTest.test_id == test_id
        ).first()

        if not test:
            raise ValueError(f"A/B test with ID {test_id} not found")

        # Extract metrics
        conversions_a = test.conversions_a
        participants_a = test.participants_a
        conversions_b = test.conversions_b
        participants_b = test.participants_b

        # Calculate conversion rates
        conversion_rate_a = (conversions_a / participants_a * 100) if participants_a > 0 else 0.0
        conversion_rate_b = (conversions_b / participants_b * 100) if participants_b > 0 else 0.0

        # Calculate confidence intervals
        ci_a = self.calculate_confidence_interval(conversions_a, participants_a)
        ci_b = self.calculate_confidence_interval(conversions_b, participants_b)

        # Perform chi-square test
        chi_square_result = self.calculate_chi_square_test(
            conversions_a, participants_a,
            conversions_b, participants_b
        )

        # Determine winner
        winner = None
        lift_percentage = 0.0
        if chi_square_result["is_significant"]:
            if conversion_rate_a > conversion_rate_b:
                winner = "A"
                lift_percentage = ((conversion_rate_a - conversion_rate_b) / conversion_rate_b * 100) if conversion_rate_b > 0 else 0.0
            elif conversion_rate_b > conversion_rate_a:
                winner = "B"
                lift_percentage = ((conversion_rate_b - conversion_rate_a) / conversion_rate_a * 100) if conversion_rate_a > 0 else 0.0

        # Calculate minimum sample size
        baseline_rate = min(conversion_rate_a, conversion_rate_b) / 100  # Convert to 0-1 range
        min_sample_size = self.calculate_minimum_sample_size(baseline_rate)

        # Calculate sample adequacy
        total_participants = participants_a + participants_b
        sample_adequacy = (total_participants / (min_sample_size * 2)) * 100 if min_sample_size > 0 else 0.0

        # Early stopping criteria
        can_stop_early = (
            chi_square_result["is_significant"] and
            sample_adequacy >= 80.0 and
            total_participants >= 100  # Minimum absolute threshold
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            chi_square_result["is_significant"],
            sample_adequacy,
            winner,
            lift_percentage,
            participants_a,
            participants_b
        )

        # Estimate days remaining (if test is running)
        days_remaining = None
        if test.status == "running" and not can_stop_early:
            days_remaining = self._estimate_days_remaining(
                test, total_participants, min_sample_size * 2
            )

        return ABTestAnalysis(
            test_id=test_id,
            test_name=test.test_name,
            variant_a_name=test.variant_a_name,
            variant_a_conversions=conversions_a,
            variant_a_participants=participants_a,
            variant_a_conversion_rate=conversion_rate_a,
            variant_a_confidence_interval=ci_a,
            variant_b_name=test.variant_b_name,
            variant_b_conversions=conversions_b,
            variant_b_participants=participants_b,
            variant_b_conversion_rate=conversion_rate_b,
            variant_b_confidence_interval=ci_b,
            p_value=chi_square_result["p_value"],
            chi_square_statistic=chi_square_result["chi_square_stat"],
            is_significant=chi_square_result["is_significant"],
            confidence_level=chi_square_result["confidence_level"],
            winner=winner,
            lift_percentage=lift_percentage,
            minimum_sample_size=min_sample_size,
            sample_adequacy=sample_adequacy,
            can_stop_early=can_stop_early,
            recommendations=recommendations,
            days_remaining_estimate=days_remaining
        )

    def _generate_recommendations(
        self,
        is_significant: bool,
        sample_adequacy: float,
        winner: Optional[str],
        lift: float,
        participants_a: int,
        participants_b: int
    ) -> List[str]:
        """Generate actionable recommendations based on test results"""
        recommendations = []

        if is_significant and sample_adequacy >= 80:
            recommendations.append(f"✅ Test is conclusive! Variant {winner} wins with {lift:.1f}% improvement.")
            recommendations.append(f"🎯 Recommendation: Deploy variant {winner} to 100% of traffic.")
        elif is_significant and sample_adequacy < 80:
            recommendations.append(f"⚠️ Early significance detected but sample size is only {sample_adequacy:.1f}% of target.")
            recommendations.append("📊 Recommendation: Continue test for more reliable results.")
        elif not is_significant and sample_adequacy >= 100:
            recommendations.append("❌ No significant difference found after reaching target sample size.")
            recommendations.append("🔄 Recommendation: Consider testing a different variable or larger effect size.")
        else:
            needed_pct = 100 - sample_adequacy
            recommendations.append(f"⏳ Test in progress. Need {needed_pct:.1f}% more data to reach target sample size.")
            recommendations.append("📈 Recommendation: Continue running the test.")

        # Check for sample imbalance
        if participants_a > 0 and participants_b > 0:
            imbalance_ratio = max(participants_a, participants_b) / min(participants_a, participants_b)
            if imbalance_ratio > 1.2:
                recommendations.append(f"⚖️ Warning: Sample sizes are imbalanced ({participants_a} vs {participants_b}). Aim for 50/50 split.")

        return recommendations

    def _estimate_days_remaining(
        self,
        test: AnalyticsABTest,
        current_participants: int,
        target_participants: int
    ) -> Optional[int]:
        """Estimate days remaining to reach target sample size"""
        if not test.start_date or current_participants >= target_participants:
            return None

        # Calculate days elapsed
        days_elapsed = (datetime.utcnow() - test.start_date).days
        if days_elapsed == 0:
            return None  # Not enough data yet

        # Calculate participant velocity (participants per day)
        velocity = current_participants / days_elapsed

        if velocity <= 0:
            return None

        # Estimate remaining days
        remaining_participants = target_participants - current_participants
        days_remaining = int(math.ceil(remaining_participants / velocity))

        return max(1, days_remaining)  # At least 1 day

    def detect_early_stopping_opportunity(self, test_id: str) -> Dict[str, Any]:
        """
        Determine if test has reached statistical significance early.

        Args:
            test_id: Unique identifier for the A/B test

        Returns:
            dict with can_stop, confidence, sample_adequacy, recommendation
        """
        analysis = self.analyze_ab_test(test_id)

        return {
            "can_stop": analysis.can_stop_early,
            "confidence": analysis.confidence_level,
            "sample_adequacy": analysis.sample_adequacy,
            "is_significant": analysis.is_significant,
            "winner": analysis.winner,
            "lift_percentage": analysis.lift_percentage,
            "recommendation": analysis.recommendations[0] if analysis.recommendations else None
        }
