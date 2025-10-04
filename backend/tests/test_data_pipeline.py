"""
Tests for Data Pipeline Services

Tests for:
- CSV Lead Import (Task 23)
- Document Processing (Task 7)
- Social Media Scraping (Task 26)
- LinkedIn ATL Contact Discovery (Task 26)
"""

import pytest
import io
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from app.services.csv_importer import CSVImportService
from app.services.document_processor import DocumentProcessor
from app.services.social_media_scraper import SocialMediaScraper
from app.services.linkedin_scraper import LinkedInScraper


# CSV Import Tests

class TestCSVImportService:
    """Tests for CSV lead import functionality"""

    def setup_method(self):
        self.csv_importer = CSVImportService()

    def test_validate_row_valid(self):
        """Test validation of valid CSV row"""
        row = {
            "company_name": "TechCorp",
            "industry": "SaaS",
            "company_website": "https://techcorp.com",
            "contact_email": "john@techcorp.com"
        }
        is_valid, error = self.csv_importer.validate_row(row, 1)
        assert is_valid is True
        assert error == ""

    def test_validate_row_missing_required(self):
        """Test validation fails for missing required fields"""
        row = {
            "company_name": "TechCorp",
            "industry": "",  # Missing required field
            "company_website": "https://techcorp.com"
        }
        is_valid, error = self.csv_importer.validate_row(row, 1)
        assert is_valid is False
        assert "industry" in error

    def test_validate_row_invalid_email(self):
        """Test validation fails for invalid email"""
        row = {
            "company_name": "TechCorp",
            "industry": "SaaS",
            "company_website": "https://techcorp.com",
            "contact_email": "invalid-email"
        }
        is_valid, error = self.csv_importer.validate_row(row, 1)
        assert is_valid is False
        assert "email" in error.lower()

    def test_parse_csv_file_valid(self):
        """Test parsing valid CSV content"""
        csv_content = """company_name,industry,company_website,contact_email
TechCorp,SaaS,https://techcorp.com,john@techcorp.com
DataInc,Analytics,https://datainc.com,jane@datainc.com"""

        leads = self.csv_importer.parse_csv_file(csv_content)
        
        assert len(leads) == 2
        assert leads[0]["company_name"] == "TechCorp"
        assert leads[1]["company_name"] == "DataInc"

    def test_parse_csv_file_missing_headers(self):
        """Test parsing fails with missing required headers"""
        csv_content = """company_name,contact_email
TechCorp,john@techcorp.com"""

        with pytest.raises(Exception) as exc:
            self.csv_importer.parse_csv_file(csv_content)
        
        assert "missing required columns" in str(exc.value).lower() or "industry" in str(exc.value).lower()

    def test_bulk_import_leads_mock(self):
        """Test bulk import with mocked database"""
        mock_db = Mock()
        mock_db.connection.return_value.connection = Mock()
        mock_cursor = Mock()
        mock_db.connection.return_value.connection.cursor.return_value = mock_cursor

        leads = [
            {
                "company_name": "TechCorp",
                "industry": "SaaS",
                "company_website": "https://techcorp.com",
                "contact_email": "john@techcorp.com"
            }
        ]

        # Mock the copy_expert method
        mock_cursor.copy_expert = Mock()
        
        result = self.csv_importer.bulk_import_leads(mock_db, leads)
        
        assert result["total_leads"] == 1
        assert result["imported_count"] == 1
        assert "duration_ms" in result


# Document Processing Tests

class TestDocumentProcessor:
    """Tests for document processing functionality"""

    def setup_method(self):
        self.processor = DocumentProcessor()

    def test_extract_text_from_txt(self):
        """Test text extraction from TXT file"""
        content = b"This is a test document.\nLine 2 of content."
        
        text = self.processor.extract_text_from_txt(content)
        
        assert "This is a test document" in text
        assert "Line 2" in text

    def test_extract_text_from_txt_empty(self):
        """Test text extraction fails on empty file"""
        content = b""
        
        with pytest.raises(Exception) as exc:
            self.processor.extract_text_from_txt(content)
        
        assert "empty" in str(exc.value).lower()

    def test_extract_text_unsupported_format(self):
        """Test extraction fails for unsupported format"""
        with pytest.raises(Exception) as exc:
            self.processor.extract_text("test.xyz", b"content")
        
        assert "unsupported" in str(exc.value).lower()

    @patch('app.services.document_processor.pdfplumber')
    def test_extract_text_from_pdf_mock(self, mock_pdfplumber):
        """Test PDF extraction with mocked pdfplumber"""
        # Mock PDF structure
        mock_page = Mock()
        mock_page.extract_text.return_value = "Page 1 content"
        mock_page.extract_tables.return_value = []
        
        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)
        
        mock_pdfplumber.open.return_value = mock_pdf
        
        text = self.processor.extract_text_from_pdf(b"fake pdf content")
        
        assert "Page 1 content" in text

    @patch('app.services.document_processor.docx')
    def test_extract_text_from_docx_mock(self, mock_docx):
        """Test DOCX extraction with mocked python-docx"""
        # Mock DOCX structure
        mock_para1 = Mock()
        mock_para1.text = "Paragraph 1"
        mock_para2 = Mock()
        mock_para2.text = "Paragraph 2"
        
        mock_doc = Mock()
        mock_doc.paragraphs = [mock_para1, mock_para2]
        mock_doc.tables = []
        
        mock_docx.Document.return_value = mock_doc
        
        text = self.processor.extract_text_from_docx(b"fake docx content")
        
        assert "Paragraph 1" in text
        assert "Paragraph 2" in text


