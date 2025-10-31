#!/usr/bin/env python3
"""
Direct Import Top 200 Dealer Prospects from CSV

Directly uses CSVImportService to import without needing API server.
Maps dealer-scraper CSV fields to Lead model fields.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try loading from root
    root_env = Path(__file__).parent.parent.parent / '.env'
    if root_env.exists():
        load_dotenv(root_env)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.models.database import get_db, engine
from app.services.csv_importer import CSVImportService
from app.models.lead import Lead
import csv
from typing import Dict, Any, List
from datetime import datetime

# CSV file path
CSV_FILE_PATH = "/Users/tmkipper/Desktop/dealer-scraper-mvp/output/top_200_prospects_final_20251029.csv"

# Field mapping from dealer-scraper CSV to Lead model
FIELD_MAPPING = {
    'name': 'company_name',
    'website': 'company_website',
    'phone': 'contact_phone',
    'email': 'contact_email',
    'employee_count': 'company_size',  # Map to company_size as string
    # Additional data will be stored in additional_data JSON field
}


def normalize_csv_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize dealer-scraper CSV row to Lead model format.
    
    Args:
        row: Raw CSV row dictionary
        
    Returns:
        Normalized lead data dictionary
    """
    normalized = {}
    
    # Map required field
    normalized['company_name'] = row.get('name', '').strip()
    if not normalized['company_name']:
        return None
    
    # Map optional standard fields
    normalized['company_website'] = row.get('website', '').strip()
    normalized['contact_phone'] = row.get('phone', '').strip()
    normalized['contact_email'] = row.get('email', '').strip()
    
    # Map company_size from employee_count
    employee_count = row.get('employee_count', '').strip()
    if employee_count:
        try:
            emp_count = int(employee_count)
            if emp_count < 10:
                normalized['company_size'] = '1-10'
            elif emp_count < 50:
                normalized['company_size'] = '11-50'
            elif emp_count < 200:
                normalized['company_size'] = '51-200'
            elif emp_count < 500:
                normalized['company_size'] = '201-500'
            else:
                normalized['company_size'] = '500+'
        except (ValueError, TypeError):
            normalized['company_size'] = employee_count  # Keep as-is if not numeric
    
    # Set industry
    normalized['industry'] = 'Energy Contractors'  # Default industry
    
    # Store all dealer-scraper data in additional_data JSON
    additional_data = {
        'source': 'dealer-scraper-mvp',
        'icp_score': row.get('ICP_Score'),
        'icp_tier': row.get('ICP_Tier'),
        'oem_count': row.get('OEM_Count'),
        'oems_certified': row.get('OEMs_Certified'),
        'has_hvac': row.get('has_hvac', '').lower() in ('true', '1', 'yes'),
        'has_solar': row.get('has_solar', '').lower() in ('true', '1', 'yes'),
        'has_battery': row.get('has_battery', '').lower() in ('true', '1', 'yes'),
        'linkedin_url': row.get('linkedin_url'),
        'domain': row.get('domain'),
        'address': {
            'street': row.get('street'),
            'city': row.get('city'),
            'state': row.get('state'),
            'zip': row.get('zip'),
            'full': row.get('address_full'),
        },
        'original_row': row  # Keep full original data
    }
    normalized['additional_data'] = additional_data
    
    return normalized


def import_dealer_csv(file_path: str) -> Dict[str, Any]:
    """
    Import dealer CSV file directly into database.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        Import result dictionary
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    
    print(f"📤 Reading CSV: {file_path}")
    
    # Read and normalize CSV
    normalized_leads = []
    errors = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for idx, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
            try:
                normalized = normalize_csv_row(row)
                if normalized:
                    normalized_leads.append(normalized)
                else:
                    errors.append(f"Row {idx}: Missing company_name")
            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")
    
    print(f"✅ Parsed {len(normalized_leads)} valid leads")
    if errors:
        print(f"⚠️  {len(errors)} rows had errors")
    
    # Import to database using batch INSERT (more compatible than COPY)
    print(f"\n💾 Importing to database...")
    start_time = datetime.now()
    
    db: Session = next(get_db())
    
    try:
        # Use batch insert instead of COPY (works with psycopg3)
        imported_count = 0
        batch_size = 100
        
        for i in range(0, len(normalized_leads), batch_size):
            batch = normalized_leads[i:i + batch_size]
            
            # Create Lead objects
            lead_objects = []
            for lead_data in batch:
                lead = Lead(
                    company_name=lead_data['company_name'],
                    company_website=lead_data.get('company_website'),
                    company_size=lead_data.get('company_size'),
                    industry=lead_data.get('industry'),
                    contact_phone=lead_data.get('contact_phone'),
                    contact_email=lead_data.get('contact_email'),
                    additional_data=lead_data.get('additional_data')
                )
                lead_objects.append(lead)
            
            # Bulk insert
            db.bulk_save_objects(lead_objects)
            imported_count += len(lead_objects)
        
        db.commit()
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        leads_per_second = imported_count / (duration_ms / 1000) if duration_ms > 0 else 0
        
        result = {
            'imported_count': imported_count,
            'leads_per_second': leads_per_second
        }
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        print(f"\n✅ Import complete!")
        print(f"   Total rows: {len(normalized_leads) + len(errors)}")
        print(f"   Imported: {result['imported_count']}")
        print(f"   Failed: {len(errors)}")
        print(f"   Duration: {duration_ms:.0f}ms")
        print(f"   Throughput: {result.get('leads_per_second', 0):.1f} leads/sec")
        
        if errors:
            print(f"\n⚠️  First 5 errors:")
            for error in errors[:5]:
                print(f"   - {error}")
        
        return {
            'success': True,
            'total_leads': len(normalized_leads) + len(errors),
            'imported_count': result['imported_count'],
            'failed_count': len(errors),
            'duration_ms': duration_ms,
            'errors': errors[:10]  # Limit to first 10 errors
        }
    finally:
        db.close()


def main():
    """Main execution"""
    try:
        result = import_dealer_csv(CSV_FILE_PATH)
        print("\n🎉 Import complete!")
        return 0
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

