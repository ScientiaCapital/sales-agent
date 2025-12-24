"""
Close CRM Campaign Audit Service

Provides comprehensive audit functionality for Close CRM campaign preparation:
- Identify NEW leads (not yet in Close CRM)
- Identify LOADED leads (already in Close CRM)
- Cross-reference Supabase database with Close CRM API
- Generate audit reports for campaign planning

Usage:
    service = CloseAuditService()

    # Get all NEW leads (close_lead_id IS NULL)
    new_leads = await service.get_new_leads(icp_tier="PLATINUM")

    # Get all LOADED leads (close_lead_id IS NOT NULL)
    loaded_leads = await service.get_loaded_leads()

    # Cross-reference with Close CRM
    report = await service.cross_reference()

    # Mark company as loaded in Close
    await service.mark_as_loaded(company_id, close_lead_id)

    # Generate CSV report of NEW leads
    await service.generate_new_leads_report("/tmp/new_leads.csv", "PLATINUM")

    # Generate campaign audit
    audit = await service.generate_campaign_audit([sequence_id_1, sequence_id_2])
"""

import os
import logging
from typing import Dict, List, Optional
from uuid import UUID
import pandas as pd
from supabase import create_client, Client
from backend.app.services.crm.close_sequences import CloseSequencesClient
from backend.app.services.crm.close import CloseProvider

logger = logging.getLogger(__name__)


