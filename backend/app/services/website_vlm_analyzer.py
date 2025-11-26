"""
Website VLM Analyzer - Visual Analysis of Company Websites

Uses Vision Language Models (VLMs) to analyze website screenshots for:
- Business legitimacy (real company vs placeholder/parked domain)
- Services/products offered
- Team member information
- Business signals (hiring, awards, certifications)
- Industry classification

Architecture:
    Website URL → Playwright Screenshot → Qwen VL (OpenRouter) → Structured Analysis

Models:
    - qwen/qwen-2.5-vl-7b-instruct: Fast, cheap ($0.064/1M input)
    - qwen/qwen-2.5-vl-72b-instruct: More accurate for complex sites ($0.40/1M input)

Usage:
    from app.services.website_vlm_analyzer import WebsiteVLMAnalyzer

    analyzer = WebsiteVLMAnalyzer()
    result = await analyzer.analyze("https://browermechanical.com")

    print(f"Business Type: {result.business_type}")
    print(f"Is Real Business: {result.is_real_business}")
    print(f"Services: {result.services}")

Author: Tim Kipper (GTM Engineering)
Date: November 26, 2025
"""

import os
import base64
import asyncio
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

import httpx
from pydantic import BaseModel, Field

from app.core.logging import setup_logging
from app.services.llm_providers import get_openrouter_model, ModelTier, MODEL_CONFIGS

logger = setup_logging(__name__)


class VLMModel(Enum):
    """Available VLM models via OpenRouter."""
    QWEN_7B = "qwen/qwen-2.5-vl-7b-instruct"  # Fast, cheap
    QWEN_72B = "qwen/qwen-2.5-vl-72b-instruct"  # More accurate


@dataclass
class VLMAnalysisResult:
    """Result of VLM website analysis."""
    url: str
    is_real_business: bool = False
    business_type: str = "unknown"
    industry: str = "unknown"
    services: List[str] = field(default_factory=list)
    team_visible: bool = False
    team_count_estimate: int = 0
    business_signals: List[str] = field(default_factory=list)
    website_quality: str = "unknown"  # professional, basic, template, placeholder
    confidence: float = 0.0
    analysis_time_ms: float = 0.0
    error: Optional[str] = None
    raw_response: Optional[str] = None


