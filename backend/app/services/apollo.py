"""
Apollo.io Contact Enrichment Service

Provides contact and company data enrichment using Apollo.io API.
Apollo is a B2B data enrichment platform that provides:
- Person enrichment (email/name → full profile with job title, LinkedIn, phone)
- Company enrichment (domain → company details, size, revenue, tech stack)

API Documentation: https://api.apollo.io/api/v1/
Rate Limits: 600 calls/hour (10 calls/minute)
"""

import os
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.core.logging import setup_logging
from app.core.exceptions import (
    MissingAPIKeyError,
    APIAuthenticationError,
    APIRateLimitError,
    APIConnectionError,
    APITimeoutError,
    ValidationError
)
from app.services.crm.base import Contact

logger = setup_logging(__name__)


class ApolloService:
    """
    Service for Apollo.io contact and company enrichment.
    
    Features:
    - Person enrichment by email, name, or LinkedIn URL
    - Company enrichment by domain or company name
    - Bulk enrichment (up to 10 records per request)
    - Rate limit handling with retry logic
    - Credit usage tracking
    """
    
    API_BASE_URL = "https://api.apollo.io/api/v1"
    TIMEOUT = 30  # seconds
    RATE_LIMIT_PER_HOUR = 600  # API limit
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Apollo service.
        
        Args:
            api_key: Apollo API key (optional, reads from environment if not provided)
        
        Raises:
            MissingAPIKeyError: If API key not provided and not in environment
        """
        self.api_key = api_key or os.getenv("APOLLO_API_KEY")
        
        if not self.api_key:
            raise MissingAPIKeyError(
                "APOLLO_API_KEY environment variable not set",
                context={"api_key": "APOLLO_API_KEY"}
            )
        
        # HTTP client for async requests
        self.client = httpx.AsyncClient(
            base_url=self.API_BASE_URL,
            timeout=self.TIMEOUT,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
                "accept": "application/json",
                "x-api-key": self.api_key
            }
        )
    
    async def enrich_contact(
        self,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        domain: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        reveal_personal_email: bool = False,
        reveal_phone: bool = False
    ) -> Contact:
        """
        Enrich contact data using Apollo person match API.
        
        Args:
            email: Business email address
            first_name: First name (works best with last_name and domain)
            last_name: Last name
            domain: Company domain (e.g., "apollo.io")
            linkedin_url: LinkedIn profile URL
            reveal_personal_email: Get personal email (consumes extra credits)
            reveal_phone: Get phone number (consumes extra credits, async delivery)
        
        Returns:
            Enriched Contact object with Apollo data
        
        Raises:
            ValidationError: If no identifying information provided
            APIAuthenticationError: If API key is invalid
            APIRateLimitError: If rate limit exceeded
            APIConnectionError: If request fails
        """
        # Validate input
        if not any([email, (first_name and last_name), linkedin_url]):
            raise ValidationError(
                "Must provide email, first_name+last_name, or linkedin_url",
                context={"provided": {"email": email, "name": f"{first_name} {last_name}"}}
            )
        
        # Build request parameters
        params = {}
        if email:
            params["email"] = email
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        if domain:
            params["domain"] = domain.replace("www.", "").replace("@", "")
        if linkedin_url:
            params["linkedin_url"] = linkedin_url
        if reveal_personal_email:
            params["reveal_personal_emails"] = "true"
        if reveal_phone:
            params["reveal_phone_number"] = "true"
        
        # Make API request
        try:
            response = await self.client.post(
                "/people/match",
                params=params
            )
            
            # Handle response
            if response.status_code == 200:
                data = response.json()
                return self._map_person_to_contact(data.get("person", {}))
            
            elif response.status_code == 401:
                raise APIAuthenticationError(
                    "Invalid Apollo API key",
                    context={"status_code": 401}
                )
            
            elif response.status_code == 429:
                error_data = response.json()
                raise APIRateLimitError(
                    f"Apollo rate limit exceeded: {error_data.get('message', 'Too many requests')}",
                    context={"status_code": 429, "response": error_data}
                )
            
            elif response.status_code == 422:
                error_data = response.json()
                raise ValidationError(
                    f"Apollo API validation error: {error_data.get('error', 'Invalid parameters')}",
                    context={"status_code": 422, "params": params}
                )
            
            else:
                raise APIConnectionError(
                    f"Apollo API error: HTTP {response.status_code}",
                    context={"status_code": response.status_code, "response": response.text}
                )
        
        except httpx.TimeoutException as e:
            raise APITimeoutError(
                f"Apollo API request timed out after {self.TIMEOUT}s",
                context={"timeout": self.TIMEOUT, "params": params}
            )
        
        except httpx.RequestError as e:
            raise APIConnectionError(
                f"Failed to connect to Apollo API: {str(e)}",
                context={"error": str(e), "params": params}
            )
    
    async def enrich_company(
        self,
        domain: str
    ) -> Dict[str, Any]:
        """
        Enrich company data using Apollo organization enrich API.
        
        Args:
            domain: Company domain without "www." or "@" (e.g., "apollo.io")
        
        Returns:
            Dictionary with enriched company data
        
        Raises:
            ValidationError: If domain is invalid
            APIAuthenticationError: If API key is invalid
            APIRateLimitError: If rate limit exceeded
            APIConnectionError: If request fails
        """
        # Clean domain
        clean_domain = domain.replace("www.", "").replace("@", "").strip()
        
        if not clean_domain:
            raise ValidationError(
                "Domain cannot be empty",
                context={"domain": domain}
            )
        
        # Make API request
        try:
            response = await self.client.post(
                "/organizations/enrich",
                params={"domain": clean_domain}
            )
            
            # Handle response
            if response.status_code == 200:
                data = response.json()
                org = data.get("organization", {})
                
                return {
                    "id": org.get("id"),
                    "name": org.get("name"),
                    "domain": org.get("primary_domain"),
                    "website": org.get("website_url"),
                    "linkedin_url": org.get("linkedin_url"),
                    "twitter_url": org.get("twitter_url"),
                    "facebook_url": org.get("facebook_url"),
                    "founded_year": org.get("founded_year"),
                    "industry": org.get("industry"),
                    "employee_count": org.get("estimated_num_employees"),
                    "logo_url": org.get("logo_url"),
                    "keywords": org.get("keywords", []),
                    "address": {
                        "street": org.get("street_address"),
                        "city": org.get("city"),
                        "state": org.get("state"),
                        "postal_code": org.get("postal_code"),
                        "country": org.get("country")
                    },
                    "raw_address": org.get("raw_address"),
                    "alexa_ranking": org.get("alexa_ranking")
                }
            
            elif response.status_code == 401:
                raise APIAuthenticationError(
                    "Invalid Apollo API key",
                    context={"status_code": 401}
                )
            
            elif response.status_code == 429:
                error_data = response.json()
                raise APIRateLimitError(
                    f"Apollo rate limit exceeded: {error_data.get('message', 'Too many requests')}",
                    context={"status_code": 429, "response": error_data}
                )
            
            elif response.status_code == 422:
                error_data = response.json()
                raise ValidationError(
                    f"Apollo API validation error: {error_data.get('error', 'Invalid domain')}",
                    context={"status_code": 422, "domain": clean_domain}
                )
            
            else:
                raise APIConnectionError(
                    f"Apollo API error: HTTP {response.status_code}",
                    context={"status_code": response.status_code, "response": response.text}
                )
        
        except httpx.TimeoutException as e:
            raise APITimeoutError(
                f"Apollo API request timed out after {self.TIMEOUT}s",
                context={"timeout": self.TIMEOUT, "domain": clean_domain}
            )
        
        except httpx.RequestError as e:
            raise APIConnectionError(
                f"Failed to connect to Apollo API: {str(e)}",
                context={"error": str(e), "domain": clean_domain}
            )
    
    async def bulk_enrich_contacts(
        self,
        contacts: List[Dict[str, str]],
        reveal_personal_emails: bool = False
    ) -> List[Contact]:
        """
        Enrich multiple contacts in a single API call (max 10).
        
        Args:
            contacts: List of contact dicts with identifying info
                     Each dict can have: email, first_name, last_name, domain
            reveal_personal_emails: Get personal emails (consumes extra credits)
        
        Returns:
            List of enriched Contact objects
        
        Raises:
            ValidationError: If more than 10 contacts or invalid data
            APIAuthenticationError: If API key is invalid
            APIRateLimitError: If rate limit exceeded
        """
        if len(contacts) > 10:
            raise ValidationError(
                "Bulk enrichment limited to 10 contacts per request",
                context={"provided": len(contacts), "max": 10}
            )
        
        # Build request body
        request_body = {
            "details": contacts,
            "reveal_personal_emails": reveal_personal_emails
        }
        
        try:
            response = await self.client.post(
                "/people/bulk_match",
                json=request_body
            )
            
            if response.status_code == 200:
                data = response.json()
                enriched_contacts = []
                
                for match in data.get("matches", []):
                    person = match.get("person")
                    if person:
                        enriched_contacts.append(self._map_person_to_contact(person))
                
                logger.info(
                    f"Bulk enrichment complete: {len(enriched_contacts)} contacts enriched, "
                    f"{data.get('credits_consumed', 0)} credits consumed"
                )
                
                return enriched_contacts
            
            elif response.status_code == 401:
                raise APIAuthenticationError("Invalid Apollo API key")
            
            elif response.status_code == 429:
                error_data = response.json()
                raise APIRateLimitError(f"Apollo rate limit exceeded: {error_data.get('message')}")
            
            else:
                raise APIConnectionError(f"Apollo API error: HTTP {response.status_code}")
        
        except httpx.TimeoutException:
            raise APITimeoutError(f"Apollo bulk enrichment timed out after {self.TIMEOUT}s")
        
        except httpx.RequestError as e:
            raise APIConnectionError(f"Failed to connect to Apollo API: {str(e)}")
    
    def _map_person_to_contact(self, person_data: Dict[str, Any]) -> Contact:
        """
        Map Apollo person data to Contact model.
        
        Args:
            person_data: Apollo person object from API response
        
        Returns:
            Contact object with mapped data
        """
        # Extract employment info (most recent job)
        employment = person_data.get("employment_history", [])
        current_job = employment[0] if employment else {}
        
        return Contact(
            email=person_data.get("email") or person_data.get("personal_email", ""),
            first_name=person_data.get("first_name"),
            last_name=person_data.get("last_name"),
            full_name=person_data.get("name"),
            title=person_data.get("title") or current_job.get("title"),
            company=current_job.get("organization_name") or person_data.get("organization", {}).get("name"),
            phone=person_data.get("phone_number"),
            linkedin_url=person_data.get("linkedin_url"),
            source_platform="apollo",
            external_ids={"apollo": person_data.get("id")},
            custom_fields={
                "headline": person_data.get("headline"),
                "email_status": person_data.get("email_status"),
                "personal_email": person_data.get("personal_email"),
                "organization_id": person_data.get("organization_id"),
                "seniority": person_data.get("seniority"),
                "departments": person_data.get("departments", []),
                "employment_history": employment[:3]  # Keep last 3 jobs
            }
        )
    
    async def get_credit_balance(self) -> Dict[str, Any]:
        """
        Get remaining API credits and usage information.
        
        Returns:
            Dictionary with credit balance and usage stats
        
        Note:
            Apollo doesn't provide a dedicated credits endpoint.
            This is a placeholder for tracking credits via response headers
            or external tracking. Implement based on your Apollo plan.
        """
        # TODO: Implement credit tracking
        # Options:
        # 1. Track locally based on API calls
        # 2. Parse response headers if Apollo provides them
        # 3. Use separate Apollo dashboard API if available
        
        logger.warning("Credit balance tracking not yet implemented")
        return {
            "credits_remaining": "Unknown",
            "credits_used": "Unknown",
            "rate_limit_remaining": f"{self.RATE_LIMIT_PER_HOUR}/hour"
        }
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
