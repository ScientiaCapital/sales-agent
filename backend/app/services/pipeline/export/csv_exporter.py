"""CSV export functionality for pipeline output."""
import csv
import logging
from typing import Dict, Any, Optional

from app.schemas.pipeline import PipelineStageResult
from .session_manager import SessionManager
from .validators import is_bad_email

logger = logging.getLogger(__name__)

# CSV field names - include all Hunter.io enrichment data
CSV_FIELDNAMES = [
    "company_name", "first_name", "last_name", "email", "phone",
    "position", "is_atl", "linkedin", "twitter", "confidence",
    "qualification_score", "dedup_status", "close_lead_id"
]


def export_to_csv(
    lead_data: Dict[str, Any],
    session: SessionManager,
    dedup_result: Optional[PipelineStageResult] = None
) -> str:
    """
    Export ALL contacts for a company to session master CSV.

    Creates one row per contact with full enrichment data.
    Filters out bad email patterns (tracking pixels, placeholders).

    Returns:
        Path to master CSV file
    """
    session.init_session_files()

    # Extract dedup status
    dedup_status = "unknown"
    close_lead_id = ""
    if dedup_result and dedup_result.output:
        dedup_status = dedup_result.output.get("recommendation", "unknown")
        close_lead_id = dedup_result.output.get("existing_lead_id", "")

    company_name = lead_data.get("name") or lead_data.get("company_name", "")
    company_phone = lead_data.get("phone", "")
    qualification_score = lead_data.get("qualification_score", 0)

    discovered_contacts = lead_data.get("_discovered_contacts", [])
    rows_written = 0

    file_exists = session.master_csv_path.exists()

    with open(session.master_csv_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        if not file_exists:
            writer.writeheader()

        if discovered_contacts:
            for contact in discovered_contacts:
                email = contact.get("email", "")

                if email and is_bad_email(email):
                    session.add_filtered_email(company_name, email, "bad_pattern")
                    session.log_to_file(f"Filtered bad email: {email} ({company_name})")
                    continue

                csv_row = {
                    "company_name": company_name,
                    "first_name": contact.get("first_name", ""),
                    "last_name": contact.get("last_name", ""),
                    "email": email,
                    "phone": contact.get("phone", "") or company_phone,
                    "position": contact.get("position", ""),
                    "is_atl": contact.get("is_atl", False),
                    "linkedin": contact.get("linkedin", ""),
                    "twitter": contact.get("twitter", ""),
                    "confidence": contact.get("confidence", 0),
                    "qualification_score": qualification_score,
                    "dedup_status": dedup_status,
                    "close_lead_id": close_lead_id
                }

                writer.writerow(csv_row)
                session.add_exported_lead(csv_row.copy())
                rows_written += 1

                atl_status = "ATL" if csv_row["is_atl"] else "BTL"
                session.log_to_file(
                    f"[{atl_status}] {company_name} - "
                    f"{csv_row['first_name']} {csv_row['last_name']} - {email}"
                )

        else:
            # No contacts discovered - write company row with existing data
            email = lead_data.get("email") or lead_data.get("contact_email", "")

            if email and is_bad_email(email):
                session.add_filtered_email(company_name, email, "bad_pattern")
                email = ""

            csv_row = {
                "company_name": company_name,
                "first_name": "",
                "last_name": "",
                "email": email,
                "phone": company_phone,
                "position": "",
                "is_atl": False,
                "linkedin": "",
                "twitter": "",
                "confidence": 0,
                "qualification_score": qualification_score,
                "dedup_status": dedup_status,
                "close_lead_id": close_lead_id
            }

            writer.writerow(csv_row)
            session.add_exported_lead(csv_row.copy())
            rows_written += 1
            session.log_to_file(f"[NO CONTACTS] {company_name} - {email or 'no email'}")

    logger.info(f"Exported {rows_written} contact(s) for {company_name}")
    return str(session.master_csv_path)