class WebsiteVLMAnalyzer:
    """
    Analyze websites visually using VLM models.

    Captures screenshots via Playwright and sends to Qwen VL for analysis.
    """

    # OpenRouter API endpoint
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

    # Analysis prompt for business websites
    ANALYSIS_PROMPT = """Analyze this website screenshot for B2B sales qualification.

Extract the following information in JSON format:

{
    "is_real_business": true/false (is this a real operating business or placeholder/parked domain?),
    "business_type": "contractor/agency/saas/manufacturer/distributor/retail/other",
    "industry": "specific industry (e.g., HVAC, plumbing, electrical, IT services)",
    "services": ["list", "of", "main", "services", "offered"],
    "team_visible": true/false (are team members shown on the page?),
    "team_count_estimate": number (estimated employees shown if visible),
    "business_signals": ["list of signals: hiring, awards, certifications, case studies, client logos"],
    "website_quality": "professional/basic/template/placeholder",
    "confidence": 0.0-1.0 (your confidence in this analysis)
}

Focus on:
1. Is this a legitimate business website or a template/placeholder?
2. What services do they offer?
3. Are there signs of business activity (team photos, case studies, client logos)?
4. Overall professionalism of the website

Return ONLY valid JSON, no other text."""

    def __init__(
        self,
        model: VLMModel = VLMModel.QWEN_7B,
        timeout: int = 30,
        headless: bool = True
    ):
        """
        Initialize VLM analyzer.

        Args:
            model: VLM model to use (default: Qwen 7B for cost efficiency)
            timeout: Request timeout in seconds
            headless: Run browser in headless mode
        """
        self.model = model
        self.timeout = timeout
        self.headless = headless

        # Get API key
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")

        logger.info(f"WebsiteVLMAnalyzer initialized: model={model.value}")

    async def capture_screenshot(self, url: str) -> Optional[bytes]:
        """
        Capture website screenshot using Playwright.

        Args:
            url: Website URL to screenshot

        Returns:
            PNG screenshot bytes or None on failure
        """
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(headless=self.headless)

                try:
                    # Create page with reasonable viewport
                    page = await browser.new_page(viewport={"width": 1280, "height": 720})

                    # Navigate with timeout
                    await page.goto(url, timeout=15000, wait_until="networkidle")

                    # Wait for dynamic content
                    await asyncio.sleep(1)

                    # Capture full page screenshot
                    screenshot = await page.screenshot(
                        full_page=False,  # Just viewport for speed
                        type="png"
                    )

                    logger.info(f"Screenshot captured: {url} ({len(screenshot)} bytes)")
                    return screenshot

                finally:
                    await browser.close()

        except Exception as e:
            logger.error(f"Screenshot capture failed for {url}: {e}")
            return None

    async def analyze_screenshot(
        self,
        screenshot_bytes: bytes,
        url: str
    ) -> Dict[str, Any]:
        """
        Send screenshot to VLM for analysis.

        Args:
            screenshot_bytes: PNG screenshot data
            url: Original URL (for context)

        Returns:
            Parsed JSON analysis result
        """
        # Encode screenshot as base64
        image_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        # Build request for OpenRouter
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://sales-agent.local",
            "X-Title": "Sales Agent VLM Analysis"
        }

        # OpenRouter vision message format
        payload = {
            "model": self.model.value,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self.ANALYSIS_PROMPT
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 800,
            "temperature": 0.2
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.OPENROUTER_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            logger.info(f"VLM analysis received for {url}: {len(content)} chars")

            # Parse JSON from response
            import json

            # Extract JSON from response (may have markdown formatting)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            try:
                return json.loads(content.strip())
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse VLM JSON response: {content[:200]}")
                return {"error": "JSON parse failed", "raw": content}

    async def analyze(self, url: str) -> VLMAnalysisResult:
        """
        Analyze a website URL using VLM.

        Args:
            url: Website URL to analyze

        Returns:
            VLMAnalysisResult with analysis data
        """
        start_time = time.time()
        result = VLMAnalysisResult(url=url)

        try:
            # Step 1: Capture screenshot
            screenshot = await self.capture_screenshot(url)
            if not screenshot:
                result.error = "Screenshot capture failed"
                return result

            # Step 2: Analyze with VLM
            analysis = await self.analyze_screenshot(screenshot, url)

            # Step 3: Map to result
            if "error" in analysis:
                result.error = analysis.get("error")
                result.raw_response = analysis.get("raw")
            else:
                result.is_real_business = analysis.get("is_real_business", False)
                result.business_type = analysis.get("business_type", "unknown")
                result.industry = analysis.get("industry", "unknown")
                result.services = analysis.get("services", [])
                result.team_visible = analysis.get("team_visible", False)
                result.team_count_estimate = analysis.get("team_count_estimate", 0)
                result.business_signals = analysis.get("business_signals", [])
                result.website_quality = analysis.get("website_quality", "unknown")
                result.confidence = analysis.get("confidence", 0.0)

            result.analysis_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"VLM analysis complete: {url} "
                f"(real_business={result.is_real_business}, "
                f"quality={result.website_quality}, "
                f"time={result.analysis_time_ms:.0f}ms)"
            )

            return result

        except Exception as e:
            logger.error(f"VLM analysis failed for {url}: {e}")
            result.error = str(e)
            result.analysis_time_ms = (time.time() - start_time) * 1000
            return result

    async def batch_analyze(
        self,
        urls: List[str],
        concurrency: int = 3
    ) -> List[VLMAnalysisResult]:
        """
        Analyze multiple URLs with controlled concurrency.

        Args:
            urls: List of website URLs
            concurrency: Max parallel analyses

        Returns:
            List of VLMAnalysisResult objects
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def analyze_with_limit(url: str) -> VLMAnalysisResult:
            async with semaphore:
                return await self.analyze(url)

        tasks = [analyze_with_limit(url) for url in urls]
        return await asyncio.gather(*tasks)


# Convenience function
def get_website_vlm_analyzer(
    model: VLMModel = VLMModel.QWEN_7B
) -> WebsiteVLMAnalyzer:
    """Get a configured VLM analyzer instance."""
    return WebsiteVLMAnalyzer(model=model)


# Export
__all__ = [
    "WebsiteVLMAnalyzer",
    "VLMAnalysisResult",
    "VLMModel",
    "get_website_vlm_analyzer"
]
