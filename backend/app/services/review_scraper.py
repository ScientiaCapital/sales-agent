"""
Review Scraper Service

Multi-platform review aggregation for reputation scoring:
- Google Reviews (rating + count)
- Yelp Reviews (rating + count)
- BBB Reviews (accreditation + complaints)
- Facebook Reviews (rating + count)

Used in enrichment pipeline for lead validation.
"""
import httpx
import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """Result from a single review platform"""
    platform: str  # "google", "yelp", "bbb", "facebook"
    rating: Optional[float]  # 0-5 scale
    review_count: Optional[int]
    status: str  # "success", "not_found", "blocked", "error"
    url: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ReviewAggregation:
    """Aggregated results from all review platforms"""
    overall_reputation_score: float  # 0-100
    total_reviews: int
    average_rating: float  # 0-5 scale
    platform_results: List[ReviewResult]
    has_negative_signals: bool  # BBB complaints, ratings < 3.0
    data_quality: str  # "high", "medium", "low", "none"


class ReviewScraperService:
    """
    Unified review scraping service with parallel execution.

    Quick Validation Approach:
    - 5s timeout per platform
    - Fail gracefully (return empty data)
    - No retries (single attempt)
    - Basic rating + count extraction
    """

    TIMEOUT_SECONDS = 5
    MAX_REDIRECTS = 3

    def __init__(self):
        """Initialize HTTP client for scraping"""
        self.client = httpx.AsyncClient(
            timeout=self.TIMEOUT_SECONDS,
            follow_redirects=True,
            max_redirects=self.MAX_REDIRECTS,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

    async def get_reviews(
        self,
        company_name: str,
        company_website: Optional[str] = None
    ) -> ReviewAggregation:
        """
        Scrape reviews from all platforms in parallel.

        Args:
            company_name: Company name for search
            company_website: Company website URL (optional)

        Returns:
            ReviewAggregation with reputation score and platform results
        """
        logger.info(f"Starting review aggregation for: {company_name}")

        # Execute all scrapers in parallel with graceful failure
        results = await asyncio.gather(
            self._scrape_google(company_name),
            self._scrape_yelp(company_name),
            self._scrape_bbb(company_name),
            self._scrape_facebook(company_name),
            return_exceptions=True  # Don't fail if one scraper fails
        )

        # Convert exceptions to error results
        platform_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                platform_name = ["google", "yelp", "bbb", "facebook"][i]
                logger.error(f"{platform_name} scraper failed: {result}")
                platform_results.append(ReviewResult(
                    platform=platform_name,
                    rating=None,
                    review_count=None,
                    status="error",
                    error_message=str(result)
                ))
            else:
                platform_results.append(result)

        # Calculate aggregated metrics
        aggregation = self._aggregate_results(platform_results)

        logger.info(
            f"Review aggregation complete for {company_name}: "
            f"score={aggregation.overall_reputation_score:.1f}, "
            f"rating={aggregation.average_rating:.1f}, "
            f"reviews={aggregation.total_reviews}"
        )

        return aggregation

    async def _scrape_google(self, company_name: str) -> ReviewResult:
        """
        Scrape Google Reviews (Google Business Profile).

        Quick approach: Search Google for "[company name] reviews"
        and extract rating from Knowledge Graph snippet.
        """
        try:
            search_query = f"{company_name} reviews"
            search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"

            response = await self.client.get(search_url)

            if response.status_code != 200:
                return ReviewResult(
                    platform="google",
                    rating=None,
                    review_count=None,
                    status="error",
                    error_message=f"HTTP {response.status_code}"
                )

            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for rating in Knowledge Graph (common patterns)
            # Example: <span>4.5</span> <span>(123 reviews)</span>
            rating = None
            review_count = None

            # Pattern 1: Knowledge Graph rating
            rating_elem = soup.find('span', {'aria-hidden': 'true', 'role': 'img'})
            if rating_elem and rating_elem.text:
                rating_match = re.search(r'(\d+\.?\d*)', rating_elem.text)
                if rating_match:
                    rating = float(rating_match.group(1))

            # Pattern 2: Review count
            review_elem = soup.find(text=re.compile(r'\d+\s+(reviews?|ratings?)'))
            if review_elem:
                count_match = re.search(r'(\d+)', review_elem)
                if count_match:
                    review_count = int(count_match.group(1))

            if rating or review_count:
                return ReviewResult(
                    platform="google",
                    rating=rating,
                    review_count=review_count,
                    status="success",
                    url=search_url
                )
            else:
                return ReviewResult(
                    platform="google",
                    rating=None,
                    review_count=None,
                    status="not_found",
                    error_message="No Google Business Profile found"
                )

        except httpx.TimeoutException:
            logger.warning(f"Google scraping timeout for: {company_name}")
            return ReviewResult(
                platform="google",
                rating=None,
                review_count=None,
                status="error",
                error_message="Timeout"
            )
        except Exception as e:
            logger.error(f"Google scraping failed for {company_name}: {e}")
            return ReviewResult(
                platform="google",
                rating=None,
                review_count=None,
                status="error",
                error_message=str(e)
            )

    async def _scrape_yelp(self, company_name: str) -> ReviewResult:
        """
        Scrape Yelp Reviews.

        Quick approach: Search Yelp and extract rating from search results.
        """
        try:
            search_query = company_name.replace(' ', '+')
            search_url = f"https://www.yelp.com/search?find_desc={search_query}"

            response = await self.client.get(search_url)

            if response.status_code != 200:
                return ReviewResult(
                    platform="yelp",
                    rating=None,
                    review_count=None,
                    status="error",
                    error_message=f"HTTP {response.status_code}"
                )

            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for first business result
            # Yelp structure: <div class="rating-large"> or <span role="img" aria-label="4.5 star rating">
            rating = None
            review_count = None

            # Pattern 1: Star rating in aria-label
            rating_elem = soup.find('span', attrs={'role': 'img', 'aria-label': re.compile(r'\d+\.?\d*\s+star')})
            if rating_elem:
                rating_match = re.search(r'(\d+\.?\d*)', rating_elem['aria-label'])
                if rating_match:
                    rating = float(rating_match.group(1))

            # Pattern 2: Review count
            review_elem = soup.find(text=re.compile(r'\d+\s+reviews?'))
            if review_elem:
                count_match = re.search(r'(\d+)', review_elem)
                if count_match:
                    review_count = int(count_match.group(1))

            if rating or review_count:
                return ReviewResult(
                    platform="yelp",
                    rating=rating,
                    review_count=review_count,
                    status="success",
                    url=search_url
                )
            else:
                return ReviewResult(
                    platform="yelp",
                    rating=None,
                    review_count=None,
                    status="not_found",
                    error_message="No Yelp listing found"
                )

        except httpx.TimeoutException:
            logger.warning(f"Yelp scraping timeout for: {company_name}")
            return ReviewResult(
                platform="yelp",
                rating=None,
                review_count=None,
                status="error",
                error_message="Timeout"
            )
        except Exception as e:
            logger.error(f"Yelp scraping failed for {company_name}: {e}")
            return ReviewResult(
                platform="yelp",
                rating=None,
                review_count=None,
                status="error",
                error_message=str(e)
            )

    async def _scrape_bbb(self, company_name: str) -> ReviewResult:
        """
        Scrape BBB (Better Business Bureau) Reviews.

        Quick approach: Search BBB and check accreditation + rating.
        BBB rating scale is A+ to F, convert to 0-5 scale.
        """
        try:
            search_query = company_name.replace(' ', '+')
            search_url = f"https://www.bbb.org/search?find_text={search_query}"

            response = await self.client.get(search_url)

            if response.status_code != 200:
                return ReviewResult(
                    platform="bbb",
                    rating=None,
                    review_count=None,
                    status="error",
                    error_message=f"HTTP {response.status_code}"
                )

            soup = BeautifulSoup(response.text, 'html.parser')

            # BBB uses letter grades (A+, A, A-, B+, etc.)
            # Convert to 0-5 scale: A+ = 5.0, A = 4.5, A- = 4.0, B+ = 3.5, etc.
            grade_mapping = {
                'A+': 5.0, 'A': 4.5, 'A-': 4.0,
                'B+': 3.5, 'B': 3.0, 'B-': 2.5,
                'C+': 2.0, 'C': 1.5, 'C-': 1.0,
                'D+': 0.75, 'D': 0.5, 'D-': 0.25,
                'F': 0.0
            }

            rating = None
            review_count = None

            # Look for BBB rating badge
            grade_elem = soup.find(text=re.compile(r'BBB Rating:\s*[A-F][+-]?'))
            if grade_elem:
                grade_match = re.search(r'([A-F][+-]?)', grade_elem)
                if grade_match:
                    grade = grade_match.group(1)
                    rating = grade_mapping.get(grade)

            # Look for review count
            review_elem = soup.find(text=re.compile(r'\d+\s+(customer reviews?|complaints?)'))
            if review_elem:
                count_match = re.search(r'(\d+)', review_elem)
                if count_match:
                    review_count = int(count_match.group(1))

            if rating or review_count:
                return ReviewResult(
                    platform="bbb",
                    rating=rating,
                    review_count=review_count,
                    status="success",
                    url=search_url
                )
            else:
                return ReviewResult(
                    platform="bbb",
                    rating=None,
                    review_count=None,
                    status="not_found",
                    error_message="No BBB listing found"
                )

        except httpx.TimeoutException:
            logger.warning(f"BBB scraping timeout for: {company_name}")
            return ReviewResult(
                platform="bbb",
                rating=None,
                review_count=None,
                status="error",
                error_message="Timeout"
            )
        except Exception as e:
            logger.error(f"BBB scraping failed for {company_name}: {e}")
            return ReviewResult(
                platform="bbb",
                rating=None,
                review_count=None,
                status="error",
                error_message=str(e)
            )

    async def _scrape_facebook(self, company_name: str) -> ReviewResult:
        """
        Scrape Facebook Business Page Reviews.

        Quick approach: Search Facebook for company page.
        Note: Facebook requires authentication for full data, so this is limited.
        """
        try:
            # Facebook search is heavily restricted without login
            # Return not_found for now - can be enhanced with Graph API later
            return ReviewResult(
                platform="facebook",
                rating=None,
                review_count=None,
                status="not_found",
                error_message="Facebook scraping requires authentication (Graph API not configured)"
            )

        except Exception as e:
            logger.error(f"Facebook scraping failed for {company_name}: {e}")
            return ReviewResult(
                platform="facebook",
                rating=None,
                review_count=None,
                status="error",
                error_message=str(e)
            )

    def _aggregate_results(self, results: List[ReviewResult]) -> ReviewAggregation:
        """
        Aggregate results from all platforms into overall reputation score.

        Scoring Formula:
        - Average rating (0-5) contributes 70% (normalized to 70 points)
        - Review volume contributes 20% (capped at 100 reviews = 20 points)
        - BBB accreditation contributes 10% (present = 10 points)

        Returns:
            ReviewAggregation with 0-100 reputation score
        """
        # Extract successful results
        successful_results = [r for r in results if r.status == "success"]

        # Calculate average rating
        ratings = [r.rating for r in successful_results if r.rating is not None]
        average_rating = sum(ratings) / len(ratings) if ratings else 0.0

        # Calculate total reviews
        review_counts = [r.review_count for r in successful_results if r.review_count is not None]
        total_reviews = sum(review_counts) if review_counts else 0

        # Check for BBB presence (positive signal)
        has_bbb = any(r.platform == "bbb" and r.status == "success" for r in results)

        # Check for negative signals
        has_negative_signals = any(
            r.rating and r.rating < 3.0  # Low rating
            for r in successful_results
        )

        # Calculate reputation score (0-100)
        rating_score = (average_rating / 5.0) * 70  # 70% weight
        volume_score = (min(total_reviews, 100) / 100) * 20  # 20% weight, capped at 100 reviews
        bbb_score = 10 if has_bbb else 0  # 10% weight

        overall_score = rating_score + volume_score + bbb_score

        # Determine data quality
        success_count = len(successful_results)
        if success_count >= 3:
            data_quality = "high"
        elif success_count >= 2:
            data_quality = "medium"
        elif success_count >= 1:
            data_quality = "low"
        else:
            data_quality = "none"

        return ReviewAggregation(
            overall_reputation_score=round(overall_score, 1),
            total_reviews=total_reviews,
            average_rating=round(average_rating, 1),
            platform_results=results,
            has_negative_signals=has_negative_signals,
            data_quality=data_quality
        )

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Singleton instance
_scraper_instance: Optional[ReviewScraperService] = None


async def get_review_scraper() -> ReviewScraperService:
    """Get or create review scraper singleton"""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = ReviewScraperService()
    return _scraper_instance