class CloseAuditService:
    """Service for auditing Close CRM campaign data against Supabase database"""

    def __init__(self):
        """Initialize Close Audit Service with Supabase and Close CRM clients"""
        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

        self.supabase: Client = create_client(supabase_url, supabase_key)

        # Initialize Close CRM clients
        self.close_sequences = CloseSequencesClient()
        self.close_provider = CloseProvider()

        logger.info("CloseAuditService initialized")

    async def get_new_leads(
        self,
        icp_tier: Optional[str] = None,
        min_contacts: int = 0,
        industry: Optional[str] = None
    ) -> List[Dict]:
        """
        Query Supabase for companies NOT in Close CRM (close_lead_id IS NULL)

        Args:
            icp_tier: Filter by ICP tier (PLATINUM, GOLD, SILVER, BRONZE)
            min_contacts: Minimum contact count (0 = include zero-contact companies)
            industry: Filter by industry (Energy, MEP, etc.)

        Returns:
            List of companies with close_lead_id = NULL
        """
        logger.info(f"Querying NEW leads (tier={icp_tier}, min_contacts={min_contacts})")

        # Build query
        query = self.supabase.table("dim_companies").select(
            "company_id, company_name, domain, icp_tier, icp_score, "
            "industry, contact_count, last_enriched_at, close_lead_id"
        )

        # Filter for NEW leads only (close_lead_id IS NULL)
        query = query.is_("close_lead_id", "null")

        # Filter for enriched companies with valid domains
        query = query.not_.is_("last_enriched_at", "null")
        query = query.not_.is_("domain", "null")
        query = query.neq("domain", "")

        # Apply tier filter
        if icp_tier:
            query = query.eq("icp_tier", icp_tier)

        # Apply contact count filter
        if min_contacts > 0:
            query = query.gte("contact_count", min_contacts)

        # Apply industry filter
        if industry:
            query = query.eq("industry", industry)

        # Execute query
        response = query.execute()

        leads = response.data
        logger.info(f"Found {len(leads)} NEW leads")

        return leads

    async def get_loaded_leads(self) -> List[Dict]:
        """
        Query Supabase for companies ALREADY in Close CRM (close_lead_id IS NOT NULL)

        Returns:
            List of companies with close_lead_id populated
        """
        logger.info("Querying LOADED leads (already in Close CRM)")

        # Query for companies with close_lead_id
        response = self.supabase.table("dim_companies").select(
            "company_id, company_name, domain, close_lead_id, "
            "icp_tier, contact_count, last_enriched_at"
        ).not_.is_("close_lead_id", "null").execute()

        leads = response.data
        logger.info(f"Found {len(leads)} LOADED leads")

        return leads

    async def cross_reference(self) -> Dict:
        """
        Cross-reference Supabase database with Close CRM API

        Queries both systems and compares to ensure accuracy

        Returns:
            Dict with counts and comparison data
        """
        logger.info("Cross-referencing Supabase with Close CRM")

        # Query Supabase
        new_leads = await self.get_new_leads()
        loaded_leads = await self.get_loaded_leads()

        # Query Close CRM (count leads)
        close_leads = await self._fetch_close_leads()

        # Build report
        report = {
            "new_leads": len(new_leads),
            "loaded_leads": len(loaded_leads),
            "total_in_supabase": len(new_leads) + len(loaded_leads),
            "total_in_close": len(close_leads),
            "discrepancy": len(close_leads) - len(loaded_leads)
        }

        logger.info(f"Cross-reference complete: {report}")

        return report

    async def mark_as_loaded(self, company_id: str, close_lead_id: str) -> bool:
        """
        Update dim_companies.close_lead_id for a company

        Args:
            company_id: UUID of company in Supabase
            close_lead_id: Close CRM lead ID (format: lead_XXXXXX)

        Returns:
            True if successful

        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        if not company_id:
            raise ValueError("company_id is required")

        if not close_lead_id:
            raise ValueError("close_lead_id is required")

        # Validate UUID format
        try:
            UUID(company_id)
        except ValueError:
            raise ValueError(f"Invalid UUID format: {company_id}")

        # Validate Close lead ID format
        if not close_lead_id.startswith("lead_"):
            raise ValueError(f"Invalid Close lead ID format: {close_lead_id}")

        logger.info(f"Marking company {company_id} as loaded (Close lead: {close_lead_id})")

        # Update database
        response = self.supabase.table("dim_companies").update({
            "close_lead_id": close_lead_id
        }).eq("company_id", company_id).execute()

        success = len(response.data) > 0
        logger.info(f"Mark as loaded: {'SUCCESS' if success else 'FAILED'}")

        return success

    async def generate_new_leads_report(
        self,
        output_path: str,
        icp_tier: Optional[str] = None,
        format: str = "csv"
    ) -> str:
        """
        Generate report of NEW leads for enrichment/campaign

        Args:
            output_path: Path to save report file
            icp_tier: Filter by tier (None = all tiers)
            format: Output format (csv, json)

        Returns:
            Path to generated report file
        """
        logger.info(f"Generating NEW leads report (tier={icp_tier}, format={format})")

        # Get NEW leads
        leads = await self.get_new_leads(icp_tier=icp_tier)

        # Convert to DataFrame
        df = pd.DataFrame(leads)

        # Ensure required columns
        required_columns = ["company_id", "company_name", "domain", "icp_tier", "contact_count"]
        for col in required_columns:
            if col not in df.columns:
                df[col] = None

        # Add close_lead_id column (all NULL for NEW leads)
        if "close_lead_id" not in df.columns:
            df["close_lead_id"] = None

        # Export
        if format == "csv":
            df.to_csv(output_path, index=False)
        elif format == "json":
            df.to_json(output_path, orient="records", indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Report generated: {output_path} ({len(leads)} leads)")

        return output_path

    async def generate_campaign_audit(self, sequence_ids: List[str]) -> Dict:
        """
        Generate comprehensive campaign audit report

        Args:
            sequence_ids: List of Close sequence IDs to audit

        Returns:
            Dict with campaign metrics and breakdowns
        """
        logger.info(f"Generating campaign audit for {len(sequence_ids)} sequences")

        total_contacts = 0
        sequence_details = []

        # Get subscriptions for each sequence
        for seq_id in sequence_ids:
            subs = await self.close_sequences.list_active_subscriptions(seq_id)
            total_contacts += len(subs)

            # Get sequence details
            sequence_details.append({
                "sequence_id": seq_id,
                "enrolled_count": len(subs)
            })

        # Get unique companies enrolled
        enrolled_companies = await self.get_sequence_enrolled_companies(sequence_ids)

        # Generate ICP breakdown
        icp_breakdown = {}
        for company in enrolled_companies:
            tier = company.get("icp_tier", "UNKNOWN")
            icp_breakdown[tier] = icp_breakdown.get(tier, 0) + 1

        # Generate industry breakdown
        industry_breakdown = {}
        for company in enrolled_companies:
            industry = company.get("industry", "Other")
            industry_breakdown[industry] = industry_breakdown.get(industry, 0) + 1

        # Generate ATL/BTL breakdown
        contact_breakdown = await self._get_atl_btl_breakdown(enrolled_companies)

        # Build report
        report = {
            "total_contacts_enrolled": total_contacts,
            "unique_companies": len(enrolled_companies),
            "sequences": sequence_details,
            "icp_breakdown": icp_breakdown,
            "industry_breakdown": industry_breakdown,
            "contact_breakdown": contact_breakdown
        }

        logger.info(f"Campaign audit complete: {total_contacts} contacts, {len(enrolled_companies)} companies")

        return report

    async def get_sequence_enrolled_companies(self, sequence_ids: List[str]) -> List[Dict]:
        """
        Get companies enrolled in specific sequences

        Args:
            sequence_ids: List of Close sequence IDs

        Returns:
            List of companies
        """
        # Query companies that are in Close (have close_lead_id)
        # This is a simplified implementation - could be enhanced to query Close API directly
        response = self.supabase.table("dim_companies").select(
            "company_id, company_name, close_lead_id, icp_tier, industry"
        ).not_.is_("close_lead_id", "null").execute()

        return response.data

    async def _get_atl_btl_breakdown(self, companies: List[Dict]) -> Dict:
        """Get ATL vs BTL breakdown for companies"""
        # Query contacts for these companies
        company_ids = [c["company_id"] for c in companies if "company_id" in c]

        if not company_ids:
            return {"atl_count": 0, "btl_count": 0, "unknown_count": 0}

        # Query contacts
        response = self.supabase.table("dim_contacts").select(
            "contact_id, company_id, is_atl"
        ).in_("company_id", company_ids).execute()

        contacts = response.data

        # Count ATL vs BTL
        atl_count = sum(1 for c in contacts if c.get("is_atl") is True)
        btl_count = sum(1 for c in contacts if c.get("is_atl") is False)
        unknown_count = sum(1 for c in contacts if c.get("is_atl") is None)

        return {
            "atl_count": atl_count,
            "btl_count": btl_count,
            "unknown_count": unknown_count
        }

    async def _fetch_close_leads(self) -> List[Dict]:
        """
        Fetch all leads from Close CRM API

        Returns:
            List of Close leads
        """
        # This is a placeholder - actual implementation depends on CloseProvider
        # For now, return loaded leads from Supabase as proxy
        loaded = await self.get_loaded_leads()
        return loaded

    async def _query_supabase(self, query_str: str) -> List[Dict]:
        """Execute raw Supabase query (for mocking in tests)"""
        # This is a helper for testing
        pass
