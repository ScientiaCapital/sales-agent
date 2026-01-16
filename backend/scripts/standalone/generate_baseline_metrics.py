#!/usr/bin/env python3
"""
Pre-Enrichment Baseline Metrics Report Generator
================================================

Generates comprehensive metrics snapshot BEFORE running enrichment on 2,951 unenriched dealer companies.

Usage:
    cd backend
    source ../venv/bin/activate
    python generate_baseline_metrics.py

Output:
    /backend/data/BASELINE_METRICS_20251215.md

Metrics Captured:
    1. Companies by source (original_source) with enrichment status breakdown
    2. Contact distribution by type (ATL vs BTL)
    3. ATL coverage: companies with 1+ ATL contacts
    4. Multi-ATL companies: companies with 2+ ATLs
    5. Enrichment status distribution
    6. Domain coverage
    7. Pipeline state distribution
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
from dotenv import load_dotenv
env_file = Path(__file__).parent.parent / '.env'
load_dotenv(env_file, override=True)

try:
    from supabase import create_client
except ImportError:
    logger.error("ERROR: pip install supabase")
    sys.exit(1)


class BaselineMetricsGenerator:
    def __init__(self):
        """Initialize Supabase client."""
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.service_key = os.getenv('SUPABASE_SERVICE_KEY')

        if not self.supabase_url or not self.service_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY required in .env")

        self.client = create_client(self.supabase_url, self.service_key)
        self.metrics = {}
        self.timestamp = datetime.now().isoformat()

        logger.info(f"Connected to Supabase: {self.supabase_url}")

    def execute_query(self, name: str, query: str) -> List[Dict[str, Any]]:
        """Execute SQL query and return results."""
        logger.info(f"Executing: {name}")
        try:
            response = self.client.rpc('execute_sql', {
                'query': query
            }).execute()
            logger.info(f"✓ {name}: {len(response.data)} rows")
            return response.data
        except Exception as e:
            logger.error(f"✗ {name} failed: {e}")
            # Try direct query as fallback
            try:
                from postgrest.exceptions import APIError
                response = self.client.from_('dim_companies').select('*').limit(0).execute()
                logger.info(f"Using fallback method for {name}")
                return []
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return []

    def get_companies_by_source(self) -> Dict[str, Any]:
        """Get companies grouped by original_source with enrichment status breakdown."""
        query = """
        SELECT
            COALESCE(original_source, 'unknown') as source,
            COUNT(*) as total_companies,
            COUNT(*) FILTER (WHERE enrichment_status IS NOT NULL) as enriched_count,
            COUNT(*) FILTER (WHERE enrichment_status IS NULL) as unenriched_count,
            ROUND(100.0 * COUNT(*) FILTER (WHERE enrichment_status IS NOT NULL) / COUNT(*), 2) as enrichment_pct
        FROM dim_companies
        GROUP BY original_source
        ORDER BY total_companies DESC;
        """

        try:
            response = self.client.from_('dim_companies').select(
                'original_source, enrichment_status'
            ).execute()

            data_by_source = {}
            for row in response.data:
                source = row.get('original_source') or 'unknown'
                status = row.get('enrichment_status')

                if source not in data_by_source:
                    data_by_source[source] = {'total': 0, 'enriched': 0, 'unenriched': 0}

                data_by_source[source]['total'] += 1
                if status is not None:
                    data_by_source[source]['enriched'] += 1
                else:
                    data_by_source[source]['unenriched'] += 1

            results = []
            for source in sorted(data_by_source.keys(), key=lambda x: data_by_source[x]['total'], reverse=True):
                stats = data_by_source[source]
                enrichment_pct = round(100.0 * stats['enriched'] / stats['total'], 2) if stats['total'] > 0 else 0
                results.append({
                    'source': source,
                    'total_companies': stats['total'],
                    'enriched_count': stats['enriched'],
                    'unenriched_count': stats['unenriched'],
                    'enrichment_pct': enrichment_pct
                })

            self.metrics['companies_by_source'] = results
            logger.info(f"✓ Companies by source: {len(results)} source groups")
            return results
        except Exception as e:
            logger.error(f"✗ get_companies_by_source failed: {e}")
            return []

    def get_contact_distribution(self) -> Dict[str, Any]:
        """Get contact distribution by type (ATL vs BTL)."""
        try:
            response = self.client.from_('dim_contacts').select(
                'is_atl'
            ).execute()

            atl_count = sum(1 for row in response.data if row.get('is_atl', False))
            btl_count = len(response.data) - atl_count
            total = len(response.data)

            results = [
                {
                    'contact_type': 'ATL (Above The Line)',
                    'total': atl_count,
                    'percentage': round(100.0 * atl_count / total, 2) if total > 0 else 0
                },
                {
                    'contact_type': 'BTL (Below The Line)',
                    'total': btl_count,
                    'percentage': round(100.0 * btl_count / total, 2) if total > 0 else 0
                }
            ]

            self.metrics['contact_distribution'] = {
                'total_contacts': total,
                'by_type': results
            }
            logger.info(f"✓ Contact distribution: {total} total ({atl_count} ATL, {btl_count} BTL)")
            return results
        except Exception as e:
            logger.error(f"✗ get_contact_distribution failed: {e}")
            return []

    def get_atl_coverage(self) -> Dict[str, Any]:
        """Get companies with 1+ ATL contacts."""
        try:
            # Get distinct companies with ATL
            response = self.client.from_('dim_contacts').select(
                'company_id'
            ).eq('is_atl', True).execute()

            companies_with_atl = len(set(row.get('company_id') for row in response.data))

            # Get total companies
            total_response = self.client.from_('dim_companies').select(
                'company_id', count='exact'
            ).execute()

            total_companies = total_response.count or len(total_response.data)

            coverage_pct = round(100.0 * companies_with_atl / total_companies, 2) if total_companies > 0 else 0

            result = {
                'companies_with_atl': companies_with_atl,
                'total_companies': total_companies,
                'atl_coverage_percentage': coverage_pct
            }

            self.metrics['atl_coverage'] = result
            logger.info(f"✓ ATL coverage: {companies_with_atl}/{total_companies} ({coverage_pct}%)")
            return result
        except Exception as e:
            logger.error(f"✗ get_atl_coverage failed: {e}")
            return {}

    def get_multi_atl_companies(self) -> Dict[str, Any]:
        """Get companies with 2+ ATL contacts."""
        try:
            response = self.client.from_('dim_contacts').select(
                'company_id'
            ).eq('is_atl', True).execute()

            # Count ATLs per company
            atl_by_company = {}
            for row in response.data:
                company_id = row.get('company_id')
                atl_by_company[company_id] = atl_by_company.get(company_id, 0) + 1

            # Filter for 2+
            multi_atl_companies = sum(1 for count in atl_by_company.values() if count >= 2)

            # Distribution
            distribution = {}
            for count in atl_by_company.values():
                if count >= 2:
                    key = f"{count}_atl"
                    distribution[key] = distribution.get(key, 0) + 1

            result = {
                'companies_with_2plus_atl': multi_atl_companies,
                'atl_count_distribution': distribution
            }

            self.metrics['multi_atl_companies'] = result
            logger.info(f"✓ Multi-ATL companies: {multi_atl_companies} companies with 2+ ATLs")
            return result
        except Exception as e:
            logger.error(f"✗ get_multi_atl_companies failed: {e}")
            return {}

    def get_enrichment_status_breakdown(self) -> List[Dict[str, Any]]:
        """Get enrichment status distribution."""
        try:
            response = self.client.from_('dim_companies').select(
                'enrichment_status'
            ).execute()

            status_counts = {}
            for row in response.data:
                status = row.get('enrichment_status') or 'unenriched'
                status_counts[status] = status_counts.get(status, 0) + 1

            total = sum(status_counts.values())
            results = []
            for status in sorted(status_counts.keys()):
                count = status_counts[status]
                results.append({
                    'status': status,
                    'count': count,
                    'percentage': round(100.0 * count / total, 2) if total > 0 else 0
                })

            self.metrics['enrichment_status'] = results
            logger.info(f"✓ Enrichment status: {len(results)} status types")
            return results
        except Exception as e:
            logger.error(f"✗ get_enrichment_status_breakdown failed: {e}")
            return []

    def get_domain_coverage(self) -> Dict[str, Any]:
        """Get companies with domain vs without."""
        try:
            response = self.client.from_('dim_companies').select(
                'domain'
            ).execute()

            with_domain = sum(1 for row in response.data if row.get('domain'))
            without_domain = len(response.data) - with_domain
            total = len(response.data)

            result = {
                'with_domain': with_domain,
                'without_domain': without_domain,
                'total': total,
                'domain_coverage_pct': round(100.0 * with_domain / total, 2) if total > 0 else 0
            }

            self.metrics['domain_coverage'] = result
            logger.info(f"✓ Domain coverage: {with_domain}/{total} ({result['domain_coverage_pct']}%)")
            return result
        except Exception as e:
            logger.error(f"✗ get_domain_coverage failed: {e}")
            return {}

    def get_pipeline_state_distribution(self) -> List[Dict[str, Any]]:
        """Get pipeline state distribution."""
        try:
            response = self.client.from_('dim_companies').select(
                'current_stage'
            ).execute()

            stage_counts = {}
            for row in response.data:
                stage = row.get('current_stage') or 'unknown'
                stage_counts[stage] = stage_counts.get(stage, 0) + 1

            total = sum(stage_counts.values())
            results = []
            for stage in sorted(stage_counts.keys(), key=lambda x: stage_counts[x], reverse=True):
                count = stage_counts[stage]
                results.append({
                    'stage': stage,
                    'count': count,
                    'percentage': round(100.0 * count / total, 2) if total > 0 else 0
                })

            self.metrics['pipeline_state'] = results
            logger.info(f"✓ Pipeline state: {len(results)} stage types")
            return results
        except Exception as e:
            logger.error(f"✗ get_pipeline_state_distribution failed: {e}")
            return []

    def generate_markdown_report(self) -> str:
        """Generate markdown report from metrics."""
        report = f"""# Pre-Enrichment Baseline Metrics Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

