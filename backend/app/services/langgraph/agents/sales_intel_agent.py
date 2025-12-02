"""
SalesIntelAgent - AI-Powered Sales Intelligence Extraction

Analyzes scraped website content and extracts actionable sales intelligence:
- Personal details (hobbies, family, pets) for rapport building
- Company origin story for connection points
- Pain points and buying signals
- Generates personalized email/SMS drafts

Architecture:
    LCEL Chain: Content → Extraction Prompt → ChatCerebras → Structured Output

This agent works WITH the BDRAgent:
1. SalesIntelAgent: Extracts intel + generates draft outreach
2. BDRAgent: Human reviews/approves → sends via integrations

Performance:
    - Target: <3000ms for extraction + draft generation
    - Model: llama3.1-8b via Cerebras (fast, cheap)
    - Cost: ~$0.00005 per analysis

Usage:
    ```python
    from app.services.langgraph.agents import SalesIntelAgent

    agent = SalesIntelAgent()
    result = await agent.analyze(
        company_name="Command Comfort",
        contact_name="Chris Parker",
        contact_title="CEO",
        scraped_content="Former child superstar... dogs named Burnt Bacon...",
        services=["HVAC", "maintenance"],
        brands=["Mitsubishi", "American Standard"]
    )

    print(result.personal_hooks)  # ["Has dogs: Burnt Bacon & Oreo", "Golfer", "Beach lover"]
    print(result.email_draft)     # Personalized email
    print(result.sms_draft)       # Short SMS opener
    print(result.voice_opener)    # For voice AI agents
    ```
"""

import os
import time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_cerebras import ChatCerebras

from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ========== Output Schema ==========

class PersonalHook(BaseModel):
    """A personal detail that can be used for rapport building."""
    category: str = Field(description="Category: family, pets, hobbies, background, community")
    detail: str = Field(description="The specific detail (e.g., 'Has 2 dogs: Burnt Bacon & Oreo')")
    conversation_opener: str = Field(description="How to use this in conversation")


class SalesIntelResult(BaseModel):
    """
    Structured output for sales intelligence extraction.
    """
    # Personal intel for rapport building
    personal_hooks: List[PersonalHook] = Field(
        default_factory=list,
        description="Personal details extracted for rapport (pets, hobbies, family, etc.)"
    )

    # Company intel
    company_story: Optional[str] = Field(
        default=None,
        description="How/why the company was founded - connection point"
    )
    years_in_business: Optional[int] = Field(
        default=None,
        description="How long they've been operating"
    )
    company_values: List[str] = Field(
        default_factory=list,
        description="Core values mentioned (family-owned, customer-first, etc.)"
    )

    # Pain points / buying signals
    pain_points: List[str] = Field(
        default_factory=list,
        description="Potential pain points based on their services/situation"
    )
    buying_signals: List[str] = Field(
        default_factory=list,
        description="Signals they might be ready to buy (growth, hiring, etc.)"
    )

    # Generated outreach drafts
    email_subject: str = Field(description="Personalized email subject line")
    email_body: str = Field(description="Personalized email body (2-3 paragraphs)")
    sms_draft: str = Field(description="Short SMS opener (under 160 chars)")
    voice_opener: str = Field(description="Opening line for voice AI or human BDR call")

    # Metadata
    confidence: float = Field(
        default=0.5,
        description="Confidence in extraction quality (0-1)"
    )
    processing_time_ms: int = Field(default=0, description="Processing time in milliseconds")


# ========== Prompt Template ==========

SALES_INTEL_PROMPT = """You are an expert BDR (Business Development Rep) analyst. Your job is to extract ACTIONABLE sales intelligence from website content.

CRITICAL: Focus on PERSONAL details that help build rapport - not generic marketing copy.

COMPANY INFORMATION:
- Company: {company_name}
- Contact: {contact_name} ({contact_title})
- Services: {services}
- Brands they carry: {brands}
- Location: {location}

SCRAPED WEBSITE CONTENT:
{scraped_content}

YOUR TASK:
1. Extract PERSONAL HOOKS - things a salesperson can use to build rapport:
   - Family mentions (wife, kids, etc.)
   - Pets (names, breeds)
   - Hobbies (golf, fishing, sports teams)
   - Background story (how they got into the business)
   - Community involvement (church, charity, volunteer)
   - Personal interests mentioned in their bio

2. Extract COMPANY INTEL:
   - Origin story (when/why founded)
   - Years in business
   - Core values they emphasize

3. Identify PAIN POINTS they might have:
   - Based on their services and market
   - Common challenges in their industry
   - Signs of growth or struggle

4. Generate PERSONALIZED OUTREACH:
   - Email: Reference something PERSONAL, then pivot to value
   - SMS: Ultra-short, personal, gets a response
   - Voice opener: First 10 seconds of a cold call

RULES:
- DO NOT use generic phrases like "I noticed you're in HVAC"
- DO reference specific personal details (their dogs, their golf game, etc.)
- Keep SMS under 160 characters
- Email should be 2-3 short paragraphs max
- Voice opener should be natural, not salesy

If no personal details found, say so honestly and focus on company-specific angles."""


