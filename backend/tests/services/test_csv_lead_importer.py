"""
Tests for CSV lead importer
"""
import pytest
import pandas as pd
from pathlib import Path
import tempfile

from app.services.csv_lead_importer import LeadCSVImporter


@pytest.fixture
def sample_csv():
    """Create temporary CSV file with sample data"""
    csv_content = """name,phone,domain,website,email,ICP_Score,OEMs_Certified,city,state
A & A GENPRO INC.,(713) 830-3280,aagenpro.com,https://www.aagenpro.com/,contact@aagenpro.com,72.8,"Generac, Cummins",Houston,TX
Another Company Inc,(555) 123-4567,another.com,https://another.com/,info@another.com,65.2,"Kohler, Generac",Austin,TX
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        return f.name


def test_csv_importer_initialization(sample_csv):
    """Test CSV importer loads file successfully"""
    importer = LeadCSVImporter(csv_path=sample_csv)

    assert importer.df is not None
    assert len(importer.df) == 2
    assert "name" in importer.df.columns
    assert "ICP_Score" in importer.df.columns


def test_get_lead_by_index(sample_csv):
    """Test extracting lead by index"""
    importer = LeadCSVImporter(csv_path=sample_csv)

    lead = importer.get_lead(0)

    assert lead["name"] == "A & A GENPRO INC."
    assert lead["phone"] == "(713) 830-3280"
    assert lead["icp_score"] == 72.8
    assert "Generac" in lead["oem_certifications"]
    assert "Cummins" in lead["oem_certifications"]


def test_get_lead_invalid_index(sample_csv):
    """Test error handling for invalid index"""
    importer = LeadCSVImporter(csv_path=sample_csv)

    with pytest.raises(IndexError):
        importer.get_lead(999)


def test_get_lead_count(sample_csv):
    """Test getting total lead count"""
    importer = LeadCSVImporter(csv_path=sample_csv)

    assert importer.get_lead_count() == 2


def test_get_all_leads(sample_csv):
    """Test getting all leads"""
    importer = LeadCSVImporter(csv_path=sample_csv)

    leads = importer.get_all_leads()

    assert len(leads) == 2
    assert all("name" in lead for lead in leads)
    assert all("icp_score" in lead for lead in leads)
