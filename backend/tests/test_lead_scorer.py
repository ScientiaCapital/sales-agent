"""
Unit tests for the LeadScorer service
"""
import pytest
from unittest.mock import Mock, patch
from app.services.lead_scorer import (
    LeadScorer, LeadScorerFactory, ScoringWeights,
    SignalData, ScoringResult
)


class TestScoringWeights:
    """Test the ScoringWeights model validation"""

    def test_default_weights(self):
        """Test default weight values sum to 1.0"""
        weights = ScoringWeights()
        assert weights.company_size == 0.30
        assert weights.industry == 0.25
        assert weights.signals == 0.45
        total = weights.company_size + weights.industry + weights.signals
        assert abs(total - 1.0) < 0.01

    def test_custom_valid_weights(self):
        """Test custom weights that sum to 1.0"""
        weights = ScoringWeights(
            company_size=0.40,
            industry=0.30,
            signals=0.30
        )
        total = weights.company_size + weights.industry + weights.signals
        assert abs(total - 1.0) < 0.01

    def test_invalid_weights_sum(self):
        """Test validation error when weights don't sum to 1.0"""
        with pytest.raises(ValueError) as exc_info:
            ScoringWeights(
                company_size=0.50,
                industry=0.30,
                signals=0.30
            )
        assert "Weights must sum to 1.0" in str(exc_info.value)

    def test_weight_boundaries(self):
        """Test weight value boundaries (0 to 1)"""
        # Valid boundary
        weights = ScoringWeights(
            company_size=0.0,
            industry=0.0,
            signals=1.0
        )
        assert weights.signals == 1.0

        # Invalid boundary
        with pytest.raises(ValueError):
            ScoringWeights(
                company_size=-0.1,
                industry=0.5,
                signals=0.6
            )


class TestSignalData:
    """Test the SignalData model"""

    def test_empty_signals(self):
        """Test creating SignalData with no data"""
        signals = SignalData()
        assert signals.recent_funding is None
        assert signals.demo_requested is None

    def test_partial_signals(self):
        """Test SignalData with partial data"""
        signals = SignalData(
            recent_funding=True,
            funding_amount_millions=15.5,
            demo_requested=False
        )
        assert signals.recent_funding is True
        assert signals.funding_amount_millions == 15.5
        assert signals.demo_requested is False
        assert signals.employee_growth_rate is None

    def test_complete_signals(self):
        """Test SignalData with all fields"""
        signals = SignalData(
            recent_funding=True,
            funding_amount_millions=25.0,
            employee_growth_rate=0.35,
            tech_stack_modern=True,
            cloud_adoption=True,
            website_traffic_rank=50000,
            content_downloads=8,
            demo_requested=True,
            competitor_customer=False,
            expansion_planned=True
        )
        assert signals.employee_growth_rate == 0.35
        assert signals.website_traffic_rank == 50000


