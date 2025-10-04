"""
CSV Lead Import Service

Bulk import leads from CSV files with PostgreSQL COPY command for high performance.
Target: 1,000 leads in < 5 seconds
"""

import csv
import io
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class CSVImportService:
    """
    Service for bulk importing leads from CSV files using PostgreSQL COPY

    Performance optimizations:
    - PostgreSQL COPY command for bulk inserts (10-100x faster than individual INSERTs)
    - Batch processing (500 leads per batch)
    - Minimal validation overhead
    - Direct database connection for COPY
    """

    BATCH_SIZE = 500
    REQUIRED_FIELDS = ["company_name", "industry", "company_website"]
    OPTIONAL_FIELDS = [
        "company_size",
        "contact_name",
        "contact_email",
        "contact_phone",
        "contact_title",
        "notes"
    ]

    def __init__(self):
        pass

    def validate_row(self, row: Dict[str, Any], row_num: int) -> Tuple[bool, str]:
        """
        Validate a single CSV row

        Args:
            row: Dictionary of CSV row data
            row_num: Row number for error reporting

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in row or not row[field] or not row[field].strip():
                return False, f"Row {row_num}: Missing required field '{field}'"

        # Validate company_name length
        if len(row["company_name"]) > 255:
            return False, f"Row {row_num}: company_name exceeds 255 characters"

        # Validate email format if provided
        if row.get("contact_email"):
            email = row["contact_email"].strip()
            if "@" not in email or "." not in email:
                return False, f"Row {row_num}: Invalid email format '{email}'"

        return True, ""

    def parse_csv_file(self, csv_content: str) -> List[Dict[str, Any]]:
        """
        Parse CSV content into list of lead dictionaries

        Args:
            csv_content: CSV file content as string

        Returns:
            List of validated lead dictionaries

        Raises:
            HTTPException: If CSV format is invalid or validation fails
        """
        try:
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)

            if not reader.fieldnames:
                raise HTTPException(
                    status_code=400,
                    detail="CSV file is empty or has no header row"
                )

            # Validate CSV headers
            missing_required = set(self.REQUIRED_FIELDS) - set(reader.fieldnames)
            if missing_required:
                raise HTTPException(
                    status_code=400,
                    detail=f"CSV missing required columns: {', '.join(missing_required)}"
                )

            leads = []
            errors = []

            for idx, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                # Clean row data
                cleaned_row = {k: v.strip() if v else None for k, v in row.items()}

                # Validate row
                is_valid, error_msg = self.validate_row(cleaned_row, idx)
                if not is_valid:
                    errors.append(error_msg)
                    continue

                # Prepare lead data
                lead_data = {
                    "company_name": cleaned_row["company_name"],
                    "company_website": cleaned_row.get("company_website"),
                    "company_size": cleaned_row.get("company_size"),
                    "industry": cleaned_row["industry"],
                    "contact_name": cleaned_row.get("contact_name"),
                    "contact_email": cleaned_row.get("contact_email"),
                    "contact_phone": cleaned_row.get("contact_phone"),
                    "contact_title": cleaned_row.get("contact_title"),
                    "notes": cleaned_row.get("notes"),
                }

                leads.append(lead_data)

            # If too many errors, reject the entire import
            if len(errors) > len(leads) * 0.1:  # More than 10% error rate
                raise HTTPException(
                    status_code=400,
                    detail=f"Too many validation errors ({len(errors)}): {'; '.join(errors[:5])}"
                )

            if not leads:
                raise HTTPException(
                    status_code=400,
                    detail="No valid leads found in CSV file"
                )

            logger.info(f"Parsed {len(leads)} valid leads from CSV (skipped {len(errors)} invalid rows)")
            return leads

        except csv.Error as e:
            raise HTTPException(
                status_code=400,
                detail=f"CSV parsing error: {str(e)}"
            )

    def bulk_import_leads(self, db: Session, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk import leads using PostgreSQL COPY command for maximum performance

        Args:
            db: SQLAlchemy database session
            leads: List of lead dictionaries to import

        Returns:
            Dictionary with import statistics

        Raises:
            HTTPException: If database import fails
        """
        import_start = datetime.now()
        total_leads = len(leads)
        imported_count = 0

        try:
            # Process in batches
            for batch_start in range(0, total_leads, self.BATCH_SIZE):
                batch_end = min(batch_start + self.BATCH_SIZE, total_leads)
                batch = leads[batch_start:batch_end]

                # Prepare CSV data for COPY command
                csv_buffer = io.StringIO()
                csv_writer = csv.writer(csv_buffer)

                for lead in batch:
                    row = [
                        lead.get("company_name"),
                        lead.get("company_website"),
                        lead.get("company_size"),
                        lead.get("industry"),
                        lead.get("contact_name"),
                        lead.get("contact_email"),
                        lead.get("contact_phone"),
                        lead.get("contact_title"),
                        lead.get("notes"),
                        datetime.now().isoformat(),  # created_at
                    ]
                    csv_writer.writerow(row)

                csv_buffer.seek(0)

                # Use raw connection for COPY command
                raw_conn = db.connection().connection
                cursor = raw_conn.cursor()

                # PostgreSQL COPY command (ultra-fast bulk insert)
                copy_sql = """
                    COPY leads (
                        company_name,
                        company_website,
                        company_size,
                        industry,
                        contact_name,
                        contact_email,
                        contact_phone,
                        contact_title,
                        notes,
                        created_at
                    )
                    FROM STDIN WITH (FORMAT CSV)
                """

                cursor.copy_expert(copy_sql, csv_buffer)
                raw_conn.commit()
                cursor.close()

                imported_count += len(batch)
                logger.info(f"Imported batch: {batch_start + 1} to {batch_end} ({len(batch)} leads)")

            import_end = datetime.now()
            duration_ms = int((import_end - import_start).total_seconds() * 1000)

            result = {
                "total_leads": total_leads,
                "imported_count": imported_count,
                "duration_ms": duration_ms,
                "leads_per_second": round(imported_count / (duration_ms / 1000), 2)
            }

            logger.info(f"CSV import completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Bulk import failed: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Database import failed: {str(e)}"
            )
