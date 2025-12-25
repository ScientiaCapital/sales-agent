"""
VLM Contact Extractor for Sales Agent

Uses Chinese VLMs via OpenRouter to extract contacts from website screenshots.
Primary: opengvlab/internvl3-78b ($0.001/screenshot)
Fallback: qwen/qwen3-vl-30b-a3b-instruct ($0.0002/screenshot)
"""

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Optional
import structlog
import redis.asyncio as redis

try:
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError("OpenAI SDK required for OpenRouter. Install with: pip install openai")

from .cache.vlm_cache import VLMCache

logger = structlog.get_logger(__name__)

# Model pricing (per 1M tokens)
MODEL_PRICING = {
    "opengvlab/internvl3-78b": {
        "input": 0.07,
        "output": 0.26,
        "description": "SOTA Chinese VLM - best accuracy"
    },
    "opengvlab/internvl3-14b": {
        "input": 0.02,
        "output": 0.08,
        "description": "Mid-tier InternVL"
    },
    "qwen/qwen3-vl-30b-a3b-instruct": {
        "input": 0.22,
        "output": 0.22,
        "description": "Proven performer from fieldvault-ai"
    },
    "qwen/qwen3-vl-8b-instruct": {
        "input": 0.12,
        "output": 0.12,
        "description": "Fast/cheap Qwen option"
    },
}

# Contact extraction prompt
CONTACT_EXTRACTION_PROMPT = """You are analyzing a screenshot of a business website.

PAGE URL: {page_url}

YOUR TASK: Extract ALL people's names (contacts) visible on this page.

WHAT TO LOOK FOR:
1. Team member cards/profiles (with photos)
2. Leadership bios
3. Staff directories
4. "Meet our team" sections
5. Contact information with names
6. About us pages with employee names

FOR EACH PERSON YOU FIND:
Extract these fields:
- name: Full name exactly as shown
- title: Job title (if visible)
- email: Email address (if visible)
- confidence: Rate your confidence
  * HIGH: Photo + name + title clearly visible
  * MEDIUM: Name + title visible (no photo)
  * LOW: Name only (no title/photo)
- visual_context: Describe WHERE/HOW you saw this person

CRITICAL RULES:
- ONLY extract REAL PEOPLE's names (not company names, locations, products)
- Skip generic text like "Our Team", "Contact Us", "Learn More"
- Skip customer testimonials/reviews (those aren't employees)
- If you see a photo gallery with names, extract ALL names

ICP SIGNALS TO DETECT:
Also look for these business capability indicators:
- has_design_build: "Design-Build", "Turnkey Solutions"
- has_engineering: "Engineering Department", "In-House CAD"
- has_medical_specialization: "Medical Gas", "Healthcare Projects"
- has_building_automation: "Building Automation", "BMS", "Controls"
- has_awards: Award badges, certifications, recognitions
- has_oem_partnerships: "Carrier Dealer", "Generac Authorized"

OUTPUT FORMAT (strict JSON):
{{
  "contacts": [
    {{
      "name": "John Doe",
      "title": "CEO & Founder",
      "email": "john@example.com",
      "confidence": "HIGH",
      "visual_context": "Large photo at top with 'CEO & Founder' caption below"
    }}
  ],
  "icp_signals": {{
    "has_design_build": true,
    "has_engineering": false,
    "has_medical_specialization": false,
    "has_building_automation": false,
    "has_awards": false,
    "has_oem_partnerships": false
  }}
}}

IMPORTANT: Output ONLY the JSON object, no other text."""