**Purpose:** Snapshot of database state BEFORE enrichment pipeline execution on 2,951+ unenriched dealer companies.

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Report Date | {datetime.now().strftime('%Y-%m-%d')} |
| Snapshot Type | Pre-Enrichment Baseline |
| Total Companies | {self.metrics.get('domain_coverage', {}).get('total', 'N/A')} |
| Total Contacts | {self.metrics.get('contact_distribution', {}).get('total_contacts', 'N/A')} |
| Domain Coverage | {self.metrics.get('domain_coverage', {}).get('domain_coverage_pct', 'N/A')}% |
| ATL Coverage | {self.metrics.get('atl_coverage', {}).get('atl_coverage_percentage', 'N/A')}% |

---

## 1. Companies by Source

Breakdown of companies by their original_source with enrichment status distribution.

"""

        if self.metrics.get('companies_by_source'):
            report += "| Source | Total | Enriched | Unenriched | Enrichment % |\n"
            report += "|--------|-------|----------|------------|-------------|\n"
            for row in self.metrics['companies_by_source']:
                report += f"| {row['source']} | {row['total_companies']} | {row['enriched_count']} | {row['unenriched_count']} | {row['enrichment_pct']}% |\n"
            report += "\n"

        report += """---

## 2. Contact Distribution (ATL vs BTL)