# Social Media Scraping Tests

class TestSocialMediaScraper:
    """Tests for social media scraping functionality"""

    def setup_method(self):
        self.scraper = SocialMediaScraper()

    def test_format_reddit_post(self):
        """Test Reddit post formatting"""
        # Mock Reddit submission
        mock_submission = Mock()
        mock_submission.id = "abc123"
        mock_submission.title = "Test Post"
        mock_submission.selftext = "Post content"
        mock_submission.created_utc = 1609459200  # 2021-01-01
        mock_submission.subreddit.display_name = "technology"
        mock_submission.score = 100
        mock_submission.num_comments = 50
        mock_submission.upvote_ratio = 0.95
        mock_submission.permalink = "/r/technology/comments/abc123/test_post"
        
        formatted = self.scraper._format_reddit_post(mock_submission)
        
        assert formatted["id"] == "abc123"
        assert formatted["title"] == "Test Post"
        assert formatted["platform"] == "reddit"
        assert formatted["subreddit"] == "technology"
        assert formatted["metrics"]["upvotes"] == 100

    def test_analyze_sentiment_empty(self):
        """Test sentiment analysis with empty posts"""
        result = self.scraper.analyze_sentiment([])
        
        assert result["overall_sentiment"] == "neutral"
        assert result["total_posts"] == 0

    @patch.object(SocialMediaScraper, '_init_twitter_client')
    @patch.object(SocialMediaScraper, '_init_reddit_client')
    def test_scraper_initialization_no_credentials(self, mock_reddit, mock_twitter):
        """Test scraper handles missing credentials gracefully"""
        mock_twitter.return_value = None
        mock_reddit.return_value = None
        
        scraper = SocialMediaScraper()
        
        assert scraper.twitter_client is None
        assert scraper.reddit_client is None


# LinkedIn Scraping Tests

class TestLinkedInScraper:
    """Tests for LinkedIn scraping via Browserbase"""

    def setup_method(self):
        self.scraper = LinkedInScraper()

    def test_scrape_company_page_no_credentials(self):
        """Test company scraping without Browserbase credentials"""
        # Should return error dict when no API key
        result = self.scraper.scrape_company_page("https://linkedin.com/company/techcorp")
        
        assert "error" in result or "scraped" in result
        if "scraped" in result:
            assert result["scraped"] is False or result.get("error") is not None

    def test_discover_employees_structure(self):
        """Test employee discovery returns correct structure"""
        employees = self.scraper.discover_employees(
            "https://linkedin.com/company/techcorp",
            job_titles=["CEO"],
            max_employees=10
        )
        
        # Should return list (empty if no credentials, mock data otherwise)
        assert isinstance(employees, list)
        
        # If mock data returned, verify structure
        if employees:
            emp = employees[0]
            assert "name" in emp
            assert "title" in emp
            assert "profile_url" in emp

    def test_discover_atl_contacts_scoring(self):
        """Test ATL contact scoring logic"""
        result = self.scraper.discover_atl_contacts(
            "https://linkedin.com/company/techcorp",
            include_titles=["CEO", "VP"]
        )
        
        assert "total_atl_contacts" in result
        assert "contacts" in result
        
        # Verify contacts are sorted by score (if any returned)
        if result["contacts"]:
            scores = [c["decision_maker_score"] for c in result["contacts"]]
            assert scores == sorted(scores, reverse=True)

    def test_build_org_chart_structure(self):
        """Test org chart building returns correct structure"""
        result = self.scraper.build_org_chart(
            "https://linkedin.com/company/techcorp",
            max_depth=2
        )
        
        assert "hierarchy" in result or "org_chart" in result
        assert "company_url" in result or "error" in result


# Integration Tests

class TestDataPipelineIntegration:
    """Integration tests for complete data pipeline workflows"""

    def test_csv_to_database_workflow(self):
        """Test complete CSV import workflow"""
        csv_content = """company_name,industry,company_website
TechCorp,SaaS,https://techcorp.com
DataInc,Analytics,https://datainc.com"""

        importer = CSVImportService()
        leads = importer.parse_csv_file(csv_content)
        
        assert len(leads) == 2
        # Verify data structure ready for DB insert
        for lead in leads:
            assert "company_name" in lead
            assert "industry" in lead

    def test_document_to_analysis_workflow(self):
        """Test document processing to analysis workflow"""
        processor = DocumentProcessor()
        
        # Simple TXT processing
        text_content = b"""John Doe
Senior Software Engineer
Skills: Python, FastAPI, PostgreSQL
5 years of experience"""

        text = processor.extract_text("resume.txt", text_content)
        
        assert "John Doe" in text
        assert "Python" in text
        
    def test_social_media_aggregation(self):
        """Test multi-platform social media aggregation"""
        scraper = SocialMediaScraper()
        
        # Test structure even without API credentials
        result = scraper.scrape_company_social(
            "TechCorp",
            platforms=["twitter", "reddit"],
            max_results_per_platform=10
        )
        
        assert "company_name" in result
        assert "platform_results" in result
        assert "sentiment_analysis" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
