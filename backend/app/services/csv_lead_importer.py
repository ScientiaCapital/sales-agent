"""
CSV lead importer utility for testing pipeline with dealer-scraper leads
"""
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List


class LeadCSVImporter:
    """
    Utility for loading and accessing leads from dealer-scraper CSV files.

    Transforms CSV format to pipeline format with proper field mapping:
    - ICP_Score → icp_score
    - OEMs_Certified → oem_certifications (parsed as list)
    """

    def __init__(self, csv_path: str):
        """
        Initialize importer with CSV file path.

        Args:
            csv_path: Absolute or relative path to CSV file

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            pd.errors.EmptyDataError: If CSV is empty
        """
        self.csv_path = Path(csv_path)
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Load CSV with pandas
        self.df = pd.read_csv(csv_path)

        if self.df.empty:
            raise ValueError(f"CSV file is empty: {csv_path}")

    def get_lead(self, index: int) -> Dict[str, Any]:
        """
        Extract lead by index with field mapping.

        Args:
            index: Row index (0-based)

        Returns:
            Lead dictionary with pipeline-format fields

        Raises:
            IndexError: If index is out of bounds
        """
        if index < 0 or index >= len(self.df):
            raise IndexError(f"Lead index {index} out of range (0-{len(self.df)-1})")

        row = self.df.iloc[index]

        # Parse OEM certifications from comma-separated string
        oem_certs = []
        if pd.notna(row.get('OEMs_Certified')):
            oem_string = str(row['OEMs_Certified'])
            # Split by comma and strip whitespace
            oem_certs = [cert.strip() for cert in oem_string.split(',') if cert.strip()]

        # Map CSV columns to pipeline format
        lead = {
            "name": row.get('name'),
            "phone": row.get('phone'),
            "domain": row.get('domain'),
            "website": row.get('website'),
            "email": row.get('email'),
            "icp_score": float(row['ICP_Score']) if pd.notna(row.get('ICP_Score')) else None,
            "oem_certifications": oem_certs,
            "city": row.get('city'),
            "state": row.get('state')
        }

        return lead

    def get_lead_count(self) -> int:
        """
        Get total number of leads in CSV.

        Returns:
            Total lead count
        """
        return len(self.df)

    def get_all_leads(self) -> List[Dict[str, Any]]:
        """
        Get all leads from CSV.

        Returns:
            List of lead dictionaries in pipeline format
        """
        return [self.get_lead(i) for i in range(len(self.df))]
