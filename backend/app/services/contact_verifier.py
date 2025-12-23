"""
Contact Verifier for Sales Agent

Immediate readback verification after saving contacts to Supabase.
Ensures contacts actually persist and aren't silently lost.
"""

from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


class ContactVerifier:
    """
    Verify contacts are saved to Supabase.

    After saving a contact, immediately reads back to confirm
    the save succeeded. This catches silent failures like:
    - Network drops after insert
    - Constraint violations that return success but don't persist
    - RLS policy blocks
    """

    def __init__(self, supabase_client):
        """
        Initialize verifier with Supabase client.

        Args:
            supabase_client: Initialized Supabase client
        """
        self.supabase = supabase_client

    def verify_contact_saved(
        self,
        company_id: str,
        contact_name: str,
    ) -> bool:
        """
        Verify a contact was saved to dim_contacts.

        Args:
            company_id: Company ID the contact belongs to
            contact_name: Full name of the contact

        Returns:
            True if contact exists in DB, False otherwise
        """
        try:
            result = self.supabase.table("dim_contacts") \
                .select("contact_id, full_name") \
                .eq("company_id", company_id) \
                .eq("full_name", contact_name) \
                .execute()

            if result.data and len(result.data) > 0:
                logger.debug(
                    "Contact verified in Supabase",
                    company_id=company_id,
                    contact_name=contact_name,
                )
                return True
            else:
                logger.warning(
                    "Contact NOT found after save",
                    company_id=company_id,
                    contact_name=contact_name,
                )
                return False

        except Exception as e:
            logger.error(
                "Verification query failed",
                company_id=company_id,
                contact_name=contact_name,
                error=str(e),
            )
            return False

    def verify_batch_saved(
        self,
        company_id: str,
        contact_names: list[str],
    ) -> dict:
        """
        Verify multiple contacts were saved.

        Args:
            company_id: Company ID
            contact_names: List of contact names to verify

        Returns:
            {
                "total": 5,
                "verified": 4,
                "missing": ["John Doe"],
                "success_rate": 0.80
            }
        """
        verified = []
        missing = []

        for name in contact_names:
            if self.verify_contact_saved(company_id, name):
                verified.append(name)
            else:
                missing.append(name)

        total = len(contact_names)
        success_rate = len(verified) / total if total > 0 else 0.0

        if missing:
            logger.warning(
                "Some contacts missing after batch save",
                company_id=company_id,
                verified_count=len(verified),
                missing_count=len(missing),
                missing_names=missing,
            )

        return {
            "total": total,
            "verified": len(verified),
            "missing": missing,
            "success_rate": success_rate,
        }

    def get_company_contact_count(self, company_id: str) -> int:
        """
        Get total contact count for a company.

        Args:
            company_id: Company ID

        Returns:
            Number of contacts in dim_contacts for this company
        """
        try:
            result = self.supabase.table("dim_contacts") \
                .select("contact_id", count="exact") \
                .eq("company_id", company_id) \
                .execute()

            return result.count if hasattr(result, 'count') else len(result.data)

        except Exception as e:
            logger.error(
                "Failed to count contacts",
                company_id=company_id,
                error=str(e),
            )
            return 0
