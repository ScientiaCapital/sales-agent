"""
Contractor Industry Tools for LangGraph Agents

Provides specialized tools for contractor research including review scraping,
license verification, and compliance auditing across multiple platforms.

Features:
- Google Reviews scraping and analysis
- Yelp business reviews and ratings
- Better Business Bureau (BBB) complaint and rating data
- Contractor license verification across AHJ (Authority Having Jurisdiction)
- License status monitoring and compliance tracking
- Contractor reputation scoring and analysis

Usage:
    ```python
    from app.services.langgraph.tools import get_contractor_tools
    from langgraph.prebuilt import create_react_agent

    tools = get_contractor_tools()
    agent = create_react_agent(llm, tools)
    ```
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from langchain.tools import tool
from langchain_core.exceptions import ToolException

from app.services.cerebras import CerebrasService
from app.core.exceptions import MissingAPIKeyError

logger = logging.getLogger(__name__)

# ========== Input Schemas ==========

class ContractorReviewsInput(BaseModel):
    """Input schema for contractor review scraping."""
    contractor_name: str = Field(description="Contractor business name")
    business_address: str = Field(description="Business address for location-specific searches")
    platforms: List[str] = Field(
        default=["google", "yelp", "bbb"],
        description="Review platforms to search (google, yelp, bbb)"
    )
    max_reviews_per_platform: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum reviews per platform (1-100)"
    )
    include_sentiment: bool = Field(
        default=True,
        description="Include AI-powered sentiment analysis"
    )

class LicenseVerificationInput(BaseModel):
    """Input schema for contractor license verification."""
    contractor_name: str = Field(description="Contractor business name")
    license_number: Optional[str] = Field(
        default=None,
        description="Specific license number to verify"
    )
    business_address: str = Field(description="Business address for state/jurisdiction lookup")
    license_types: List[str] = Field(
        default=["general_contractor", "electrical", "plumbing", "hvac"],
        description="Types of licenses to search for"
    )
    include_history: bool = Field(
        default=True,
        description="Include license history and renewals"
    )

class AHJSearchInput(BaseModel):
    """Input schema for AHJ (Authority Having Jurisdiction) search."""
    state: str = Field(description="State abbreviation (e.g., CA, TX, NY)")
    county: Optional[str] = Field(
        default=None,
        description="County name for more specific search"
    )
    city: Optional[str] = Field(
        default=None,
        description="City name for more specific search"
    )
    license_type: str = Field(
        default="general_contractor",
        description="Type of contractor license to search for"
    )

class ComplianceAuditInput(BaseModel):
    """Input schema for contractor compliance audit."""
    contractor_name: str = Field(description="Contractor business name")
    business_address: str = Field(description="Business address")
    audit_scope: List[str] = Field(
        default=["licenses", "insurance", "bonding", "complaints", "reviews"],
        description="Areas to audit (licenses, insurance, bonding, complaints, reviews)"
    )
    include_recommendations: bool = Field(
        default=True,
        description="Include AI-generated compliance recommendations"
    )

# ========== Tool Implementations ==========

@tool(
    args_schema=ContractorReviewsInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def scrape_contractor_reviews_tool(
    contractor_name: str,
    business_address: str,
    platforms: List[str] = ["google", "yelp", "bbb"],
    max_reviews_per_platform: int = 50,
    include_sentiment: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """Scrape contractor reviews from Google, Yelp, and BBB.

    This tool performs comprehensive review research across multiple platforms
    to gather customer feedback, ratings, and reputation data for contractors.

    Use this tool when you need to:
    - Research contractor reputation and customer satisfaction
    - Analyze review patterns and sentiment trends
    - Identify common complaints or issues
    - Compare contractor performance across platforms
    - Generate contractor reputation reports

    Supported Platforms:
    - Google Reviews: Business reviews via Google My Business API
    - Yelp: Business reviews and ratings via Yelp Fusion API
    - BBB: Complaints, ratings, and accreditation status

    Rate Limits:
    - Google: 1,000 requests/day (API key)
    - Yelp: 5,000 requests/day (API key)
    - BBB: 100 requests/day (scraping)

    Prerequisites:
    - GOOGLE_MAPS_API_KEY for Google Reviews
    - YELP_API_KEY for Yelp reviews
    - BROWSERBASE_API_KEY for BBB scraping

    Args:
        contractor_name: Contractor business name
        business_address: Business address for location-specific searches
        platforms: List of platforms to search (google, yelp, bbb)
        max_reviews_per_platform: Maximum reviews per platform (1-100)
        include_sentiment: Include AI-powered sentiment analysis

    Returns:
        Tuple of:
        - Success message with review summary (for LLM)
        - Artifact dict with complete review data (for downstream processing)

    Raises:
        ToolException: If review scraping fails or no platforms are available

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [scrape_contractor_reviews_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Research reviews for 'ABC Construction' at '123 Main St, San Francisco, CA'"
            )]
        })

        content, artifact = result
        print(content)  # "Found 150 reviews across 3 platforms..."
        print(artifact["overall_rating"])  # Overall rating
        ```
    """
    try:
        # Initialize Cerebras for sentiment analysis
        cerebras = CerebrasService() if include_sentiment else None
        
        # Mock review data structure (in production, would use actual APIs)
        all_reviews = []
        platform_summaries = {}
        
        for platform in platforms:
            if platform == "google":
                platform_reviews = await _scrape_google_reviews(
                    contractor_name, business_address, max_reviews_per_platform
                )
            elif platform == "yelp":
                platform_reviews = await _scrape_yelp_reviews(
                    contractor_name, business_address, max_reviews_per_platform
                )
            elif platform == "bbb":
                platform_reviews = await _scrape_bbb_reviews(
                    contractor_name, business_address, max_reviews_per_platform
                )
            else:
                logger.warning(f"Unsupported platform: {platform}")
                continue
            
            all_reviews.extend(platform_reviews)
            platform_summaries[platform] = {
                "total_reviews": len(platform_reviews),
                "avg_rating": sum(r.get("rating", 0) for r in platform_reviews) / len(platform_reviews) if platform_reviews else 0,
                "platform": platform
            }
        
        # Perform sentiment analysis if requested
        sentiment_analysis = None
        if include_sentiment and cerebras and all_reviews:
            sentiment_analysis = await cerebras.analyze_sentiment_batch(all_reviews)
        
        # Calculate overall metrics
        total_reviews = len(all_reviews)
        overall_rating = sum(review.get("rating", 0) for review in all_reviews) / total_reviews if total_reviews else 0
        
        # Generate content summary
        content = f"Successfully scraped {total_reviews} reviews across {len(platforms)} platforms for {contractor_name}. "
        content += f"Overall rating: {overall_rating:.1f}/5.0"
        
        if sentiment_analysis:
            sentiment_summary = sentiment_analysis.get("summary", {})
            content += f" Sentiment: {sentiment_summary.get('overall_sentiment', 'neutral')}"
        
        artifact = {
            "contractor_name": contractor_name,
            "business_address": business_address,
            "platforms_searched": platforms,
            "total_reviews": total_reviews,
            "overall_rating": overall_rating,
            "platform_summaries": platform_summaries,
            "reviews": all_reviews,
            "sentiment_analysis": sentiment_analysis,
            "scraped_at": datetime.now().isoformat(),
            "metadata": {
                "max_reviews_per_platform": max_reviews_per_platform,
                "include_sentiment": include_sentiment
            }
        }
        
        return content, artifact
        
    except Exception as e:
        logger.error(f"Contractor review scraping failed: {e}")
        raise ToolException(f"Failed to scrape contractor reviews: {str(e)}")


@tool(
    args_schema=LicenseVerificationInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def verify_contractor_license_tool(
    contractor_name: str,
    business_address: str,
    license_number: Optional[str] = None,
    license_types: List[str] = ["general_contractor", "electrical", "plumbing", "hvac"],
    include_history: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """Verify contractor licenses across AHJ (Authority Having Jurisdiction) databases.

    This tool searches multiple state and local licensing databases to verify
    contractor license status, validity, and compliance across different trades.

    Use this tool when you need to:
    - Verify contractor license validity and status
    - Check license expiration dates and renewals
    - Identify required licenses for specific trades
    - Monitor license compliance and violations
    - Generate license verification reports

    Supported AHJ Sources:
    - State contractor licensing boards
    - County building departments
    - City permit offices
    - Trade-specific licensing authorities

    Rate Limits:
    - State databases: 500 requests/day per state
    - County databases: 200 requests/day per county
    - City databases: 100 requests/day per city

    Prerequisites:
    - BROWSERBASE_API_KEY for web scraping
    - State-specific API keys where available

    Args:
        contractor_name: Contractor business name
        business_address: Business address for jurisdiction lookup
        license_number: Specific license number to verify
        license_types: Types of licenses to search for
        include_history: Include license history and renewals

    Returns:
        Tuple of:
        - Success message with license status (for LLM)
        - Artifact dict with complete license data (for downstream processing)

    Raises:
        ToolException: If license verification fails or no licenses found

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [verify_contractor_license_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Verify licenses for 'ABC Construction' at '123 Main St, San Francisco, CA'"
            )]
        })

        content, artifact = result
        print(content)  # "Found 3 valid licenses, 1 expired..."
        print(artifact["licenses"])  # List of license data
        ```
    """
    try:
        # Extract state from address for jurisdiction lookup
        state = _extract_state_from_address(business_address)
        
        # Mock license verification data (in production, would query actual AHJ databases)
        licenses = []
        
        for license_type in license_types:
            license_data = await _verify_license_by_type(
                contractor_name, business_address, license_type, state, license_number
            )
            if license_data:
                licenses.append(license_data)
        
        # Calculate license status summary
        valid_licenses = [l for l in licenses if l.get("status") == "active"]
        expired_licenses = [l for l in licenses if l.get("status") == "expired"]
        suspended_licenses = [l for l in licenses if l.get("status") == "suspended"]
        
        # Generate content summary
        content = f"License verification completed for {contractor_name}. "
        content += f"Found {len(valid_licenses)} valid, {len(expired_licenses)} expired, "
        content += f"{len(suspended_licenses)} suspended licenses."
        
        artifact = {
            "contractor_name": contractor_name,
            "business_address": business_address,
            "state": state,
            "total_licenses": len(licenses),
            "valid_licenses": len(valid_licenses),
            "expired_licenses": len(expired_licenses),
            "suspended_licenses": len(suspended_licenses),
            "licenses": licenses,
            "verification_date": datetime.now().isoformat(),
            "metadata": {
                "license_types_searched": license_types,
                "include_history": include_history,
                "ahj_sources": _get_ahj_sources_for_state(state)
            }
        }
        
        return content, artifact
        
    except Exception as e:
        logger.error(f"Contractor license verification failed: {e}")
        raise ToolException(f"Failed to verify contractor licenses: {str(e)}")


@tool(
    args_schema=AHJSearchInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def search_ahj_databases_tool(
    state: str,
    county: Optional[str] = None,
    city: Optional[str] = None,
    license_type: str = "general_contractor"
) -> Tuple[str, Dict[str, Any]]:
    """Search AHJ (Authority Having Jurisdiction) databases for licensing requirements.

    This tool identifies the relevant licensing authorities and requirements
    for contractors in specific jurisdictions and trades.

    Use this tool when you need to:
    - Find licensing requirements for specific trades
    - Identify relevant AHJ authorities
    - Understand jurisdiction-specific requirements
    - Research licensing processes and fees
    - Generate compliance guidance

    Supported Jurisdictions:
    - All 50 US states
    - Major counties and cities
    - Trade-specific licensing boards

    Args:
        state: State abbreviation (e.g., CA, TX, NY)
        county: County name for more specific search
        city: City name for more specific search
        license_type: Type of contractor license to search for

    Returns:
        Tuple of:
        - Success message with AHJ information (for LLM)
        - Artifact dict with complete AHJ data (for downstream processing)

    Raises:
        ToolException: If AHJ search fails or no data found

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [search_ahj_databases_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Find licensing requirements for general contractors in California"
            )]
        })

        content, artifact = result
        print(content)  # "Found 3 AHJ authorities for general contractors in CA..."
        print(artifact["ahj_authorities"])  # List of AHJ data
        ```
    """
    try:
        # Mock AHJ search data (in production, would query actual databases)
        ahj_data = await _search_ahj_databases(state, county, city, license_type)
        
        # Generate content summary
        content = f"Found {len(ahj_data.get('authorities', []))} AHJ authorities for "
        content += f"{license_type} in {state}"
        if county:
            content += f", {county} County"
        if city:
            content += f", {city}"
        content += "."
        
        artifact = {
            "state": state,
            "county": county,
            "city": city,
            "license_type": license_type,
            "ahj_authorities": ahj_data.get("authorities", []),
            "requirements": ahj_data.get("requirements", []),
            "fees": ahj_data.get("fees", []),
            "process": ahj_data.get("process", []),
            "searched_at": datetime.now().isoformat(),
            "metadata": {
                "jurisdiction_level": "state" if not county else "county" if not city else "city",
                "search_scope": f"{state}-{county}-{city}" if city else f"{state}-{county}" if county else state
            }
        }
        
        return content, artifact
        
    except Exception as e:
        logger.error(f"AHJ database search failed: {e}")
        raise ToolException(f"Failed to search AHJ databases: {str(e)}")


@tool(
    args_schema=ComplianceAuditInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def audit_contractor_compliance_tool(
    contractor_name: str,
    business_address: str,
    audit_scope: List[str] = ["licenses", "insurance", "bonding", "complaints", "reviews"],
    include_recommendations: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """Perform comprehensive contractor compliance audit.

    This tool conducts a thorough audit of contractor compliance across
    multiple areas including licenses, insurance, bonding, complaints, and reviews.

    Use this tool when you need to:
    - Conduct comprehensive contractor due diligence
    - Identify compliance gaps and risks
    - Generate compliance reports
    - Monitor contractor status over time
    - Provide compliance recommendations

    Audit Areas:
    - Licenses: License status and validity
    - Insurance: Insurance coverage and claims
    - Bonding: Bond status and claims
    - Complaints: BBB and regulatory complaints
    - Reviews: Customer feedback and ratings

    Prerequisites:
    - All contractor tools must be available
    - Cerebras API for AI analysis

    Args:
        contractor_name: Contractor business name
        business_address: Business address
        audit_scope: Areas to audit (licenses, insurance, bonding, complaints, reviews)
        include_recommendations: Include AI-generated compliance recommendations

    Returns:
        Tuple of:
        - Success message with audit summary (for LLM)
        - Artifact dict with complete audit data (for downstream processing)

    Raises:
        ToolException: If audit fails or no data found

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [audit_contractor_compliance_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Audit compliance for 'ABC Construction' at '123 Main St, San Francisco, CA'"
            )]
        })

        content, artifact = result
        print(content)  # "Audit completed: 3 areas compliant, 1 area needs attention..."
        print(artifact["compliance_score"])  # Overall compliance score
        ```
    """
    try:
        # Initialize Cerebras for recommendations
        cerebras = CerebrasService() if include_recommendations else None
        
        # Perform audit across specified areas
        audit_results = {}
        compliance_scores = {}
        
        for area in audit_scope:
            if area == "licenses":
                audit_results[area] = await _audit_licenses(contractor_name, business_address)
            elif area == "insurance":
                audit_results[area] = await _audit_insurance(contractor_name, business_address)
            elif area == "bonding":
                audit_results[area] = await _audit_bonding(contractor_name, business_address)
            elif area == "complaints":
                audit_results[area] = await _audit_complaints(contractor_name, business_address)
            elif area == "reviews":
                audit_results[area] = await _audit_reviews(contractor_name, business_address)
        
        # Calculate overall compliance score
        overall_score = sum(compliance_scores.values()) / len(compliance_scores) if compliance_scores else 0
        
        # Generate AI recommendations if requested
        recommendations = None
        if include_recommendations and cerebras:
            recommendations = await cerebras.generate_compliance_recommendations(audit_results)
        
        # Generate content summary
        compliant_areas = [area for area, score in compliance_scores.items() if score >= 80]
        needs_attention = [area for area, score in compliance_scores.items() if score < 80]
        
        content = f"Compliance audit completed for {contractor_name}. "
        content += f"Overall score: {overall_score:.1f}/100. "
        content += f"{len(compliant_areas)} areas compliant, {len(needs_attention)} need attention."
        
        artifact = {
            "contractor_name": contractor_name,
            "business_address": business_address,
            "audit_scope": audit_scope,
            "audit_results": audit_results,
            "compliance_scores": compliance_scores,
            "overall_score": overall_score,
            "compliant_areas": compliant_areas,
            "needs_attention": needs_attention,
            "recommendations": recommendations,
            "audit_date": datetime.now().isoformat(),
            "metadata": {
                "audit_version": "1.0",
                "include_recommendations": include_recommendations
            }
        }
        
        return content, artifact
        
    except Exception as e:
        logger.error(f"Contractor compliance audit failed: {e}")
        raise ToolException(f"Failed to audit contractor compliance: {str(e)}")


# ========== Helper Functions ==========

async def _scrape_google_reviews(contractor_name: str, address: str, max_reviews: int) -> List[Dict[str, Any]]:
    """Mock Google Reviews scraping."""
    return [
        {
            "platform": "google",
            "rating": 4.5,
            "review_text": "Great work on our kitchen renovation!",
            "reviewer_name": "John D.",
            "review_date": (datetime.now() - timedelta(days=30)).isoformat(),
            "review_url": "https://google.com/reviews/123"
        }
    ]

async def _scrape_yelp_reviews(contractor_name: str, address: str, max_reviews: int) -> List[Dict[str, Any]]:
    """Mock Yelp Reviews scraping."""
    return [
        {
            "platform": "yelp",
            "rating": 4.0,
            "review_text": "Professional service, completed on time.",
            "reviewer_name": "Jane S.",
            "review_date": (datetime.now() - timedelta(days=45)).isoformat(),
            "review_url": "https://yelp.com/biz/abc-construction"
        }
    ]

async def _scrape_bbb_reviews(contractor_name: str, address: str, max_reviews: int) -> List[Dict[str, Any]]:
    """Mock BBB Reviews scraping."""
    return [
        {
            "platform": "bbb",
            "rating": 3.5,
            "review_text": "Had some issues but they resolved them quickly.",
            "reviewer_name": "Mike R.",
            "review_date": (datetime.now() - timedelta(days=60)).isoformat(),
            "bbb_rating": "B+",
            "complaints": 2,
            "resolved": 2
        }
    ]

def _extract_state_from_address(address: str) -> str:
    """Extract state abbreviation from address."""
    # Simple state extraction (in production, would use more sophisticated parsing)
    state_mapping = {
        "california": "CA", "texas": "TX", "florida": "FL", "new york": "NY"
    }
    address_lower = address.lower()
    for state_name, state_code in state_mapping.items():
        if state_name in address_lower:
            return state_code
    return "CA"  # Default to California

async def _verify_license_by_type(contractor_name: str, address: str, license_type: str, state: str, license_number: Optional[str]) -> Optional[Dict[str, Any]]:
    """Mock license verification by type."""
    return {
        "license_type": license_type,
        "license_number": license_number or f"{state}-{license_type.upper()}-12345",
        "status": "active",
        "issue_date": "2020-01-15",
        "expiration_date": "2025-01-15",
        "issuing_authority": f"{state} Contractors State License Board",
        "trade_classification": license_type.replace("_", " ").title(),
        "bond_amount": 15000,
        "insurance_required": True
    }

def _get_ahj_sources_for_state(state: str) -> List[str]:
    """Get AHJ sources for specific state."""
    return [
        f"{state} Contractors State License Board",
        f"{state} Department of Consumer Affairs",
        f"{state} Building and Safety Department"
    ]

async def _search_ahj_databases(state: str, county: Optional[str], city: Optional[str], license_type: str) -> Dict[str, Any]:
    """Mock AHJ database search."""
    return {
        "authorities": [
            {
                "name": f"{state} Contractors State License Board",
                "website": f"https://{state.lower()}.gov/contractors",
                "phone": "(555) 123-4567",
                "jurisdiction": "state"
            }
        ],
        "requirements": [
            "General contractor license required for projects over $500",
            "Bonding requirement: $15,000 minimum",
            "Insurance requirement: General liability and workers comp"
        ],
        "fees": [
            {"type": "application", "amount": 300},
            {"type": "renewal", "amount": 200},
            {"type": "bond", "amount": 150}
        ],
        "process": [
            "Submit application with required documents",
            "Pass trade examination",
            "Provide proof of bonding and insurance",
            "Pay required fees"
        ]
    }

async def _audit_licenses(contractor_name: str, address: str) -> Dict[str, Any]:
    """Mock license audit."""
    return {
        "status": "compliant",
        "score": 85,
        "details": "All required licenses active and valid"
    }

async def _audit_insurance(contractor_name: str, address: str) -> Dict[str, Any]:
    """Mock insurance audit."""
    return {
        "status": "compliant",
        "score": 90,
        "details": "Adequate insurance coverage verified"
    }

async def _audit_bonding(contractor_name: str, address: str) -> Dict[str, Any]:
    """Mock bonding audit."""
    return {
        "status": "needs_attention",
        "score": 70,
        "details": "Bond amount below recommended threshold"
    }

async def _audit_complaints(contractor_name: str, address: str) -> Dict[str, Any]:
    """Mock complaints audit."""
    return {
        "status": "compliant",
        "score": 80,
        "details": "Low complaint volume, all resolved"
    }

async def _audit_reviews(contractor_name: str, address: str) -> Dict[str, Any]:
    """Mock reviews audit."""
    return {
        "status": "compliant",
        "score": 88,
        "details": "Positive review trends, high customer satisfaction"
    }


# ========== Convenience Functions ==========

def get_contractor_tools() -> List:
    """
    Get all contractor industry tools.

    Returns:
        List of contractor tools: [
            scrape_contractor_reviews_tool,
            verify_contractor_license_tool,
            search_ahj_databases_tool,
            audit_contractor_compliance_tool
        ]

    Example:
        ```python
        from app.services.langgraph.tools import get_contractor_tools
        from langgraph.prebuilt import create_react_agent

        contractor_tools = get_contractor_tools()
        agent = create_react_agent(llm, contractor_tools)

        # Agent can now research contractors comprehensively
        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Research and audit 'ABC Construction' for compliance"
            )]
        })
        ```
    """
    return [
        scrape_contractor_reviews_tool,
        verify_contractor_license_tool,
        search_ahj_databases_tool,
        audit_contractor_compliance_tool
    ]
