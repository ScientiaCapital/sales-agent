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
import re
import httpx
from typing import Dict, Any, Optional, List

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
        # Phone reveal requires webhook URL for async delivery (Apollo API requirement)
        if reveal_phone:
            webhook_base = os.getenv('APOLLO_WEBHOOK_BASE_URL')
            if webhook_base:
                params["reveal_phone_number"] = "true"
                params["webhook_url"] = f"{webhook_base}/api/v1/webhooks/apollo/phone-reveal"
                logger.info(f"Phone reveal enabled with webhook: {params['webhook_url']}")
            else:
                logger.warning("Phone reveal requested but APOLLO_WEBHOOK_BASE_URL not configured")
        
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
        
        except httpx.TimeoutException:
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
        
        except httpx.TimeoutException:
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

    async def bulk_enrich_with_reveal(
        self,
        contacts: List[Dict[str, str]],
        reveal_emails: bool = True,
        reveal_phones: bool = True
    ) -> Dict[str, Any]:
        """
        Bulk enrich up to 10 contacts with PAID email and phone reveals.

        This is the credit-efficient method for revealing real contact info:
        - Emails: Returned immediately in response (~1 credit each)
        - Phones: Delivered async to webhook URL (~1-2 credits each)

        Args:
            contacts: List of contact dicts with identifying info.
                     Each dict should have: first_name, last_name, domain
                     Optional: email, linkedin_url, organization_name
            reveal_emails: Get verified email addresses (costs credits)
            reveal_phones: Get phone numbers via webhook (costs credits)

        Returns:
            Dict with:
                - enriched_contacts: List of contacts with revealed emails
                - credits_consumed: Number of credits used
                - phone_webhook_pending: True if phones will arrive via webhook

        Note:
            Phone reveals require APOLLO_WEBHOOK_BASE_URL environment variable.
            Phones are delivered async to /api/v1/apollo/webhooks/phone-reveal
        """
        if len(contacts) > 10:
            raise ValidationError(
                "Bulk enrichment limited to 10 contacts per request",
                context={"provided": len(contacts), "max": 10}
            )

        # Build request params
        params = {}
        if reveal_emails:
            params["reveal_personal_emails"] = "true"

        # Phone reveal requires webhook URL
        phone_webhook_pending = False
        if reveal_phones:
            webhook_base = os.getenv('APOLLO_WEBHOOK_BASE_URL')
            if webhook_base:
                params["reveal_phone_number"] = "true"
                params["webhook_url"] = f"{webhook_base}/api/v1/webhooks/apollo/phone-reveal"
                phone_webhook_pending = True
                logger.info(f"Phone reveal enabled with webhook: {params['webhook_url']}")
            else:
                logger.warning(
                    "Phone reveal requested but APOLLO_WEBHOOK_BASE_URL not configured. "
                    "Phones will NOT be retrieved. Set APOLLO_WEBHOOK_BASE_URL in .env"
                )

        # Build request body
        request_body = {"details": contacts}

        try:
            response = await self.client.post(
                "/people/bulk_match",
                params=params,
                json=request_body
            )

            if response.status_code == 200:
                data = response.json()
                enriched_contacts = []

                for match in data.get("matches", []):
                    # Handle null matches (person not found in Apollo)
                    if match is None:
                        continue

                    # bulk_match returns data directly on match object, NOT nested under "person"
                    # Check for "person" key for backwards compatibility, otherwise use match directly
                    person = match.get("person") if "person" in match else match
                    if not person or not person.get("id"):
                        continue

                    # Extract key fields
                    email = person.get("email") or person.get("personal_email")
                    is_real_email = email and "@" in email and "not_unlocked" not in email.lower()

                    contact = {
                        "apollo_person_id": person.get("id"),
                        "first_name": person.get("first_name"),
                        "last_name": person.get("last_name"),
                        "full_name": person.get("name"),
                        "email": email if is_real_email else None,
                        "email_verified": is_real_email,
                        "email_status": person.get("email_status"),
                        "phone": person.get("phone_number"),  # May be None if async
                        "title": person.get("title"),
                        "linkedin_url": person.get("linkedin_url"),
                        "seniority": person.get("seniority"),
                        "departments": person.get("departments", []),
                    }
                    enriched_contacts.append(contact)

                credits = data.get("credits_consumed", len(enriched_contacts))
                logger.info(
                    f"Bulk enrichment with reveal complete: {len(enriched_contacts)} contacts, "
                    f"{credits} credits consumed, phone_webhook_pending={phone_webhook_pending}"
                )

                return {
                    "enriched_contacts": enriched_contacts,
                    "credits_consumed": credits,
                    "phone_webhook_pending": phone_webhook_pending
                }

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

    async def search_contacts_free(
        self,
        domain: str,
        job_titles: Optional[List[str]] = None,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        FREE search for contacts at a company - NO credits consumed!

        Uses /mixed_people/api_search endpoint which is FREE.
        Returns names, titles, LinkedIn URLs - but NO emails or phones.
        Use bulk_enrich_with_reveal() to get actual contact info.

        Args:
            domain: Company domain (e.g., "acmecompany.com")
            job_titles: Optional list of titles to filter (e.g., ["CEO", "Owner"])
            max_results: Max contacts to return (default: 50)

        Returns:
            List of contact dicts with:
                - first_name, last_name, name
                - title, seniority
                - linkedin_url
                - apollo_person_id (for matching later)
                - NO email or phone (these require paid reveal)
        """
        clean_domain = domain.replace("www.", "").replace("@", "").strip()

        if not clean_domain:
            raise ValidationError("Domain cannot be empty", context={"domain": domain})

        # Build search request for FREE /mixed_people/api_search
        search_body = {
            "q_organization_domains_list": [clean_domain],
            "per_page": min(max_results, 100),
            "page": 1
        }

        # Add title filters if provided
        if job_titles:
            search_body["person_titles"] = job_titles

        try:
            response = await self.client.post(
                "/mixed_people/api_search",
                json=search_body
            )

            if response.status_code == 200:
                data = response.json()
                people = data.get("people", [])

                contacts = []
                for person in people:
                    contact = {
                        "apollo_person_id": person.get("id"),
                        "first_name": person.get("first_name"),
                        "last_name": person.get("last_name"),
                        "name": person.get("name"),
                        "title": person.get("title"),
                        "seniority": person.get("seniority"),
                        "linkedin_url": person.get("linkedin_url"),
                        "organization_name": person.get("organization", {}).get("name"),
                        # NO email/phone - this is FREE search
                    }
                    contacts.append(contact)

                logger.info(
                    f"FREE search found {len(contacts)} contacts at {clean_domain} "
                    f"(filtered by titles: {bool(job_titles)})"
                )

                return contacts

            elif response.status_code == 401:
                raise APIAuthenticationError("Invalid Apollo API key")

            elif response.status_code == 429:
                error_data = response.json()
                raise APIRateLimitError(f"Apollo rate limit exceeded: {error_data.get('message')}")

            else:
                raise APIConnectionError(f"Apollo API error: HTTP {response.status_code}")

        except httpx.TimeoutException:
            raise APITimeoutError(f"Apollo search timed out after {self.TIMEOUT}s")

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
    
    async def search_company_contacts(
        self,
        domain: str,
        job_titles: Optional[List[str]] = None,
        max_results: int = 25
    ) -> List[Dict[str, Any]]:
        """
        Search for contacts at a company using Apollo People Search API.
        
        Uses Apollo's Mixed People Search endpoint to find people by domain.
        Can filter by job titles to find specific roles (e.g., CEO, VP Finance).
        
        Args:
            domain: Company domain without "www." or "@" (e.g., "apollo.io")
            job_titles: Optional list of job titles to filter (e.g., ["CEO", "CFO", "VP"])
            max_results: Maximum number of contacts to return (default: 25, max: 100)
        
        Returns:
            List of contact dictionaries with:
            - email, name, title, company
            - linkedin_url, phone
            - seniority, departments
        
        Raises:
            ValidationError: If domain is invalid
            APIAuthenticationError: If API key is invalid
            APIRateLimitError: If rate limit exceeded
            APIConnectionError: If request fails
        
        Example:
            >>> contacts = await apollo.search_company_contacts(
            ...     domain="acme.com",
            ...     job_titles=["CEO", "CFO", "VP"]
            ... )
            >>> for contact in contacts:
            ...     print(f"{contact['name']} - {contact['title']}")
        """
        # Clean domain
        clean_domain = domain.replace("www.", "").replace("@", "").strip()
        
        if not clean_domain:
            raise ValidationError(
                "Domain cannot be empty",
                context={"domain": domain}
            )
        
        # Build search query
        search_params = {
            "organization_domains": clean_domain,
            "per_page": min(max_results, 100),  # Apollo max is 100
            "page": 1
        }
        
        # Add job title filters if provided
        if job_titles:
            # Apollo supports title filtering via "person_titles" parameter
            search_params["person_titles"] = job_titles
        
        try:
            response = await self.client.post(
                "/mixed_people/search",
                json=search_params
            )
            
            # Handle response
            if response.status_code == 200:
                data = response.json()
                people = data.get("people", [])
                
                contacts = []
                for person in people:
                    # Extract employment info
                    employment = person.get("employment_history", [])
                    current_job = employment[0] if employment else {}
                    
                    contact = {
                        "email": person.get("email"),
                        "name": person.get("name"),
                        "first_name": person.get("first_name"),
                        "last_name": person.get("last_name"),
                        "title": person.get("title") or current_job.get("title"),
                        "company": current_job.get("organization_name") or person.get("organization", {}).get("name"),
                        "linkedin_url": person.get("linkedin_url"),
                        "phone": person.get("phone_number"),
                        "seniority": person.get("seniority"),
                        "departments": person.get("departments", []),
                        "apollo_id": person.get("id"),
                        "source": "apollo_search"
                    }
                    contacts.append(contact)
                
                logger.info(
                    f"Found {len(contacts)} contacts at {clean_domain} "
                    f"(requested: {max_results}, filtered by titles: {bool(job_titles)})"
                )
                
                return contacts
            
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
                    f"Apollo API validation error: {error_data.get('error', 'Invalid search parameters')}",
                    context={"status_code": 422, "domain": clean_domain, "params": search_params}
                )
            
            else:
                raise APIConnectionError(
                    f"Apollo API error: HTTP {response.status_code}",
                    context={"status_code": response.status_code, "response": response.text}
                )
        
        except httpx.TimeoutException:
            raise APITimeoutError(
                f"Apollo search request timed out after {self.TIMEOUT}s",
                context={"timeout": self.TIMEOUT, "domain": clean_domain}
            )
        
        except httpx.RequestError as e:
            raise APIConnectionError(
                f"Failed to connect to Apollo API: {str(e)}",
                context={"error": str(e), "domain": clean_domain}
            )
    
    async def search_and_enrich_contacts(
        self,
        domain: str,
        job_titles: Optional[List[str]] = None,
        max_results: int = 10,
        reveal_emails: bool = True,
        reveal_phones: bool = False  # Requires webhook_url - disabled by default
    ) -> List[Dict[str, Any]]:
        """
        Search for contacts and enrich them to get REAL emails and phones.

        This is the CORRECT way to get verified contact data from Apollo:
        1. Search: Find people at a company (returns names, titles, Apollo IDs)
        2. Enrich: Reveal actual email addresses (costs credits per person)

        Args:
            domain: Company domain (e.g., "acmecompany.com")
            job_titles: Optional ATL title filters (e.g., ["CEO", "Owner", "President"])
            max_results: Max contacts to enrich (default: 10, balance cost vs coverage)
            reveal_emails: Get real emails (costs 1 credit per contact)
            reveal_phones: Get phone numbers (costs additional credits)

        Returns:
            List of enriched contact dicts with verified data:
            - email: REAL verified email (not placeholder)
            - phone: Actual phone number
            - email_verified: True if email was revealed
            - source: "apollo_enriched" (vs "apollo_search" for placeholders)
            - confidence: Apollo's confidence score

        Cost:
            ~1-2 credits per contact enriched (emails + phones)
        """
        # Step 1: Search to find contacts (names/titles/IDs)
        search_results = await self.search_company_contacts(
            domain=domain,
            job_titles=job_titles,
            max_results=max_results
        )

        if not search_results:
            logger.info(f"No contacts found at {domain}")
            return []

        # Step 2: Enrich each contact to reveal real emails
        enriched_contacts = []
        skipped = 0

        for person in search_results:
            # Skip if no identifying info for enrichment
            first_name = person.get("first_name")
            last_name = person.get("last_name")
            linkedin_url = person.get("linkedin_url")

            if not ((first_name and last_name) or linkedin_url):
                skipped += 1
                continue

            try:
                # Enrich to reveal real email
                enriched = await self.enrich_contact(
                    first_name=first_name,
                    last_name=last_name,
                    domain=domain,
                    linkedin_url=linkedin_url,
                    reveal_personal_email=reveal_emails,
                    reveal_phone=reveal_phones
                )

                # Check if we got a real email (not placeholder)
                email = enriched.email
                is_real_email = email and "not_unlocked" not in email.lower() and "@" in email

                # Build full name from first + last
                enriched_first = enriched.first_name or first_name
                enriched_last = enriched.last_name or last_name
                full_name = f"{enriched_first} {enriched_last}".strip() if enriched_first or enriched_last else ""

                contact = {
                    "email": email if is_real_email else None,
                    "name": full_name,
                    "first_name": enriched_first,
                    "last_name": enriched_last,
                    "title": enriched.title or person.get("title"),
                    "company": enriched.company or person.get("company"),
                    "phone": enriched.phone,
                    "linkedin_url": enriched.linkedin_url or linkedin_url,
                    "seniority": person.get("seniority"),
                    "departments": person.get("departments", []),
                    "apollo_id": person.get("apollo_id"),
                    "source": "apollo_enriched",
                    "email_verified": is_real_email,
                    "confidence": getattr(enriched, 'custom_fields', {}).get("email_status", "unknown") if hasattr(enriched, 'custom_fields') else "enriched"
                }
                enriched_contacts.append(contact)

                logger.debug(f"Enriched: {contact['name']} - {contact['email']} (verified: {is_real_email})")

            except Exception as e:
                logger.warning(f"Failed to enrich {first_name} {last_name}: {e}")
                # Fall back to search data BUT skip placeholder emails
                search_email = person.get("email", "")
                if search_email and "not_unlocked" not in search_email.lower():
                    enriched_contacts.append({
                        **person,
                        "source": "apollo_search",
                        "email_verified": False,
                        "confidence": "search_only"
                    })
                else:
                    logger.debug(f"Skipped {first_name} {last_name} - placeholder email")

        logger.info(
            f"Apollo enrichment complete: {len(enriched_contacts)} contacts enriched "
            f"({skipped} skipped due to missing data) from {domain}"
        )

        return enriched_contacts

    async def enrich_by_phone(
        self,
        phone: str,
        company_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find contacts using phone number when website is unavailable.

        This is a fallback method for contractors without websites.
        Apollo can find people associated with a phone number.

        Args:
            phone: Business phone number (any format)
            company_name: Optional company name for filtering

        Returns:
            List of contact dicts with email, name, title, etc.
        """
        if not phone:
            return []

        # Clean phone number (remove formatting)
        clean_phone = re.sub(r'[^\d+]', '', phone)
        if not clean_phone:
            return []

        logger.info(f"Apollo phone lookup: {phone}")

        try:
            # Search for organization by phone
            search_params = {
                "organization_num_phones": [clean_phone],
                "per_page": 10,
                "page": 1
            }

            response = await self.client.post(
                "/mixed_people/search",
                json=search_params
            )

            if response.status_code != 200:
                logger.warning(f"Apollo phone search failed: HTTP {response.status_code}")
                return []

            data = response.json()
            people = data.get("people", [])

            if not people:
                logger.info(f"No contacts found for phone {phone}")
                return []

            # Map to contact format
            contacts = []
            for person in people:
                email = person.get("email", "")

                # Skip placeholder emails
                if not email or "not_unlocked" in email.lower():
                    continue

                contact = {
                    "email": email,
                    "name": person.get("name", ""),
                    "first_name": person.get("first_name", ""),
                    "last_name": person.get("last_name", ""),
                    "title": person.get("title", ""),
                    "company": person.get("organization", {}).get("name", ""),
                    "phone": person.get("phone_number", ""),
                    "linkedin_url": person.get("linkedin_url", ""),
                    "seniority": person.get("seniority", ""),
                    "source": "apollo_phone",
                    "email_verified": False,  # Phone search doesn't reveal emails
                    "confidence": "phone_lookup"
                }
                contacts.append(contact)

            logger.info(f"Apollo phone search found {len(contacts)} contacts")
            return contacts

        except Exception as e:
            logger.error(f"Apollo phone search failed: {e}")
            return []

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
        # NOTE: Credit tracking deferred - Apollo doesn't provide real-time credit API
        # Options when needed:
        # 1. Track locally per request type (~1 credit/enrichment, 0 for search)
        # 2. Parse X-RateLimit-* headers if available
        # 3. Periodic manual check via Apollo dashboard
        # Track usage in enrichment_tracking.db instead

        logger.debug("Credit balance checked - use Apollo dashboard for accurate count")
        return {
            "credits_remaining": "Unknown",
            "credits_used": "Unknown",
            "rate_limit_remaining": f"{self.RATE_LIMIT_PER_HOUR}/hour"
        }
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
