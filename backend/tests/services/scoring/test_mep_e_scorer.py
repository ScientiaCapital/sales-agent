"""
Unit tests for MEPEScorer service

Tests scoring algorithm against BuildOps marquee client patterns:
- Crete United: 97/100 (6/6 categories, 11+ OEMs, full energy transition)
- Haynes Mechanical: 87/100 (5/6 categories, 6-7 OEMs, smart buildings)
- Binsky Home: 62/100 (3-4/6 categories, 4-5 OEMs, no solar yet)
"""

import pytest
from app.services.scoring.mep_e_scorer import MEPEScorer, calculate_mep_e_score


class TestMEPEScorer:
    """Test suite for MEPEScorer service"""

    @pytest.fixture
    def scorer(self):
        """Create MEPEScorer instance for tests"""
        return MEPEScorer()

    # =========================================================================
    # BuildOps Client Pattern Tests
    # =========================================================================

    def test_crete_united_profile_platinum_tier(self, scorer):
        """
        Test Crete United profile: 6/6 categories, 10+ OEMs, full energy transition
        Expected: 95-100/100 score, PLATINUM tier
        """
        crete_data = {
            "oems_certified": [
                # HVAC (2 OEMs)
                "Daikin",
                "Carrier",
                # Solar (2 OEMs)
                "Tesla",
                "SunPower",
                # Battery (2 OEMs)
                "Enphase",
                "LG Chem",
                # Generator (1 OEM)
                "Generac",
                # Smart Panel (2 OEMs)
                "Span",
                "Schneider Electric",
                # IoT (2 OEMs)
                "Ecobee Pro",
                "Control4",
            ],
            "has_heat_pump": True,
            "has_microgrid": True,
            "has_smart_panel": True,
            "has_commercial": True,
            "has_ops_maintenance": True,
        }

        score = scorer.calculate_score(crete_data)
        tier = scorer.classify_tier(score)

        assert 95 <= score <= 100, f"Expected 95-100, got {score}"
        assert tier == "PLATINUM"

    def test_haynes_mechanical_profile_gold_tier(self, scorer):
        """
        Test Haynes Mechanical profile: 5/6 categories, 6-7 OEMs, smart buildings
        Expected: 85-90/100 score, PLATINUM tier
        """
        haynes_data = {
            "oems_certified": [
                # HVAC (2 OEMs)
                "Trane",
                "Lennox",
                # Solar (1 OEM)
                "SolarEdge",
                # Battery (1 OEM)
                "Generac PWRcell",
                # Generator (1 OEM)
                "Kohler",
                # Smart Panel (1 OEM)
                "Eaton",
                # IoT (1 OEM)
                "Honeywell Prestige",
            ],
            "has_heat_pump": False,
            "has_microgrid": False,
            "has_smart_panel": True,
            "has_commercial": True,
            "has_ops_maintenance": True,
        }

        score = scorer.calculate_score(haynes_data)
        tier = scorer.classify_tier(score)

        assert 85 <= score <= 90, f"Expected 85-90, got {score}"
        assert tier == "PLATINUM"

    def test_binsky_home_profile_gold_tier(self, scorer):
        """
        Test Binsky Home profile: 3-4/6 categories, 4-5 OEMs, no solar
        Expected: 60-65/100 score, GOLD tier
        """
        binsky_data = {
            "oems_certified": [
                # HVAC (2 OEMs)
                "Daikin",
                "Rheem",
                # No solar (explicitly noted by user)
                # Generator (1 OEM)
                "Generac",
                # Smart Panel (1 OEM)
                "Span",
            ],
            "has_heat_pump": True,
            "has_ev_charger": True,
            "has_smart_panel": True,
            "has_commercial": False,
            "has_ops_maintenance": False,
        }

        score = scorer.calculate_score(binsky_data)
        tier = scorer.classify_tier(score)

        assert 60 <= score <= 65, f"Expected 60-65, got {score}"
        assert tier == "GOLD"

    def test_qmerit_profile_high_renewable_readiness(self, scorer):
        """
        Test Qmerit profile: EV specialist network (E+E), high renewable-readiness
        Expected: GOLD tier, very high renewable_readiness_score
        """
        qmerit_data = {
            "oems_certified": [
                # Battery (1 OEM)
                "Tesla",
                # Smart Panel (1 OEM)
                "Span",
            ],
            "has_ev_charger": True,
            "has_smart_panel": True,
            "has_commercial": True,
        }

        score = scorer.calculate_score(qmerit_data)
        icp_scores = scorer.calculate_icp_category_scores(qmerit_data, score)

        assert score >= 60, f"Expected >= 60, got {score}"
        assert (
            icp_scores["renewable_readiness_score"] >= 70
        ), "Expected high renewable-readiness for EV specialist"

    # =========================================================================
    # Tier Classification Tests
    # =========================================================================

    def test_classify_tier_platinum(self, scorer):
        """Test PLATINUM tier classification (80-100)"""
        assert scorer.classify_tier(100) == "PLATINUM"
        assert scorer.classify_tier(90) == "PLATINUM"
        assert scorer.classify_tier(80) == "PLATINUM"

    def test_classify_tier_gold(self, scorer):
        """Test GOLD tier classification (60-79)"""
        assert scorer.classify_tier(79) == "GOLD"
        assert scorer.classify_tier(70) == "GOLD"
        assert scorer.classify_tier(60) == "GOLD"

    def test_classify_tier_silver(self, scorer):
        """Test SILVER tier classification (40-59)"""
        assert scorer.classify_tier(59) == "SILVER"
        assert scorer.classify_tier(50) == "SILVER"
        assert scorer.classify_tier(40) == "SILVER"

    def test_classify_tier_bronze(self, scorer):
        """Test BRONZE tier classification (0-39)"""
        assert scorer.classify_tier(39) == "BRONZE"
        assert scorer.classify_tier(20) == "BRONZE"
        assert scorer.classify_tier(0) == "BRONZE"

    # =========================================================================
    # Capability Detection Tests
    # =========================================================================

    def test_detect_capabilities_all_categories(self, scorer):
        """Test capability detection for all 6 OEM categories"""
        oems = [
            "Daikin",  # HVAC
            "Tesla",  # Solar + Battery
            "Generac",  # Generator
            "Span",  # Smart Panel
            "Ecobee Pro",  # IoT
        ]

        caps = scorer.detect_capabilities(oems)

        assert caps["has_hvac"] is True
        assert caps["has_solar"] is True
        assert caps["has_battery"] is True
        assert caps["has_generator"] is True
        assert caps["has_smart_panel"] is True
        # Cannot infer these from OEMs alone
        assert caps["has_ev_charger"] is False
        assert caps["has_heat_pump"] is False
        assert caps["has_microgrid"] is False

    def test_detect_capabilities_empty_list(self, scorer):
        """Test capability detection with no OEMs"""
        caps = scorer.detect_capabilities([])

        assert all(cap is False for cap in caps.values())

    # =========================================================================
    # ICP Category Scoring Tests
    # =========================================================================

    def test_icp_renewable_readiness_high_score(self, scorer):
        """Test renewable-readiness scoring for solar/battery contractor"""
        data = {
            "oems_certified": ["Tesla", "SunPower", "Enphase", "LG Chem"],
            "has_heat_pump": True,
            "has_microgrid": True,
            "has_ev_charger": True,
        }

        icp_scores = scorer.calculate_icp_category_scores(data, 90)

        # 50 (solar) + 50 (battery) + 20 (heat pump) + 20 (microgrid) + 10 (EV) = 150 → cap at 100
        assert icp_scores["renewable_readiness_score"] == 100

    def test_icp_asset_centric_high_score(self, scorer):
        """Test asset-centric scoring for O&M-focused contractor"""
        data = {
            "oems_certified": ["Generac", "Kohler", "Span", "Ecobee Pro"],
            "has_ops_maintenance": True,
            "has_commercial": True,
        }

        icp_scores = scorer.calculate_icp_category_scores(data, 80)

        # 40 (O&M) + 30 (generators) + 15 (smart panel) + 30 (commercial) + 10 (IoT) = 125 → cap at 100
        assert icp_scores["asset_centric_score"] == 100

    def test_icp_projects_service_high_score(self, scorer):
        """Test projects+service scoring for multi-OEM contractor with O&M"""
        data = {
            "oems_certified": ["Generac", "Tesla", "Enphase", "Daikin"],
            "has_commercial": True,
            "has_ops_maintenance": True,
        }

        icp_scores = scorer.calculate_icp_category_scores(data, 85)

        # 50 (multi-OEM) + 50 (commercial + O&M) = 100
        assert icp_scores["projects_service_score"] == 100

    # =========================================================================
    # Edge Case Tests
    # =========================================================================

    def test_calculate_score_no_oems(self, scorer):
        """Test score calculation with no OEM certifications"""
        data = {"oems_certified": []}

        score = scorer.calculate_score(data)

        assert score == 0

    def test_calculate_score_single_category(self, scorer):
        """Test score with only one OEM category"""
        data = {
            "oems_certified": ["Generac", "Kohler"],  # Only generators
        }

        score = scorer.calculate_score(data)

        # 1/6 categories = 6.67 pts
        # 2 Tier1 OEMs = 6 pts
        # No bonuses = 0 pts
        # 2 OEMs = 0 bonus pts
        # Total: ~13 pts
        assert 10 <= score <= 20

    def test_calculate_score_multi_oem_sophistication_bonus(self, scorer):
        """Test multi-OEM sophistication bonus (8+ OEMs)"""
        data = {
            "oems_certified": [
                "Daikin",
                "Carrier",
                "Tesla",
                "SunPower",
                "Enphase",
                "Generac",
                "Span",
                "Ecobee Pro",
                "Control4",
            ],  # 9 OEMs
        }

        score = scorer.calculate_score(data)

        # Should include 10 pts for 8+ OEM sophistication
        assert score >= 50

    # =========================================================================
    # Convenience Function Tests
    # =========================================================================

    def test_calculate_mep_e_score_complete_output(self):
        """Test convenience function returns all required fields"""
        data = {
            "oems_certified": ["Generac", "Tesla", "Enphase", "Daikin"],
            "has_commercial": True,
        }

        result = calculate_mep_e_score(data)

        # Check all required fields are present
        assert "mep_e_score" in result
        assert "tier" in result
        assert "total_oem_count" in result
        assert "hvac_oem_count" in result
        assert "solar_oem_count" in result
        assert "battery_oem_count" in result
        assert "generator_oem_count" in result
        assert "smart_panel_oem_count" in result
        assert "iot_oem_count" in result
        assert "has_hvac" in result
        assert "has_solar" in result
        assert "has_battery" in result
        assert "has_generator" in result
        assert "renewable_readiness_score" in result
        assert "asset_centric_score" in result
        assert "projects_service_score" in result

    def test_calculate_mep_e_score_matches_individual_methods(self, scorer):
        """Test convenience function produces same results as individual method calls"""
        data = {
            "oems_certified": ["Generac", "Tesla", "Daikin"],
            "has_heat_pump": True,
        }

        # Calculate using convenience function
        result = calculate_mep_e_score(data)

        # Calculate using individual methods
        score = scorer.calculate_score(data)
        tier = scorer.classify_tier(score)
        icp_scores = scorer.calculate_icp_category_scores(data, score)

        assert result["mep_e_score"] == score
        assert result["tier"] == tier
        assert (
            result["renewable_readiness_score"]
            == icp_scores["renewable_readiness_score"]
        )
        assert (
            result["asset_centric_score"] == icp_scores["asset_centric_score"]
        )
        assert (
            result["projects_service_score"]
            == icp_scores["projects_service_score"]
        )


