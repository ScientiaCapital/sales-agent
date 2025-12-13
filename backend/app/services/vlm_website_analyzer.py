"""
VLM Website Analyzer - Analyze screenshots using vlm-core

Uses Qwen 2.5 VL via OpenRouter to extract company information from screenshots:
- Company name/logo
- Value proposition
- Services offered
- Contact information
- Team members (from photos)
- Industry signals
- Tech stack mentions

Cost: ~$0.0008/image with 30B model (good balance of quality/cost)
"""

import os
import base64
from typing import Dict, Any, Optional, List
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)

# Website analysis prompt for VLM
WEBSITE_ANALYSIS_PROMPT = """Analyze this company website screenshot and extract the following information.

Return a JSON object with these fields:
{
  "company_name": "Company name from logo or header",
  "tagline": "Main tagline or slogan if visible",
  "value_proposition": "Main value proposition (headline text)",
  "industry": "Primary industry/vertical (e.g., 'Solar Energy', 'Software', 'Financial Services')",
  "services": ["List of services or products mentioned"],
  "target_customer": "B2B or B2C, and description of ideal customer",
  "contact_info": {
    "phone": "Phone number if visible",
    "email": "Email if visible",
    "address": "Address if visible"
  },
  "team_members": [
    {"name": "Person name", "title": "Job title"}
  ],
  "social_proof": ["Customer logos or testimonials visible"],
  "tech_signals": ["Technology mentions like 'Salesforce', 'AWS', etc."],
  "cta_text": "Main call-to-action button text",
  "is_hiring": false,
  "confidence": 0.8
}

Important:
- Only include fields where you have confidence in the extraction
- For team_members, only include C-level or VP-level executives
- Set confidence 0.0-1.0 based on image quality and clarity
- If the screenshot is unclear or doesn't contain useful info, set confidence low
"""

# Simpler prompt for team page analysis
TEAM_PAGE_PROMPT = """Analyze this team/about page screenshot and extract executive information.

Return a JSON object:
{
  "team_members": [
    {"name": "Full Name", "title": "Job Title"}
  ],
  "company_name": "Company name if visible",
  "confidence": 0.8
}

Focus ONLY on executives with these titles:
- CEO, CFO, COO, CTO, CMO, CRO, CPO
- President, Vice President, VP
- Founder, Co-Founder
- Director, Managing Director

Ignore: Managers, Engineers, Analysts, Coordinators, Associates
"""


