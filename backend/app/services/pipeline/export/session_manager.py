"""Session management for pipeline exports."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages pipeline session files and export tracking."""

    def __init__(self, base_dir: Optional[Path] = None):
        self._session_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self._output_dir = base_dir or self._get_default_output_dir()
        self._master_csv_path: Optional[Path] = None
        self._master_json_path: Optional[Path] = None
        self._log_path: Optional[Path] = None
        self._exported_leads: List[Dict[str, Any]] = []
        self._filtered_emails: List[Dict[str, Any]] = []

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def master_csv_path(self) -> Optional[Path]:
        return self._master_csv_path

    @property
    def exported_leads(self) -> List[Dict[str, Any]]:
        return self._exported_leads

    @property
    def filtered_emails(self) -> List[Dict[str, Any]]:
        return self._filtered_emails

    def _get_default_output_dir(self) -> Path:
        """Get absolute path to output directory."""
        base_dir = Path(__file__).parent.parent.parent.parent.parent
        output_dir = base_dir / "data" / "final_enrichment_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def init_session_files(self) -> None:
        """Initialize session files for master export (CSV, JSON, log)."""
        if self._master_csv_path is None:
            self._master_csv_path = self._output_dir / f"MASTER_enriched_leads_{self._session_id}.csv"
            self._master_json_path = self._output_dir / f"enrichment_log_{self._session_id}.json"
            self._log_path = self._output_dir / f"pipeline_{self._session_id}.log"

            with open(self._log_path, 'w') as f:
                f.write(f"Pipeline Session Started: {self._session_id}\n")
                f.write(f"Output Directory: {self._output_dir}\n")
                f.write("-" * 50 + "\n")

            logger.info(f"Session files initialized: {self._session_id}")

    def log_to_file(self, message: str) -> None:
        """Append message to session log file."""
        if self._log_path:
            with open(self._log_path, 'a') as f:
                timestamp = datetime.now().strftime("%H:%M:%S")
                f.write(f"[{timestamp}] {message}\n")

    def add_exported_lead(self, lead: Dict[str, Any]) -> None:
        """Track an exported lead."""
        self._exported_leads.append(lead)

    def add_filtered_email(self, company: str, email: str, reason: str) -> None:
        """Track a filtered email."""
        self._filtered_emails.append({
            "company": company,
            "email": email,
            "reason": reason
        })

    def finalize_export(self) -> Dict[str, Any]:
        """Finalize the session export by writing JSON summary."""
        if not self._exported_leads:
            return {"status": "no_leads_exported"}

        summary = {
            "session_id": self._session_id,
            "timestamp": datetime.now().isoformat(),
            "total_leads": len(self._exported_leads),
            "valid_emails": sum(1 for lead in self._exported_leads if lead.get("email")),
            "filtered_emails": len(self._filtered_emails),
            "atl_leads": sum(1 for lead in self._exported_leads if lead.get("is_atl")),
            "btl_leads": sum(1 for lead in self._exported_leads if not lead.get("is_atl")),
            "files": {
                "csv": str(self._master_csv_path),
                "json": str(self._master_json_path),
                "log": str(self._log_path)
            },
            "leads": self._exported_leads,
            "filtered_bad_emails": self._filtered_emails
        }

        if self._master_json_path:
            with open(self._master_json_path, 'w') as f:
                json.dump(summary, f, indent=2, default=str)

        self.log_to_file(f"Session Complete: {len(self._exported_leads)} leads exported")
        self.log_to_file(f"Valid emails: {summary['valid_emails']}")
        self.log_to_file(f"Filtered bad emails: {len(self._filtered_emails)}")
        self.log_to_file(f"ATL: {summary['atl_leads']}, BTL: {summary['btl_leads']}")

        logger.info(f"Export finalized: {len(self._exported_leads)} leads")

        return summary
