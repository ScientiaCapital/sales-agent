#!/usr/bin/env python3
"""
Transform dealer-scraper CSV format to sales-agent import format

Maps columns:
- name → company_name
- website → company_website (falls back to domain)
- email → contact_email
- phone → contact_phone
- domain → (used for enrichment notes)
"""
import csv
import sys
from pathlib import Path

def transform_csv(input_file, output_file):
    """Transform dealer CSV to import format"""
    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            # Map dealer CSV columns to import format
            rows = []
            for row in reader:
                # Get company name (required)
                company_name = row.get('name', '').strip()
                if not company_name:
                    continue  # Skip empty company names
                
                # Get website or construct from domain
                website = row.get('website', '').strip()
                if not website and row.get('domain'):
                    domain = row.get('domain', '').strip()
                    if domain:
                        website = f"https://{domain}"
                
                # Get contact info
                email = row.get('email', '').strip() or ''
                phone = row.get('phone', '').strip() or ''
                
                # Build notes with enrichment data
                notes_parts = []
                if row.get('ICP_Score'):
                    notes_parts.append(f"ICP Score: {row.get('ICP_Score')}")
                if row.get('ICP_Tier'):
                    notes_parts.append(f"Tier: {row.get('ICP_Tier')}")
                if row.get('domain'):
                    notes_parts.append(f"Domain: {row.get('domain')}")
                if row.get('OEMs_Certified'):
                    notes_parts.append(f"OEMs: {row.get('OEMs_Certified')}")
                
                transformed = {
                    'company_name': company_name,
                    'company_website': website,
                    'contact_email': email,
                    'contact_phone': phone,
                    'industry': 'Generator/Electrical Services',
                    'company_size': '',  # Not in source data
                    'contact_name': '',  # Not in source data
                    'contact_title': '',  # Not in source data
                    'notes': ' | '.join(notes_parts) if notes_parts else ''
                }
                rows.append(transformed)
        
        # Write transformed CSV
        with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            fieldnames = [
                'company_name', 'company_website', 'company_size', 
                'industry', 'contact_name', 'contact_email', 
                'contact_phone', 'contact_title', 'notes'
            ]
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"✅ Successfully transformed {len(rows)} companies")
        print(f"✅ Output saved to: {output_file}")
        return True
        
    except FileNotFoundError:
        print(f"❌ Error: File not found: {input_file}")
        return False
    except Exception as e:
        print(f"❌ Error transforming CSV: {e}")
        return False

if __name__ == "__main__":
    # Default paths
    input_file = "/Users/tmkipper/Desktop/dealer-scraper-mvp/output/top_200_prospects_20251028.csv"
    output_file = "companies_ready_to_import.csv"
    
    # Allow override via command line
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    success = transform_csv(input_file, output_file)
    sys.exit(0 if success else 1)

