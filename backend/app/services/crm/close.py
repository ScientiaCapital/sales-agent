"""
Close CRM Integration

Implements API key authentication and lead/contact management for Close CRM.
Close is a sales-focused CRM with a simple REST API using Basic auth.

API Documentation: https://developer.close.com/
"""

from typing import Optional, Dict, List, Any
from datetime import datetime
import httpx
import logging
import base64
import os

from app.services.crm.base import (
    CRMProvider,
    Contact,
    CRMCredentials,
    SyncResult,
    WebhookEvent,
    CRMAuthenticationError,
    CRMRateLimitError,
    CRMNotFoundError,
    CRMValidationError,
    CRMNetworkError,
)

logger = logging.getLogger(__name__)


class CloseProvider(CRMProvider):
    """
    Close CRM integration using API key authentication.

    Features:
    - API key authentication (Basic auth with format "api_key:")
    - Lead management (Close uses Leads, not Contacts, as primary object)
    - Contact sync (contacts are nested within Leads)
    - Redis-based rate limiting (respects RateLimit headers)
    - Webhooks for real-time updates
    - Bulk import/export operations

    Close API Details:
    - Base URL: https://api.close.com/api/v1/
    - Auth: Authorization: Basic {base64(api_key:)}
    - Rate Limits: Per endpoint group, shown in RateLimit header
    - Primary Resource: Leads (contain contacts, opportunities, activities)
    """

    BASE_URL = "https://api.close.com/api/v1"

    # Rate limits vary by endpoint group - we track conservatively
    RATE_LIMIT_SAFE_THRESHOLD = 100  # Requests per window

    def __init__(
        self,
        credentials: Optional[CRMCredentials] = None,
        redis_client: Optional[Any] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize Close CRM provider.

        Args:
            credentials: CRM credentials with encrypted API key (optional if api_key provided)
            redis_client: Redis client for rate limiting (optional)
            api_key: Direct API key (optional if credentials provided)
        """
        # Support direct api_key for convenience
        if api_key and not credentials:
            credentials = CRMCredentials(
                platform="close",
                api_key=api_key,  # Store unencrypted for now (encryption optional)
                encrypted=False
            )

        if not credentials:
            raise CRMValidationError("Either credentials or api_key must be provided")

        super().__init__(credentials)
        self.redis = redis_client

        # Get API key - either encrypted or direct
        self.api_key = None
        if api_key:
            # Direct API key provided
            self.api_key = api_key
        elif credentials.api_key:
            # Decrypt if encrypted
            if credentials.encrypted:
                self.api_key = self.decrypt_credential(credentials.api_key)
            else:
                self.api_key = credentials.api_key
        elif credentials.access_token:
            # Fallback: some configs might store API key as access_token
            if credentials.encrypted:
                self.api_key = self.decrypt_credential(credentials.access_token)
            else:
                self.api_key = credentials.access_token

        if not self.api_key:
            raise CRMValidationError("Close CRM API key is required")

        # Close uses Basic auth with format "api_key:" (note the colon)
        auth_string = f"{self.api_key}:"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        self.auth_header = f"Basic {auth_b64}"

    async def authenticate(self) -> bool:
        """
        Verify authentication by making a test API call.

        Returns:
            True if authenticated successfully

        Raises:
            CRMAuthenticationError: If authentication fails
        """
        try:
            # Test auth with a simple API call to get current user
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/me/",
                    headers={
                        "Authorization": self.auth_header,
                        "Content-Type": "application/json",
                    },
                    timeout=30.0
                )

                if response.status_code == 401:
                    raise CRMAuthenticationError("Invalid Close CRM API key")
                elif response.status_code == 403:
                    raise CRMAuthenticationError("Close CRM API key lacks necessary permissions")
                elif response.status_code >= 400:
                    raise CRMAuthenticationError(f"Authentication failed: {response.status_code}")

                logger.info("Close CRM authentication successful")
                return True

        except httpx.HTTPError as e:
            logger.error(f"Close CRM authentication network error: {e}")
            raise CRMNetworkError(f"Network error during authentication: {e}")

    async def refresh_access_token(self) -> str:
        """
        Close uses API key authentication (no token refresh needed).

        Returns:
            The current API key
        """
        logger.info("Close CRM uses API key authentication - no token refresh needed")
        return self.api_key

    def _map_lead_to_contact(self, lead: Dict[str, Any]) -> List[Contact]:
        """
        Map Close lead response to unified Contact model(s).

        Close's data model: Lead contains multiple contacts
        We extract each contact from the lead's contacts array.

        Args:
            lead: Close lead object from API response

        Returns:
            List of Contact objects (one per contact in lead)
        """
        contacts_list = []
        lead_id = lead.get("id")
        lead_name = lead.get("name", "")

        # Extract contacts from lead
        for contact_data in lead.get("contacts", []):
            # Get first email if available
            emails = contact_data.get("emails", [])
            email = emails[0].get("email") if emails else None

            # Get first phone if available
            phones = contact_data.get("phones", [])
            phone = phones[0].get("phone") if phones else None

            # Split contact name into first/last
            contact_name = contact_data.get("name", "")
            name_parts = contact_name.split(" ", 1)
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            contact = Contact(
                external_id=contact_data.get("id"),
                email=email,
                first_name=first_name,
                last_name=last_name,
                title=contact_data.get("title"),
                company=lead_name,
                phone=phone,
                custom_fields={
                    "close_lead_id": lead_id,
                    "close_contact_id": contact_data.get("id"),
                    "lead_status": lead.get("status_label"),
                    "lead_url": lead.get("url"),
                    "raw_close_data": contact_data
                }
            )
            contacts_list.append(contact)

        return contacts_list

    async def get_contact(self, contact_id: str) -> Contact:
        """
        Retrieve a contact by Close contact ID.

        Note: In Close, contacts belong to leads, so we need to
        fetch the parent lead to get contact details.

        Args:
            contact_id: Close contact ID

        Returns:
            Contact object with person data

        Raises:
            CRMNotFoundError: If contact not found
            CRMRateLimitError: If rate limit exceeded
        """
        try:
            await self._check_rate_limit()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/contact/{contact_id}/",
                    headers={
                        "Authorization": self.auth_header,
                        "Content-Type": "application/json",
                    },
                    timeout=30.0
                )

                await self._update_rate_limit(response)

                if response.status_code == 404:
                    raise CRMNotFoundError(f"Contact {contact_id} not found in Close CRM")
                elif response.status_code == 429:
                    self._handle_rate_limit_error(response)
                elif response.status_code >= 400:
                    raise CRMNetworkError(f"Close CRM API error: {response.status_code}")

                contact_data = response.json()

                # Get the parent lead to get full context
                lead_id = contact_data.get("lead_id")
                if lead_id:
                    lead_response = await client.get(
                        f"{self.BASE_URL}/lead/{lead_id}/",
                        headers={
                            "Authorization": self.auth_header,
                            "Content-Type": "application/json",
                        },
                        timeout=30.0
                    )
                    if lead_response.status_code == 200:
                        lead_data = lead_response.json()
                        contacts = self._map_lead_to_contact(lead_data)
                        # Find the specific contact
                        for contact in contacts:
                            if contact.custom_fields.get("close_contact_id") == contact_id:
                                return contact

                # Fallback: create contact from contact data alone
                emails = contact_data.get("emails", [])
                email = emails[0].get("email") if emails else None

                phones = contact_data.get("phones", [])
                phone = phones[0].get("phone") if phones else None

                contact_name = contact_data.get("name", "")
                name_parts = contact_name.split(" ", 1)
                first_name = name_parts[0] if name_parts else ""
                last_name = name_parts[1] if len(name_parts) > 1 else ""

                return Contact(
                    external_id=contact_data.get("id"),
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    title=contact_data.get("title"),
                    phone=phone,
                    custom_fields={
                        "close_contact_id": contact_data.get("id"),
                        "close_lead_id": lead_id,
                        "raw_close_data": contact_data
                    }
                )

        except httpx.HTTPError as e:
            logger.error(f"Network error getting contact {contact_id}: {e}")
            raise CRMNetworkError(f"Network error: {e}")

    async def create_contact(self, contact: Contact) -> Contact:
        """
        Create a new contact in Close CRM.

        Note: In Close, you create a Lead first, then add contacts to it.
        We'll create a lead with the company name and add the contact.

        Args:
            contact: Contact data to create

        Returns:
            Created contact with external_id populated

        Raises:
            CRMValidationError: If required fields missing
            CRMRateLimitError: If rate limit exceeded
        """
        # SAFETY: Disable all writes to Close CRM
        if os.getenv("CLOSE_WRITE_DISABLED") == "True":
            logger.warning("⚠️ CLOSE_WRITE_DISABLED: Skipping create_contact() - read-only mode")
            # Return mock contact with error status
            contact.external_id = "disabled"
            return contact

        try:
            if not contact.email:
                raise CRMValidationError("Email is required to create a contact in Close CRM")

            await self._check_rate_limit()

            # Prepare lead data
            lead_name = contact.company or f"{contact.first_name} {contact.last_name}".strip() or "New Lead"

            contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()

            lead_data = {
                "name": lead_name,
                "contacts": [
                    {
                        "name": contact_name if contact_name else None,
                        "title": contact.title,
                        "emails": [{"email": contact.email}],
                        "phones": [{"phone": contact.phone}] if contact.phone else [],
                    }
                ]
            }

            # Assign default owner (Tim Kipper) if configured
            default_owner = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")
            if default_owner:
                lead_data["created_by"] = default_owner

            # Set lead priority status based on enrichment data
            enrichment = contact.enrichment_data or {}
            is_atl = enrichment.get("is_atl", False)
            qualification_score = enrichment.get("qualification_score", 0)
            contact_level = enrichment.get("contact_level", "Unknown")

            # ALL leads start as "Raw" - Smart views filter by custom fields
            status_id = "stat_4qxeqdfEDGNFmh93pFmXz4l8bw78DuQtTlATratY2Qb"  # Raw
            lead_data["status_id"] = status_id

            # Determine priority label for description (not status!)
            if is_atl:
                if qualification_score >= 70:
                    priority_label = "🔥 Hot ATL"
                else:
                    priority_label = "⭐ Validated ATL"
            else:
                priority_label = "📋 BTL"

            # Add enrichment metadata to description
            description_parts = []
            if qualification_score > 0:
                description_parts.append(f"Qualification Score: {qualification_score}/100")
            if contact_level and contact_level != "Unknown":
                description_parts.append(f"Contact Level: {contact_level}")
            if is_atl:
                description_parts.append("Decision Maker (ATL)")
            else:
                description_parts.append("Individual Contributor (BTL)")

            if description_parts:
                lead_data["description"] = f"{priority_label}\n\n" + "\n".join(description_parts)

            # Add custom fields for smart view filtering
            tier = enrichment.get("tier", "unknown")
            lead_data["custom"] = {
                "qualification_score": qualification_score,
                "is_atl": "Yes" if is_atl else "No",  # Close uses choices field (Yes/No)
                "priority_label": priority_label,
                "tier": tier  # hot/warm/cold/unqualified
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/lead/",
                    headers={
                        "Authorization": self.auth_header,
                        "Content-Type": "application/json",
                    },
                    json=lead_data,
                    timeout=30.0
                )

                await self._update_rate_limit(response)

                if response.status_code == 429:
                    self._handle_rate_limit_error(response)
                elif response.status_code >= 400:
                    error_data = response.json() if response.text else {}
                    raise CRMValidationError(
                        f"Failed to create lead in Close CRM: {error_data.get('error', response.status_code)}"
                    )

                lead = response.json()
                contacts = self._map_lead_to_contact(lead)

                # Return the first contact (the one we just created)
                if contacts:
                    return contacts[0]
                else:
                    raise CRMValidationError("Failed to create contact - no contacts in created lead")

        except httpx.HTTPError as e:
            logger.error(f"Network error creating contact: {e}")
            raise CRMNetworkError(f"Network error: {e}")

    async def add_contact_to_lead(self, lead_id: str, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a single contact to an existing lead in Close CRM.

        This is used when deduplication finds that the company exists but the contact is new.
        Prevents creating duplicate companies while adding new decision-makers.

        Args:
            lead_id: Close CRM lead ID (e.g., "lead_xxx...")
            contact_data: Contact information dict with:
                - first_name: str
                - last_name: str
                - email: str (required)
                - position: str (job title)
                - phone: str (optional)
                - linkedin: str (optional)
                - is_atl: bool

        Returns:
            Created contact data with contact_id

        Raises:
            CRMValidationError: If email is missing
            CRMNetworkError: If network error occurs
        """
        # SAFETY: Disable all writes to Close CRM
        if os.getenv("CLOSE_WRITE_DISABLED") == "True":
            logger.warning("⚠️ CLOSE_WRITE_DISABLED: Skipping add_contact_to_lead() - read-only mode")
            return {
                "status": "disabled",
                "contact_id": "disabled",
                "message": "Close CRM write operations are disabled"
            }

        try:
            email = contact_data.get("email")
            if not email:
                raise CRMValidationError("Email is required to add contact to lead")

            await self._check_rate_limit()

            # Build contact payload for Close API
            contact_payload = {
                "name": f"{contact_data.get('first_name', '')} {contact_data.get('last_name', '')}".strip(),
                "title": contact_data.get("position"),
                "emails": [{"email": email}]
            }

            # Add phone if available
            if contact_data.get("phone"):
                contact_payload["phones"] = [{"phone": contact_data["phone"]}]

            # Add LinkedIn URL as custom field or URL
            if contact_data.get("linkedin"):
                contact_payload["urls"] = [{"url": contact_data["linkedin"], "type": "linkedin"}]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/lead/{lead_id}/contact/",
                    headers={
                        "Authorization": self.auth_header,
                        "Content-Type": "application/json",
                    },
                    json=contact_payload,
                    timeout=30.0
                )

                await self._update_rate_limit(response)

                if response.status_code == 429:
                    self._handle_rate_limit_error(response)
                elif response.status_code >= 400:
                    error_data = response.json() if response.text else {}
                    raise CRMValidationError(
                        f"Failed to add contact to lead in Close CRM: {error_data.get('error', response.status_code)}"
                    )

                result = response.json()
                logger.info(f"✅ Added contact {contact_payload['name']} to lead {lead_id} (contact_id: {result.get('id')})")

                return {
                    "contact_id": result.get("id"),
                    "name": contact_payload["name"],
                    "email": email,
                    "title": contact_data.get("position"),
                    "is_atl": contact_data.get("is_atl", False)
                }

        except httpx.HTTPError as e:
            logger.error(f"Network error adding contact to lead: {e}")
            raise CRMNetworkError(f"Network error: {e}")

    async def create_lead(self, lead: Dict[str, Any], matched_lead_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a lead in Close CRM from pipeline lead data.

        Converts lead dict to Contact object and creates in Close CRM with:
        - Automatic ATL/BTL prioritization
        - Lead status assignment (Hot ATL, Validated ATL, BTL)
        - Qualification score in description
        - Tim Kipper as owner

        Args:
            lead: Lead dict with email, company, qualification_score, is_atl, etc.

        Returns:
            Created lead/contact data

        Raises:
            CRMValidationError: If required fields missing
        """
        # SAFETY: Disable all writes to Close CRM
        if os.getenv("CLOSE_WRITE_DISABLED") == "True":
            logger.warning("⚠️ CLOSE_WRITE_DISABLED: Skipping create_lead() - read-only mode")
            return {
                "status": "disabled",
                "reason": "write_operations_disabled",
                "message": "Close CRM write operations are disabled for safety"
            }

        try:
            # Get email - must be a valid email address (not domain)
            email = lead.get("email")

            # Validate email format if provided
            if email and "@" not in email:
                logger.warning(f"Invalid email format: {email}, skipping CRM creation")
                email = None

            # Check if we have discovered contacts from Hunter.io
            discovered_contacts = lead.get("_discovered_contacts", [])

            # If no email and no discovered contacts, we can't create contacts in Close CRM
            # (Close CRM requires at least one contact per lead)
            if not email and not discovered_contacts:
                logger.info(
                    f"No contacts available for {lead.get('name')} - "
                    f"skipping Close CRM creation until contacts are discovered"
                )
                return {
                    "status": "skipped",
                    "reason": "no_contacts",
                    "message": "Lead has no email or discovered contacts - waiting for enrichment"
                }

            # Use first discovered contact if we don't have primary email
            if not email and discovered_contacts:
                primary_contact = discovered_contacts[0]
                email = primary_contact.get("email")
                logger.info(f"Using first discovered contact email: {email}")

            # If we have discovered contacts, create ALL of them in Close CRM
            if discovered_contacts:
                lead_name = lead.get("name") or lead.get("company") or "Unknown Company"
                qualification_score = lead.get("qualification_score", 0)

                # If matched_lead_id provided, ADD contacts to existing lead (deduplication!)
                if matched_lead_id:
                    logger.info(f"Adding {len(discovered_contacts)} contacts to EXISTING lead {matched_lead_id} for {lead_name}")

                    added_contacts = []
                    for contact in discovered_contacts:
                        try:
                            result = await self.add_contact_to_lead(matched_lead_id, contact)
                            added_contacts.append(result)
                        except Exception as e:
                            logger.error(f"Failed to add contact {contact.get('email')} to lead {matched_lead_id}: {e}")
                            # Continue adding other contacts even if one fails
                            continue

                    logger.info(f"✅ Added {len(added_contacts)} contacts to existing lead {matched_lead_id}")

                    return {
                        "id": matched_lead_id,
                        "company": lead_name,
                        "status": "contacts_added",
                        "contacts_created": len(added_contacts),
                        "added_contacts": [c["name"] for c in added_contacts],
                        "action": "add_contact_to_existing"
                    }

                # Otherwise, CREATE new lead with ALL contacts at once
                logger.info(f"Creating NEW lead with {len(discovered_contacts)} ATL contacts for {lead_name}")

                # Build contacts array for ALL discovered contacts
                contacts_data = []
                for contact in discovered_contacts:
                    contact_data = {
                        "name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                        "title": contact.get("position"),
                        "emails": [{"email": contact.get("email")}],
                    }
                    if contact.get("phone"):
                        contact_data["phones"] = [{"phone": contact.get("phone")}]

                    contacts_data.append(contact_data)

                # ALL leads start as "Raw" - Smart views filter by custom fields
                status_id = "stat_4qxeqdfEDGNFmh93pFmXz4l8bw78DuQtTlATratY2Qb"  # Raw

                # Determine priority label for description (not status!)
                first_contact_is_atl = discovered_contacts[0].get("is_atl", False)
                if first_contact_is_atl:
                    if qualification_score >= 70:
                        priority_label = "🔥 Hot ATL"
                    else:
                        priority_label = "⭐ Validated ATL"
                else:
                    priority_label = "📋 BTL"

                # Build lead data with ALL contacts
                lead_data = {
                    "name": lead_name,
                    "contacts": contacts_data,
                    "status_id": status_id,  # Always "Raw"
                    "description": f"{priority_label}\n\nQualification Score: {qualification_score}/100\nHunter.io ATL Contacts: {len(discovered_contacts)}",
                    "custom": {
                        "qualification_score": qualification_score,
                        "is_atl": "Yes" if first_contact_is_atl else "No",  # Close uses choices field (Yes/No)
                        "priority_label": priority_label,
                        "tier": lead.get("tier", "unknown")  # hot/warm/cold/unqualified
                    }
                }

                # Assign default owner (Tim Kipper)
                default_owner = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")
                if default_owner:
                    lead_data["created_by"] = default_owner

                # Create lead with ALL contacts via Close API
                import httpx
                await self._check_rate_limit()

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.BASE_URL}/lead/",
                        headers={
                            "Authorization": self.auth_header,
                            "Content-Type": "application/json",
                        },
                        json=lead_data,
                        timeout=30.0
                    )

                    await self._update_rate_limit(response)

                    if response.status_code == 429:
                        self._handle_rate_limit_error(response)
                    elif response.status_code >= 400:
                        error_data = response.json() if response.text else {}
                        raise CRMValidationError(
                            f"Failed to create lead in Close CRM: {error_data.get('error', response.status_code)}"
                        )

                    result = response.json()
                    logger.info(f"✅ Created lead {result.get('id')} with {len(contacts_data)} ATL contacts")

                    return {
                        "id": result.get("id"),
                        "company": lead_name,
                        "status": "created",
                        "contacts_created": len(contacts_data),
                        "atl_contacts": [c.get("name") for c in contacts_data]
                    }

            else:
                # No discovered contacts - fall back to single contact creation
                contact = Contact(
                    email=email,
                    first_name=lead.get("first_name"),
                    last_name=lead.get("last_name"),
                    company=lead.get("name") or lead.get("company"),
                    title=lead.get("title"),
                    phone=lead.get("phone"),
                    linkedin_url=lead.get("linkedin_url"),
                    enrichment_data={
                        "is_atl": lead.get("is_atl", False),
                        "qualification_score": lead.get("qualification_score", 0),
                        "contact_level": lead.get("contact_level", "Unknown")
                    }
                )

                # Create in Close CRM (will auto-set status and owner)
                created_contact = await self.create_contact(contact)

                return {
                    "id": created_contact.external_ids.get("close"),
                    "email": created_contact.email,
                    "company": created_contact.company,
                    "name": f"{created_contact.first_name or ''} {created_contact.last_name or ''}".strip(),
                    "status": "created",
                    "contacts_created": 1
                }

        except Exception as e:
            logger.error(f"Failed to create lead in Close CRM: {e}")
            raise

    async def update_contact(self, contact_id: str, contact: Contact) -> Contact:
        """
        Update an existing contact in Close CRM.

        Args:
            contact_id: Close contact ID
            contact: Updated contact data

        Returns:
            Updated contact

        Raises:
            CRMNotFoundError: If contact not found
            CRMRateLimitError: If rate limit exceeded
        """
        # SAFETY: Disable all writes to Close CRM
        if os.getenv("CLOSE_WRITE_DISABLED") == "True":
            logger.warning("⚠️ CLOSE_WRITE_DISABLED: Skipping update_contact() - read-only mode")
            # Return contact unchanged
            contact.external_id = contact_id
            return contact

        try:
            await self._check_rate_limit()

            # Prepare update data
            contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
            update_data = {}

            if contact_name:
                update_data["name"] = contact_name
            if contact.title:
                update_data["title"] = contact.title
            if contact.email:
                update_data["emails"] = [{"email": contact.email}]
            if contact.phone:
                update_data["phones"] = [{"phone": contact.phone}]

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.BASE_URL}/contact/{contact_id}/",
                    headers={
                        "Authorization": self.auth_header,
                        "Content-Type": "application/json",
                    },
                    json=update_data,
                    timeout=30.0
                )

                await self._update_rate_limit(response)

                if response.status_code == 404:
                    raise CRMNotFoundError(f"Contact {contact_id} not found in Close CRM")
                elif response.status_code == 429:
                    self._handle_rate_limit_error(response)
                elif response.status_code >= 400:
                    error_data = response.json() if response.text else {}
                    raise CRMValidationError(
                        f"Failed to update contact: {error_data.get('error', response.status_code)}"
                    )

                response.json()

                # Fetch full contact details with lead context
                return await self.get_contact(contact_id)

        except httpx.HTTPError as e:
            logger.error(f"Network error updating contact {contact_id}: {e}")
            raise CRMNetworkError(f"Network error: {e}")

    async def enrich_contact(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Enrich contact data (not supported by Close CRM).

        Close CRM does not provide enrichment capabilities.
        Use Apollo integration for contact enrichment instead.

        Args:
            email: Contact email address

        Returns:
            None (enrichment not supported)
        """
        logger.debug(f"enrich_contact called for {email} - Close CRM does not support enrichment")
        return None

    async def sync_contacts(
        self,
        direction: str = "import",
        filters: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Sync contacts between local database and Close CRM.

        Args:
            direction: Sync direction ("import", "export", "bidirectional")
            filters: Optional filters for selective sync
                - query: Search query for leads
                - created_date_gte: Leads created after this date
                - updated_date_gte: Leads updated after this date

        Returns:
            SyncResult with sync metrics

        Raises:
            CRMValidationError: If invalid direction
        """
        if direction not in ["import", "export", "bidirectional"]:
            raise CRMValidationError(
                f"Invalid sync direction: {direction}. Must be 'import', 'export', or 'bidirectional'"
            )

        try:
            contacts_created = 0
            contacts_updated = 0
            contacts_failed = 0
            total_processed = 0

            if direction in ["import", "bidirectional"]:
                # Import leads from Close CRM
                logger.info("Starting Close CRM import...")

                # Build query parameters
                params = {
                    "_limit": 100,  # Pagination limit
                    "_skip": 0,
                }

                if filters:
                    if filters.get("query"):
                        params["query"] = filters["query"]
                    if filters.get("created_date_gte"):
                        params["date_created__gte"] = filters["created_date_gte"]
                    if filters.get("updated_date_gte"):
                        params["date_updated__gte"] = filters["updated_date_gte"]

                # Paginate through all leads
                has_more = True
                while has_more:
                    await self._check_rate_limit()

                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"{self.BASE_URL}/lead/",
                            headers={
                                "Authorization": self.auth_header,
                                "Content-Type": "application/json",
                            },
                            params=params,
                            timeout=30.0
                        )

                        await self._update_rate_limit(response)

                        if response.status_code == 429:
                            self._handle_rate_limit_error(response)
                            continue
                        elif response.status_code >= 400:
                            logger.error(f"Error fetching leads: {response.status_code}")
                            break

                        data = response.json()
                        leads = data.get("data", [])
                        has_more = data.get("has_more", False)

                        # Process each lead's contacts
                        for lead in leads:
                            total_processed += 1
                            try:
                                contacts = self._map_lead_to_contact(lead)
                                # Here you would save contacts to local database
                                # For now, just count them
                                contacts_created += len(contacts)
                            except Exception as e:
                                logger.error(f"Failed to process lead {lead.get('id')}: {e}")
                                contacts_failed += 1

                        # Update skip for next page
                        params["_skip"] += params["_limit"]

            if direction in ["export", "bidirectional"]:
                # Export contacts to Close CRM
                # This would fetch contacts from local DB and push to Close
                logger.info("Close CRM export not yet fully implemented")

            return SyncResult(
                platform="close",
                operation=direction,
                contacts_processed=total_processed,
                contacts_created=contacts_created,
                contacts_updated=contacts_updated,
                contacts_failed=contacts_failed,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Error during Close CRM sync: {e}")
            raise

    async def get_updated_contacts(self, since: datetime) -> List[Contact]:
        """
        Get contacts updated since a specific datetime.

        Args:
            since: DateTime to get updates from

        Returns:
            List of contacts updated since the given time
        """
        try:
            contacts_list = []

            # Format datetime for Close API
            since_str = since.strftime("%Y-%m-%dT%H:%M:%S")

            filters = {
                "updated_date_gte": since_str
            }

            # Use sync_contacts to get updated leads
            result = await self.sync_contacts(direction="import", filters=filters)

            # Note: This is a simplified implementation
            # In production, you'd store the contacts during sync and return them here
            logger.info(f"Found {result.total_processed} leads updated since {since_str}")

            return contacts_list

        except Exception as e:
            logger.error(f"Error getting updated contacts: {e}")
            return []

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Close CRM webhook signature.

        Args:
            payload: Webhook payload bytes
            signature: Signature from webhook headers

        Returns:
            True if signature is valid
        """
        # Close CRM webhook verification would go here
        # Check Close API docs for their webhook signature algorithm
        logger.warning("Close CRM webhook verification not yet implemented")
        return False

    async def handle_webhook(self, event: WebhookEvent) -> None:
        """
        Handle Close CRM webhook events.

        Args:
            event: Webhook event to process
        """
        logger.info(f"Close CRM webhook event received: {event.event_type}")

        # Process different event types
        if event.event_type == "lead.created":
            logger.info(f"New lead created: {event.payload.get('id')}")
        elif event.event_type == "lead.updated":
            logger.info(f"Lead updated: {event.payload.get('id')}")
        elif event.event_type == "contact.created":
            logger.info(f"New contact created: {event.payload.get('id')}")
        elif event.event_type == "contact.updated":
            logger.info(f"Contact updated: {event.payload.get('id')}")

        # Here you would trigger a sync for the specific lead/contact

    async def _check_rate_limit(self) -> None:
        """
        Check if rate limit allows making a request.

        Raises:
            CRMRateLimitError: If rate limit exceeded
        """
        if not self.redis:
            return  # No Redis, skip rate limiting

        try:
            # Check requests in current window
            key = f"close:rate_limit:{datetime.utcnow().strftime('%Y-%m-%d:%H:%M')}"
            current_count = await self.redis.get(key)

            if current_count and int(current_count) >= self.RATE_LIMIT_SAFE_THRESHOLD:
                raise CRMRateLimitError(
                    f"Close CRM rate limit exceeded: {self.RATE_LIMIT_SAFE_THRESHOLD} requests/minute"
                )

        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}")
            # Don't block requests if Redis fails

    async def _update_rate_limit(self, response: httpx.Response) -> None:
        """
        Update rate limit counters based on API response.

        Close returns rate limit info in RateLimit header:
        RateLimit: limit=100, remaining=50, reset=5

        Args:
            response: HTTP response from Close API
        """
        if not self.redis:
            return

        try:
            # Parse RateLimit header
            rate_limit_header = response.headers.get("RateLimit", "")
            if rate_limit_header:
                # Parse "limit=100, remaining=50, reset=5" format
                parts = {}
                for part in rate_limit_header.split(","):
                    key, value = part.strip().split("=")
                    parts[key] = int(value)

                logger.debug(f"Close rate limit: {parts}")

                # Store in Redis for monitoring
                key = "close:rate_limit:current"
                await self.redis.set(
                    key,
                    str(parts.get("remaining", 0)),
                    ex=int(parts.get("reset", 60))
                )

            # Increment request counter
            minute_key = f"close:rate_limit:{datetime.utcnow().strftime('%Y-%m-%d:%H:%M')}"
            await self.redis.incr(minute_key)
            await self.redis.expire(minute_key, 60)

        except Exception as e:
            logger.warning(f"Failed to update rate limit: {e}")

    def _handle_rate_limit_error(self, response: httpx.Response) -> None:
        """
        Handle rate limit error from Close API.

        Args:
            response: HTTP response with 429 status

        Raises:
            CRMRateLimitError: Always raises with retry information
        """
        # Parse RateLimit header to get reset time
        rate_limit_header = response.headers.get("RateLimit", "")
        reset_seconds = 60  # Default

        if rate_limit_header:
            try:
                for part in rate_limit_header.split(","):
                    key, value = part.strip().split("=")
                    if key == "reset":
                        reset_seconds = int(value)
            except Exception:
                pass

        raise CRMRateLimitError(
            f"Close CRM rate limit exceeded. Retry after {reset_seconds} seconds",
            context={"retry_after": reset_seconds}
        )

    async def check_rate_limit(self) -> Dict[str, Any]:
        """
        Get current rate limit status.

        Returns:
            Dict with rate limit information
        """
        if not self.redis:
            return {
                "rate_limit_enabled": False,
                "message": "Rate limiting disabled (no Redis)"
            }

        try:
            current_key = "close:rate_limit:current"
            remaining = await self.redis.get(current_key)

            minute_key = f"close:rate_limit:{datetime.utcnow().strftime('%Y-%m-%d:%H:%M')}"
            used_this_minute = await self.redis.get(minute_key)

            return {
                "rate_limit_enabled": True,
                "remaining_from_api": int(remaining) if remaining else None,
                "used_this_minute": int(used_this_minute) if used_this_minute else 0,
                "safe_threshold": self.RATE_LIMIT_SAFE_THRESHOLD,
            }

        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return {
                "rate_limit_enabled": True,
                "error": str(e)
            }
