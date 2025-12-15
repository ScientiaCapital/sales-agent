"""
Audit Report Exporters - Investor-Grade Reports

Generates:
- AUDIT_REPORT.md - Executive summary for investor demos
- model_registry.csv - Flat export for spreadsheets
- summary_stats.json - Aggregated metrics

Business Purpose:
- Proves Chinese VLM cost arbitrage vs Western models
- Validates accuracy parity for 3-year pro forma
- Portfolio-ready documentation for Scientia Capital
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any, Optional

from .schema import (
    AuditRecord,
    OPENROUTER_MODELS,
    ANTHROPIC_MODELS,
    GEMINI_MODELS,
    ALL_MODELS,
    ModelTier,
    calculate_margin_comparison,
    project_annual_costs,
)


class AuditReportExporter:
    """
    Generates investor-ready reports from audit data.

    Output files:
    - AUDIT_REPORT.md - Markdown report for presentations
    - model_registry.csv - Flat export for spreadsheets
    - summary_stats.json - JSON summary for dashboards
    """

    def __init__(self, audit_dir: Optional[Path] = None):
        if audit_dir is None:
            self.audit_dir = Path(__file__).parent.parent.parent / "audit"
        else:
            self.audit_dir = audit_dir

        self.audit_dir.mkdir(parents=True, exist_ok=True)

        # Input files
        self.jsonl_path = self.audit_dir / "test_runs.jsonl"
        self.registry_path = self.audit_dir / "model_registry.json"

        # Output files
        self.report_path = self.audit_dir / "AUDIT_REPORT.md"
        self.registry_csv_path = self.audit_dir / "model_registry.csv"
        self.summary_path = self.audit_dir / "summary_stats.json"

    def load_records(self) -> list[dict[str, Any]]:
        """Load all audit records from JSONL file."""
        records = []
        if self.jsonl_path.exists():
            with open(self.jsonl_path) as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
        return records

    def load_registry(self) -> dict[str, Any]:
        """Load model registry."""
        if self.registry_path.exists():
            with open(self.registry_path) as f:
                return json.load(f)
        return {"models": {}, "summary": {}}

    def calculate_stats(self, records: list[dict]) -> dict[str, Any]:
        """Calculate comprehensive statistics from records."""
        if not records:
            return {"error": "No records found"}

        # Separate by provider type
        chinese_records = [r for r in records if r.get("model", {}).get("is_chinese_vlm", False)]
        western_records = [r for r in records if not r.get("model", {}).get("is_chinese_vlm", False)]

        # Cost stats
        chinese_costs = [r["cost"]["total_cost_usd"] for r in chinese_records if r["cost"]["total_cost_usd"] > 0]
        western_costs = [r["cost"]["total_cost_usd"] for r in western_records if r["cost"]["total_cost_usd"] > 0]

        # Latency stats
        chinese_latencies = [r["latency"]["total_latency_ms"] for r in chinese_records]
        western_latencies = [r["latency"]["total_latency_ms"] for r in western_records]

        # Success rates
        chinese_success = sum(1 for r in chinese_records if r["accuracy"]["success"])
        western_success = sum(1 for r in western_records if r["accuracy"]["success"])

        stats = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_records": len(records),

            # Chinese VLMs
            "chinese": {
                "total_tests": len(chinese_records),
                "successful_tests": chinese_success,
                "success_rate": chinese_success / len(chinese_records) if chinese_records else 0,
                "total_cost": sum(chinese_costs),
                "avg_cost": mean(chinese_costs) if chinese_costs else 0,
                "min_cost": min(chinese_costs) if chinese_costs else 0,
                "max_cost": max(chinese_costs) if chinese_costs else 0,
                "avg_latency_ms": mean(chinese_latencies) if chinese_latencies else 0,
                "p50_latency_ms": median(sorted(chinese_latencies)) if chinese_latencies else 0,
                "p95_latency_ms": self._percentile(chinese_latencies, 95) if chinese_latencies else 0,
            },

            # Western Models
            "western": {
                "total_tests": len(western_records),
                "successful_tests": western_success,
                "success_rate": western_success / len(western_records) if western_records else 0,
                "total_cost": sum(western_costs),
                "avg_cost": mean(western_costs) if western_costs else 0,
                "min_cost": min(western_costs) if western_costs else 0,
                "max_cost": max(western_costs) if western_costs else 0,
                "avg_latency_ms": mean(western_latencies) if western_latencies else 0,
                "p50_latency_ms": median(sorted(western_latencies)) if western_latencies else 0,
                "p95_latency_ms": self._percentile(western_latencies, 95) if western_latencies else 0,
            },

            # Trades tested
            "trades_tested": list(set(
                r["metadata"].get("trade") for r in records
                if r["metadata"].get("trade")
            )),

            # Models tested
            "models_tested": list(set(r["model"]["model_name"] for r in records)),
        }

        # Calculate cost comparison
        if chinese_costs and western_costs:
            chinese_avg = mean(chinese_costs)
            western_avg = mean(western_costs)
            stats["comparison"] = {
                "cost_ratio": western_avg / chinese_avg if chinese_avg > 0 else 0,
                "cost_savings_percent": ((western_avg - chinese_avg) / western_avg) * 100 if western_avg > 0 else 0,
                "chinese_cheaper_by": western_avg - chinese_avg,
                "accuracy_parity": abs(stats["chinese"]["success_rate"] - stats["western"]["success_rate"]) < 0.05,
            }

            # 3-year projections (100k calls/month)
            stats["projections"] = {
                "chinese_3_year": project_annual_costs(chinese_avg, 100_000),
                "western_3_year": project_annual_costs(western_avg, 100_000),
            }

            # Margin analysis
            stats["margin"] = calculate_margin_comparison(
                chinese_vlm_cost=chinese_avg,
                western_cost=western_avg,
                our_price_to_customer=0.05,  # $0.05/call to customers
            )

        return stats

    def _percentile(self, data: list[float], p: int) -> float:
        """Calculate percentile."""
        if not data:
            return 0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * (p / 100)
        f = int(k)
        c = f + 1 if f < len(sorted_data) - 1 else f
        return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)

    def generate_report(self) -> str:
        """Generate investor-ready markdown report."""
        records = self.load_records()
        registry = self.load_registry()
        stats = self.calculate_stats(records)

        if "error" in stats:
            return f"# Audit Report\n\n**Error:** {stats['error']}"

        report = []

        # Header
        report.append("# Scientia Capital VLM Audit Report")
        report.append("")
        report.append(f"**Generated:** {stats['generated_at']}")
        report.append(f"**Repository:** vlm-ai-core")
        report.append(f"**Total Tests:** {stats['total_records']}")
        report.append("")

        # Executive Summary
        report.append("## Executive Summary")
        report.append("")

        if "comparison" in stats:
            report.append(f"**Key Finding:** Chinese VLMs are **{stats['comparison']['cost_ratio']:.1f}x cheaper** than Western models")
            report.append(f"- Cost Savings: **{stats['comparison']['cost_savings_percent']:.1f}%**")
            report.append(f"- Accuracy Parity: **{'YES' if stats['comparison']['accuracy_parity'] else 'NO'}**")
            report.append("")

            # Margin Analysis
            if "margin" in stats:
                margin = stats["margin"]
                report.append("### Margin Impact (@ $0.05/call to customer)")
                report.append("")
                report.append(f"| Metric | Chinese VLM | Western Model |")
                report.append(f"|--------|-------------|---------------|")
                report.append(f"| Cost per call | ${margin['chinese_vlm_cost']:.6f} | ${margin['western_cost']:.6f} |")
                report.append(f"| Gross margin | ${margin['chinese_margin']:.4f} | ${margin['western_margin']:.4f} |")
                report.append(f"| Margin % | {margin['chinese_margin_percent']:.1f}% | {margin['western_margin_percent']:.1f}% |")
                report.append("")

        # Provider Comparison
        report.append("## Provider Comparison")
        report.append("")
        report.append("| Provider Type | Tests | Success Rate | Avg Cost | Avg Latency |")
        report.append("|---------------|-------|--------------|----------|-------------|")

        cn = stats["chinese"]
        report.append(f"| Chinese VLMs | {cn['total_tests']} | {cn['success_rate']*100:.1f}% | ${cn['avg_cost']:.6f} | {cn['avg_latency_ms']:.0f}ms |")

        we = stats["western"]
        report.append(f"| Western Models | {we['total_tests']} | {we['success_rate']*100:.1f}% | ${we['avg_cost']:.6f} | {we['avg_latency_ms']:.0f}ms |")
        report.append("")

        # Model Registry
        report.append("## Model Registry")
        report.append("")
        report.append("### Verified Model Strings (2025-12-13)")
        report.append("")

        if registry.get("models"):
            report.append("| Provider | Model | Tier | Calls | Success Rate | Avg Cost |")
            report.append("|----------|-------|------|-------|--------------|----------|")

            for model_key, model_data in registry["models"].items():
                provider = model_data.get("provider", "unknown")
                model_name = model_data.get("model_name", model_key)
                tier = model_data.get("model_tier", "standard")
                calls = model_data.get("total_calls", 0)
                success = model_data.get("success_rate", 0) * 100
                avg_cost = model_data.get("cost_per_call_avg", 0)

                report.append(f"| {provider} | `{model_name}` | {tier} | {calls} | {success:.1f}% | ${avg_cost:.6f} |")
            report.append("")

        # 3-Year Projections
        if "projections" in stats:
            report.append("## 3-Year Cost Projections")
            report.append("")
            report.append("Assumes 100,000 calls/month with 50% YoY growth")
            report.append("")

            cn_proj = stats["projections"]["chinese_3_year"]
            we_proj = stats["projections"]["western_3_year"]

            report.append("| Year | Chinese VLM Cost | Western Cost | Savings |")
            report.append("|------|------------------|--------------|---------|")

            for i, key in enumerate(["year_1_cost", "year_2_cost", "year_3_cost"], 1):
                cn_cost = cn_proj[key]
                we_cost = we_proj[key]
                savings = we_cost - cn_cost
                report.append(f"| Year {i} | ${cn_cost:,.2f} | ${we_cost:,.2f} | ${savings:,.2f} |")

            total_cn = cn_proj["total_3_year_cost"]
            total_we = we_proj["total_3_year_cost"]
            total_savings = total_we - total_cn
            report.append(f"| **Total** | **${total_cn:,.2f}** | **${total_we:,.2f}** | **${total_savings:,.2f}** |")
            report.append("")

        # Trades Tested
        report.append("## Trades Tested")
        report.append("")
        for trade in stats.get("trades_tested", []):
            report.append(f"- {trade.upper()}")
        report.append("")

        # Technical Appendix
        report.append("## Technical Appendix")
        report.append("")
        report.append("### Model Pricing Reference (per 1M tokens)")
        report.append("")
        report.append("| Model | Input | Output | Vision | Context |")
        report.append("|-------|-------|--------|--------|---------|")

        for model_name, config in ALL_MODELS.items():
            input_price = config.get("cost_per_1m_input", 0)
            output_price = config.get("cost_per_1m_output", 0)
            vision = "Yes" if config.get("vision", False) else "No"
            context = config.get("context_length", 0)
            report.append(f"| `{model_name}` | ${input_price:.2f} | ${output_price:.2f} | {vision} | {context:,} |")
        report.append("")

        # Footer
        report.append("---")
        report.append("")
        report.append("*Generated by Scientia Capital VLM Audit Infrastructure*")
        report.append(f"*Audit files: `{self.audit_dir}`*")

        return "\n".join(report)

    def export_registry_csv(self) -> None:
        """Export model registry to CSV."""
        registry = self.load_registry()

        if not registry.get("models"):
            return

        # Flatten model entries for CSV
        rows = []
        for model_key, model_data in registry["models"].items():
            row = {
                "model_key": model_key,
                "provider": model_data.get("provider", ""),
                "model_name": model_data.get("model_name", ""),
                "model_tier": model_data.get("model_tier", ""),
                "is_chinese_vlm": model_data.get("is_chinese_vlm", False),
                "total_calls": model_data.get("total_calls", 0),
                "successful_calls": model_data.get("successful_calls", 0),
                "failed_calls": model_data.get("failed_calls", 0),
                "success_rate": model_data.get("success_rate", 0),
                "total_cost_usd": model_data.get("total_cost_usd", 0),
                "cost_per_call_avg": model_data.get("cost_per_call_avg", 0),
                "total_tokens": model_data.get("total_tokens", 0),
                "trades_tested": ",".join(model_data.get("trades_tested", [])),
                "first_seen": model_data.get("first_seen", ""),
                "last_seen": model_data.get("last_seen", ""),
            }
            rows.append(row)

        if rows:
            with open(self.registry_csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

    def export_summary_json(self) -> None:
        """Export summary statistics to JSON."""
        records = self.load_records()
        stats = self.calculate_stats(records)

        with open(self.summary_path, "w") as f:
            json.dump(stats, f, indent=2, default=str)

    def export_all(self) -> dict[str, Path]:
        """Generate all export files."""
        # Generate markdown report
        report = self.generate_report()
        with open(self.report_path, "w") as f:
            f.write(report)

        # Export registry CSV
        self.export_registry_csv()

        # Export summary JSON
        self.export_summary_json()

        return {
            "report": self.report_path,
            "registry_csv": self.registry_csv_path,
            "summary_json": self.summary_path,
        }


def generate_audit_report(audit_dir: Optional[Path] = None) -> Path:
    """
    Convenience function to generate investor-ready audit report.

    Returns path to generated AUDIT_REPORT.md
    """
    exporter = AuditReportExporter(audit_dir)
    paths = exporter.export_all()

    print(f"\n{'='*60}")
    print("AUDIT REPORT GENERATED")
    print("="*60)
    print(f"  Report: {paths['report']}")
    print(f"  Registry CSV: {paths['registry_csv']}")
    print(f"  Summary JSON: {paths['summary_json']}")
    print("="*60 + "\n")

    return paths["report"]


if __name__ == "__main__":
    # Generate report when run directly
    generate_audit_report()
