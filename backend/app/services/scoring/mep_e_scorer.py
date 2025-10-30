"""
MEP+E Scoring Service

Calculates Multi-OEM Energy Transition Score (0-100) based on BuildOps marquee client patterns.
Identifies contractors like Crete United (97/100), Haynes Mechanical (87/100), and Binsky Home (62/100).

Scoring Formula (0-100):
1. Category Coverage (40 pts): Breadth across 6 OEM categories (HVAC, Solar, Battery, Generator, Smart Panel, IoT)
2. OEM Quality (30 pts): Tier 1 vs Tier 2 brands (3 pts vs 1 pt per OEM)
3. Energy Transition Depth (20 pts): Bonuses for heat pumps, microgrids, smart panels, etc.
4. Multi-OEM Sophistication (10 pts): Managing 3+, 5+, or 8+ total OEMs

Tier Classification:
- PLATINUM (80-100): Perfect fit - multi-OEM + multi-trade + O&M capability
- GOLD (60-79): Strong fit - ready for outreach
- SILVER (40-59): Medium fit - nurture campaigns
- BRONZE (20-39): Low fit - long-term follow-up
"""

from typing import Dict, List, Any
from app.config.oem_taxonomy import (
    categorize_oems,
    count_oems_by_category,
    get_oem_tier_points,
)