Breakdown of all contacts by type:
- **ATL (Above The Line):** Decision makers, executives, key stakeholders
- **BTL (Below The Line):** Individual contributors, technical staff

"""

        if self.metrics.get('contact_distribution'):
            report += f"**Total Contacts:** {self.metrics['contact_distribution'].get('total_contacts', 'N/A')}\n\n"
            report += "| Contact Type | Count | Percentage |\n"
            report += "|--------------|-------|------------|\n"
            for row in self.metrics['contact_distribution'].get('by_type', []):
                report += f"| {row['contact_type']} | {row['total']} | {row['percentage']}% |\n"
            report += "\n"

        report += """---

## 3. ATL Coverage Analysis

Coverage of companies with decision-maker level contacts.

"""

        if self.metrics.get('atl_coverage'):
            coverage = self.metrics['atl_coverage']
            report += f"| Metric | Value |\n"
            report += f"|--------|-------|\n"
            report += f"| Companies with 1+ ATL Contacts | {coverage.get('companies_with_atl', 'N/A')} |\n"
            report += f"| Total Companies | {coverage.get('total_companies', 'N/A')} |\n"
            report += f"| ATL Coverage % | {coverage.get('atl_coverage_percentage', 'N/A')}% |\n\n"

        report += """---

## 4. Multi-ATL Companies

Companies with 2 or more ATL contacts (high-value targets for priority outreach).

"""

        if self.metrics.get('multi_atl_companies'):
            multi = self.metrics['multi_atl_companies']
            report += f"| Metric | Value |\n"
            report += f"|--------|-------|\n"
            report += f"| Companies with 2+ ATL Contacts | {multi.get('companies_with_2plus_atl', 'N/A')} |\n"

            if multi.get('atl_count_distribution'):
                report += f"\n**ATL Count Distribution:**\n\n"
                for count_type, count_value in sorted(multi['atl_count_distribution'].items()):
                    report += f"- {count_type}: {count_value} companies\n"
            report += "\n"

        report += """---

## 5. Enrichment Status Distribution

Breakdown of enrichment progress across all companies.

"""

        if self.metrics.get('enrichment_status'):
            report += "| Status | Count | Percentage |\n"
            report += "|--------|-------|------------|\n"
            for row in self.metrics['enrichment_status']:
                report += f"| {row['status']} | {row['count']} | {row['percentage']}% |\n"
            report += "\n"

        report += """**Status Definitions:**