# =============================================================================
# Integration Tests (Validate Against dealer-scraper-mvp Patterns)
# =============================================================================


class TestMEPEScorerIntegration:
    """Integration tests validating against dealer-scraper-mvp patterns"""

    def test_multi_oem_deduplication_pattern(self):
        """
        Test scoring for contractor found in multiple OEM networks
        (matching dealer-scraper-mvp 97.3% deduplication accuracy)
        """
        # Contractor certified with Generac, Tesla, and Enphase
        # (found in 3 separate manufacturer networks)
        data = {
            "oems_certified": ["Generac", "Tesla Powerwall", "Enphase"],
            "has_commercial": True,
            "has_ops_maintenance": True,
        }

        scorer = MEPEScorer()
        score = scorer.calculate_score(data)

        # Multi-OEM sophistication = high pain point = higher score
        assert score >= 70, "Multi-OEM contractors should score >= 70"

    def test_enphase_platinum_tier_scoring(self):
        """
        Test scoring for Enphase Platinum installer
        (highest tier from manufacturer network scraping)
        """
        data = {
            "oems_certified": ["Enphase"],
            "has_solar": True,
            "has_battery": True,
            "has_ops_maintenance": True,
        }

        scorer = MEPEScorer()
        score = scorer.calculate_score(data)
        icp_scores = scorer.calculate_icp_category_scores(data, score)

        # Enphase Platinum = premium tier = high renewable-readiness
        assert (
            icp_scores["renewable_readiness_score"] >= 50
        ), "Enphase Platinum should have high renewable-readiness"

    def test_generator_only_contractor_low_score(self):
        """
        Test scoring for generator-only contractor
        (from Generac/Briggs network scraping, no energy transition)
        """
        data = {
            "oems_certified": ["Generac", "Kohler"],
            "has_generator": True,
        }

        scorer = MEPEScorer()
        score = scorer.calculate_score(data)

        # Generator-only = low energy transition = lower score
        assert score < 40, "Generator-only contractors should score < 40"
