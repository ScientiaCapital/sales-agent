"""
Batch Import MEP Leads from Dealer-Scraper - Safe CSV Export Mode

Processes MEP leads through the full pipeline:
1. Qualification (Cerebras AI) + Website Discovery
2. Email Extraction (from discovered website)
3. Hunter.io Fallback (if scraping fails)
4. Deduplication check (against Close CRM)
5. CSV Export (to data/final_enrichment_output/)

SAFE MODE: No writes to Close CRM (CLOSE_WRITE_DISABLED=True)

Usage:
    python import_mep_batch.py top_100_mep_energy_prospects_20251119.csv
    python import_mep_batch.py --list  # Show available files
"""
import asyncio
import csv
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import logging

# Load environment
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.schemas.pipeline import PipelineTestRequest, PipelineTestOptions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
SCRAPER_OUTPUT_DIR = Path(__file__).parent / 'data/csv/scraper_output'

# ===== OEM FILTER LIST =====
# Comprehensive list of equipment manufacturers (OEMs)
# We want to filter these out - they're suppliers, not potential customers
KNOWN_OEMS = {
    # Major HVAC OEMs
    "trane", "trane u s", "trane technologies",
    "carrier", "carrier global", "carrier corporation",
    "lennox", "lennox international",
    "rheem", "rheem manufacturing",
    "goodman", "goodman manufacturing",
    "daikin", "daikin industries", "daikin north america",
    "johnson controls", "york", "york international",
    "mitsubishi electric", "mitsubishi hvac",
    "fujitsu", "fujitsu general",
    "lg electronics", "lg hvac",
    "samsung hvac",
    "bosch", "bosch thermotechnology",
    "nortek", "nortek global hvac",
    "unico", "unico system",
    "american standard", "american standard heating",
    "amana", "amana hvac",
    "heil", "heil hvac",
    "ruud", "ruud hvac",
    "weatherking",
    "comfortmaker",
    "keeprite",
    "arcoaire",
    "day & night",
    "tempstar",
    # Electrical OEMs
    "schneider electric", "schneider",
    "siemens", "siemens industry",
    "eaton", "eaton corporation",
    "honeywell", "honeywell international",
    "emerson", "emerson electric",
    # Plumbing OEMs
    "kohler", "kohler co",
    "moen", "moen incorporated",
    "delta faucet",
    "grohe",
    "hansgrohe",
    "rinnai", "rinnai america",
    "navien",
    "bradford white",
    "a.o. smith", "ao smith",
    "state water heaters",
    # Generators & Solar (from dealer-scraper)
    "generac", "cummins", "briggs & stratton",
    "solaredge", "enphase", "sma", "fronius", "sungrow",
    "goodwe", "growatt", "sol-ark", "solark",
    "tesla", "simpliphi",
}

# Short OEM names that need exact match only (to avoid false positives)
# These won't match as substrings in other words
SHORT_OEMS = {"ge", "abb", "lg", "sma"}