class VLMWebsiteAnalyzer:
    """
    Analyze website screenshots using Vision Language Models.

    Uses Qwen 2.5 VL via OpenRouter for:
    - Homepage analysis (value prop, services, industry)
    - Team page analysis (executive extraction)
    - Contact extraction
    - Tech stack detection
    """

    # Available models (cost per image)
    MODELS = {
        "fast": "qwen/qwen2.5-vl-8b-instruct",      # $0.0003/image
        "balanced": "qwen/qwen2.5-vl-30b-instruct",  # $0.0008/image
        "best": "qwen/qwen2.5-vl-72b-instruct",      # $0.0015/image
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_tier: str = "balanced",
        site_url: str = "https://sales-agent.scientiacapital.com",
        app_name: str = "SalesAgent"
    ):
        """
        Initialize VLM analyzer.

        Args:
            api_key: OpenRouter API key (defaults to env var)
            model_tier: 'fast', 'balanced', or 'best'
            site_url: Site URL for OpenRouter tracking
            app_name: App name for OpenRouter tracking
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = self.MODELS.get(model_tier, self.MODELS["balanced"])
        self.site_url = site_url
        self.app_name = app_name

        self._provider = None
        self._circuit_breaker = None

    def _get_provider(self):
        """Lazy load provider to avoid import errors if vlm_core not installed."""
        if self._provider is None:
            try:
                from vlm_core.providers.openrouter import OpenRouterProvider
                from vlm_core import CircuitBreaker, CircuitBreakerConfig

                if not self.api_key:
                    raise ValueError("OPENROUTER_API_KEY not set")

                self._provider = OpenRouterProvider(
                    api_key=self.api_key,
                    site_url=self.site_url,
                    app_name=self.app_name
                )

                self._circuit_breaker = CircuitBreaker(
                    config=CircuitBreakerConfig(
                        service_name="vlm-website",
                        failure_threshold=3,
                        success_threshold=2,
                        timeout_seconds=60.0,
                        half_open_max_calls=2,
                    )
                )
            except ImportError as e:
                logger.error("vlm_core not installed", error=str(e))
                raise ImportError(
                    "vlm-core required. Install with: "
                    "pip install -e /path/to/vlm-ai-core/packages/python"
                )

        return self._provider

    async def analyze_screenshot(
        self,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None,
        analysis_type: str = "website"
    ) -> Dict[str, Any]:
        """
        Analyze a website screenshot.

        Args:
            image_path: Path to screenshot file
            image_base64: Base64 encoded image (alternative to path)
            analysis_type: 'website' for full analysis, 'team' for team page

        Returns:
            Extracted company data
        """
        from vlm_core import VLMConfig, withRetry

        provider = self._get_provider()

        # Load image
        if image_path:
            image_base64 = self._load_image(image_path)
        elif not image_base64:
            raise ValueError("Either image_path or image_base64 required")

        # Select prompt
        prompt = TEAM_PAGE_PROMPT if analysis_type == "team" else WEBSITE_ANALYSIS_PROMPT

        # Configure VLM request
        config = VLMConfig(
            model=self.model,
            prompt=prompt,
            max_tokens=2000,
            temperature=0.1,  # Low temp for structured extraction
        )

        try:
            # Execute with circuit breaker and retry
            async def _analyze():
                return await provider.analyze(image_base64, config)

            if self._circuit_breaker:
                result = await self._circuit_breaker.execute(
                    lambda: withRetry(_analyze)
                )
            else:
                result = await _analyze()

            extraction = result.extraction

            # Log success
            logger.info(
                "VLM analysis complete",
                model=self.model,
                tokens=result.tokens_used,
                latency_ms=result.latency_ms,
                company=extraction.get("company_name"),
            )

            return extraction

        except Exception as e:
            logger.error("VLM analysis failed", error=str(e))
            return {
                "error": str(e),
                "confidence": 0.0
            }

    async def analyze_homepage(self, image_path: str) -> Dict[str, Any]:
        """Analyze a homepage screenshot for company info."""
        return await self.analyze_screenshot(image_path=image_path, analysis_type="website")

    async def analyze_team_page(self, image_path: str) -> Dict[str, Any]:
        """Analyze a team page screenshot for executives."""
        return await self.analyze_screenshot(image_path=image_path, analysis_type="team")

    async def batch_analyze(
        self,
        images: List[Dict[str, Any]],
        analysis_type: str = "website"
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple screenshots.

        Args:
            images: List of {"path": "/path/to/image.png"} or {"base64": "..."}
            analysis_type: Type of analysis

        Returns:
            List of extraction results
        """
        import asyncio

        results = []
        for img in images:
            try:
                if "path" in img:
                    result = await self.analyze_screenshot(
                        image_path=img["path"],
                        analysis_type=analysis_type
                    )
                else:
                    result = await self.analyze_screenshot(
                        image_base64=img.get("base64"),
                        analysis_type=analysis_type
                    )
                results.append(result)

                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)

            except Exception as e:
                results.append({"error": str(e), "confidence": 0.0})

        return results

    def _load_image(self, image_path: str) -> str:
        """Load image from file and convert to base64."""
        path = Path(image_path)

        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Determine mime type
        suffix = path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(suffix, "image/jpeg")

        # Read and encode
        with open(path, "rb") as f:
            image_data = f.read()

        encoded = base64.b64encode(image_data).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def estimate_cost(self, num_images: int) -> float:
        """Estimate cost for analyzing N images."""
        costs = {
            "qwen/qwen2.5-vl-8b-instruct": 0.0003,
            "qwen/qwen2.5-vl-30b-instruct": 0.0008,
            "qwen/qwen2.5-vl-72b-instruct": 0.0015,
        }
        return num_images * costs.get(self.model, 0.0008)


# Convenience functions
async def analyze_website_screenshot(
    image_path: str,
    model_tier: str = "balanced"
) -> Dict[str, Any]:
    """Quick function to analyze a single screenshot."""
    analyzer = VLMWebsiteAnalyzer(model_tier=model_tier)
    return await analyzer.analyze_homepage(image_path)


async def analyze_team_screenshot(
    image_path: str,
    model_tier: str = "balanced"
) -> Dict[str, Any]:
    """Quick function to analyze a team page screenshot."""
    analyzer = VLMWebsiteAnalyzer(model_tier=model_tier)
    return await analyzer.analyze_team_page(image_path)


# Test function
async def test_analyzer():
    """Test the VLM analyzer with a sample image."""
    import asyncio

    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY not set - skipping test")
        return

    analyzer = VLMWebsiteAnalyzer(model_tier="fast")

    print(f"Model: {analyzer.model}")
    print(f"Estimated cost for 100 images: ${analyzer.estimate_cost(100):.2f}")

    # Test with a sample image if available
    test_image = Path("/tmp/screenshots/test.png")
    if test_image.exists():
        result = await analyzer.analyze_homepage(str(test_image))
        print(f"Result: {result}")
    else:
        print("No test image available at /tmp/screenshots/test.png")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_analyzer())
