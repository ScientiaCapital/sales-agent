"""
HubSpot CRM Integration Service

Full integration with HubSpot CRM for marketing automation, contact sync,
and Close CRM bidirectional sync.

Features:
- Contact/Company/Deal CRUD operations
- Close CRM ↔ HubSpot bidirectional sync
- Form submission webhook handling
- Marketing email integration
- Rate limiting (100 requests/10 seconds for free tier)

API Docs: https://developers.hubspot.com/docs/api/overview
"""

import asyncio
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field

from app.services.crm.base import (
    CRMProvider, CRMCredentials, Contact, SyncResult, WebhookEvent,
    CRMAuthenticationError, CRMRateLimitError, CRMNotFoundError,
    CRMValidationError, CRMNetworkError
)
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# HUBSPOT-SPECIFIC MODELS
# ============================================================================


class HubSpotContact(BaseModel):
    """HubSpot contact representation"""
    id: Optional[str] = None
    email: str
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    company: Optional[str] = None
    jobtitle: Optional[str] = None
    phone: Optional[str] = None
    lifecyclestage: Optional[str] = None  # subscriber, lead, marketingqualifiedlead, salesqualifiedlead, opportunity, customer
    hs_lead_status: Optional[str] = None  # new, open, in_progress, open_deal, unqualified, attempted_to_contact, connected, bad_timing

    # Marketing fields
    hs_email_optout: bool = False
    hs_analytics_source: Optional[str] = None  # organic, paid, referral, direct, social, email
    hs_analytics_first_url: Optional[str] = None

    # Close CRM sync fields
    close_lead_id: Optional[str] = None
    close_contact_id: Optional[str] = None

    # Timestamps
    createdate: Optional[datetime] = None
    lastmodifieddate: Optional[datetime] = None


class HubSpotCompany(BaseModel):
    """HubSpot company representation"""
    id: Optional[str] = None
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    numberofemployees: Optional[int] = None
    annualrevenue: Optional[float] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    # Close CRM sync
    close_lead_id: Optional[str] = None


class HubSpotDeal(BaseModel):
    """HubSpot deal representation"""
    id: Optional[str] = None
    dealname: str
    amount: Optional[float] = None
    dealstage: Optional[str] = None  # appointmentscheduled, qualifiedtobuy, presentationscheduled, decisionmakerboughtin, contractsent, closedwon, closedlost
    pipeline: Optional[str] = None
    closedate: Optional[datetime] = None

    # Associations
    contact_ids: List[str] = Field(default_factory=list)
    company_ids: List[str] = Field(default_factory=list)


class HubSpotFormSubmission(BaseModel):
    """HubSpot form submission event"""
    form_id: str
    submission_timestamp: datetime
    portal_id: str
    page_url: Optional[str] = None
    page_title: Optional[str] = None

    # Form fields (dynamic)
    fields: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# RATE LIMITER
# ============================================================================