def is_oem(company_name: str) -> bool:
    """Check if company name matches a known OEM manufacturer.

    Uses strict matching to avoid false positives:
    - Short names (ge, abb, lg) only match at start or as exact match
    - Other OEM names match as complete words, not substrings
    """
    if not company_name:
        return False

    # Normalize: lowercase, remove common suffixes
    name = company_name.lower().strip()

    # Remove common suffixes for comparison
    for suffix in [" inc", " llc", " corp", " co", " ltd", " company", " usa", " u s"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()

    # Check exact match first (most reliable)
    if name in KNOWN_OEMS:
        return True

    # Split into words for matching
    name_words = set(name.replace('-', ' ').replace('&', ' ').split())

    # Check short OEMs - only match at START of name or exact match
    for short_oem in SHORT_OEMS:
        if name == short_oem or name.startswith(short_oem + " "):
            return True

    # Check other OEMs - must match as complete words
    for oem in KNOWN_OEMS:
        if oem in SHORT_OEMS:
            continue  # Already handled above

        oem_words = set(oem.split())

        # For single-word OEMs (4+ chars), match as word
        if len(oem_words) == 1:
            oem_word = list(oem_words)[0]
            if oem_word in name_words:
                return True
        else:
            # For multi-word OEMs, all words must be present
            if oem_words.issubset(name_words):
                return True

    return False


def list_available_files():
    """List available MEP CSV files from scraper output"""
    print("\n📂 AVAILABLE MEP FILES FROM DEALER-SCRAPER:")
    print("=" * 70)

    csv_files = list(SCRAPER_OUTPUT_DIR.glob("*mep*.csv")) + list(SCRAPER_OUTPUT_DIR.glob("*top*.csv"))
    csv_files = sorted(set(csv_files), key=lambda x: x.stat().st_mtime, reverse=True)

    for f in csv_files[:10]:
        size = f.stat().st_size / 1024
        # Count rows
        with open(f, 'r') as fp:
            row_count = sum(1 for _ in fp) - 1  # Subtract header
        print(f"  {f.name:50} {row_count:>5} rows  ({size:.1f} KB)")

    print("\n💡 Usage: python import_mep_batch.py <filename>")


def estimate_size_from_score(coperniq_score: float) -> str:
    """Estimate company size from coperniq score"""
    if coperniq_score >= 80:
        return "100-200"
    elif coperniq_score >= 60:
        return "50-100"
    elif coperniq_score >= 40:
        return "20-50"
    else:
        return "10-20"


async def import_mep_batch(filename: str):
    """Import MEP leads through full enrichment pipeline"""
    print("\n" + "=" * 80)
    print(f"BATCH IMPORT - MEP ENERGY PROSPECTS (SAFE MODE)")
    print("=" * 80)

    # Verify safety mode
    if os.getenv("CLOSE_WRITE_DISABLED") != "True":
        print("❌ ERROR: CLOSE_WRITE_DISABLED must be True for safety")
        print("   Set CLOSE_WRITE_DISABLED=True in .env file")
        return
    else:
        print("✅ SAFE MODE: Close CRM writes disabled")
        print("✅ Will export to CSV: data/final_enrichment_output/\n")

    # Find the CSV file
    csv_path = SCRAPER_OUTPUT_DIR / filename
    if not csv_path.exists():
        # Try with date suffix
        matching = list(SCRAPER_OUTPUT_DIR.glob(f"*{filename}*"))
        if matching:
            csv_path = matching[0]
        else:
            print(f"❌ File not found: {filename}")
            print(f"   Looking in: {SCRAPER_OUTPUT_DIR}")
            list_available_files()
            return

    print(f"📁 Reading: {csv_path}")

    leads = []
    oems_filtered = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Support both old (business_name) and new (company_name) column formats
            company_name = row.get('company_name', row.get('business_name', '')).strip()

            # ===== OEM FILTER: Skip equipment manufacturers =====
            if is_oem(company_name):
                oems_filtered.append(company_name)
                continue  # Skip this row

            # Map columns - support both old and new formats
            # Old format: phone_normalized, coperniq_score, license_classifications
            # New format: phone, icp_score, license_count
            phone = row.get('phone', row.get('phone_normalized', ''))
            score = row.get('icp_score', row.get('coperniq_score', 50))
            licenses = row.get('license_count', row.get('license_classifications', ''))
            domain = row.get('domain', '')  # New format has domain column

            lead = {
                'name': company_name,
                'company_name': company_name,
                'website': domain,  # Use domain if available, otherwise discovered later
                'phone': str(phone).replace('.0', ''),
                'company_size': estimate_size_from_score(float(score or 50)),
                'industry': 'MEP Contractor',  # MEP = Mechanical, Electrical, Plumbing
                'address': f"{row.get('city', '')}, {row.get('state', '')} {row.get('zip', '')}".strip(', '),
                'contact_name': '',  # Will be discovered
                'email': row.get('email', ''),  # Use email if available in CSV
                # Metadata for qualification
                'notes': f"ICP: {row.get('icp_tier', '')} | Score: {score} | Licenses: {licenses}",
            }
            leads.append(lead)

    # Report OEM filtering
    if oems_filtered:
        print(f"🚫 Filtered {len(oems_filtered)} OEMs (equipment manufacturers):")
        for oem in oems_filtered[:5]:  # Show first 5
            print(f"   - {oem}")
        if len(oems_filtered) > 5:
            print(f"   ... and {len(oems_filtered) - 5} more")
        print()

    print(f"✅ Loaded {len(leads)} leads from {csv_path.name} (after OEM filtering)\n")

    # Initialize pipeline
    orchestrator = PipelineOrchestrator()

    # Process each lead
    results = []
    successful = 0
    failed = 0

    for i, lead in enumerate(leads, 1):
        try:
            print(f"\n[{i}/{len(leads)}] Processing: {lead['name'][:40]}")

            # Create pipeline request - lead data goes in 'lead' dict
            request = PipelineTestRequest(
                lead={
                    'name': lead['company_name'],
                    'company': lead['company_name'],
                    'website': lead['website'],
                    'company_size': lead['company_size'],
                    'industry': lead['industry'],
                    'contact_name': lead['contact_name'],
                    'email': lead['email'],
                    'phone': lead['phone'],
                    'address': lead['address'],
                    'notes': lead['notes'],
                },
                options=PipelineTestOptions(
                    stop_on_duplicate=False,  # Log but continue
                    skip_enrichment=False,    # We want enrichment
                    create_in_crm=False,      # Safe mode - export only
                    dry_run=True              # Don't write to CRM
                )
            )

            # Run pipeline
            response = await orchestrator.execute(request)

            # Extract results from PipelineTestResponse
            qual_output = response.stages.get("qualification", {})
            qual_data = qual_output.output if hasattr(qual_output, 'output') and qual_output.output else {}

            dedup_output = response.stages.get("deduplication", {})
            dedup_data = dedup_output.output if hasattr(dedup_output, 'output') and dedup_output.output else {}

            enrich_output = response.stages.get("enrichment", {})
            enrich_data = enrich_output.output if hasattr(enrich_output, 'output') and enrich_output.output else {}

            # Get metadata from qualification
            metadata = qual_data.get("metadata", {})

            # Extract email from multiple sources
            email = (
                metadata.get("extracted_email") or
                enrich_data.get("email") or
                lead.get('email', '')
            )

            # Extract website from multiple sources
            website = (
                metadata.get("discovered_website") or
                lead.get('website', '')
            )

            output = {
                'company_name': lead['company_name'],
                'phone': lead['phone'],
                'address': lead['address'],
                'website': website,
                'contact_name': enrich_data.get('contact_name', '') or metadata.get('contact_name', ''),
                'email': email,
                'qualification_score': qual_data.get('qualification_score', 0),
                'qualification_tier': qual_data.get('tier', ''),
                'is_atl': metadata.get('is_atl', False),
                'dedup_status': dedup_data.get('recommendation', 'new'),
                'close_lead_id': dedup_data.get('close_lead_id', ''),
                'notes': lead['notes'],
                'pipeline_success': response.success,
                'total_latency_ms': response.total_latency_ms,
                'total_cost_usd': response.total_cost_usd,
            }

            results.append(output)
            successful += 1

            # Log progress
            status = "✅" if output['email'] else "⚠️ No email"
            score = output['qualification_score']
            latency = f"{response.total_latency_ms}ms"
            print(f"   {status} Score: {score} | Email: {output['email'] or 'Not found'} | {latency}")

        except Exception as e:
            logger.error(f"Failed to process {lead['name']}: {e}")
            failed += 1
            results.append({
                'company_name': lead['company_name'],
                'phone': lead['phone'],
                'address': lead['address'],
                'error': str(e)
            })

    # Export results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent / 'data/final_enrichment_output'
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"MEP_enriched_{csv_path.stem}_{timestamp}.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        if results:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    # Summary
    print("\n" + "=" * 80)
    print("IMPORT SUMMARY")
    print("=" * 80)
    print(f"  Total processed: {len(leads)}")
    print(f"  ✅ Successful: {successful}")
    print(f"  ❌ Failed: {failed}")

    with_email = sum(1 for r in results if r.get('email'))
    with_website = sum(1 for r in results if r.get('website'))
    print(f"\n📊 Enrichment Results:")
    print(f"  Websites discovered: {with_website}/{len(results)}")
    print(f"  Emails found: {with_email}/{len(results)}")

    print(f"\n📁 Output saved to: {output_file}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == '--list':
        list_available_files()
    else:
        asyncio.run(import_mep_batch(sys.argv[1]))
