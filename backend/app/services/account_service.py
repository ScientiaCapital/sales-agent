"""
Account Service for managing account-based sales operations.

This service provides core functionality for:
- Creating and managing accounts
- Auto-grouping companies by domain
- Calculating rollup metrics and stakeholder scores
- Managing multi-stakeholder engagement workflows
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from urllib.parse import urlparse

from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import Account, AccountStage

logger = logging.getLogger(__name__)


class AccountService:
    """
    Service for account-based sales operations.

    Provides methods for creating accounts, grouping companies by domain,
    calculating engagement metrics, and managing stakeholder relationships.
    """

    def __init__(self, session: AsyncSession):
        """Initialize service with database session."""
        self.session = session

    # =========================================================================
    # ACCOUNT CREATION
    # =========================================================================

    async def create_account(
        self,
        name: str,
        domain: Optional[str] = None,
        industry: Optional[str] = None,
        employee_count: Optional[int] = None,
    ) -> Account:
        """
        Create a new account.

        Args:
            name: Account/company name
            domain: Website domain (e.g., 'example.com')
            industry: Industry classification
            employee_count: Approximate employee count

        Returns:
            Created Account instance
        """
        # Normalize domain
        normalized_domain = self._normalize_domain(domain) if domain else None

        # Check for existing account with same domain
        if normalized_domain:
            existing = await self.get_account_by_domain(normalized_domain)
            if existing:
                logger.info(f"Account already exists for domain {normalized_domain}")
                return existing

        account = Account(
            name=name,
            domain=normalized_domain,
            industry=industry,
            employee_count=employee_count,
            account_stage=AccountStage.PROSPECT.value,
            total_contacts=0,
            engaged_contacts=0,
            total_activities=0,
        )

        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)

        logger.info(f"Created account: {name} (domain={normalized_domain})")
        return account

    async def get_account_by_domain(self, domain: str) -> Optional[Account]:
        """Get account by domain."""
        normalized = self._normalize_domain(domain)
        query = select(Account).where(Account.domain == normalized)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_account_by_id(self, account_id: UUID) -> Optional[Account]:
        """Get account by ID."""
        return await self.session.get(Account, account_id)

    # =========================================================================
    # DOMAIN GROUPING
    # =========================================================================

    async def group_by_domain(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Auto-group companies by domain into accounts.

        Scans dim_companies for ungrouped records and creates/assigns accounts
        based on domain matching.

        Args:
            dry_run: If True, only report what would be done without making changes

        Returns:
            Dict with grouping statistics
        """
        from app.models.domain import Domain

        # Find companies without account_id that have a website
        # Using raw SQL for efficiency with large datasets
        query = """
            SELECT id, name, website, domain
            FROM dim_companies
            WHERE account_id IS NULL
            AND (website IS NOT NULL OR domain IS NOT NULL)
            ORDER BY domain, name
        """
        result = await self.session.execute(query)
        companies = result.fetchall()

        grouped_count = 0
        accounts_created = 0
        errors = []
        domain_groups: Dict[str, List] = {}

        # Group companies by normalized domain
        for company in companies:
            company_id, name, website, domain = company
            normalized = self._extract_domain(website) or self._normalize_domain(domain)

            if normalized:
                if normalized not in domain_groups:
                    domain_groups[normalized] = []
                domain_groups[normalized].append({
                    "id": company_id,
                    "name": name,
                })

        if dry_run:
            return {
                "dry_run": True,
                "domains_found": len(domain_groups),
                "companies_to_group": sum(len(c) for c in domain_groups.values()),
                "domain_breakdown": {
                    d: len(c) for d, c in domain_groups.items()
                },
            }

        # Create accounts and assign companies
        for domain, domain_companies in domain_groups.items():
            try:
                # Check if account exists
                account = await self.get_account_by_domain(domain)

                if not account:
                    # Create account using first company name
                    primary_name = domain_companies[0]["name"]
                    account = await self.create_account(
                        name=primary_name,
                        domain=domain,
                    )
                    accounts_created += 1

                # Assign companies to account
                company_ids = [c["id"] for c in domain_companies]
                await self._assign_companies_to_account(account.id, company_ids)
                grouped_count += len(company_ids)

            except Exception as e:
                logger.error(f"Error grouping domain {domain}: {e}")
                errors.append({"domain": domain, "error": str(e)})

        await self.session.commit()

        return {
            "dry_run": False,
            "accounts_created": accounts_created,
            "companies_grouped": grouped_count,
            "domains_processed": len(domain_groups),
            "errors": errors,
        }

    async def _assign_companies_to_account(
        self,
        account_id: UUID,
        company_ids: List
    ) -> int:
        """Assign multiple companies to an account."""
        stmt = (
            update(self._get_company_table())
            .where(self._get_company_table().c.id.in_(company_ids))
            .values(account_id=account_id)
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    def _get_company_table(self):
        """Get the dim_companies table for raw queries."""
        from sqlalchemy import Table, MetaData
        metadata = MetaData()
        return Table('dim_companies', metadata, autoload_with=self.session.get_bind())

    # =========================================================================
    # CONTACT RETRIEVAL
    # =========================================================================

    async def get_account_with_contacts(
        self,
        account_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get account with all associated contacts.

        Args:
            account_id: Account UUID

        Returns:
            Dict with account data and contacts list
        """
        account = await self.get_account_by_id(account_id)
        if not account:
            return None

        # Get contacts through companies
        contacts_query = """
            SELECT
                c.id,
                c.name,
                c.email,
                c.title,
                c.phone,
                c.linkedin_url,
                c.is_atl,
                c.confidence,
                comp.name as company_name,
                comp.id as company_id
            FROM dim_contacts c
            JOIN dim_companies comp ON c.company_id = comp.id
            WHERE comp.account_id = :account_id
            ORDER BY c.is_atl DESC, c.name
        """
        result = await self.session.execute(
            contacts_query,
            {"account_id": str(account_id)}
        )
        contacts = [dict(row._mapping) for row in result.fetchall()]

        return {
            "account": account.to_dict(),
            "contacts": contacts,
            "contact_count": len(contacts),
            "atl_count": sum(1 for c in contacts if c.get("is_atl")),
        }

    # =========================================================================
    # ROLLUP METRICS
    # =========================================================================

    async def update_rollup_metrics(self, account_id: UUID) -> Dict[str, Any]:
        """
        Recalculate and update denormalized rollup metrics for an account.

        Updates:
        - total_contacts: Count of all contacts
        - engaged_contacts: Contacts with any engagement activity
        - total_activities: Sum of all activity counts
        - stakeholder_score: % of ATL contacts that are engaged

        Args:
            account_id: Account UUID

        Returns:
            Dict with updated metrics
        """
        # Count total contacts
        total_query = """
            SELECT COUNT(c.id) as total
            FROM dim_contacts c
            JOIN dim_companies comp ON c.company_id = comp.id
            WHERE comp.account_id = :account_id
        """
        result = await self.session.execute(
            total_query, {"account_id": str(account_id)}
        )
        total_contacts = result.scalar() or 0

        # Count engaged contacts (those with sequence entries that have activity)
        engaged_query = """
            SELECT COUNT(DISTINCT c.id) as engaged
            FROM dim_contacts c
            JOIN dim_companies comp ON c.company_id = comp.id
            LEFT JOIN dim_sequence_entries se ON se.lead_id = comp.id
            WHERE comp.account_id = :account_id
            AND (se.opens > 0 OR se.clicks > 0 OR se.reply_received IS NOT NULL)
        """
        result = await self.session.execute(
            engaged_query, {"account_id": str(account_id)}
        )
        engaged_contacts = result.scalar() or 0

        # Count total activities
        activities_query = """
            SELECT COALESCE(SUM(se.emails_sent), 0) +
                   COALESCE(SUM(se.opens), 0) +
                   COALESCE(SUM(se.clicks), 0) as total
            FROM dim_sequence_entries se
            JOIN dim_companies comp ON se.lead_id = comp.id
            WHERE comp.account_id = :account_id
        """
        result = await self.session.execute(
            activities_query, {"account_id": str(account_id)}
        )
        total_activities = result.scalar() or 0

        # Calculate stakeholder score (ATL engagement)
        stakeholder_score = await self._calculate_stakeholder_score(account_id)

        # Update account
        account = await self.get_account_by_id(account_id)
        if account:
            account.total_contacts = total_contacts
            account.engaged_contacts = engaged_contacts
            account.total_activities = int(total_activities)
            account.stakeholder_score = stakeholder_score
            await self.session.commit()

        return {
            "account_id": str(account_id),
            "total_contacts": total_contacts,
            "engaged_contacts": engaged_contacts,
            "total_activities": int(total_activities),
            "stakeholder_score": stakeholder_score,
        }

    async def _calculate_stakeholder_score(self, account_id: UUID) -> Optional[float]:
        """Calculate stakeholder score (% ATL contacts engaged)."""
        query = """
            SELECT
                COUNT(CASE WHEN c.is_atl = true THEN 1 END) as atl_total,
                COUNT(CASE WHEN c.is_atl = true AND (
                    se.opens > 0 OR se.clicks > 0 OR se.reply_received IS NOT NULL
                ) THEN 1 END) as atl_engaged
            FROM dim_contacts c
            JOIN dim_companies comp ON c.company_id = comp.id
            LEFT JOIN dim_sequence_entries se ON se.lead_id = comp.id
            WHERE comp.account_id = :account_id
        """
        result = await self.session.execute(query, {"account_id": str(account_id)})
        row = result.fetchone()

        if row and row.atl_total > 0:
            return row.atl_engaged / row.atl_total
        return None

    # =========================================================================
    # STAKEHOLDER MAP
    # =========================================================================

    async def get_stakeholder_map(self, account_id: UUID) -> Dict[str, Any]:
        """
        Get stakeholder breakdown for an account.

        Returns ATL (Above The Line) vs non-ATL contacts with engagement status.

        Args:
            account_id: Account UUID

        Returns:
            Dict with stakeholder analysis
        """
        query = """
            SELECT
                c.id,
                c.name,
                c.email,
                c.title,
                c.is_atl,
                CASE
                    WHEN se.reply_received IS NOT NULL THEN 'replied'
                    WHEN se.clicks > 0 THEN 'clicked'
                    WHEN se.opens > 0 THEN 'opened'
                    WHEN se.emails_sent > 0 THEN 'contacted'
                    ELSE 'not_contacted'
                END as engagement_status,
                se.emails_sent,
                se.opens,
                se.clicks,
                se.reply_intent
            FROM dim_contacts c
            JOIN dim_companies comp ON c.company_id = comp.id
            LEFT JOIN dim_sequence_entries se ON se.lead_id = comp.id
            WHERE comp.account_id = :account_id
            ORDER BY c.is_atl DESC, c.name
        """
        result = await self.session.execute(query, {"account_id": str(account_id)})
        contacts = [dict(row._mapping) for row in result.fetchall()]

        # Separate ATL and non-ATL
        atl_contacts = [c for c in contacts if c.get("is_atl")]
        non_atl_contacts = [c for c in contacts if not c.get("is_atl")]

        # Calculate engagement stats
        def calc_stats(contact_list):
            total = len(contact_list)
            engaged = sum(1 for c in contact_list
                         if c.get("engagement_status") not in ["not_contacted", None])
            replied = sum(1 for c in contact_list
                         if c.get("engagement_status") == "replied")
            return {
                "total": total,
                "engaged": engaged,
                "replied": replied,
                "engagement_rate": (engaged / total * 100) if total > 0 else 0,
            }

        return {
            "account_id": str(account_id),
            "atl": {
                "contacts": atl_contacts,
                "stats": calc_stats(atl_contacts),
            },
            "non_atl": {
                "contacts": non_atl_contacts,
                "stats": calc_stats(non_atl_contacts),
            },
            "stakeholder_score": (
                calc_stats(atl_contacts)["engagement_rate"] / 100
                if atl_contacts else None
            ),
        }

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _normalize_domain(self, domain: Optional[str]) -> Optional[str]:
        """Normalize domain to lowercase without www prefix."""
        if not domain:
            return None
        domain = domain.lower().strip()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _extract_domain(self, url: Optional[str]) -> Optional[str]:
        """Extract and normalize domain from URL."""
        if not url:
            return None
        try:
            # Add scheme if missing
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split("/")[0]
            return self._normalize_domain(domain)
        except Exception:
            return None