- `unenriched` - No enrichment attempt yet
- `found_contacts` - Team page found with contacts extracted
- `found_page_no_contacts` - Team page found but no contacts extracted
- `no_team_page` - No team page discovered
- `needs_js_render` - Explicitly flagged for Browserbase JS rendering

---

## 6. Domain Coverage

Analysis of domain data availability.

"""

        if self.metrics.get('domain_coverage'):
            domain = self.metrics['domain_coverage']
            report += f"| Metric | Value |\n"
            report += f"|--------|-------|\n"
            report += f"| Companies with Domain | {domain.get('with_domain', 'N/A')} |\n"
            report += f"| Companies without Domain | {domain.get('without_domain', 'N/A')} |\n"
            report += f"| Total Companies | {domain.get('total', 'N/A')} |\n"
            report += f"| Domain Coverage % | {domain.get('domain_coverage_pct', 'N/A')}% |\n\n"

        report += """---

## 7. Pipeline State Distribution

Current distribution of companies across pipeline stages.

"""

        if self.metrics.get('pipeline_state'):
            report += "| Stage | Count | Percentage |\n"
            report += "|-------|-------|------------|\n"
            for row in self.metrics['pipeline_state']:
                report += f"| {row['stage']} | {row['count']} | {row['percentage']}% |\n"
            report += "\n"

        report += """---

## Next Steps

1. **Run Enrichment Pipeline**
   ```bash
   cd backend
   source ../venv/bin/activate
   python run_enrichment.py
   ```

2. **Monitor Progress**
   ```bash
   python live_enrichment_monitor.py
   ```

3. **Generate Post-Enrichment Report**
   After enrichment completes, run this script again with a different timestamp to capture final metrics.

4. **Compare Results**
   Use the before/after metrics to measure:
   - Enrichment success rate
   - Contact discovery efficiency
   - ATL coverage improvements
   - Quality of discovered contacts

---

## Technical Details

**Database Schema:**
- `dim_companies` - Master company dimension table
- `dim_contacts` - Contact records (many-to-one with companies)
- Fields tracked: `original_source`, `enrichment_status`, `is_atl`, `domain`, `current_stage`

**Query Methodology:**
- All queries are read-only, point-in-time snapshots
- Executed against Supabase PostgreSQL backend
- Service role authentication used for full table access

**Report Generation Date:** {datetime.now().isoformat()}
"""

        return report

    def save_report(self, report: str):
        """Save report to file."""
        output_dir = Path(__file__).parent / 'data'
        output_dir.mkdir(exist_ok=True, parents=True)

        timestamp = datetime.now().strftime('%Y%m%d')
        filename = output_dir / f'BASELINE_METRICS_{timestamp}.md'

        filename.write_text(report, encoding='utf-8')
        logger.info(f"✓ Report saved to: {filename}")

        # Also save JSON for programmatic access
        json_filename = output_dir / f'BASELINE_METRICS_{timestamp}.json'
        with open(json_filename, 'w') as f:
            json.dump({
                'timestamp': self.timestamp,
                'metrics': self.metrics
            }, f, indent=2, default=str)
        logger.info(f"✓ JSON saved to: {json_filename}")

        return filename

    def run(self):
        """Execute all metrics generation."""
        logger.info("Starting baseline metrics generation...")

        try:
            # Fetch all metrics
            self.get_companies_by_source()
            self.get_contact_distribution()
            self.get_atl_coverage()
            self.get_multi_atl_companies()
            self.get_enrichment_status_breakdown()
            self.get_domain_coverage()
            self.get_pipeline_state_distribution()

            # Generate report
            report = self.generate_markdown_report()

            # Save to file
            filename = self.save_report(report)

            logger.info("✓ Baseline metrics generation complete!")
            logger.info(f"\nReport saved to: {filename}")

            # Print summary
            print("\n" + "="*70)
            print("BASELINE METRICS GENERATION COMPLETE")
            print("="*70)
            print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            if self.metrics.get('domain_coverage'):
                print(f"Total Companies: {self.metrics['domain_coverage']['total']}")
                print(f"Domain Coverage: {self.metrics['domain_coverage']['domain_coverage_pct']}%")

            if self.metrics.get('contact_distribution'):
                print(f"Total Contacts: {self.metrics['contact_distribution']['total_contacts']}")
                print(f"  - ATL: {self.metrics['contact_distribution']['by_type'][0]['total']}")
                print(f"  - BTL: {self.metrics['contact_distribution']['by_type'][1]['total']}")

            if self.metrics.get('atl_coverage'):
                print(f"ATL Coverage: {self.metrics['atl_coverage']['atl_coverage_percentage']}%")

            print(f"\nReport: {filename}")
            print("="*70 + "\n")

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)


if __name__ == '__main__':
    generator = BaselineMetricsGenerator()
    generator.run()