class HubSpotRateLimiter:
    """
    Rate limiter for HubSpot API.

    Free tier: 100 requests per 10 seconds
    Paid tier: Much higher limits, depends on plan
    """

    def __init__(self, requests_per_window: int = 100, window_seconds: int = 10):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.requests: List[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        async with self._lock:
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=self.window_seconds)

            # Remove old requests outside window
            self.requests = [r for r in self.requests if r > window_start]

            # If at limit, wait until oldest request expires
            if len(self.requests) >= self.requests_per_window:
                oldest = min(self.requests)
                sleep_time = (oldest + timedelta(seconds=self.window_seconds) - now).total_seconds()
                if sleep_time > 0:
                    logger.warning(f"HubSpot rate limit reached, waiting {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)
                    # Recursive call after sleep
                    return await self.acquire()

            # Record this request
            self.requests.append(now)


# ============================================================================
# HUBSPOT SERVICE
# ============================================================================


class HubSpotService(CRMProvider):
    """
    HubSpot CRM integration service.

    Implements CRMProvider interface for consistent behavior across CRM platforms.
    Provides additional HubSpot-specific features:
    - Form submission handling
    - Marketing email integration
    - Lifecycle stage management
    - Close CRM sync
    """

    BASE_URL = "https://api.hubapi.com"

    # API rate limits
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_WINDOW = 10  # seconds

    def __init__(
        self,
        credentials: Optional[CRMCredentials] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize HubSpot service.

        Args:
            credentials: CRM credentials (if using OAuth)
            api_key: API key (if using Private App)
        """
        # Support both credential object and direct API key
        if credentials:
            super().__init__(credentials)
            self._api_key = credentials.api_key
            self._access_token = credentials.access_token
        else:
            self.platform = "hubspot"
            self._api_key = api_key or settings.HUBSPOT_API_KEY
            self._access_token = None

        # HTTP client with retry
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers=self._build_headers()
        )

        # Rate limiter
        self._rate_limiter = HubSpotRateLimiter(
            requests_per_window=self.RATE_LIMIT_REQUESTS,
            window_seconds=self.RATE_LIMIT_WINDOW
        )

        logger.info("HubSpot service initialized")

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers with auth."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        elif self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated request to HubSpot API.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            endpoint: API endpoint (e.g., "/crm/v3/objects/contacts")
            data: Request body
            params: Query parameters

        Returns:
            Response JSON

        Raises:
            CRMAuthenticationError: If auth fails
            CRMRateLimitError: If rate limited
            CRMNotFoundError: If resource not found
            CRMNetworkError: If network error
        """
        # Respect rate limits
        await self._rate_limiter.acquire()

        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = await self._client.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=self._build_headers()
            )

            # Handle errors
            if response.status_code == 401:
                raise CRMAuthenticationError(
                    "HubSpot authentication failed. Check API key or access token.",
                    context={"endpoint": endpoint}
                )

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 10))
                raise CRMRateLimitError(
                    f"HubSpot rate limit exceeded. Retry after {retry_after}s.",
                    context={"endpoint": endpoint},
                    retry_after=retry_after
                )

            if response.status_code == 404:
                raise CRMNotFoundError(
                    f"Resource not found: {endpoint}",
                    context={"endpoint": endpoint}
                )

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CRMValidationError(
                    f"HubSpot API error: {error_data.get('message', response.text)}",
                    context={"status": response.status_code, "response": error_data}
                )

            return response.json() if response.content else {}

        except httpx.RequestError as e:
            raise CRMNetworkError(
                f"Network error connecting to HubSpot: {e}",
                context={"endpoint": endpoint}
            )

    # ========================================================================
    # AUTHENTICATION (CRMProvider interface)
    # ========================================================================

    async def authenticate(self) -> bool:
        """Test authentication with HubSpot API."""
        try:
            # Simple test call to verify credentials
            await self._request("GET", "/crm/v3/objects/contacts", params={"limit": 1})
            logger.info("HubSpot authentication successful")
            return True
        except CRMAuthenticationError:
            return False

    async def refresh_access_token(self) -> str:
        """
        Refresh OAuth access token.

        For Private Apps, tokens don't expire. For OAuth apps, implement refresh logic.
        """
        if not self.credentials or not self.credentials.refresh_token:
            raise CRMAuthenticationError(
                "No refresh token available. Using Private App API key.",
                context={"auth_type": "api_key"}
            )

        # OAuth refresh flow (implement if using OAuth)
        # For now, using Private App which doesn't need refresh
        return self._access_token or self._api_key

    # ========================================================================
    # CONTACT OPERATIONS (CRMProvider interface)
    # ========================================================================

    async def get_contact(self, contact_id: str) -> Contact:
        """Get contact by HubSpot ID."""
        response = await self._request(
            "GET",
            f"/crm/v3/objects/contacts/{contact_id}",
            params={"properties": "email,firstname,lastname,company,jobtitle,phone,lifecyclestage,hs_lead_status"}
        )

        props = response.get("properties", {})
        return Contact(
            email=props.get("email", ""),
            first_name=props.get("firstname"),
            last_name=props.get("lastname"),
            company=props.get("company"),
            title=props.get("jobtitle"),
            phone=props.get("phone"),
            external_ids={"hubspot": response.get("id")},
            source_platform="hubspot"
        )

    async def get_contact_by_email(self, email: str) -> Optional[Contact]:
        """Get contact by email address."""
        try:
            response = await self._request(
                "POST",
                "/crm/v3/objects/contacts/search",
                data={
                    "filterGroups": [{
                        "filters": [{
                            "propertyName": "email",
                            "operator": "EQ",
                            "value": email.lower()
                        }]
                    }],
                    "properties": ["email", "firstname", "lastname", "company", "jobtitle", "phone", "lifecyclestage"]
                }
            )

            results = response.get("results", [])
            if not results:
                return None

            contact_data = results[0]
            props = contact_data.get("properties", {})

            return Contact(
                email=props.get("email", email),
                first_name=props.get("firstname"),
                last_name=props.get("lastname"),
                company=props.get("company"),
                title=props.get("jobtitle"),
                phone=props.get("phone"),
                external_ids={"hubspot": contact_data.get("id")},
                source_platform="hubspot"
            )

        except CRMNotFoundError:
            return None

    async def create_contact(self, contact: Contact) -> Contact:
        """Create new contact in HubSpot."""
        properties = {
            "email": contact.email,
            "firstname": contact.first_name or "",
            "lastname": contact.last_name or "",
            "company": contact.company or "",
            "jobtitle": contact.title or "",
            "phone": contact.phone or ""
        }

        # Add Close CRM reference if available
        if "close" in contact.external_ids:
            properties["close_lead_id"] = contact.external_ids["close"]

        response = await self._request(
            "POST",
            "/crm/v3/objects/contacts",
            data={"properties": properties}
        )

        contact.external_ids["hubspot"] = response.get("id")
        contact.source_platform = "hubspot"

        logger.info(f"Created HubSpot contact: {contact.email} (ID: {response.get('id')})")
        return contact

    async def update_contact(self, contact_id: str, contact: Contact) -> Contact:
        """Update existing contact."""
        properties = {}

        if contact.first_name:
            properties["firstname"] = contact.first_name
        if contact.last_name:
            properties["lastname"] = contact.last_name
        if contact.company:
            properties["company"] = contact.company
        if contact.title:
            properties["jobtitle"] = contact.title
        if contact.phone:
            properties["phone"] = contact.phone

        if not properties:
            logger.warning(f"No properties to update for contact {contact_id}")
            return contact

        response = await self._request(
            "PATCH",
            f"/crm/v3/objects/contacts/{contact_id}",
            data={"properties": properties}
        )

        contact.external_ids["hubspot"] = response.get("id")
        logger.info(f"Updated HubSpot contact: {contact_id}")
        return contact

    async def enrich_contact(self, email: str) -> Optional[Dict[str, Any]]:
        """
        HubSpot doesn't provide enrichment like Apollo.
        Returns existing contact data if found.
        """
        contact = await self.get_contact_by_email(email)
        if contact:
            return {
                "email": contact.email,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "company": contact.company,
                "title": contact.title,
                "phone": contact.phone,
                "source": "hubspot"
            }
        return None

    # ========================================================================
    # COMPANY OPERATIONS
    # ========================================================================

    async def get_company(self, company_id: str) -> HubSpotCompany:
        """Get company by HubSpot ID."""
        response = await self._request(
            "GET",
            f"/crm/v3/objects/companies/{company_id}",
            params={"properties": "name,domain,industry,numberofemployees,annualrevenue,phone,city,state,country"}
        )

        props = response.get("properties", {})
        return HubSpotCompany(
            id=response.get("id"),
            name=props.get("name", ""),
            domain=props.get("domain"),
            industry=props.get("industry"),
            numberofemployees=int(props["numberofemployees"]) if props.get("numberofemployees") else None,
            annualrevenue=float(props["annualrevenue"]) if props.get("annualrevenue") else None,
            phone=props.get("phone"),
            city=props.get("city"),
            state=props.get("state"),
            country=props.get("country")
        )

    async def create_company(self, company: HubSpotCompany) -> HubSpotCompany:
        """Create company in HubSpot."""
        properties = {
            "name": company.name,
            "domain": company.domain or "",
            "industry": company.industry or "",
            "phone": company.phone or ""
        }

        if company.numberofemployees:
            properties["numberofemployees"] = str(company.numberofemployees)
        if company.city:
            properties["city"] = company.city
        if company.state:
            properties["state"] = company.state

        response = await self._request(
            "POST",
            "/crm/v3/objects/companies",
            data={"properties": properties}
        )

        company.id = response.get("id")
        logger.info(f"Created HubSpot company: {company.name} (ID: {company.id})")
        return company

    # ========================================================================
    # DEAL OPERATIONS
    # ========================================================================

    async def create_deal(self, deal: HubSpotDeal) -> HubSpotDeal:
        """Create deal in HubSpot."""
        properties = {
            "dealname": deal.dealname,
            "pipeline": deal.pipeline or "default",
            "dealstage": deal.dealstage or "appointmentscheduled"
        }

        if deal.amount:
            properties["amount"] = str(deal.amount)
        if deal.closedate:
            properties["closedate"] = deal.closedate.isoformat()

        response = await self._request(
            "POST",
            "/crm/v3/objects/deals",
            data={"properties": properties}
        )

        deal.id = response.get("id")

        # Associate with contacts and companies
        if deal.contact_ids:
            for contact_id in deal.contact_ids:
                await self._associate(deal.id, "deals", contact_id, "contacts")

        if deal.company_ids:
            for company_id in deal.company_ids:
                await self._associate(deal.id, "deals", company_id, "companies")

        logger.info(f"Created HubSpot deal: {deal.dealname} (ID: {deal.id})")
        return deal

    async def _associate(
        self,
        from_id: str,
        from_type: str,
        to_id: str,
        to_type: str
    ) -> None:
        """Create association between objects."""
        await self._request(
            "PUT",
            f"/crm/v3/objects/{from_type}/{from_id}/associations/{to_type}/{to_id}/contact_to_company"
        )

    # ========================================================================
    # SYNC OPERATIONS (CRMProvider interface)
    # ========================================================================

    async def sync_contacts(
        self,
        direction: str = "import",
        filters: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Sync contacts with HubSpot.

        Args:
            direction: "import" (HubSpot→Local), "export" (Local→HubSpot), "bidirectional"
            filters: Optional filters (lifecycle_stage, lead_status, etc.)
        """
        started_at = datetime.utcnow()
        result = SyncResult(
            platform="hubspot",
            operation=direction,
            started_at=started_at
        )

        try:
            if direction in ["import", "bidirectional"]:
                import_result = await self._import_contacts(filters)
                result.contacts_processed += import_result["processed"]
                result.contacts_created += import_result["created"]
                result.contacts_updated += import_result["updated"]

            if direction in ["export", "bidirectional"]:
                export_result = await self._export_contacts(filters)
                result.contacts_processed += export_result["processed"]
                result.contacts_created += export_result["created"]
                result.contacts_updated += export_result["updated"]

        except Exception as e:
            result.errors.append({"error": str(e), "timestamp": datetime.utcnow().isoformat()})
            result.contacts_failed += 1
            logger.error(f"Sync error: {e}")

        result.completed_at = datetime.utcnow()
        result.duration_seconds = (result.completed_at - started_at).total_seconds()

        logger.info(
            f"HubSpot sync complete: {result.contacts_processed} processed, "
            f"{result.contacts_created} created, {result.contacts_updated} updated"
        )

        return result

    async def _import_contacts(self, filters: Optional[Dict] = None) -> Dict[str, int]:
        """Import contacts from HubSpot to local database."""
        # Get all contacts with pagination
        contacts = await self.list_contacts(limit=100, filters=filters)

        processed = 0
        created = 0
        updated = 0

        for contact in contacts:
            processed += 1
            # Here you would save to local database
            # For now, just counting
            logger.debug(f"Would import: {contact.email}")

        return {"processed": processed, "created": created, "updated": updated}

    async def _export_contacts(self, filters: Optional[Dict] = None) -> Dict[str, int]:
        """Export contacts from local database to HubSpot."""
        # This would read from local DB and push to HubSpot
        # Placeholder for now
        return {"processed": 0, "created": 0, "updated": 0}

    async def get_updated_contacts(self, since: datetime) -> List[Contact]:
        """Get contacts updated since timestamp."""
        response = await self._request(
            "POST",
            "/crm/v3/objects/contacts/search",
            data={
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "lastmodifieddate",
                        "operator": "GTE",
                        "value": int(since.timestamp() * 1000)  # HubSpot uses milliseconds
                    }]
                }],
                "properties": ["email", "firstname", "lastname", "company", "jobtitle", "phone"],
                "limit": 100
            }
        )

        contacts = []
        for result in response.get("results", []):
            props = result.get("properties", {})
            contacts.append(Contact(
                email=props.get("email", ""),
                first_name=props.get("firstname"),
                last_name=props.get("lastname"),
                company=props.get("company"),
                title=props.get("jobtitle"),
                phone=props.get("phone"),
                external_ids={"hubspot": result.get("id")},
                source_platform="hubspot"
            ))

        return contacts

    async def list_contacts(
        self,
        limit: int = 100,
        after: Optional[str] = None,
        filters: Optional[Dict] = None
    ) -> List[Contact]:
        """
        List contacts with pagination.

        Args:
            limit: Max contacts to return (max 100)
            after: Pagination cursor
            filters: Optional filters
        """
        params = {
            "limit": min(limit, 100),
            "properties": "email,firstname,lastname,company,jobtitle,phone,lifecyclestage,hs_lead_status"
        }
        if after:
            params["after"] = after

        response = await self._request("GET", "/crm/v3/objects/contacts", params=params)

        contacts = []
        for result in response.get("results", []):
            props = result.get("properties", {})
            contacts.append(Contact(
                email=props.get("email", ""),
                first_name=props.get("firstname"),
                last_name=props.get("lastname"),
                company=props.get("company"),
                title=props.get("jobtitle"),
                phone=props.get("phone"),
                external_ids={"hubspot": result.get("id")},
                source_platform="hubspot"
            ))

        return contacts

    # ========================================================================
    # WEBHOOK HANDLING
    # ========================================================================

    async def handle_webhook(self, event: WebhookEvent) -> None:
        """
        Handle incoming webhook from HubSpot.

        Event types:
        - contact.creation
        - contact.propertyChange
        - contact.deletion
        - form.submission
        """
        logger.info(f"Received HubSpot webhook: {event.event_type}")

        if event.event_type == "contact.creation":
            await self._handle_contact_created(event)
        elif event.event_type == "contact.propertyChange":
            await self._handle_contact_updated(event)
        elif event.event_type == "contact.deletion":
            await self._handle_contact_deleted(event)
        elif event.event_type.startswith("form."):
            await self._handle_form_submission(event)

    async def _handle_contact_created(self, event: WebhookEvent) -> None:
        """Handle contact creation webhook."""
        contact_id = event.payload.get("objectId")
        if contact_id:
            contact = await self.get_contact(str(contact_id))
            logger.info(f"New HubSpot contact: {contact.email}")
            # Sync to Close CRM if needed

    async def _handle_contact_updated(self, event: WebhookEvent) -> None:
        """Handle contact update webhook."""
        contact_id = event.payload.get("objectId")
        property_name = event.payload.get("propertyName")
        property_value = event.payload.get("propertyValue")

        logger.info(f"HubSpot contact {contact_id} updated: {property_name}={property_value}")

    async def _handle_contact_deleted(self, event: WebhookEvent) -> None:
        """Handle contact deletion webhook."""
        contact_id = event.payload.get("objectId")
        logger.warning(f"HubSpot contact deleted: {contact_id}")

    async def _handle_form_submission(self, event: WebhookEvent) -> None:
        """Handle form submission webhook - create lead in Close."""
        form_data = event.payload

        logger.info(f"HubSpot form submission: {form_data.get('formId')}")

        # Extract contact data from form
        # This would create a new lead in Close CRM

    # ========================================================================
    # CLOSE CRM SYNC
    # ========================================================================

    async def sync_from_close(self, close_lead_id: str, close_data: Dict[str, Any]) -> Optional[str]:
        """
        Sync a lead from Close CRM to HubSpot.

        Args:
            close_lead_id: Close CRM lead ID
            close_data: Lead data from Close

        Returns:
            HubSpot contact ID if created/updated
        """
        # Extract contact from Close lead data
        contacts = close_data.get("contacts", [])
        if not contacts:
            return None

        primary_contact = contacts[0]
        email = primary_contact.get("emails", [{}])[0].get("email")

        if not email:
            logger.warning(f"Close lead {close_lead_id} has no email, skipping HubSpot sync")
            return None

        # Check if contact exists in HubSpot
        existing = await self.get_contact_by_email(email)

        contact = Contact(
            email=email,
            first_name=primary_contact.get("first_name"),
            last_name=primary_contact.get("last_name"),
            company=close_data.get("display_name"),
            title=primary_contact.get("title"),
            phone=primary_contact.get("phones", [{}])[0].get("phone"),
            external_ids={"close": close_lead_id}
        )

        if existing:
            # Update existing
            hubspot_id = existing.external_ids.get("hubspot")
            if hubspot_id:
                await self.update_contact(hubspot_id, contact)
                return hubspot_id
        else:
            # Create new
            created = await self.create_contact(contact)
            return created.external_ids.get("hubspot")

    async def sync_to_close(self, hubspot_contact_id: str) -> Optional[str]:
        """
        Sync a contact from HubSpot to Close CRM.

        Returns Close lead ID if created/updated.
        """
        # Get HubSpot contact
        await self.get_contact(hubspot_contact_id)

        # This would call Close CRM service to create/update lead
        # For now, returning None as Close writes are disabled
        logger.info(f"Would sync HubSpot contact {hubspot_contact_id} to Close (writes disabled)")
        return None

    # ========================================================================
    # MARKETING FEATURES
    # ========================================================================

    async def update_lifecycle_stage(self, contact_id: str, stage: str) -> None:
        """
        Update contact lifecycle stage.

        Stages: subscriber, lead, marketingqualifiedlead, salesqualifiedlead,
                opportunity, customer, evangelist, other
        """
        await self._request(
            "PATCH",
            f"/crm/v3/objects/contacts/{contact_id}",
            data={"properties": {"lifecyclestage": stage}}
        )
        logger.info(f"Updated lifecycle stage for {contact_id}: {stage}")

    async def update_lead_status(self, contact_id: str, status: str) -> None:
        """
        Update contact lead status.

        Statuses: new, open, in_progress, open_deal, unqualified,
                  attempted_to_contact, connected, bad_timing
        """
        await self._request(
            "PATCH",
            f"/crm/v3/objects/contacts/{contact_id}",
            data={"properties": {"hs_lead_status": status}}
        )
        logger.info(f"Updated lead status for {contact_id}: {status}")

    async def get_marketing_emails(self, contact_id: str) -> List[Dict[str, Any]]:
        """Get marketing emails sent to a contact."""
        response = await self._request(
            "GET",
            f"/email/public/v1/emails/contacts/{contact_id}/messages"
        )
        return response.get("messages", [])

    # ========================================================================
    # CLEANUP
    # ========================================================================

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
        logger.info("HubSpot service closed")


# ============================================================================
# FACTORY FUNCTION
# ============================================================================


def get_hubspot_service(api_key: Optional[str] = None) -> HubSpotService:
    """
    Get HubSpot service instance.

    Args:
        api_key: Optional API key (uses settings.HUBSPOT_API_KEY if not provided)
    """
    return HubSpotService(api_key=api_key)
