"""
Audit Logger - Writes to JSONL, CSV, updates registry

Business Purpose:
- Track every VLM call for investor reporting
- Build model registry with exact strings
- Calculate cost projections for 3-year pro forma
"""

import csv
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from .schema import AuditRecord, calculate_margin_comparison, project_annual_costs


class AuditLogger:
    """
    Centralized audit logging for VLM providers.

    Writes to:
    - test_runs.jsonl (one record per line)
    - test_runs.csv (flat export for spreadsheets)
    - model_registry.json (aggregated stats per model)
    """

    def __init__(
        self,
        repo_name: str = "vlm-ai-core",
        audit_dir: Optional[Path] = None,
    ):
        self.repo_name = repo_name

        # Default to project audit directory
        if audit_dir is None:
            self.audit_dir = Path(__file__).parent.parent.parent / "audit"
        else:
            self.audit_dir = audit_dir

        # Ensure directory exists
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        # File paths
        self.jsonl_path = self.audit_dir / "test_runs.jsonl"
        self.csv_path = self.audit_dir / "test_runs.csv"
        self.registry_path = self.audit_dir / "model_registry.json"

        # Get git info
        self.git_commit = self._get_git_commit()
        self.git_branch = self._get_git_branch()

    def _get_git_commit(self) -> Optional[str]:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.audit_dir.parent,
            )
            return result.stdout.strip()[:8] if result.returncode == 0 else None
        except Exception:
            return None

    def _get_git_branch(self) -> Optional[str]:
        """Get current git branch."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.audit_dir.parent,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def log(self, record: AuditRecord) -> None:
        """
        Log audit record to all outputs.

        Args:
            record: Complete AuditRecord to log
        """
        # Add git info
        record.metadata.git_commit = self.git_commit
        record.metadata.git_branch = self.git_branch
        record.metadata.repo_name = self.repo_name

        # Serialize record
        record_dict = record.model_dump(mode="json")

        # 1. Append to JSONL
        self._append_jsonl(record_dict)

        # 2. Append to CSV
        self._append_csv(record)

        # 3. Update model registry
        self._update_registry(record)

        # 4. Check cost alert
        if record.cost.cost_alert_triggered:
            self._cost_alert(record)

    def _append_jsonl(self, record_dict: dict) -> None:
        """Append record to JSONL file."""
        with open(self.jsonl_path, "a") as f:
            f.write(json.dumps(record_dict, default=str) + "\n")

    def _append_csv(self, record: AuditRecord) -> None:
        """Append flattened record to CSV."""
        flat = record.to_flat_dict()
        file_exists = self.csv_path.exists()

        with open(self.csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=flat.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(flat)

    def _update_registry(self, record: AuditRecord) -> None:
        """Update model registry with stats."""
        # Load or create registry
        if self.registry_path.exists():
            with open(self.registry_path) as f:
                registry = json.load(f)
        else:
            registry = {
                "models": {},
                "summary": {},
                "last_updated": None,
            }

        # Model key
        model_key = f"{record.model.provider.value}:{record.model.model_name}"

        # Initialize model entry if new
        if model_key not in registry["models"]:
            registry["models"][model_key] = {
                "provider": record.model.provider.value,
                "model_name": record.model.model_name,
                "model_tier": record.model.model_tier.value,
                "is_chinese_vlm": record.model.is_chinese_vlm,
                "first_seen": record.metadata.timestamp.isoformat(),
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "latencies_ms": [],
                "cost_per_call_avg": 0.0,
                "success_rate": 0.0,
                "trades_tested": [],
                "last_seen": None,
            }

        # Update stats
        entry = registry["models"][model_key]
        entry["total_calls"] += 1
        entry["last_seen"] = record.metadata.timestamp.isoformat()

        if record.accuracy.success:
            entry["successful_calls"] += 1
        else:
            entry["failed_calls"] += 1

        entry["total_cost_usd"] += record.cost.total_cost_usd
        entry["total_tokens"] += record.tokens.total_tokens
        entry["total_input_tokens"] += record.tokens.input_tokens
        entry["total_output_tokens"] += record.tokens.output_tokens

        # Keep last 1000 latencies for percentile calculation
        entry["latencies_ms"].append(record.latency.total_latency_ms)
        entry["latencies_ms"] = entry["latencies_ms"][-1000:]

        # Recalculate averages
        entry["cost_per_call_avg"] = entry["total_cost_usd"] / entry["total_calls"]
        entry["success_rate"] = entry["successful_calls"] / entry["total_calls"]

        # Track trades tested
        if record.metadata.trade and record.metadata.trade not in entry["trades_tested"]:
            entry["trades_tested"].append(record.metadata.trade)

        # Update summary
        registry["summary"] = self._calculate_summary(registry["models"])
        registry["last_updated"] = datetime.utcnow().isoformat()

        # Save
        with open(self.registry_path, "w") as f:
            json.dump(registry, f, indent=2)

    def _calculate_summary(self, models: dict) -> dict:
        """Calculate portfolio-level summary stats."""
        chinese_vlms = [m for m in models.values() if m["is_chinese_vlm"]]
        western_models = [m for m in models.values() if not m["is_chinese_vlm"]]

        chinese_avg_cost = (
            sum(m["cost_per_call_avg"] for m in chinese_vlms) / len(chinese_vlms)
            if chinese_vlms else 0
        )
        western_avg_cost = (
            sum(m["cost_per_call_avg"] for m in western_models) / len(western_models)
            if western_models else 0
        )

        chinese_success_rate = (
            sum(m["success_rate"] for m in chinese_vlms) / len(chinese_vlms)
            if chinese_vlms else 0
        )
        western_success_rate = (
            sum(m["success_rate"] for m in western_models) / len(western_models)
            if western_models else 0
        )

        return {
            "total_models_tested": len(models),
            "chinese_vlm_count": len(chinese_vlms),
            "western_model_count": len(western_models),
            "chinese_avg_cost_per_call": chinese_avg_cost,
            "western_avg_cost_per_call": western_avg_cost,
            "cost_savings_percent": (
                ((western_avg_cost - chinese_avg_cost) / western_avg_cost) * 100
                if western_avg_cost > 0 else 0
            ),
            "chinese_success_rate": chinese_success_rate,
            "western_success_rate": western_success_rate,
            "accuracy_parity": abs(chinese_success_rate - western_success_rate) < 0.05,
            # Margin analysis
            "margin_analysis": calculate_margin_comparison(
                chinese_vlm_cost=chinese_avg_cost,
                western_cost=western_avg_cost,
            ) if chinese_avg_cost > 0 and western_avg_cost > 0 else None,
            # 3-year projections
            "projections_chinese": project_annual_costs(chinese_avg_cost) if chinese_avg_cost > 0 else None,
            "projections_western": project_annual_costs(western_avg_cost) if western_avg_cost > 0 else None,
        }

    def _cost_alert(self, record: AuditRecord) -> None:
        """Print cost alert warning."""
        print(f"\n{'='*60}")
        print(f"⚠️  COST ALERT: ${record.cost.total_cost_usd:.4f}")
        print(f"   Model: {record.model.provider.value}/{record.model.model_name}")
        print(f"   Threshold: ${record.cost.cost_alert_threshold_usd:.4f}")
        print(f"{'='*60}\n")

    def get_session_summary(self, session_id: str) -> dict:
        """Get summary for a specific test session."""
        records = []

        if not self.jsonl_path.exists():
            return {"error": "No test runs found"}

        with open(self.jsonl_path) as f:
            for line in f:
                record = json.loads(line)
                if record.get("metadata", {}).get("session_id") == session_id:
                    records.append(record)

        if not records:
            return {"error": f"No records found for session {session_id}"}

        return {
            "session_id": session_id,
            "total_calls": len(records),
            "successful_calls": sum(1 for r in records if r["accuracy"]["success"]),
            "total_cost": sum(r["cost"]["total_cost_usd"] for r in records),
            "models_tested": list(set(r["model"]["model_name"] for r in records)),
            "trades_tested": list(set(r["metadata"].get("trade") for r in records if r["metadata"].get("trade"))),
        }

    def print_gate_summary(self, record: AuditRecord) -> None:
        """Print summary for interactive gate review."""
        print("\n" + "=" * 60)
        print("GATE REVIEW - Provider Test Results")
        print("=" * 60)
        print(record.summary())

        if record.cost.cost_savings_percent:
            print(f"💰 Cost Savings vs Claude: {record.cost.cost_savings_percent:.1f}%")
            print(f"   Your cost: ${record.cost.total_cost_usd:.6f}")
            print(f"   Claude cost: ${record.cost.western_baseline_cost_usd:.6f}")

        print("\n" + "-" * 60)
        print("Press Enter to approve and continue, or Ctrl+C to abort...")
