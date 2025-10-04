"""
Contact Discovery and Social Media API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models import get_db
from app.services.linkedin_scraper import LinkedInScraper
from app.services.social_media_scraper import SocialMediaScraper
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

# Initialize services
linkedin_scraper = LinkedInScraper()
social_scraper = SocialMediaScraper()


@router.post("/discover")
async def discover_atl_contacts(
    company_linkedin_url: str,
    include_titles: Optional[List[str]] = Query(default=None),
    db: Session = Depends(get_db)
):
    """
    Discover Above-The-Line (ATL) decision makers from LinkedIn

    **ATL Contacts** are C-level executives, VPs, and senior directors who make
    purchasing decisions.

    **Features**:
    - Automated LinkedIn scraping via Browserbase (no Selenium setup!)
    - Employee discovery from company pages
    - Decision-maker scoring (0-100)
    - Contact prioritization (high/medium/low)
    - Organizational chart inference

    **Default Title Filters** (if not specified):
    - CEO, CTO, CFO, COO, CMO, Chief Officers
    - VP, Vice President levels
    - Directors, Head of departments

    **Parameters**:
    - `company_linkedin_url`: LinkedIn company page URL (e.g., https://linkedin.com/company/techcorp)
    - `include_titles`: Optional list of job title keywords to filter

    **Returns**:
    - List of ATL contacts with decision-maker scores
    - Contact details (name, title, profile URL, tenure)
    - Priority ranking for outreach

    **Example**:
    ```json
    {
        "company_url": "https://linkedin.com/company/techcorp",
        "total_atl_contacts": 8,
        "contacts": [
            {
                "name": "John Doe",
                "title": "CEO & Co-Founder",
                "decision_maker_score": 100,
                "contact_priority": "high",
                "profile_url": "https://linkedin.com/in/johndoe"
            }
        ]
    }
    ```
    """
    try:
        # Validate LinkedIn URL
        if "linkedin.com/company/" not in company_linkedin_url:
            raise HTTPException(
                status_code=400,
                detail="Invalid LinkedIn company URL format"
            )

        # Discover ATL contacts
        result = linkedin_scraper.discover_atl_contacts(
            company_linkedin_url=company_linkedin_url,
            include_titles=include_titles
        )

        logger.info(f"ATL discovery completed: {company_linkedin_url} - {result['total_atl_contacts']} contacts found")
        
        return {
            "message": "ATL contacts discovered successfully",
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ATL discovery error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Contact discovery failed: {str(e)}"
        )


@router.get("/org-chart")
async def build_org_chart(
    company_linkedin_url: str,
    max_depth: int = Query(default=2, ge=1, le=3),
    db: Session = Depends(get_db)
):
    """
    Build organizational chart from LinkedIn employee data

    Analyzes employee titles and relationships to create a hierarchical org chart.

    **Parameters**:
    - `company_linkedin_url`: LinkedIn company page URL
    - `max_depth`: Org chart depth (1=C-level only, 2=includes VPs, 3=includes Directors)

    **Returns**:
    - Hierarchical organization structure
    - Reporting relationships
    - Team sizes
    - Key decision makers
    """
    try:
        result = linkedin_scraper.build_org_chart(
            company_linkedin_url=company_linkedin_url,
            max_depth=max_depth
        )

        return {
            "message": "Org chart built successfully",
            **result
        }

    except Exception as e:
        logger.error(f"Org chart building error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Org chart building failed: {str(e)}"
        )


@router.get("/social-media")
async def scrape_social_media(
    company_name: str,
    platforms: List[str] = Query(default=["twitter", "reddit"]),
    max_results: int = Query(default=50, ge=10, le=100),
    db: Session = Depends(get_db)
):
    """
    Scrape multiple social media platforms for company mentions

    **Supported Platforms**:
    - `twitter` - Recent tweets mentioning the company (last 7 days)
    - `reddit` - Reddit posts and comments
    - `instagram` - Business profile posts (requires Browserbase)
    - `facebook` - Company page posts (requires Graph API token)

    **Features**:
    - Multi-platform aggregation
    - Sentiment analysis with Cerebras AI
    - Engagement metrics (likes, shares, comments)
    - Activity timeline tracking

    **Parameters**:
    - `company_name`: Company name to search for
    - `platforms`: List of platforms to scrape (default: twitter, reddit)
    - `max_results`: Max results per platform (10-100)

    **Returns**:
    - Total mentions across platforms
    - Platform-specific results
    - AI sentiment analysis (positive/negative/neutral)
    - Top posts with engagement metrics
    - Sentiment reasoning and score

    **Example Response**:
    ```json
    {
        "company_name": "TechCorp",
        "total_mentions": 156,
        "platform_results": {
            "twitter": {"count": 89, "status": "success"},
            "reddit": {"count": 67, "status": "success"}
        },
        "sentiment_analysis": {
            "overall_sentiment": "positive",
            "sentiment_score": 78.5,
            "sentiment_reasoning": "Mostly positive mentions..."
        }
    }
    ```
    """
    try:
        # Validate platforms
        supported_platforms = ["twitter", "reddit", "instagram", "facebook"]
        invalid_platforms = [p for p in platforms if p not in supported_platforms]
        
        if invalid_platforms:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platforms: {', '.join(invalid_platforms)}. Supported: {', '.join(supported_platforms)}"
            )

        # Scrape social media
        result = social_scraper.scrape_company_social(
            company_name=company_name,
            platforms=platforms,
            max_results_per_platform=max_results
        )

        logger.info(f"Social media scrape completed: {company_name} - {result['total_mentions']} mentions")
        
        return {
            "message": "Social media scraping completed",
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Social media scraping error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Social media scraping failed: {str(e)}"
        )


@router.get("/profile/{profile_url:path}")
async def scrape_linkedin_profile(
    profile_url: str,
    db: Session = Depends(get_db)
):
    """
    Scrape individual LinkedIn profile for detailed information

    **Extracted Data**:
    - Full name and headline
    - Current position and company
    - Work experience history
    - Education background
    - Skills and endorsements
    - Connection count

    **Parameters**:
    - `profile_url`: LinkedIn profile URL (e.g., https://linkedin.com/in/johndoe)

    **Returns**:
    - Complete profile data
    - Experience timeline
    - Education history
    - Skills list
    """
    try:
        # Validate profile URL
        if "linkedin.com/in/" not in profile_url:
            raise HTTPException(
                status_code=400,
                detail="Invalid LinkedIn profile URL format"
            )

        result = linkedin_scraper.scrape_profile(profile_url=profile_url)

        return {
            "message": "Profile scraped successfully",
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile scraping error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Profile scraping failed: {str(e)}"
        )
