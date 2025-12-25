"""
Close CRM Campaign Audit - Report Generation Tests

Tests report generation functionality for:
- CSV export of NEW leads
- Campaign audit reports
- JSON/HTML export formats
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from app.services.close_audit_service import CloseAuditService


@pytest.mark.asyncio
async def test_generate_new_leads_report_csv():
    """Test generating CSV report of NEW leads only"""
    service = CloseAuditService()

    # Use temp file for output
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        output_path = f.name

    try:
        report_path = await service.generate_new_leads_report(
            output_path=output_path,
            icp_tier="PLATINUM"
        )

        # Verify file was created
        assert os.path.exists(report_path), f"Report file should exist at {report_path}"
        assert report_path == output_path, "Should return the output path"

        # Verify CSV structure
        import pandas as pd
        df = pd.read_csv(report_path)

        # Required columns
        assert "company_id" in df.columns, "Should have company_id column"
        assert "company_name" in df.columns, "Should have company_name column"
        assert "domain" in df.columns, "Should have domain column"
        assert "close_lead_id" in df.columns, "Should have close_lead_id column"
        assert "icp_tier" in df.columns, "Should have icp_tier column"

        # All should be NEW (close_lead_id = NULL)
        assert df["close_lead_id"].isna().all(), \
            "All leads in report should have NULL close_lead_id (NEW)"

        # All should be PLATINUM
        assert (df["icp_tier"] == "PLATINUM").all(), \
            "All leads should be PLATINUM tier"

    finally:
        # Cleanup
        if os.path.exists(output_path):
            os.remove(output_path)


@pytest.mark.asyncio
async def test_generate_campaign_audit_report():
    """Test generating comprehensive campaign audit"""
    service = CloseAuditService()

    sequence_ids = [
        "seq_469XPP98mPXSR2wh5cX9y6",  # ICP-Energy-Multitrade
        "seq_0FHFD0OQtDAOS8x40MIANW"   # Solar-Pivot-2026
    ]

    report = await service.generate_campaign_audit(sequence_ids=sequence_ids)

    # Verify report structure
    assert isinstance(report, dict), "Should return dict report"

    # Required fields
    assert "total_contacts_enrolled" in report, "Should have total_contacts_enrolled"
    assert "unique_companies" in report, "Should have unique_companies"
    assert "sequences" in report, "Should have sequences breakdown"

    # Verify counts
    assert isinstance(report["total_contacts_enrolled"], int), \
        "total_contacts_enrolled should be int"
    assert report["total_contacts_enrolled"] > 0, \
        "Should have enrolled contacts"

    assert isinstance(report["unique_companies"], int), \
        "unique_companies should be int"
    assert report["unique_companies"] > 0, \
        "Should have unique companies"

    # Verify sequences breakdown
    assert isinstance(report["sequences"], list), "sequences should be list"
    assert len(report["sequences"]) == 2, "Should have 2 sequences"


@pytest.mark.asyncio
async def test_generate_new_leads_report_all_tiers():
    """Test generating NEW leads report for all tiers"""
    service = CloseAuditService()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        output_path = f.name

    try:
        report_path = await service.generate_new_leads_report(
            output_path=output_path,
            icp_tier=None  # All tiers
        )

        assert os.path.exists(report_path), "Report file should exist"

        # Verify CSV structure
        import pandas as pd
        df = pd.read_csv(report_path)

        # All should be NEW (close_lead_id = NULL)
        assert df["close_lead_id"].isna().all(), \
            "All leads should be NEW (NULL close_lead_id)"

        # Should have mix of tiers
        tiers = df["icp_tier"].unique()
        assert len(tiers) > 1, "Should have multiple tier values"

    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


@pytest.mark.asyncio
async def test_generate_report_json_format():
    """Test generating report in JSON format"""
    service = CloseAuditService()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        output_path = f.name

    try:
        report_path = await service.generate_new_leads_report(
            output_path=output_path,
            icp_tier="GOLD",
            format="json"
        )

        assert os.path.exists(report_path), "JSON report should exist"

        # Verify JSON structure
        with open(report_path, "r") as f:
            data = json.load(f)

        assert isinstance(data, dict) or isinstance(data, list), \
            "JSON should be dict or list"

        if isinstance(data, list):
            # List of leads
            assert len(data) > 0, "Should have at least one lead"
            assert "company_id" in data[0], "Each lead should have company_id"
            assert "company_name" in data[0], "Each lead should have company_name"

    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


@pytest.mark.asyncio
async def test_campaign_audit_icp_breakdown():
    """Test that campaign audit includes ICP tier breakdown"""
    service = CloseAuditService()

    sequence_ids = ["seq_469XPP98mPXSR2wh5cX9y6"]

    report = await service.generate_campaign_audit(sequence_ids=sequence_ids)

    # Should have ICP breakdown
    assert "icp_breakdown" in report or "tier_breakdown" in report, \
        "Should include ICP tier breakdown"

    breakdown_key = "icp_breakdown" if "icp_breakdown" in report else "tier_breakdown"
    breakdown = report[breakdown_key]

    assert isinstance(breakdown, dict), "Breakdown should be dict"

    # Should have tier counts
    valid_tiers = {"PLATINUM", "GOLD", "SILVER", "BRONZE"}
    for tier, count in breakdown.items():
        assert tier in valid_tiers, f"Invalid tier: {tier}"
        assert isinstance(count, int), f"Count should be int, got {type(count)}"
        assert count >= 0, f"Count should be non-negative, got {count}"


@pytest.mark.asyncio
async def test_campaign_audit_industry_breakdown():
    """Test that campaign audit includes industry breakdown"""
    service = CloseAuditService()

    sequence_ids = ["seq_469XPP98mPXSR2wh5cX9y6"]

    report = await service.generate_campaign_audit(sequence_ids=sequence_ids)

    # Should have industry breakdown
    assert "industry_breakdown" in report, "Should include industry breakdown"

    breakdown = report["industry_breakdown"]
    assert isinstance(breakdown, dict), "Breakdown should be dict"

    # Should have Energy and/or MEP
    assert "Energy" in breakdown or "MEP" in breakdown, \
        "Should have Energy or MEP companies"


@pytest.mark.asyncio
async def test_campaign_audit_atl_btl_breakdown():
    """Test that campaign audit includes ATL vs BTL breakdown"""
    service = CloseAuditService()

    sequence_ids = ["seq_469XPP98mPXSR2wh5cX9y6"]

    report = await service.generate_campaign_audit(sequence_ids=sequence_ids)

    # Should have contact level breakdown
    assert "contact_breakdown" in report or "atl_btl_breakdown" in report, \
        "Should include ATL/BTL breakdown"

    breakdown_key = "contact_breakdown" if "contact_breakdown" in report else "atl_btl_breakdown"
    breakdown = report[breakdown_key]

    assert isinstance(breakdown, dict), "Breakdown should be dict"

    # Should have ATL and BTL counts
    assert "atl_count" in breakdown or "ATL" in breakdown, "Should have ATL count"
    assert "btl_count" in breakdown or "BTL" in breakdown, "Should have BTL count"


@pytest.mark.asyncio
async def test_report_empty_results():
    """Test report generation with empty results"""
    service = CloseAuditService()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        output_path = f.name

    try:
        # Request tier that might not exist
        report_path = await service.generate_new_leads_report(
            output_path=output_path,
            icp_tier="UNKNOWN_TIER"
        )

        assert os.path.exists(report_path), "Should create file even if empty"

        # Verify CSV has headers but no data
        import pandas as pd
        df = pd.read_csv(report_path)

        assert len(df.columns) > 0, "Should have column headers"
        # Data might be empty, that's okay

    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


@pytest.mark.asyncio
async def test_report_invalid_path():
    """Test error handling for invalid output paths"""
    service = CloseAuditService()

    invalid_path = "/nonexistent/directory/report.csv"

    with pytest.raises(Exception):
        await service.generate_new_leads_report(
            output_path=invalid_path,
            icp_tier="PLATINUM"
        )


@pytest.mark.asyncio
async def test_campaign_audit_performance():
    """Test that campaign audit completes in reasonable time"""
    service = CloseAuditService()
    import time

    sequence_ids = [
        "seq_469XPP98mPXSR2wh5cX9y6",
        "seq_0FHFD0OQtDAOS8x40MIANW"
    ]

    start = time.time()
    report = await service.generate_campaign_audit(sequence_ids=sequence_ids)
    elapsed = time.time() - start

    # Should complete in under 30 seconds
    assert elapsed < 30, f"Audit took too long: {elapsed}s (should be < 30s)"

    assert report is not None, "Should return report"


@pytest.mark.asyncio
async def test_new_leads_report_includes_metadata():
    """Test that NEW leads report includes useful metadata"""
    service = CloseAuditService()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        output_path = f.name

    try:
        report_path = await service.generate_new_leads_report(
            output_path=output_path,
            icp_tier="PLATINUM"
        )

        import pandas as pd
        df = pd.read_csv(report_path)

        # Should include useful metadata columns
        expected_columns = [
            "company_id",
            "company_name",
            "domain",
            "icp_tier",
            "contact_count"
        ]

        for col in expected_columns:
            assert col in df.columns, f"Should include {col} column"

    finally:
        if os.path.exists(output_path):
            os.remove(output_path)
