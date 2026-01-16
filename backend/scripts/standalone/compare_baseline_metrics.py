#!/usr/bin/env python3
"""
Baseline Metrics Comparison Tool
=================================

Compares pre-enrichment and post-enrichment baseline metrics to measure
enrichment pipeline effectiveness.

Usage:
    python compare_baseline_metrics.py [before_date] [after_date]

    Example:
    python compare_baseline_metrics.py 20251215 20251216

    Or with file paths:
    python compare_baseline_metrics.py \
        data/BASELINE_METRICS_20251215.json \
        data/BASELINE_METRICS_20251216.json

Output:
    - Console comparison report
    - CSV export: data/BASELINE_COMPARISON_YYYYMMDD.csv
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BaselineComparator:
    def __init__(self):
        self.before_data = None
        self.after_data = None
        self.comparison_results = {}

    def load_metrics(self, filepath: str) -> Dict[str, Any]:
        """Load metrics from JSON file."""
        path = Path(filepath)

        # If given a date string like "20251215", find the file
        if not path.exists() and len(filepath) == 8 and filepath.isdigit():
            data_dir = Path(__file__).parent / 'data'
            path = data_dir / f'BASELINE_METRICS_{filepath}.json'

        if not path.exists():
            raise FileNotFoundError(f"Metrics file not found: {path}")

        try:
            with open(path, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded metrics from: {path}")
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}")

    def safe_get(self, data: Dict, key: str, default=None):
        """Safely get value from metrics dict."""
        if not data or 'metrics' not in data:
            return default
        return data['metrics'].get(key, default)

    def calculate_delta(self, before: Any, after: Any, as_percentage=False) -> Tuple[str, str]:
        """Calculate change and percentage."""
        if before is None or after is None:
            return "N/A", "N/A"

        try:
            delta = after - before
            if before == 0:
                pct = "N/A" if delta == 0 else "∞"
            else:
                pct = f"{(delta / before * 100):.1f}%"
            return f"{delta:+.0f}", pct
        except (TypeError, ZeroDivisionError):
            return "N/A", "N/A"

    def compare_domain_coverage(self):
        """Compare domain coverage metrics."""
        before = self.safe_get(self.before_data, 'domain_coverage', {})
        after = self.safe_get(self.after_data, 'domain_coverage', {})

        results = {
            'Companies with Domain': (
                before.get('with_domain', 'N/A'),
                after.get('with_domain', 'N/A')
            ),
            'Companies without Domain': (
                before.get('without_domain', 'N/A'),
                after.get('without_domain', 'N/A')
            ),
            'Total Companies': (
                before.get('total', 'N/A'),
                after.get('total', 'N/A')
            ),
            'Domain Coverage %': (
                before.get('domain_coverage_pct', 'N/A'),
                after.get('domain_coverage_pct', 'N/A')
            ),
        }

        self.comparison_results['domain_coverage'] = results
        return results

    def compare_atl_coverage(self):
        """Compare ATL coverage metrics."""
        before = self.safe_get(self.before_data, 'atl_coverage', {})
        after = self.safe_get(self.after_data, 'atl_coverage', {})

        before_atl = before.get('companies_with_atl', 0)
        after_atl = after.get('companies_with_atl', 0)
        before_total = before.get('total_companies', 1)
        after_total = after.get('total_companies', 1)

        results = {
            'Companies with ATL': (
                before_atl,
                after_atl,
                self.calculate_delta(before_atl, after_atl)[0],
                self.calculate_delta(before_atl, after_atl)[1]
            ),
            'ATL Coverage %': (
                before.get('atl_coverage_percentage', 'N/A'),
                after.get('atl_coverage_percentage', 'N/A'),
                *self.calculate_delta(
                    before.get('atl_coverage_percentage'),
                    after.get('atl_coverage_percentage')
                )
            ),
        }

        self.comparison_results['atl_coverage'] = results
        return results

    def compare_contact_distribution(self):
        """Compare contact distribution."""
        before = self.safe_get(self.before_data, 'contact_distribution', {})
        after = self.safe_get(self.after_data, 'contact_distribution', {})

        before_total = before.get('total_contacts', 0)
        after_total = after.get('total_contacts', 0)

        before_atl = 0
        after_atl = 0

        if before.get('by_type'):
            before_atl = before['by_type'][0].get('total', 0)
        if after.get('by_type'):
            after_atl = after['by_type'][0].get('total', 0)

        results = {
            'Total Contacts': (
                before_total,
                after_total,
                *self.calculate_delta(before_total, after_total)
            ),
            'ATL Contacts': (
                before_atl,
                after_atl,
                *self.calculate_delta(before_atl, after_atl)
            ),
            'BTL Contacts': (
                before_total - before_atl,
                after_total - after_atl,
                *self.calculate_delta(before_total - before_atl, after_total - after_atl)
            ),
        }

        self.comparison_results['contact_distribution'] = results
        return results

    def compare_multi_atl(self):
        """Compare multi-ATL companies."""
        before = self.safe_get(self.before_data, 'multi_atl_companies', {})
        after = self.safe_get(self.after_data, 'multi_atl_companies', {})

        before_count = before.get('companies_with_2plus_atl', 0)
        after_count = after.get('companies_with_2plus_atl', 0)

        results = {
            'Companies with 2+ ATLs': (
                before_count,
                after_count,
                *self.calculate_delta(before_count, after_count)
            ),
        }

        self.comparison_results['multi_atl'] = results
        return results

    def compare_enrichment_status(self):
        """Compare enrichment status distribution."""
        before_data = self.safe_get(self.before_data, 'enrichment_status', [])
        after_data = self.safe_get(self.after_data, 'enrichment_status', [])

        before_map = {item['status']: item['count'] for item in before_data}
        after_map = {item['status']: item['count'] for item in after_data}

        # Get all statuses
        all_statuses = set(before_map.keys()) | set(after_map.keys())

        results = {}
        for status in sorted(all_statuses):
            before_count = before_map.get(status, 0)
            after_count = after_map.get(status, 0)
            results[f"Status: {status}"] = (
                before_count,
                after_count,
                *self.calculate_delta(before_count, after_count)
            )

        self.comparison_results['enrichment_status'] = results
        return results

    def print_comparison_report(self):
        """Print formatted comparison report."""
        print("\n" + "=" * 100)
        print("BASELINE METRICS COMPARISON REPORT")
        print("=" * 100)

        if self.before_data and self.after_data:
            before_ts = self.before_data.get('timestamp', 'Unknown').split('T')[0]
            after_ts = self.after_data.get('timestamp', 'Unknown').split('T')[0]
            print(f"\nBefore: {before_ts}  →  After: {after_ts}")

        print("\n" + "-" * 100)
        print("DOMAIN COVERAGE")
        print("-" * 100)
        self._print_section('domain_coverage')

        print("\n" + "-" * 100)
        print("ATL COVERAGE (Decision Makers)")
        print("-" * 100)
        self._print_section('atl_coverage')

        print("\n" + "-" * 100)
        print("CONTACT DISTRIBUTION")
        print("-" * 100)
        self._print_section('contact_distribution')

        print("\n" + "-" * 100)
        print("MULTI-ATL COMPANIES (2+ Decision Makers)")
        print("-" * 100)
        self._print_section('multi_atl')

        print("\n" + "-" * 100)
        print("ENRICHMENT STATUS BREAKDOWN")
        print("-" * 100)
        self._print_section('enrichment_status')

        print("\n" + "=" * 100 + "\n")

    def _print_section(self, section_name: str):
        """Print a comparison section."""
        if section_name not in self.comparison_results:
            return

        data = self.comparison_results[section_name]

        # Determine if we have delta columns
        has_delta = False
        for key, values in data.items():
            if len(values) > 2:
                has_delta = True
                break

        if has_delta:
            print(f"{'Metric':<40} {'Before':>15} {'After':>15} {'Delta':>10} {'%':>10}")
            print("-" * 90)
            for metric, values in data.items():
                before = values[0]
                after = values[1]
                delta = values[2] if len(values) > 2 else ""
                pct = values[3] if len(values) > 3 else ""

                # Format values
                before_str = f"{before:,.0f}" if isinstance(before, (int, float)) else str(before)
                after_str = f"{after:,.0f}" if isinstance(after, (int, float)) else str(after)

                print(f"{metric:<40} {before_str:>15} {after_str:>15} {delta:>10} {pct:>10}")
        else:
            print(f"{'Metric':<40} {'Before':>15} {'After':>15}")
            print("-" * 70)
            for metric, values in data.items():
                before = values[0]
                after = values[1]

                before_str = f"{before:,.0f}" if isinstance(before, (int, float)) else str(before)
                after_str = f"{after:,.0f}" if isinstance(after, (int, float)) else str(after)

                print(f"{metric:<40} {before_str:>15} {after_str:>15}")

    def calculate_success_metrics(self) -> Dict[str, float]:
        """Calculate enrichment success metrics."""
        before_domain = self.safe_get(self.before_data, 'domain_coverage', {})
        after_domain = self.safe_get(self.after_data, 'domain_coverage', {})

        before_total = before_domain.get('total', 0)
        after_total = after_domain.get('total', 0)

        # Calculate success rate (new contacts divided by originally unenriched)
        before_contacts = self.safe_get(self.before_data, 'contact_distribution', {}).get('total_contacts', 0)
        after_contacts = self.safe_get(self.after_data, 'contact_distribution', {}).get('total_contacts', 0)
        new_contacts = after_contacts - before_contacts

        before_atl = self.safe_get(self.before_data, 'atl_coverage', {}).get('companies_with_atl', 0)
        after_atl = self.safe_get(self.after_data, 'atl_coverage', {}).get('companies_with_atl', 0)

        return {
            'new_contacts_discovered': new_contacts,
            'atl_improvement_percentage': after_atl - before_atl,
            'contact_growth_rate': (after_contacts / before_contacts - 1) * 100 if before_contacts > 0 else 0,
        }

    def save_csv_report(self):
        """Save comparison to CSV."""
        import csv
        from datetime import datetime

        timestamp = datetime.now().strftime('%Y%m%d')
        output_path = Path(__file__).parent / 'data' / f'BASELINE_COMPARISON_{timestamp}.csv'
        output_path.parent.mkdir(exist_ok=True, parents=True)

        try:
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow(['Metric', 'Before', 'After', 'Delta', 'Percentage Change'])

                # Write all comparison data
                for section_name, data in self.comparison_results.items():
                    writer.writerow([])  # Blank row
                    writer.writerow([section_name.upper()])

                    for metric, values in data.items():
                        if len(values) == 4:
                            writer.writerow([metric, values[0], values[1], values[2], values[3]])
                        else:
                            writer.writerow([metric, values[0], values[1]])

            logger.info(f"✓ CSV report saved to: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"✗ Failed to save CSV: {e}")
            return None

    def run(self, before_path: str, after_path: str):
        """Run comparison."""
        try:
            logger.info(f"Loading baseline metrics...")
            self.before_data = self.load_metrics(before_path)
            self.after_data = self.load_metrics(after_path)

            logger.info(f"Comparing metrics...")
            self.compare_domain_coverage()
            self.compare_atl_coverage()
            self.compare_contact_distribution()
            self.compare_multi_atl()
            self.compare_enrichment_status()

            self.print_comparison_report()

            # Calculate and print success metrics
            success = self.calculate_success_metrics()
            print("\nSUCCESS METRICS")
            print("-" * 50)
            print(f"New Contacts Discovered: {success['new_contacts_discovered']:,.0f}")
            print(f"ATL Improvement: {success['atl_improvement_percentage']:+.0f} companies")
            print(f"Contact Growth Rate: {success['contact_growth_rate']:+.1f}%")
            print()

            # Save CSV
            self.save_csv_report()

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nUsage Examples:")
        print("  python compare_baseline_metrics.py 20251215 20251216")
        print("  python compare_baseline_metrics.py \\")
        print("    data/BASELINE_METRICS_20251215.json \\")
        print("    data/BASELINE_METRICS_20251216.json")
        sys.exit(1)

    before_path = sys.argv[1]
    after_path = sys.argv[2]

    comparator = BaselineComparator()
    comparator.run(before_path, after_path)


if __name__ == '__main__':
    main()