class TestLeadScorer:
    """Test the LeadScorer main functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.scorer = LeadScorer()

    def test_initialization_default(self):
        """Test LeadScorer initialization with default weights"""
        scorer = LeadScorer()
        assert scorer.weights.company_size == 0.30
        assert scorer.weights.industry == 0.25
        assert scorer.weights.signals == 0.45

    def test_initialization_custom_weights(self):
        """Test LeadScorer initialization with custom weights"""
        weights = ScoringWeights(
            company_size=0.40,
            industry=0.30,
            signals=0.30
        )
        scorer = LeadScorer(weights)
        assert scorer.weights.company_size == 0.40

    def test_get_industry_score_high_value(self):
        """Test industry scoring for high-value industries"""
        # SaaS - highest multiplier
        score = self.scorer.get_industry_score("SaaS")
        assert score > 80

        # FinTech - high multiplier
        score = self.scorer.get_industry_score("FinTech")
        assert score > 70

    def test_get_industry_score_low_value(self):
        """Test industry scoring for low-value industries"""
        # Manufacturing - low multiplier
        score = self.scorer.get_industry_score("Manufacturing")
        assert score < 70

        # Non-profit - lowest multiplier
        score = self.scorer.get_industry_score("Non-profit")
        assert score < 50

    def test_get_industry_score_unknown(self):
        """Test industry scoring for unknown industry"""
        score = self.scorer.get_industry_score("Unknown Industry XYZ")
        assert score == 70.0  # Default score

    def test_get_industry_score_none(self):
        """Test industry scoring with None input"""
        score = self.scorer.get_industry_score(None)
        assert score == 50.0

    def test_get_industry_score_partial_match(self):
        """Test industry scoring with partial matches"""
        # Should match "Software"
        score = self.scorer.get_industry_score("Custom Software Development")
        assert score > 80

    def test_get_size_score_ranges(self):
        """Test company size scoring for different ranges"""
        # Small company
        score = self.scorer.get_size_score("1-10")
        assert score == 40

        # Medium company
        score = self.scorer.get_size_score("51-200")
        assert score == 75

        # Large company
        score = self.scorer.get_size_score("1000+")
        assert score == 95

        # Enterprise
        score = self.scorer.get_size_score("Enterprise")
        assert score == 100

    def test_get_size_score_numeric_parsing(self):
        """Test size scoring with numeric string parsing"""
        # Should parse "500 employees"
        score = self.scorer.get_size_score("500 employees")
        assert 80 <= score <= 90

        # Should parse "About 2000 people"
        score = self.scorer.get_size_score("About 2000 people")
        assert score >= 95

    def test_get_size_score_keywords(self):
        """Test size scoring with keyword matching"""
        score = self.scorer.get_size_score("Large enterprise")
        assert score == 100

        score = self.scorer.get_size_score("Mid-size company")
        assert score == 75

        score = self.scorer.get_size_score("Small startup")
        assert score == 50

    def test_get_size_score_none(self):
        """Test size scoring with None input"""
        score = self.scorer.get_size_score(None)
        assert score == 50.0  # Default score

    def test_analyze_signals_strong(self):
        """Test signal analysis with strong buying signals"""
        signals = SignalData(
            recent_funding=True,
            funding_amount_millions=50.0,
            employee_growth_rate=0.6,
            demo_requested=True,
            expansion_planned=True
        )
        score = self.scorer.analyze_signals(signals)
        assert score > 85  # Should be very high

    def test_analyze_signals_weak(self):
        """Test signal analysis with weak buying signals"""
        signals = SignalData(
            recent_funding=False,
            employee_growth_rate=-0.1,  # Negative growth
            demo_requested=False,
            expansion_planned=False
        )
        score = self.scorer.analyze_signals(signals)
        assert score < 50  # Should be low

    def test_analyze_signals_mixed(self):
        """Test signal analysis with mixed signals"""
        signals = SignalData(
            recent_funding=True,
            employee_growth_rate=0.1,
            tech_stack_modern=False,
            demo_requested=False,
            competitor_customer=True
        )
        score = self.scorer.analyze_signals(signals)
        assert 50 <= score <= 75  # Should be moderate

    def test_analyze_signals_none(self):
        """Test signal analysis with None input"""
        score = self.scorer.analyze_signals(None)
        assert score == 50.0  # Default score

    def test_analyze_signals_website_traffic(self):
        """Test website traffic ranking signal"""
        # Top 10k website
        signals = SignalData(website_traffic_rank=5000)
        score = self.scorer.analyze_signals(signals)
        assert score > 70

        # Low traffic website
        signals = SignalData(website_traffic_rank=5000000)
        score = self.scorer.analyze_signals(signals)
        assert score < 50

    def test_calculate_score_complete_data(self):
        """Test full scoring calculation with complete data"""
        lead_data = {
            "company_size": "201-500",
            "industry": "SaaS"
        }
        signals = SignalData(
            recent_funding=True,
            demo_requested=True,
            employee_growth_rate=0.3
        )

        result = self.scorer.calculate_score(lead_data, signals)

        assert isinstance(result, ScoringResult)
        assert 0 <= result.score <= 100
        assert 0 <= result.confidence <= 1.0
        assert result.tier in ["A", "B", "C", "D"]
        assert len(result.factors) == 3
        assert len(result.reasoning) > 0
        assert len(result.recommendations) > 0

    def test_calculate_score_tier_classification(self):
        """Test tier classification based on scores"""
        # High score -> Tier A
        lead_data = {
            "company_size": "1000+",
            "industry": "SaaS"
        }
        signals = SignalData(
            recent_funding=True,
            demo_requested=True,
            funding_amount_millions=100
        )
        result = self.scorer.calculate_score(lead_data, signals)
        assert result.tier == "A"
        assert result.score >= 80

        # Low score -> Tier D
        lead_data = {
            "company_size": "1-10",
            "industry": "Non-profit"
        }
        result = self.scorer.calculate_score(lead_data, None)
        assert result.tier in ["C", "D"]
        assert result.score < 65

    def test_calculate_score_partial_data(self):
        """Test scoring with partial data"""
        # Only company size
        lead_data = {"company_size": "51-200"}
        result = self.scorer.calculate_score(lead_data)

        assert result.score > 0
        assert result.confidence < 0.6  # Low confidence
        assert "company_size" in result.factors

        # Only industry
        lead_data = {"industry": "FinTech"}
        result = self.scorer.calculate_score(lead_data)

        assert result.score > 0
        assert result.confidence < 0.6

    def test_calculate_score_no_data(self):
        """Test scoring with no data"""
        lead_data = {}
        result = self.scorer.calculate_score(lead_data)

        assert result.score == 50.0  # All defaults
        assert result.confidence <= 0.4  # Very low confidence

    def test_confidence_calculation(self):
        """Test confidence score calculation based on data completeness"""
        # Full data - high confidence
        lead_data = {
            "company_size": "201-500",
            "industry": "SaaS"
        }
        signals = SignalData(
            recent_funding=True,
            demo_requested=True,
            employee_growth_rate=0.3,
            tech_stack_modern=True,
            cloud_adoption=True
        )
        result = self.scorer.calculate_score(lead_data, signals)
        assert result.confidence > 0.85

        # Partial data - medium confidence
        lead_data = {
            "company_size": "51-200"
        }
        signals = SignalData(demo_requested=True)
        result = self.scorer.calculate_score(lead_data, signals)
        assert 0.4 < result.confidence < 0.8

    def test_recommendations_generation(self):
        """Test recommendation generation based on tier and signals"""
        # Tier A with demo request
        lead_data = {
            "company_size": "1000+",
            "industry": "SaaS"
        }
        signals = SignalData(
            demo_requested=True,
            recent_funding=True
        )
        result = self.scorer.calculate_score(lead_data, signals)

        assert any("immediate outreach" in r.lower() for r in result.recommendations)
        assert any("demo" in r.lower() for r in result.recommendations)

        # Tier C
        lead_data = {
            "company_size": "11-50",
            "industry": "Retail"
        }
        result = self.scorer.calculate_score(lead_data)
        assert any("nurture" in r.lower() or "email" in r.lower()
                  for r in result.recommendations)

    def test_reasoning_generation(self):
        """Test reasoning text generation"""
        lead_data = {
            "company_size": "201-500",
            "industry": "FinTech"
        }
        signals = SignalData(
            recent_funding=True,
            demo_requested=True
        )
        result = self.scorer.calculate_score(lead_data, signals)

        assert "Tier" in result.reasoning
        assert str(result.score) in result.reasoning
        assert any(word in result.reasoning.lower()
                  for word in ["company", "industry", "signal", "buying"])


class TestLeadScorerFactory:
    """Test the LeadScorerFactory patterns"""

    def test_create_default(self):
        """Test creating default scorer"""
        scorer = LeadScorerFactory.create_default()
        assert isinstance(scorer, LeadScorer)
        assert scorer.weights.company_size == 0.30
        assert scorer.weights.industry == 0.25
        assert scorer.weights.signals == 0.45

    def test_create_enterprise_focused(self):
        """Test creating enterprise-focused scorer"""
        scorer = LeadScorerFactory.create_enterprise_focused()
        assert scorer.weights.company_size == 0.40  # Higher weight
        assert scorer.weights.signals == 0.40

    def test_create_signal_focused(self):
        """Test creating signal-focused scorer"""
        scorer = LeadScorerFactory.create_signal_focused()
        assert scorer.weights.signals == 0.60  # Highest weight
        assert scorer.weights.company_size == 0.20

    def test_create_industry_focused(self):
        """Test creating industry-focused scorer"""
        scorer = LeadScorerFactory.create_industry_focused()
        assert scorer.weights.industry == 0.40  # Highest weight
        assert scorer.weights.company_size == 0.25

    def test_factory_scorers_sum_to_one(self):
        """Test all factory scorers have weights that sum to 1.0"""
        scorers = [
            LeadScorerFactory.create_default(),
            LeadScorerFactory.create_enterprise_focused(),
            LeadScorerFactory.create_signal_focused(),
            LeadScorerFactory.create_industry_focused()
        ]

        for scorer in scorers:
            total = (scorer.weights.company_size +
                    scorer.weights.industry +
                    scorer.weights.signals)
            assert abs(total - 1.0) < 0.01


class TestEdgeCases:
    """Test edge cases and error handling"""

    def setup_method(self):
        """Set up test fixtures"""
        self.scorer = LeadScorer()

    def test_score_boundaries(self):
        """Test that scores stay within 0-100 range"""
        # Test with maximum values
        lead_data = {
            "company_size": "5000+",
            "industry": "SaaS"
        }
        signals = SignalData(
            recent_funding=True,
            funding_amount_millions=1000,
            employee_growth_rate=2.0,
            demo_requested=True,
            tech_stack_modern=True,
            cloud_adoption=True,
            website_traffic_rank=1,
            content_downloads=100,
            competitor_customer=True,
            expansion_planned=True
        )
        result = self.scorer.calculate_score(lead_data, signals)
        assert result.score <= 100
        assert result.score >= 0

    def test_malformed_input_handling(self):
        """Test handling of malformed input data"""
        # Empty strings
        lead_data = {
            "company_size": "",
            "industry": ""
        }
        result = self.scorer.calculate_score(lead_data)
        assert result.score >= 0  # Should not crash

        # Whitespace only
        lead_data = {
            "company_size": "   ",
            "industry": "   "
        }
        result = self.scorer.calculate_score(lead_data)
        assert result.score >= 0

    def test_special_characters_in_industry(self):
        """Test handling of special characters in industry names"""
        industries = [
            "B2B/SaaS",
            "E-commerce & Retail",
            "Healthcare (Digital)",
            "Fin-Tech",
            "IoT/Hardware"
        ]

        for industry in industries:
            score = self.scorer.get_industry_score(industry)
            assert 0 <= score <= 100  # Should handle without crashing

    def test_unicode_handling(self):
        """Test handling of unicode characters"""
        lead_data = {
            "company_size": "50-200 employés",  # French
            "industry": "金融科技"  # Chinese for FinTech
        }
        result = self.scorer.calculate_score(lead_data)
        assert result.score >= 0  # Should not crash

    def test_very_large_numbers(self):
        """Test handling of very large numbers in signals"""
        signals = SignalData(
            funding_amount_millions=10000.0,  # $10B
            website_traffic_rank=1,
            content_downloads=1000000
        )
        score = self.scorer.analyze_signals(signals)
        assert 0 <= score <= 100

    def test_negative_values(self):
        """Test handling of negative values"""
        signals = SignalData(
            employee_growth_rate=-0.5,  # 50% decline
        )
        score = self.scorer.analyze_signals(signals)
        assert score < 50  # Should be low but valid

    def test_concurrent_scorer_instances(self):
        """Test that multiple scorer instances don't interfere"""
        scorer1 = LeadScorer()
        scorer2 = LeadScorerFactory.create_enterprise_focused()

        lead_data = {"company_size": "201-500", "industry": "SaaS"}

        result1 = scorer1.calculate_score(lead_data)
        result2 = scorer2.calculate_score(lead_data)

        # Different weights should produce different scores
        assert result1.score != result2.score
        assert result1.factors["company_size"] != result2.factors["company_size"]