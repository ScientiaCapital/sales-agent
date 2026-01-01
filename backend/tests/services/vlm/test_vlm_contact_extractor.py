"""
Tests for VLMContactExtractor - VLM-based contact extraction from screenshots.

Tests cover:
- JSON response parsing (valid and markdown-wrapped)
- Garbage contact filtering
- ICP signal detection
- Fallback model behavior
- Cost calculation
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables BEFORE importing app modules
env_path = Path(__file__).parent.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestVLMContactExtractor:
    """Tests for VLMContactExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create a VLMContactExtractor instance with test API key."""
        from app.services.vlm_contact_extractor import VLMContactExtractor
        return VLMContactExtractor(
            api_key="test-openrouter-key",
            primary_model="opengvlab/internvl3-78b",
            fallback_model="qwen/qwen3-vl-30b-a3b-instruct"
        )

    def test_parse_valid_json_response(self, extractor, sample_vlm_response_valid):
        """
        Test parsing a valid JSON response with contacts and ICP signals.

        The extractor should correctly parse:
        - contacts array with name, title, email, confidence, visual_context
        - icp_signals object with boolean flags
        """
        result = extractor._parse_json_response(sample_vlm_response_valid)

        # Verify contacts parsed correctly
        assert "contacts" in result
        assert len(result["contacts"]) == 2

        # Check first contact
        contact1 = result["contacts"][0]
        assert contact1["name"] == "John Smith"
        assert contact1["title"] == "CEO & Founder"
        assert contact1["email"] == "john@example.com"
        assert contact1["confidence"] == "HIGH"

        # Check second contact
        contact2 = result["contacts"][1]
        assert contact2["name"] == "Sarah Johnson"
        assert contact2["title"] == "VP of Operations"

        # Verify ICP signals parsed correctly
        assert "icp_signals" in result
        assert result["icp_signals"]["has_design_build"] is True
        assert result["icp_signals"]["has_engineering"] is False
        assert result["icp_signals"]["has_medical_specialization"] is True
        assert result["icp_signals"]["has_awards"] is True

    def test_parse_markdown_code_block(self, extractor, sample_vlm_response_markdown):
        """
        Test parsing a response wrapped in markdown ```json ... ``` block.

        VLMs sometimes wrap their JSON output in markdown code blocks.
        The parser should strip the markdown and extract the JSON.
        """
        result = extractor._parse_json_response(sample_vlm_response_markdown)

        # Verify contacts parsed correctly despite markdown wrapper
        assert "contacts" in result
        assert len(result["contacts"]) == 1

        contact = result["contacts"][0]
        assert contact["name"] == "Michael Brown"
        assert contact["title"] == "Project Manager"
        assert contact["email"] == "michael@company.com"

        # Verify ICP signals
        assert result["icp_signals"]["has_engineering"] is True
        assert result["icp_signals"]["has_design_build"] is False

    def test_filter_garbage_contacts(self, extractor, sample_vlm_response_with_garbage):
        """
        Test filtering of garbage contacts from VLM output.

        VLMContactExtractor filters:
        - Testimonial names (with years/customer titles)
        - Generic text ("Our Team", "Contact Us")
        - Names < 3 characters
        - Names with single letter last names (initials)

        Note: "None" and "null" literal strings pass VLM filter
        but are caught by SaveVerifier validation layer.
        """
        parsed = extractor._parse_json_response(sample_vlm_response_with_garbage)
        clean_contacts = extractor._filter_garbage_contacts(parsed["contacts"])

        # Get filtered names
        filtered_names = [c["name"] for c in clean_contacts]

        # These SHOULD be filtered by VLMContactExtractor
        assert "Kenneth A." not in filtered_names  # Initial-only last name (testimonial)
        assert "Our Team" not in filtered_names  # Generic text pattern
        assert "Contact Us" not in filtered_names  # Generic text pattern
        assert "AB" not in filtered_names  # Too short (<3 chars)

        # "John Doe" should be kept - valid name
        assert "John Doe" in filtered_names

        # Note: "None" and "null" pass VLM filter but are caught by SaveVerifier
        # This is defense-in-depth - VLM filters UI garbage, SaveVerifier filters data garbage

    def test_detect_icp_signals(self, extractor, sample_vlm_response_valid):
        """
        Test detection of ICP (Ideal Customer Profile) signals.

        The extractor should identify business capability indicators:
        - has_design_build
        - has_engineering
        - has_medical_specialization
        - has_building_automation
        - has_awards
        - has_oem_partnerships
        """
        result = extractor._parse_json_response(sample_vlm_response_valid)

        icp_signals = result["icp_signals"]

        # Verify all expected signal keys exist
        expected_signals = [
            "has_design_build",
            "has_engineering",
            "has_medical_specialization",
            "has_building_automation",
            "has_awards",
            "has_oem_partnerships"
        ]

        for signal in expected_signals:
            assert signal in icp_signals, f"Missing ICP signal: {signal}"
            assert isinstance(icp_signals[signal], bool), f"{signal} should be boolean"

        # Verify specific values from sample
        assert icp_signals["has_design_build"] is True
        assert icp_signals["has_medical_specialization"] is True
        assert icp_signals["has_awards"] is True
        assert icp_signals["has_engineering"] is False
        assert icp_signals["has_building_automation"] is False
        assert icp_signals["has_oem_partnerships"] is False

    @pytest.mark.asyncio
    async def test_fallback_model_on_failure(
        self,
        extractor,
        mock_openai_client_with_fallback,
        mock_screenshot_path
    ):
        """
        Test fallback to secondary model when primary fails.

        When the primary model (internvl3-78b) fails with an error,
        the extractor should automatically retry with the fallback
        model (qwen3-vl-30b).
        """
        # Patch the client initialization
        with patch.object(extractor, '_client', mock_openai_client_with_fallback):
            result = await extractor.extract_contacts(
                screenshot_path=mock_screenshot_path,
                page_url="https://example.com/team"
            )

        # Should have succeeded with fallback model
        assert result["model_used"] == "qwen/qwen3-vl-30b-a3b-instruct"
        assert len(result["contacts"]) == 1
        assert result["contacts"][0]["name"] == "James Wilson"

        # Verify API was called twice (primary failed, fallback succeeded)
        assert mock_openai_client_with_fallback.chat.completions.create.call_count == 2

    def test_cost_calculation(self, extractor):
        """
        Test cost calculation from token usage.

        Cost is calculated as:
        - Input: (input_tokens / 1M) * input_price_per_million
        - Output: (output_tokens / 1M) * output_price_per_million
        - Total: Input + Output

        For internvl3-78b:
        - Input: $0.07/1M tokens
        - Output: $0.26/1M tokens
        """
        model = "opengvlab/internvl3-78b"

        # Test case 1: Standard usage
        input_tokens = 1000
        output_tokens = 200

        cost = extractor._calculate_cost(model, input_tokens, output_tokens)

        # Expected: (1000/1M * 0.07) + (200/1M * 0.26)
        # = 0.00007 + 0.000052 = 0.000122
        expected_cost = (1000 / 1_000_000) * 0.07 + (200 / 1_000_000) * 0.26
        assert abs(cost - expected_cost) < 0.0001

        # Test case 2: Larger usage
        input_tokens = 10000
        output_tokens = 2000

        cost = extractor._calculate_cost(model, input_tokens, output_tokens)

        expected_cost = (10000 / 1_000_000) * 0.07 + (2000 / 1_000_000) * 0.26
        assert abs(cost - expected_cost) < 0.0001

        # Test case 3: Qwen model (different pricing)
        qwen_model = "qwen/qwen3-vl-30b-a3b-instruct"
        cost = extractor._calculate_cost(qwen_model, 1000, 200)

        # Qwen: $0.22/1M for both input and output
        expected_cost = (1000 / 1_000_000) * 0.22 + (200 / 1_000_000) * 0.22
        assert abs(cost - expected_cost) < 0.0001


    def test_init_client_lazy_loading(self):
        """
        Test that OpenAI client is not initialized until first use (lazy loading).

        The client initialization is deferred to reduce startup time and
        avoid unnecessary connections if extraction is never called.
        """
        from app.services.vlm_contact_extractor import VLMContactExtractor

        extractor = VLMContactExtractor(api_key="test-key")

        # Client should be None initially
        assert extractor._client is None

        # After calling _init_client, it should be initialized
        # Note: This is tested via the extract_contacts test which calls _init_client

    def test_load_image_base64_png(self, extractor, tmp_path):
        """
        Test loading PNG image and detecting correct MIME type.

        PNG files start with magic bytes: \\x89PNG\\r\\n\\x1a\\n
        The loader should detect this and return mime_type="image/png"
        """
        # Create a minimal PNG file
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
            b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
            b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        png_file = tmp_path / "test.png"
        png_file.write_bytes(png_data)

        base64_str, mime_type = extractor._load_image_base64(png_file)

        # Verify MIME type detected correctly
        assert mime_type == "image/png"

        # Verify base64 encoding is valid
        import base64
        decoded = base64.b64decode(base64_str)
        assert decoded == png_data

    def test_load_image_base64_jpeg(self, extractor, tmp_path):
        """
        Test loading JPEG image and detecting correct MIME type.

        JPEG files start with magic bytes: \\xff\\xd8\\xff
        The loader should detect this and return mime_type="image/jpeg"
        """
        # Create a JPEG file with magic bytes
        jpeg_data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        jpeg_file = tmp_path / "test.jpg"
        jpeg_file.write_bytes(jpeg_data)

        base64_str, mime_type = extractor._load_image_base64(jpeg_file)

        # Verify MIME type detected correctly
        assert mime_type == "image/jpeg"

        # Verify base64 encoding is valid
        import base64
        decoded = base64.b64decode(base64_str)
        assert decoded == jpeg_data


class TestVLMContactExtractorEdgeCases:
    """Edge case tests for VLMContactExtractor."""

    @pytest.fixture
    def extractor(self):
        """Create a VLMContactExtractor instance."""
        from app.services.vlm_contact_extractor import VLMContactExtractor
        return VLMContactExtractor(api_key="test-key")

    def test_parse_empty_response(self, extractor):
        """Test handling of empty JSON response."""
        result = extractor._parse_json_response('{"contacts": [], "icp_signals": {}}')

        assert result["contacts"] == []
        assert result["icp_signals"] == {}

    def test_parse_invalid_json(self, extractor):
        """Test handling of invalid JSON response."""
        result = extractor._parse_json_response("This is not valid JSON at all")

        assert "contacts" in result
        assert result["contacts"] == []
        assert "parse_error" in result

    def test_filter_contacts_with_newlines(self, extractor):
        """Test filtering contacts with newline characters in names."""
        contacts = [
            {"name": "Valid Name", "title": "CEO"},
            {"name": "Invalid\nName", "title": "CTO"},
            {"name": "Also%0ABad", "title": "CFO"},
        ]

        clean = extractor._filter_garbage_contacts(contacts)

        assert len(clean) == 1
        assert clean[0]["name"] == "Valid Name"

    def test_filter_contacts_with_location_suffixes(self, extractor):
        """Test filtering contacts ending with state abbreviations."""
        contacts = [
            {"name": "John Smith", "title": "CEO"},
            {"name": "ACME Corp, FL", "title": "Company"},
            {"name": "Jane Doe 32801", "title": "Director"},  # Zip code
        ]

        clean = extractor._filter_garbage_contacts(contacts)

        assert len(clean) == 1
        assert clean[0]["name"] == "John Smith"

    def test_filter_contacts_too_many_words(self, extractor):
        """Test filtering contacts with too many words (>4)."""
        contacts = [
            {"name": "John Smith", "title": "CEO"},
            {"name": "This Is Way Too Many Words In A Name", "title": "Nobody"},
        ]

        clean = extractor._filter_garbage_contacts(contacts)

        assert len(clean) == 1
        assert clean[0]["name"] == "John Smith"

    def test_api_key_required(self):
        """Test that API key is required."""
        from app.services.vlm_contact_extractor import VLMContactExtractor

        with pytest.raises(ValueError, match="OpenRouter API key required"):
            VLMContactExtractor(api_key="")

        with pytest.raises(ValueError, match="OpenRouter API key required"):
            VLMContactExtractor(api_key=None)