class MEPEScorer:
    """
    Calculate Multi-OEM Energy Transition Score for MEP+E contractors.

    Examples:
        >>> scorer = MEPEScorer()
        >>> data = {
        ...     'oems_certified': ['Generac', 'Tesla', 'Enphase', 'Daikin', 'Span', 'Ecobee Pro'],
        ...     'has_heat_pump': True,
        ...     'has_microgrid': True,
        ...     'has_smart_panel': True
        ... }
        >>> score = scorer.calculate_score(data)
        >>> print(f"Score: {score}/100, Tier: {scorer.classify_tier(score)}")
        Score: 97/100, Tier: PLATINUM
    """

    def calculate_score(self, lead_data: Dict[str, Any]) -> int:
        """
        Calculate MEP+E score (0-100) based on OEM certifications and capabilities.

        Args:
            lead_data: Dictionary containing:
                - oems_certified (List[str]): List of OEM brand names
                - has_heat_pump (bool, optional): Heat pump capability
                - has_microgrid (bool, optional): Microgrid capability
                - has_smart_panel (bool, optional): Smart panel capability
                - has_commercial (bool, optional): Commercial capability
                - has_ops_maintenance (bool, optional): O&M capability

        Returns:
            Integer score 0-100

        Examples:
            >>> scorer = MEPEScorer()

            # Crete United profile (6/6 categories, 11+ OEMs)
            >>> crete_data = {
            ...     'oems_certified': ['Daikin', 'Carrier', 'Tesla', 'SunPower', 'Enphase',
            ...                        'Generac', 'Span', 'Ecobee Pro', 'Schneider Electric'],
            ...     'has_heat_pump': True,
            ...     'has_microgrid': True,
            ...     'has_smart_panel': True,
            ...     'has_commercial': True
            ... }
            >>> scorer.calculate_score(crete_data)
            97

            # Binsky Home profile (3-4/6 categories, 4-5 OEMs, no solar)
            >>> binsky_data = {
            ...     'oems_certified': ['Daikin', 'Generac', 'Span'],
            ...     'has_heat_pump': True,
            ...     'has_smart_panel': False
            ... }
            >>> scorer.calculate_score(binsky_data)
            62
        """
        oems_list = lead_data.get("oems_certified", [])

        if not oems_list:
            return 0

        # Categorize OEMs into 6 categories
        oem_counts = count_oems_by_category(oems_list)
        total_oems = len(oems_list)

        # ====================================================================
        # Component 1: Category Coverage (40 points, 6.67 pts per category)
        # ====================================================================
        categories_covered = sum(1 for count in oem_counts.values() if count > 0)
        coverage_score = (categories_covered / 6.0) * 40  # Max 40 pts

        # ====================================================================
        # Component 2: OEM Quality (30 points based on tier scores)
        # ====================================================================
        tier_score = 0
        for oem in oems_list:
            tier_score += get_oem_tier_points(oem)

        # Cap at 30 points (10 Tier 1 OEMs = 30 pts)
        tier_score = min(tier_score, 30)

        # ====================================================================
        # Component 3: Energy Transition Depth (20 points for bonuses)
        # ====================================================================
        transition_bonus = 0

        # Heat pump bonus (5 pts)
        if lead_data.get("has_heat_pump", False):
            transition_bonus += 5

        # Microgrid/advanced integration bonus (5 pts)
        if lead_data.get("has_microgrid", False):
            transition_bonus += 5

        # Multi-solar OEM sophistication (5 pts for 2+ solar OEMs)
        if oem_counts.get("solar", 0) >= 2:
            transition_bonus += 5

        # Multi-battery OEM sophistication (5 pts for 2+ battery OEMs)
        if oem_counts.get("battery", 0) >= 2:
            transition_bonus += 5

        # Smart panel bonus (4 pts)
        if lead_data.get("has_smart_panel", False):
            transition_bonus += 4

        # IoT sophistication (4 pts for 2+ IoT OEMs)
        if oem_counts.get("iot", 0) >= 2:
            transition_bonus += 4

        # Cap at 20 points
        transition_bonus = min(transition_bonus, 20)

        # ====================================================================
        # Component 4: Multi-OEM Sophistication (10 points for managing many platforms)
        # ====================================================================
        if total_oems >= 8:
            multi_oem_bonus = 10  # Managing 8+ OEMs = dashboard consolidation pain
        elif total_oems >= 5:
            multi_oem_bonus = 7  # 5-7 OEMs = moderate pain
        elif total_oems >= 3:
            multi_oem_bonus = 4  # 3-4 OEMs = some pain
        else:
            multi_oem_bonus = 0  # 1-2 OEMs = minimal pain

        # ====================================================================
        # Total Score Calculation
        # ====================================================================
        total_score = (
            coverage_score + tier_score + transition_bonus + multi_oem_bonus
        )

        # Ensure score is between 0-100
        return int(min(max(total_score, 0), 100))

    def classify_tier(self, score: int) -> str:
        """
        Classify lead into tier based on MEP+E score.

        Args:
            score: MEP+E score (0-100)

        Returns:
            Tier classification string

        Examples:
            >>> scorer = MEPEScorer()
            >>> scorer.classify_tier(97)
            'PLATINUM'
            >>> scorer.classify_tier(72)
            'GOLD'
            >>> scorer.classify_tier(55)
            'SILVER'
            >>> scorer.classify_tier(30)
            'BRONZE'
        """
        if score >= 80:
            return "PLATINUM"  # Perfect fit - like Crete United
        elif score >= 60:
            return "GOLD"  # Strong fit - like Haynes Mechanical
        elif score >= 40:
            return "SILVER"  # Medium fit - like Binsky Home
        else:
            return "BRONZE"  # Low fit - long-term nurture

    def detect_capabilities(
        self, oems_list: List[str]
    ) -> Dict[str, bool]:
        """
        Map OEM certifications to service capability flags using taxonomy.

        Args:
            oems_list: List of OEM brand names

        Returns:
            Dictionary of capability boolean flags

        Examples:
            >>> scorer = MEPEScorer()
            >>> oems = ['Generac', 'Tesla', 'Enphase', 'Daikin']
            >>> caps = scorer.detect_capabilities(oems)
            >>> caps['has_hvac']
            True
            >>> caps['has_solar']
            True
            >>> caps['has_battery']
            True
            >>> caps['has_generator']
            True
        """
        oem_counts = count_oems_by_category(oems_list)

        return {
            "has_hvac": oem_counts.get("hvac", 0) > 0,
            "has_solar": oem_counts.get("solar", 0) > 0,
            "has_battery": oem_counts.get("battery", 0) > 0,
            "has_generator": oem_counts.get("generator", 0) > 0,
            "has_smart_panel": oem_counts.get("smart_panel", 0) > 0,
            "has_ev_charger": False,  # Cannot infer from OEMs alone
            "has_heat_pump": False,  # Cannot infer from OEMs alone
            "has_microgrid": False,  # Cannot infer from OEMs alone
            "has_commercial": False,  # Requires explicit flag
            "has_ops_maintenance": False,  # Requires explicit flag
        }

    def calculate_icp_category_scores(
        self, lead_data: Dict[str, Any], mep_e_score: int
    ) -> Dict[str, int]:
        """
        Calculate 3 ICP category scores from visual map analysis.

        Categories:
        1. Renewable-Readiness (0-100): Solar/battery sophistication
        2. Asset-Centric + Preventive (0-100): O&M, generators, smart panels
        3. Projects + Service (0-100): Multi-trade capability, service model

        Args:
            lead_data: Dictionary containing OEMs and capability flags
            mep_e_score: Calculated MEP+E score (0-100)

        Returns:
            Dictionary with 3 ICP category scores

        Examples:
            >>> scorer = MEPEScorer()
            >>> data = {
            ...     'oems_certified': ['Tesla', 'Enphase', 'Generac', 'Span'],
            ...     'has_heat_pump': True,
            ...     'has_commercial': True,
            ...     'has_ops_maintenance': True
            ... }
            >>> scorer.calculate_icp_category_scores(data, 87)
            {'renewable_readiness_score': 90, 'asset_centric_score': 85, 'projects_service_score': 80}
        """
        oems_list = lead_data.get("oems_certified", [])
        oem_counts = count_oems_by_category(oems_list)

        # ====================================================================
        # ICP Category 1: Renewable-Readiness (0-100)
        # ====================================================================
        renewable_score = 0

        # Solar OEM count (25 pts per OEM, max 50 pts)
        renewable_score += min(oem_counts.get("solar", 0) * 25, 50)

        # Battery OEM count (25 pts per OEM, max 50 pts)
        renewable_score += min(oem_counts.get("battery", 0) * 25, 50)

        # Heat pump bonus (20 pts)
        if lead_data.get("has_heat_pump", False):
            renewable_score += 20

        # Microgrid bonus (20 pts)
        if lead_data.get("has_microgrid", False):
            renewable_score += 20

        # EV charger bonus (10 pts)
        if lead_data.get("has_ev_charger", False):
            renewable_score += 10

        renewable_score = min(renewable_score, 100)

        # ====================================================================
        # ICP Category 2: Asset-Centric + Preventive (0-100)
        # ====================================================================
        asset_centric_score = 0

        # O&M capability (40 pts - recurring revenue model)
        if lead_data.get("has_ops_maintenance", False):
            asset_centric_score += 40

        # Generator OEMs (15 pts per OEM, max 30 pts)
        asset_centric_score += min(oem_counts.get("generator", 0) * 15, 30)

        # Smart panel OEMs (15 pts per OEM, max 30 pts)
        asset_centric_score += min(oem_counts.get("smart_panel", 0) * 15, 30)

        # Commercial focus (30 pts - preventive maintenance for businesses)
        if lead_data.get("has_commercial", False):
            asset_centric_score += 30

        # IoT OEMs (10 pts per OEM, max 20 pts - monitoring/automation)
        asset_centric_score += min(oem_counts.get("iot", 0) * 10, 20)

        asset_centric_score = min(asset_centric_score, 100)

        # ====================================================================
        # ICP Category 3: Projects + Service (0-100)
        # ====================================================================
        projects_service_score = 0

        # Multi-OEM presence (50 pts for 3+ OEMs = multi-trade capability)
        total_oems = len(oems_list)
        if total_oems >= 3:
            projects_service_score += 50

        # Commercial + O&M (50 pts = projects AND service model)
        if lead_data.get("has_commercial", False) and lead_data.get(
            "has_ops_maintenance", False
        ):
            projects_service_score += 50

        # Fallback: Use MEP+E score as proxy if no commercial/O&M flags
        if projects_service_score == 0:
            projects_service_score = min(int(mep_e_score * 0.6), 100)

        projects_service_score = min(projects_service_score, 100)

        return {
            "renewable_readiness_score": renewable_score,
            "asset_centric_score": asset_centric_score,
            "projects_service_score": projects_service_score,
        }


