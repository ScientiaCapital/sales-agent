"""
SaveVerifier - Mandatory readback verification for all Supabase saves.

This service ensures that every INSERT/UPDATE to Supabase is verified with a readback
to catch silent failures, constraint violations, and network issues.

Usage:
    from app.services.save_verifier import SaveVerifier

    verifier = SaveVerifier(supabase_client)

    # For contacts
    success, error = verifier.save_contact(company_id, contact_data)

    # For signals
    success, error = verifier.update_company_signals(company_id, signals_dict)

All failures are logged to fact_enrichment_errors for audit.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from supabase import Client

logger = logging.getLogger(__name__)


class SaveVerifier:
    """
    Mandatory readback verification for Supabase operations.

    Every save operation:
    1. Attempts the INSERT/UPDATE
    2. Reads back the record to verify
    3. Compares key fields
    4. Logs errors to fact_enrichment_errors
    5. Returns success/failure with details
    """

    def __init__(self, supabase: Client, max_retries: int = 2):
        self.supabase = supabase
        self.max_retries = max_retries

    def save_contact(
        self,
        company_id: str,
        contact_data: dict,
        source: str = "unknown"
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Save a contact with readback verification.

        Args:
            company_id: Company UUID
            contact_data: Dict with full_name, title, email, phone, etc.
            source: Origin of the contact (vlm_screenshot, hunter_io, etc.)

        Returns:
            tuple: (success, contact_id, error_message)
        """
        full_name = contact_data.get("full_name", "").strip()

        # Validation
        if not full_name or len(full_name) < 3:
            self._log_error(company_id, "contact", "validation",
                           f"Invalid name: '{full_name}'", source)
            return False, None, "Invalid name (too short)"

        if full_name.lower() in ["none", "none none", "null"]:
            self._log_error(company_id, "contact", "validation",
                           f"Garbage name: '{full_name}'", source)
            return False, None, "Garbage name rejected"

        # Check for existing (case-insensitive)
        existing = self.supabase.table("dim_contacts") \
            .select("contact_id,full_name") \
            .eq("company_id", company_id) \
            .ilike("full_name", full_name.strip()) \
            .execute()

        if existing.data:
            return False, existing.data[0]["contact_id"], f"Exists: {full_name}"

        # Generate contact_id
        contact_id = str(uuid4())

        # Prepare insert data
        insert_data = {
            "contact_id": contact_id,
            "company_id": company_id,
            "full_name": full_name,
            "first_name": contact_data.get("first_name", ""),
            "last_name": contact_data.get("last_name", ""),
            "title": contact_data.get("title", ""),
            "email": contact_data.get("email"),
            "phone": contact_data.get("phone"),
            "is_atl": contact_data.get("is_atl", False),
            "confidence": contact_data.get("confidence", 50),
            "source": source,
            "validated": False,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Try insert with retries
        for attempt in range(self.max_retries + 1):
            try:
                self.supabase.table("dim_contacts").insert(insert_data).execute()

                # READBACK VERIFICATION
                readback = self.supabase.table("dim_contacts") \
                    .select("contact_id,full_name,company_id") \
                    .eq("contact_id", contact_id) \
                    .execute()

                if not readback.data:
                    error_msg = "Insert appeared to succeed but readback found nothing"
                    self._log_error(company_id, "contact", "readback_failed",
                                   error_msg, source, contact_id)
                    if attempt < self.max_retries:
                        continue
                    return False, None, error_msg

                # Verify key fields match
                saved = readback.data[0]
                if saved["full_name"] != full_name:
                    error_msg = f"Name mismatch: sent '{full_name}', got '{saved['full_name']}'"
                    self._log_error(company_id, "contact", "data_corruption",
                                   error_msg, source, contact_id)
                    return False, contact_id, error_msg

                if saved["company_id"] != company_id:
                    error_msg = f"Company mismatch: sent '{company_id}', got '{saved['company_id']}'"
                    self._log_error(company_id, "contact", "data_corruption",
                                   error_msg, source, contact_id)
                    return False, contact_id, error_msg

                # SUCCESS
                logger.info(f"Verified save: {full_name} ({contact_id[:8]})")
                return True, contact_id, None

            except Exception as e:
                error_msg = str(e)
                if "duplicate key" in error_msg.lower():
                    # Race condition - another process inserted first
                    return False, None, f"Duplicate: {full_name}"

                self._log_error(company_id, "contact", "insert_exception",
                               error_msg[:200], source, contact_id)

                if attempt < self.max_retries:
                    logger.warning(f"Retry {attempt + 1}/{self.max_retries} for {full_name}")
                    continue

                return False, None, f"Insert failed: {error_msg[:50]}"

        return False, None, "Max retries exceeded"

    def update_company_signals(
        self,
        company_id: str,
        signals: dict,
        source: str = "scraper"
    ) -> tuple[bool, Optional[str]]:
        """
        Update company ICP signals with readback verification.

        Args:
            company_id: Company UUID
            signals: Dict of signal columns (has_commercial, has_industrial, etc.)
            source: Origin of the signals

        Returns:
            tuple: (success, error_message)
        """
        if not signals:
            return False, "No signals to update"

        # Filter to only valid signal columns
        valid_signals = {}
        signal_columns = {
            "has_commercial", "has_industrial", "has_generators",
            "has_design_build", "has_engineering", "has_medical_specialization",
            "has_building_automation", "has_oem_partnerships", "has_awards",
            "has_emergency_service", "has_membership", "has_specials",
            "has_financing", "is_hiring", "has_funding"
        }

        for key, value in signals.items():
            if key in signal_columns:
                valid_signals[key] = bool(value)

        if not valid_signals:
            return False, "No valid signal columns"

        # Add metadata
        valid_signals["last_enriched_at"] = datetime.utcnow().isoformat()

        for attempt in range(self.max_retries + 1):
            try:
                self.supabase.table("dim_companies") \
                    .update(valid_signals) \
                    .eq("company_id", company_id) \
                    .execute()

                # READBACK VERIFICATION
                readback = self.supabase.table("dim_companies") \
                    .select(",".join(valid_signals.keys())) \
                    .eq("company_id", company_id) \
                    .execute()

                if not readback.data:
                    error_msg = "Company not found after update"
                    self._log_error(company_id, "signal", "readback_failed",
                                   error_msg, source)
                    return False, error_msg

                # Verify signals match
                saved = readback.data[0]
                mismatches = []
                for key in valid_signals:
                    if key == "last_enriched_at":
                        continue
                    if saved.get(key) != valid_signals[key]:
                        mismatches.append(f"{key}: {valid_signals[key]} -> {saved.get(key)}")

                if mismatches:
                    error_msg = f"Signal mismatch: {', '.join(mismatches[:3])}"
                    self._log_error(company_id, "signal", "data_corruption",
                                   error_msg, source)
                    if attempt < self.max_retries:
                        continue
                    return False, error_msg

                # SUCCESS
                logger.info(f"Verified signals for {company_id[:8]}: {len(valid_signals) - 1} updated")
                return True, None

            except Exception as e:
                error_msg = str(e)
                self._log_error(company_id, "signal", "update_exception",
                               error_msg[:200], source)

                if attempt < self.max_retries:
                    logger.warning(f"Retry {attempt + 1}/{self.max_retries}")
                    continue

                return False, f"Update failed: {error_msg[:50]}"

        return False, "Max retries exceeded"

    def _log_error(
        self,
        company_id: str,
        entity_type: str,
        error_type: str,
        error_message: str,
        source: str,
        entity_id: str = None
    ):
        """Log error to fact_enrichment_errors table."""
        try:
            self.supabase.table("fact_enrichment_errors").insert({
                "error_id": str(uuid4()),
                "company_id": company_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "error_type": error_type,
                "error_message": error_message[:500],
                "source": source,
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
        except Exception as e:
            # Don't fail the main operation if error logging fails
            logger.error(f"Failed to log error: {e}")

    def verify_contact_exists(self, contact_id: str) -> bool:
        """Check if a contact exists in the database."""
        result = self.supabase.table("dim_contacts") \
            .select("contact_id") \
            .eq("contact_id", contact_id) \
            .execute()
        return len(result.data) > 0

    def verify_company_exists(self, company_id: str) -> bool:
        """Check if a company exists in the database."""
        result = self.supabase.table("dim_companies") \
            .select("company_id") \
            .eq("company_id", company_id) \
            .execute()
        return len(result.data) > 0

    def get_contact_count(self, company_id: str) -> int:
        """Get count of contacts for a company."""
        result = self.supabase.table("dim_contacts") \
            .select("contact_id", count="exact") \
            .eq("company_id", company_id) \
            .execute()
        return result.count or 0