class VLMContactExtractor:
    """
    VLM-based contact extraction using OpenRouter.

    Uses screenshot analysis to identify real people by their:
    - Photos
    - Name/title pairings
    - Page layout context
    """

    def __init__(
        self,
        api_key: str,
        primary_model: str = "opengvlab/internvl3-78b",
        fallback_model: str = "qwen/qwen3-vl-30b-a3b-instruct",
        site_url: str = "https://scientia.capital",
        app_name: str = "Sales-Agent-VLM",
        # NEW: Cache parameters
        enable_cache: bool = True,
        redis_url: str = None,
        cache_ttl: int = 86400,
    ):
        """
        Initialize VLM extractor with OpenRouter credentials.

        Args:
            api_key: OpenRouter API key
            primary_model: Primary model for extraction
            fallback_model: Fallback if primary fails
            site_url: Site URL for OpenRouter headers
            app_name: App name for OpenRouter headers
            enable_cache: Enable Redis caching for VLM responses
            redis_url: Redis URL (defaults to REDIS_URL env var)
            cache_ttl: Cache TTL in seconds (default: 24 hours)
        """
        if not api_key:
            raise ValueError("OpenRouter API key required")

        self.api_key = api_key
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.site_url = site_url
        self.app_name = app_name
        self._client: Optional[AsyncOpenAI] = None

        # Cache settings
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self._redis_url = redis_url or os.getenv("REDIS_URL")
        self._cache: Optional[VLMCache] = None

    async def _init_client(self) -> None:
        """Initialize OpenRouter client (lazy)."""
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                default_headers={
                    "HTTP-Referer": self.site_url,
                    "X-Title": self.app_name,
                }
            )

    async def _get_cache(self) -> Optional[VLMCache]:
        """Lazy-load cache connection."""
        if not self.enable_cache or not self._redis_url:
            return None
        if self._cache is None:
            try:
                client = redis.from_url(self._redis_url)
                self._cache = VLMCache(client, self.cache_ttl)
            except Exception as e:
                logger.warning(f"Failed to connect to Redis cache: {e}")
                return None
        return self._cache

    def _load_image_base64(self, image_path: Path) -> tuple[str, str]:
        """
        Load image and return base64 + MIME type.

        Args:
            image_path: Path to screenshot file

        Returns:
            Tuple of (base64_data, mime_type)
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Screenshot not found: {image_path}")

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        # Detect format from magic bytes
        if image_bytes[:3] == b'\xff\xd8\xff':
            mime_type = "image/jpeg"
        elif image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            mime_type = "image/png"
        elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
            mime_type = "image/webp"
        else:
            mime_type = "image/png"  # Default to PNG for screenshots

        base64_data = base64.b64encode(image_bytes).decode("utf-8")
        return base64_data, mime_type

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """
        Parse JSON from VLM response.

        Handles markdown code blocks and raw JSON.
        """
        try:
            # Handle markdown code blocks
            if "```json" in content:
                json_start = content.index("```json") + 7
                json_end = content.index("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.index("```") + 3
                json_end = content.index("```", json_start)
                content = content[json_start:json_end].strip()

            return json.loads(content)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse VLM JSON response", error=str(e))
            return {"contacts": [], "icp_signals": {}, "parse_error": str(e)}

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for API call."""
        pricing = MODEL_PRICING.get(model, {"input": 0.10, "output": 0.10})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    async def extract_contacts(
        self,
        screenshot_path: Path,
        page_url: str,
        page_text: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """
        Extract contacts from a screenshot using VLM.

        Args:
            screenshot_path: Path to full-page screenshot
            page_url: URL of the page (for context)
            page_text: Extracted text (optional, for fallback)
            max_tokens: Max output tokens
            temperature: Sampling temperature

        Returns:
            {
                "contacts": [
                    {
                        "name": "John Doe",
                        "title": "CEO",
                        "email": "john@example.com",
                        "confidence": "HIGH",
                        "visual_context": "Photo with title below"
                    }
                ],
                "icp_signals": {
                    "has_design_build": True,
                    ...
                },
                "cost": 0.001,
                "model_used": "opengvlab/internvl3-78b",
                "latency_ms": 1500,
                "input_tokens": 1200,
                "output_tokens": 300
            }
        """
        # Check cache first
        cache = await self._get_cache()
        if cache:
            screenshot_bytes = Path(screenshot_path).read_bytes()
            cached = await cache.get_vlm_response(screenshot_bytes)
            if cached:
                logger.info(f"VLM Cache HIT for {page_url}")
                return cached

        await self._init_client()

        # Load screenshot
        base64_data, mime_type = self._load_image_base64(Path(screenshot_path))
        data_url = f"data:{mime_type};base64,{base64_data}"

        # Build prompt
        prompt = CONTACT_EXTRACTION_PROMPT.format(page_url=page_url)

        # Prepare messages
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url}
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]

        # Try primary model, then fallback
        models_to_try = [self.primary_model, self.fallback_model]
        last_error = None

        for model in models_to_try:
            start_time = time.time()

            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                latency_ms = int((time.time() - start_time) * 1000)

                # Extract content
                content = response.choices[0].message.content or ""

                # Parse JSON
                extracted = self._parse_json_response(content)

                # Get token counts
                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0

                # Calculate cost
                cost = self._calculate_cost(model, input_tokens, output_tokens)

                # Clean contacts (filter garbage)
                contacts = extracted.get("contacts", [])
                clean_contacts = self._filter_garbage_contacts(contacts)

                logger.info(
                    "VLM extraction complete",
                    model=model,
                    contacts_found=len(clean_contacts),
                    cost_usd=f"${cost:.4f}",
                    latency_ms=latency_ms,
                    page_url=page_url,
                )

                result = {
                    "contacts": clean_contacts,
                    "icp_signals": extracted.get("icp_signals", {}),
                    "cost": cost,
                    "model_used": model,
                    "latency_ms": latency_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "raw_response": content[:500] if len(content) > 500 else content,
                }

                # Store in cache if successful
                if cache and result.get("contacts"):
                    try:
                        screenshot_bytes = Path(screenshot_path).read_bytes()
                        await cache.set_vlm_response(screenshot_bytes, result, self.cache_ttl)
                        logger.info(f"VLM Cache STORE for {page_url}")
                    except Exception as e:
                        logger.warning(f"Failed to cache VLM result: {e}")

                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    "VLM extraction failed, trying fallback",
                    model=model,
                    error=str(e),
                )
                continue

        # All models failed
        logger.error(
            "All VLM models failed",
            page_url=page_url,
            error=str(last_error),
        )

        return {
            "contacts": [],
            "icp_signals": {},
            "cost": 0.0,
            "model_used": None,
            "latency_ms": 0,
            "error": str(last_error),
        }

    def _filter_garbage_contacts(self, contacts: list[dict]) -> list[dict]:
        """
        Filter out garbage names that VLM might still extract.

        Even VLMs can sometimes extract UI text or company names.
        """
        garbage_patterns = {
            # Generic text
            "our team", "contact us", "learn more", "read more",
            "meet the team", "about us", "get started",
            # UI elements
            "menu", "home", "services", "projects", "careers",
            "privacy policy", "terms of service", "copyright",
            # Business terms
            "mission statement", "our mission", "our values",
            "testimonials", "reviews", "what clients say",
            # Phone/contact labels (not people)
            "phone", "fax", "email", "corporate", "office",
            "toll free", "main line", "direct line",
            # Location labels
            "space coast", "orlando", "tampa", "miami",
            "headquarters", "branch", "location",
        }

        # Titles that indicate testimonials, not team members
        testimonial_titles = {
            "years with", "year with", "years ago", "year ago",
            "customer", "client", "homeowner", "satisfied",
            "happy", "review", "testimonial",
        }

        clean = []
        for contact in contacts:
            name = contact.get("name", "").strip()
            title = contact.get("title", "").strip().lower()

            if not name or len(name) < 3:
                continue

            # Check for garbage names
            name_lower = name.lower()
            if any(pattern in name_lower for pattern in garbage_patterns):
                logger.debug(f"Filtered garbage VLM contact: {name}")
                continue

            # Check for testimonial titles (not real employees)
            if any(pattern in title for pattern in testimonial_titles):
                logger.debug(f"Filtered testimonial: {name} ({title})")
                continue

            # Check for names with newlines (extraction errors)
            if '\n' in name or '%0A' in name:
                continue

            # Check for too many words (real names are 2-3 words)
            if len(name.split()) > 4:
                continue

            # Check for names ending in state abbreviations or zip codes
            if name.endswith(tuple([f", {state}" for state in ["FL", "CA", "TX", "NY", "AZ"]])):
                continue
            if any(char.isdigit() for char in name[-5:]):  # Zip code at end
                continue

            # Check for single letter last names (likely initials, not full names)
            parts = name.split()
            if len(parts) == 2 and len(parts[1]) == 1:
                # Like "Kenneth A." - probably a testimonial with initial
                logger.debug(f"Filtered initial-only name: {name}")
                continue

            clean.append(contact)

        return clean


# Convenience test function
async def test_vlm_extraction(
    api_key: str,
    screenshot_path: str,
    page_url: str = "https://example.com/team",
) -> dict[str, Any]:
    """
    Quick test function for VLM contact extraction.

    Args:
        api_key: OpenRouter API key
        screenshot_path: Path to screenshot file
        page_url: URL context

    Returns:
        Extraction results
    """
    extractor = VLMContactExtractor(api_key=api_key)
    result = await extractor.extract_contacts(
        screenshot_path=Path(screenshot_path),
        page_url=page_url,
    )
    return result