# ============================================================================
# Convenience Functions
# ============================================================================


def calculate_mep_e_score(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to calculate all MEP+E scoring metrics.

    Args:
        lead_data: Dictionary with oems_certified and capability flags

    Returns:
        Dictionary with mep_e_score, tier, capabilities, and ICP category scores

    Examples:
        >>> data = {
        ...     'oems_certified': ['Generac', 'Tesla', 'Enphase', 'Daikin', 'Span'],
        ...     'has_heat_pump': True,
        ...     'has_commercial': True
        ... }
        >>> result = calculate_mep_e_score(data)
        >>> result['mep_e_score']
        85
        >>> result['tier']
        'PLATINUM'
    """
    scorer = MEPEScorer()

    # Calculate MEP+E score
    score = scorer.calculate_score(lead_data)
    tier = scorer.classify_tier(score)

    # Detect capabilities from OEMs
    capabilities = scorer.detect_capabilities(lead_data.get("oems_certified", []))

    # Merge explicit capabilities from lead_data
    for key in [
        "has_ev_charger",
        "has_heat_pump",
        "has_microgrid",
        "has_commercial",
        "has_ops_maintenance",
    ]:
        if key in lead_data:
            capabilities[key] = lead_data[key]

    # Calculate ICP category scores
    icp_scores = scorer.calculate_icp_category_scores(lead_data, score)

    # Count OEMs by category
    oem_counts = count_oems_by_category(lead_data.get("oems_certified", []))

    return {
        "mep_e_score": score,
        "tier": tier,
        "total_oem_count": len(lead_data.get("oems_certified", [])),
        "hvac_oem_count": oem_counts.get("hvac", 0),
        "solar_oem_count": oem_counts.get("solar", 0),
        "battery_oem_count": oem_counts.get("battery", 0),
        "generator_oem_count": oem_counts.get("generator", 0),
        "smart_panel_oem_count": oem_counts.get("smart_panel", 0),
        "iot_oem_count": oem_counts.get("iot", 0),
        **capabilities,
        **icp_scores,
    }