# ========== Agent Implementation ==========

class SalesIntelAgent:
    """
    AI-powered sales intelligence extraction agent.

    Analyzes scraped website content and extracts actionable intel
    for BDR outreach, including personalized email/SMS drafts.
    """

    def __init__(self, model_name: str = "llama-3.3-70b"):
        """Initialize with Cerebras for fast inference."""
        self.model_name = model_name
        self.llm = None
        self._initialize_llm()

    def _initialize_llm(self):
        """Initialize Cerebras LLM with structured output."""
        api_key = os.getenv("CEREBRAS_API_KEY")
        if not api_key:
            logger.warning("CEREBRAS_API_KEY not set - SalesIntelAgent will not work")
            return

        self.llm = ChatCerebras(
            model=self.model_name,
            api_key=api_key,
            temperature=0.3,  # Some creativity for outreach
            max_tokens=2000,
        )

        # Create structured output chain
        self.chain = self.llm.with_structured_output(SalesIntelResult)

    async def analyze(
        self,
        company_name: str,
        contact_name: str,
        contact_title: str,
        scraped_content: str,
        services: List[str] = None,
        brands: List[str] = None,
        location: str = None,
    ) -> SalesIntelResult:
        """
        Analyze scraped content and extract sales intelligence.

        Args:
            company_name: Name of the company
            contact_name: Name of the primary contact (owner/CEO)
            contact_title: Title of the contact
            scraped_content: Raw text from website scraping
            services: List of services they offer
            brands: List of brands they carry
            location: City, State

        Returns:
            SalesIntelResult with personal hooks and outreach drafts
        """
        if not self.llm:
            logger.error("LLM not initialized - check CEREBRAS_API_KEY")
            return SalesIntelResult(
                email_subject="",
                email_body="",
                sms_draft="",
                voice_opener="",
                confidence=0.0
            )

        start_time = time.time()

        try:
            # Build prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an expert sales intelligence analyst. Extract actionable intel and generate personalized outreach."),
                ("human", SALES_INTEL_PROMPT)
            ])

            # Prepare inputs
            services_str = ", ".join(services[:8]) if services else "Not specified"
            brands_str = ", ".join(brands[:6]) if brands else "Not specified"
            location_str = location or "Not specified"

            # Truncate content to avoid token limits
            content = scraped_content[:8000] if len(scraped_content) > 8000 else scraped_content

            # Run extraction
            chain = prompt | self.chain
            result = await chain.ainvoke({
                "company_name": company_name,
                "contact_name": contact_name,
                "contact_title": contact_title,
                "services": services_str,
                "brands": brands_str,
                "location": location_str,
                "scraped_content": content,
            })

            # Add processing time
            result.processing_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"SalesIntelAgent analyzed {company_name}: "
                f"{len(result.personal_hooks)} hooks found, "
                f"{result.processing_time_ms}ms"
            )

            return result

        except Exception as e:
            logger.error(f"SalesIntelAgent error: {e}")
            return SalesIntelResult(
                email_subject=f"Quick question for {company_name}",
                email_body=f"Hi {contact_name},\n\nI came across {company_name} and wanted to reach out...",
                sms_draft=f"Hi {contact_name}, quick Q about {company_name}?",
                voice_opener=f"Hi {contact_name}, this is [Name] - do you have 30 seconds?",
                confidence=0.1,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )


# ========== Standalone Function for scrape_domain.py ==========

async def extract_sales_intel(
    company_name: str,
    contact_name: str,
    contact_title: str,
    scraped_content: str,
    services: List[str] = None,
    brands: List[str] = None,
    location: str = None,
) -> Dict[str, Any]:
    """
    Standalone function to extract sales intel - can be called from scrape_domain.py

    Returns a dict for easy integration into existing code.
    """
    agent = SalesIntelAgent()
    result = await agent.analyze(
        company_name=company_name,
        contact_name=contact_name,
        contact_title=contact_title,
        scraped_content=scraped_content,
        services=services,
        brands=brands,
        location=location,
    )

    return {
        "personal_hooks": [
            {"category": h.category, "detail": h.detail, "opener": h.conversation_opener}
            for h in result.personal_hooks
        ],
        "company_story": result.company_story,
        "years_in_business": result.years_in_business,
        "company_values": result.company_values,
        "pain_points": result.pain_points,
        "buying_signals": result.buying_signals,
        "email_subject": result.email_subject,
        "email_body": result.email_body,
        "sms_draft": result.sms_draft,
        "voice_opener": result.voice_opener,
        "confidence": result.confidence,
        "processing_time_ms": result.processing_time_ms,
    }
