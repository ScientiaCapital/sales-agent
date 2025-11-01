# LinkedIn ATL Discovery Pipeline - Complete Architecture

**Version**: 1.0
**Date**: 2025-10-31
**Status**: Design Complete - Ready for Implementation

---

## Executive Summary

A comprehensive 6-stage pipeline for discovering, enriching, deduplicating, scoring, and engaging with Above-The-Line (ATL) contacts using LinkedIn Sales Navigator, Hunter.io, and Close CRM integration.

### Key Features
- **Multi-source Discovery**: Sales Navigator API, existing connections, company pages
- **Intelligent Enrichment**: Hunter.io email discovery with fuzzy matching
- **Fuzzy Deduplication**: Prevent duplicates in Close CRM using Levenshtein distance
- **Lead Scoring**: HOT/WARM/COLD tiers for InMail prioritization
- **InMail Quota Management**: Track and allocate limited InMails (50/month) to HOT contacts only
- **Smart Outreach Routing**: InMail vs Email vs Connection Invites based on score + availability

### Performance Targets
- **Total Pipeline**: ~6 minutes for 1000 contacts
- **Discovery**: ~100s (Sales Navigator searches)
- **Enrichment**: ~25s (Hunter.io domain searches)
- **Deduplication**: ~50s (Close CRM fuzzy matching)
- **Lead Scoring**: ~5s (algorithmic scoring)
- **CRM Export**: ~140s (Close API creates/updates)
- **Outreach**: Daily batches (InMail quota + connection invite rate limits)

---

## Data Sources

### Contractor License Lists (State-Level)

**Location**: `data/licenses/`

#### Texas Contractors (Available)
- **File**: `tx_final_hottest_leads_20251031.csv`
- **Count**: 242 enriched Texas contractors
- **Match Method**: 100% phone number matching (normalized to 10 digits)
- **Data Quality**:
  - ✅ All licenses active and current
  - ✅ License expiration dates available
  - ✅ Clean 10-digit phone numbers (ready for outreach)
  - ✅ OEM certifications (Generac, Cummins, Tesla, etc.)
- **ICP Scoring**: Pre-scored with resimercial, multi-OEM, MEP+R, O&M dimensions

**Columns Available**:
```
name, phone, domain, website, city, state, zip
oem_source, license_number, license_type, license_status
license_expiration_date, icp_score, tier
resimercial_score, om_score, mepr_score, multi_oem_score
```

**ICP Tier Distribution (Texas)**:
| Tier | Count | % | Priority |
|------|-------|---|----------|
| PLATINUM (80-100) | 0 | 0.0% | 🔥 CALL FIRST |
| GOLD (60-79) | 0 | 0.0% | High priority |
| SILVER (40-59) | 3 | 1.2% | Medium priority |
| BRONZE (<40) | 239 | 98.8% | Standard |

**Top 3 Hottest TX Leads**:
1. **Freedom Enterprises Electrical & Generator Service** (48/100 SILVER) - Austin, TX
2. **ABC HOME & COMMERCIAL SERVICES, INC** (42/100 SILVER) - Austin, TX
3. **TRUSERV ENERGY SOLUTIONS** (39/100 BRONZE) - Plano, TX

#### California Contractors (Available)
- **File**: `ca_licenses_raw_20251031.csv`
- **Count**: 242,892 contractor licenses (73MB file)
- **Source**: California Contractors State License Board (CSLB)
- **Match Method**: Same phone number matching strategy (pending cross-reference)
- **Classifications**: C57 (Electrical), C36 (Plumbing), C20 (HVAC), C10 (Electrical), and more
- **Data Quality**:
  - ✅ Business names and phone numbers
  - ✅ License numbers and expiration dates
  - ✅ Bond and insurance information
  - ✅ Classifications (specialties)
- **Expected Match Rate**: ~30-40% (similar to TX, phone number dependent)
- **Expected Enriched Count**: ~80,000-100,000 contractors after OEM cross-reference

**Columns Available**:
```
LicenseNo, BusinessName, MailingAddress, City, State, County, ZIPCode
BusinessPhone, BusinessType, IssueDate, ExpirationDate
PrimaryStatus, Classifications(s), WCInsuranceCompany, CBSuretyCompany
```

**Next Step**: Cross-reference with OEM contractor database (similar to TX pipeline)

---

**Integration with LinkedIn Discovery Pipeline**:
1. Upload CA/TX CSV to Stage 1 Discovery → `discover_from_csv()`
2. Extract company names for Sales Navigator search
3. Find ATL contacts at each contractor company
4. Enrich with Hunter.io emails
5. Score leads (combine ICP score + ATL title score)
6. Export to Close CRM with tier tags

---

## Architecture Overview

### Pipeline Stages

```
┌─────────────────────────────────────────────────────────────┐
│                     STAGE 1: DISCOVERY                       │
│  Sales Navigator API: Target companies + Existing connections│
│  Output: 1000 raw ATL contacts                              │
│  Time: ~100s                                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    STAGE 2: ENRICHMENT                       │
│  Hunter.io: Find emails by domain                           │
│  Output: Contacts with emails (where available)             │
│  Time: ~25s                                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  STAGE 3: DEDUPLICATION                      │
│  Close CRM: Fuzzy match existing leads                      │
│  Output: Create/Update/Skip decisions                       │
│  Time: ~50s                                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   STAGE 4: LEAD SCORING                      │
│  Score 0-100, tier HOT/WARM/COLD                           │
│  Output: InMail eligibility flags                           │
│  Time: ~5s                                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    STAGE 5: CRM EXPORT                       │
│  Close API: Create new leads, update existing              │
│  Output: Close lead IDs for all contacts                   │
│  Time: ~140s                                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  STAGE 6: SMART OUTREACH                     │
│  HOT + no email → InMail (quota managed)                    │
│  HOT + email → Email campaign                               │
│  WARM/COLD → Connection invites with notes                 │
│  Time: Variable (daily batches)                             │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

```python
# Service Layer
LinkedInATLDiscoveryService      # Stage 1: Multi-source discovery
HunterEnrichmentService          # Stage 2: Email enrichment
DeduplicationService             # Stage 3: Fuzzy matching
LeadScoringService               # Stage 4: HOT/WARM/COLD tiers
CloseCRMExportService            # Stage 5: CRM integration
SmartOutreachService             # Stage 6: InMail vs Invite routing

# Client Layer
SalesNavigatorClient             # LinkedIn Sales Navigator API
HunterEmailService               # Hunter.io API (existing)
CloseAPIClient                   # Close CRM API (existing)
BrowserbaseAutomation            # Connection request automation

# Utility Layer
RateLimiter                      # API rate limiting
PipelineErrorHandler             # Retry logic + error handling
InMailQuotaTracker               # InMail usage monitoring
```

---

## Complete Data Models

### Stage 1: Discovery Output

```python
from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class ATLContact(BaseModel):
    """Raw ATL contact from discovery stage"""
    linkedin_url: str
    name: str
    title: str
    company: str
    discovery_source: Literal[
        "existing_connection",
        "sales_nav_search",
        "company_page"
    ]
    discovery_timestamp: datetime
```

### Stage 2: Enrichment Output

```python
class EnrichedContact(ATLContact):
    """Contact after Hunter.io enrichment"""
    email: Optional[str] = None
    email_confidence: int = 0  # 0-100
    email_source: Optional[str] = None  # "hunter.io"
```

### Stage 3: Deduplication Output

```python
class DeduplicationResult(BaseModel):
    """Result from deduplication check"""
    status: Literal["skip", "update", "create"]
    match_type: Literal[
        "exact_email",
        "fuzzy_company",
        "linkedin_url",
        "none"
    ]
    close_lead_id: Optional[int] = None
    similarity_score: int = 0  # 0-100 (fuzzy match confidence)
```

### Stage 4: Lead Scoring Output

```python
class LeadScore(BaseModel):
    """Lead scoring result"""
    score: int  # 0-100
    tier: Literal["HOT", "WARM", "COLD"]
    inmail_eligible: bool
    scoring_breakdown: dict  # {"title": 40, "company_size": 20, ...}

class ScoredContact(EnrichedContact):
    """Contact after lead scoring"""
    lead_score: LeadScore
    dedup_result: DeduplicationResult
    close_lead_id: Optional[int] = None  # Set in Stage 5
```

### Stage 6: Outreach Output

```python
class OutreachAction(BaseModel):
    """Outreach action for a contact"""
    contact: ScoredContact
    action_type: Literal["inmail", "email", "connection_invite"]
    message_template: str
    priority: int  # 1-10, based on lead score
    scheduled_date: Optional[datetime] = None
    status: Literal[
        "pending",
        "sent",
        "delivered",
        "opened",
        "replied",
        "failed"
    ] = "pending"

class OutreachPlan(BaseModel):
    """Complete outreach plan for a batch"""
    inmails: List[OutreachAction]
    emails: List[OutreachAction]
    connection_invites: List[OutreachAction]
    inmails_remaining: int
    total_contacts: int
    estimated_completion_date: datetime
```

---

## Stage 1: Discovery (Sales Navigator API)

### Implementation: LinkedInATLDiscoveryService

```python
class LinkedInATLDiscoveryService:
    """Discover ATL contacts from multiple LinkedIn sources"""

    def __init__(self, sales_nav_client: SalesNavigatorClient):
        self.sales_nav_client = sales_nav_client

    async def discover_from_csv(
        self,
        csv_companies: List[str],
        limit_per_company: int = 5
    ) -> List[ATLContact]:
        """
        Discover ATL contacts from CSV target companies

        Flow:
        1. Load companies from CSV (e.g., 200 contractors)
        2. For each company, search Sales Navigator for ATL titles
        3. Limit to top 5 per company (1000 total contacts max)

        Args:
            csv_companies: List of company names from CSV
            limit_per_company: Max ATL contacts per company

        Returns:
            List of ATLContact objects

        Performance: ~500ms per company = ~100 seconds total for 200 companies
        Rate Limit: 100 searches/hour (Sales Navigator API)
        """
        contacts = []

        for company_name in csv_companies:
            # Sales Navigator People Search
            results = await self.sales_nav_client.search_people(
                company_name=company_name,
                titles=["CEO", "President", "VP", "Director", "Founder"],
                limit=limit_per_company
            )

            for person in results:
                contacts.append(ATLContact(
                    linkedin_url=person.linkedin_url,
                    name=person.name,
                    title=person.title,
                    company=company_name,
                    discovery_source="sales_nav_search",
                    discovery_timestamp=datetime.utcnow()
                ))

        logger.info(f"Discovered {len(contacts)} ATL contacts from {len(csv_companies)} companies")
        return contacts

    async def discover_from_existing_connections(
        self,
        user_linkedin_id: str
    ) -> List[ATLContact]:
        """
        Mine ATL contacts from user's existing LinkedIn connections

        Flow:
        1. Fetch all connections via Sales Navigator API
        2. Filter for ATL titles (CEO, CTO, VP, Director, etc.)
        3. Already connected = high-value leads (discovery_source = "existing_connection")

        Args:
            user_linkedin_id: Authenticated user's LinkedIn ID

        Returns:
            List of ATLContact objects

        Performance: ~2000ms for 500 connections
        Rate Limit: 50 requests/hour (Sales Navigator API)
        """
        connections = await self.sales_nav_client.get_connections(user_linkedin_id)

        atl_connections = []
        for conn in connections:
            if self._is_atl_title(conn.title):
                atl_connections.append(ATLContact(
                    linkedin_url=conn.linkedin_url,
                    name=conn.name,
                    title=conn.title,
                    company=conn.company,
                    discovery_source="existing_connection",
                    discovery_timestamp=datetime.utcnow()
                ))

        logger.info(f"Found {len(atl_connections)} ATL contacts in existing connections")
        return atl_connections

    async def discover_from_company_pages(
        self,
        company_linkedin_urls: List[str]
    ) -> List[ATLContact]:
        """
        Discover ATL contacts from LinkedIn company pages

        Flow:
        1. Visit company LinkedIn page
        2. Navigate to "People" tab
        3. Filter for ATL titles
        4. Extract profiles

        Args:
            company_linkedin_urls: List of LinkedIn company page URLs

        Returns:
            List of ATLContact objects

        Performance: ~1500ms per company page
        Rate Limit: 100 requests/hour (Sales Navigator API)
        """
        contacts = []

        for company_url in company_linkedin_urls:
            # Sales Navigator Company Page API
            people = await self.sales_nav_client.get_company_people(
                company_url=company_url,
                title_filters=["CEO", "CTO", "CFO", "VP", "President", "Director"]
            )

            for person in people:
                contacts.append(ATLContact(
                    linkedin_url=person.linkedin_url,
                    name=person.name,
                    title=person.title,
                    company=person.company,
                    discovery_source="company_page",
                    discovery_timestamp=datetime.utcnow()
                ))

        return contacts

    def _is_atl_title(self, title: str) -> bool:
        """Check if title is Above The Line (ATL)"""
        atl_keywords = [
            "CEO", "Chief Executive", "President",
            "CTO", "Chief Technology", "VP", "Vice President",
            "CFO", "Chief Financial", "COO", "Chief Operating",
            "Founder", "Co-Founder", "Owner",
            "Director", "Head of", "Partner", "Managing Director"
        ]
        title_lower = title.lower()
        return any(keyword.lower() in title_lower for keyword in atl_keywords)
```

### Sales Navigator API Client

```python
class SalesNavigatorClient:
    """LinkedIn Sales Navigator API client"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.linkedin.com/v2"
        self.rate_limiter = RateLimiter(
            max_requests=100,  # 100 requests per hour
            window=3600
        )

    async def search_people(
        self,
        company_name: str,
        titles: List[str],
        limit: int = 5
    ) -> List[SalesNavPerson]:
        """
        Search for people at company with specific titles

        API Endpoint: POST /sales/people/search
        Rate Limit: 100 requests/hour
        Cost: Included in Sales Navigator subscription ($79.99-$149.99/month)

        Args:
            company_name: Target company name
            titles: List of job titles to search for
            limit: Max results to return

        Returns:
            List of SalesNavPerson objects
        """
        await self.rate_limiter.wait_if_needed()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/sales/people/search",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "query": {
                        "company": company_name,
                        "titles": titles
                    },
                    "start": 0,
                    "count": limit
                }
            )

            response.raise_for_status()
            data = response.json()

            return [
                SalesNavPerson(
                    linkedin_url=person["publicProfileUrl"],
                    name=f"{person['firstName']} {person['lastName']}",
                    title=person["headline"],
                    company=person["companyName"]
                )
                for person in data["elements"]
            ]

    async def get_connections(
        self,
        user_id: str
    ) -> List[SalesNavPerson]:
        """
        Get all connections for authenticated user

        API Endpoint: GET /sales/connections
        Rate Limit: 50 requests/hour

        Args:
            user_id: LinkedIn user ID

        Returns:
            List of SalesNavPerson objects (all connections)
        """
        await self.rate_limiter.wait_if_needed()

        connections = []
        start = 0
        count = 100  # Max per request

        while True:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/sales/connections",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    params={"start": start, "count": count}
                )

                response.raise_for_status()
                data = response.json()
                connections.extend(data["elements"])

                if len(data["elements"]) < count:
                    break  # No more pages

                start += count

        return [
            SalesNavPerson(
                linkedin_url=conn["publicProfileUrl"],
                name=f"{conn['firstName']} {conn['lastName']}",
                title=conn["headline"],
                company=conn.get("companyName", "Unknown")
            )
            for conn in connections
        ]

    async def get_company_people(
        self,
        company_url: str,
        title_filters: List[str]
    ) -> List[SalesNavPerson]:
        """
        Get people at a company (from company page)

        API Endpoint: GET /sales/companies/{id}/people
        Rate Limit: 100 requests/hour

        Args:
            company_url: LinkedIn company page URL
            title_filters: List of titles to filter for

        Returns:
            List of SalesNavPerson objects
        """
        await self.rate_limiter.wait_if_needed()

        # Extract company ID from URL
        company_id = self._extract_company_id(company_url)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/sales/companies/{company_id}/people",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={
                    "titleFilters": ",".join(title_filters),
                    "count": 50
                }
            )

            response.raise_for_status()
            data = response.json()

            return [
                SalesNavPerson(
                    linkedin_url=person["publicProfileUrl"],
                    name=f"{person['firstName']} {person['lastName']}",
                    title=person["headline"],
                    company=person["companyName"]
                )
                for person in data["elements"]
            ]

    def _extract_company_id(self, company_url: str) -> str:
        """Extract company ID from LinkedIn URL"""
        import re
        match = re.search(r'linkedin\.com/company/([^/\?]+)', company_url)
        if match:
            return match.group(1)
        raise ValueError(f"Invalid LinkedIn company URL: {company_url}")
```

---

## Stage 2: Enrichment (Hunter.io Email Discovery)

### Implementation: HunterEnrichmentService

```python
class HunterEnrichmentService:
    """Enrich ATL contacts with email addresses from Hunter.io"""

    def __init__(self, hunter_service: HunterEmailService):
        self.hunter_service = hunter_service

    async def enrich_batch(
        self,
        contacts: List[ATLContact]
    ) -> List[EnrichedContact]:
        """
        Batch enrich contacts with Hunter.io

        Strategy:
        1. Group contacts by company domain (reduce API calls)
        2. Use Hunter.io domain search (1 API call per domain)
        3. Match contacts by name + title fuzzy matching
        4. Add email if found with confidence score

        Args:
            contacts: List of ATLContact from discovery stage

        Returns:
            List of EnrichedContact with emails (where found)

        Performance: ~500ms per domain
        Hunter.io Rate Limit: 25 searches/month (free), 500/month (starter $49/mo)
        """
        # Group by domain to minimize API calls
        contacts_by_domain = self._group_by_domain(contacts)

        enriched = []
        domains_searched = 0
        max_domains = 25  # Free tier limit

        for domain, domain_contacts in contacts_by_domain.items():
            if domains_searched >= max_domains:
                logger.warning(f"Hunter.io monthly limit reached ({max_domains} domains)")
                # Add remaining contacts without emails
                enriched.extend([
                    EnrichedContact(**c.dict())
                    for c in domain_contacts
                ])
                continue

            # Search domain once for all contacts at that company
            hunter_result = await self.hunter_service.find_emails(
                domain=domain,
                atl_only=True
            )

            domains_searched += 1

            # Match Hunter.io results to contacts
            for contact in domain_contacts:
                matched_email = self._match_email(contact, hunter_result.contacts)

                enriched.append(EnrichedContact(
                    **contact.dict(),
                    email=matched_email.email if matched_email else None,
                    email_confidence=matched_email.confidence if matched_email else 0,
                    email_source="hunter.io" if matched_email else None
                ))

        logger.info(f"Enriched {len(enriched)} contacts from {domains_searched} domains")
        logger.info(f"Emails found: {sum(1 for c in enriched if c.email)}/{len(enriched)}")

        return enriched

    def _group_by_domain(
        self,
        contacts: List[ATLContact]
    ) -> Dict[str, List[ATLContact]]:
        """
        Group contacts by company domain for batch processing

        Strategy:
        - Use LinkedIn company page to extract domain
        - Fallback to Google search "company name domain"
        - Group all contacts from same company together
        """
        from urllib.parse import urlparse

        grouped = {}
        for contact in contacts:
            # Extract domain from company name or LinkedIn
            domain = self._extract_domain(contact.company)

            if domain not in grouped:
                grouped[domain] = []
            grouped[domain].append(contact)

        return grouped

    def _extract_domain(self, company_name: str) -> str:
        """
        Extract domain from company name

        Examples:
        - "Acme Corporation" → "acme.com"
        - "TechStart Inc" → "techstart.io"

        Strategy:
        1. Remove legal suffixes (Inc, LLC, Corp, etc.)
        2. Lowercase and concatenate
        3. Append .com (most common TLD)

        Note: This is a heuristic. For production, consider:
        - Clearbit Company API for domain lookup
        - Manual company → domain mapping CSV
        """
        import re

        # Remove legal suffixes
        clean = re.sub(r'\b(Inc|LLC|Corp|Corporation|Ltd|Limited)\b', '', company_name, flags=re.IGNORECASE)
        clean = clean.strip().lower()

        # Remove special characters
        clean = re.sub(r'[^a-z0-9\s]', '', clean)

        # Take first word as domain
        domain_name = clean.split()[0] if clean.split() else "unknown"

        return f"{domain_name}.com"

    def _match_email(
        self,
        contact: ATLContact,
        hunter_contacts: List[HunterContact]
    ) -> Optional[HunterContact]:
        """
        Match contact to Hunter.io result by name and title

        Matching strategy:
        1. Exact name match (first + last)
        2. Fuzzy name match (85% similarity threshold)
        3. Title verification (ensure title matches)

        Args:
            contact: ATLContact to match
            hunter_contacts: Results from Hunter.io domain search

        Returns:
            Matched HunterContact or None
        """
        from fuzzywuzzy import fuzz

        contact_name_parts = contact.name.lower().split()

        for hunter in hunter_contacts:
            hunter_name = f"{hunter.first_name} {hunter.last_name}".lower()

            # Exact match
            if contact.name.lower() == hunter_name:
                return hunter

            # Fuzzy match (85% threshold)
            similarity = fuzz.ratio(contact.name.lower(), hunter_name)
            if similarity >= 85:
                # Verify title contains matching keywords
                contact_keywords = set(contact.title.lower().split())
                hunter_keywords = set(hunter.position.lower().split())

                # At least one keyword overlap (e.g., "CEO", "President")
                if contact_keywords & hunter_keywords:
                    return hunter

        return None
```

---

## Stage 3: Deduplication (Fuzzy Matching vs Close CRM)

### Implementation: DeduplicationService

```python
class DeduplicationService:
    """Fuzzy matching deduplication against Close CRM"""

    def __init__(self, close_api: CloseAPIClient):
        self.close_api = close_api

    async def check_duplicate(
        self,
        contact: EnrichedContact
    ) -> DeduplicationResult:
        """
        Check if contact/company already exists in Close CRM

        Matching hierarchy (fast → slow):
        1. Exact email match (indexed lookup, <10ms)
        2. Exact LinkedIn URL match (custom field lookup, <50ms)
        3. Fuzzy company name match (full scan, ~500ms)

        Args:
            contact: EnrichedContact to check

        Returns:
            DeduplicationResult with status (skip/update/create)

        Performance:
        - Email match: <10ms
        - LinkedIn URL match: <50ms
        - Fuzzy match: ~500ms (fallback only)
        """

        # 1. Exact email match (100% confidence - skip duplicate)
        if contact.email:
            existing = await self.close_api.find_lead_by_email(contact.email)
            if existing:
                logger.info(f"Exact email match: {contact.email} → Lead {existing.id}")
                return DeduplicationResult(
                    status="skip",
                    match_type="exact_email",
                    close_lead_id=existing.id,
                    similarity_score=100
                )

        # 2. Exact LinkedIn URL match (95% confidence - update if has email)
        if contact.linkedin_url:
            existing = await self.close_api.find_lead_by_custom_field(
                field_name="linkedin_url",
                field_value=contact.linkedin_url
            )
            if existing:
                logger.info(f"LinkedIn URL match: {contact.linkedin_url} → Lead {existing.id}")

                # If contact has email but existing doesn't, update
                status = "update" if contact.email and not existing.email else "skip"

                return DeduplicationResult(
                    status=status,
                    match_type="linkedin_url",
                    close_lead_id=existing.id,
                    similarity_score=95
                )

        # 3. Fuzzy company name match (85% threshold - create new contact at same company)
        existing_companies = await self.close_api.list_companies()
        best_match = self._fuzzy_match_company(
            contact.company,
            existing_companies
        )

        if best_match.similarity_score >= 85:
            logger.info(f"Fuzzy company match: {contact.company} → {best_match.company_name} (score: {best_match.similarity_score})")

            # Company exists, but this is a new contact at that company
            # Create new contact, associate with existing company
            return DeduplicationResult(
                status="update",  # Update company record with new contact
                match_type="fuzzy_company",
                close_lead_id=best_match.lead_id,
                similarity_score=best_match.similarity_score
            )

        # 4. No match - create new lead
        return DeduplicationResult(
            status="create",
            match_type="none",
            similarity_score=0
        )

    def _fuzzy_match_company(
        self,
        company_name: str,
        existing_companies: List[Company]
    ) -> FuzzyMatch:
        """
        Fuzzy match using Levenshtein distance

        Normalizations:
        - Remove "Inc", "LLC", "Corp", "Corporation", "Ltd", "Limited"
        - Lowercase
        - Remove special characters
        - Remove extra whitespace

        Matching algorithm:
        - fuzz.ratio() for overall similarity
        - 85% threshold to balance precision/recall

        Args:
            company_name: Company name to match
            existing_companies: List of companies in Close CRM

        Returns:
            FuzzyMatch with best match and similarity score
        """
        from fuzzywuzzy import fuzz

        normalized = self._normalize_company_name(company_name)

        best_score = 0
        best_match = None

        for company in existing_companies:
            company_normalized = self._normalize_company_name(company.name)

            # Calculate similarity (0-100)
            score = fuzz.ratio(normalized, company_normalized)

            if score > best_score:
                best_score = score
                best_match = company

        return FuzzyMatch(
            company_name=best_match.name if best_match else None,
            lead_id=best_match.id if best_match else None,
            similarity_score=best_score
        )

    def _normalize_company_name(self, name: str) -> str:
        """
        Normalize company name for fuzzy matching

        Examples:
        - "Acme Corporation" → "acme"
        - "TechStart, Inc." → "techstart"
        - "Blue Sky LLC" → "blue sky"
        """
        import re

        # Remove legal suffixes
        normalized = re.sub(
            r'\b(Inc|LLC|Corp|Corporation|Ltd|Limited|Co)\b\.?',
            '',
            name,
            flags=re.IGNORECASE
        )

        # Lowercase
        normalized = normalized.lower()

        # Remove special characters (keep spaces)
        normalized = re.sub(r'[^a-z0-9\s]', '', normalized)

        # Remove extra whitespace
        normalized = ' '.join(normalized.split())

        return normalized.strip()
```

---

## Stage 4: Lead Scoring (HOT/WARM/COLD)

### Implementation: LeadScoringService

```python
class LeadScoringService:
    """Score leads to identify HOT prospects for InMail allocation"""

    async def score_contact(
        self,
        contact: EnrichedContact,
        enrichment_data: Optional[dict] = None
    ) -> LeadScore:
        """
        Score contact based on multiple factors:

        Scoring breakdown (0-100 points):
        - Title seniority (0-40 points)
          * CEO/Chief Executive: 40
          * President: 35
          * VP/Vice President: 30
          * Director: 20

        - Company size (0-20 points)
          * Enterprise (500+): 20
          * Mid-market (50-500): 15
          * SMB (<50): 10

        - Email availability (0-15 points)
          * Has email: 15 (can reach via email, less urgent for InMail)
          * No email: 0 (InMail candidate)

        - Discovery source (0-15 points)
          * Existing connection: 15 (already connected, high value)
          * Sales Nav search: 10
          * Company page: 5

        - Industry match (0-10 points)
          * Target industry: 10
          * Adjacent industry: 5
          * Other: 0

        Tiers:
        - HOT: 80-100 points (InMail eligible if no email)
        - WARM: 50-79 points
        - COLD: 0-49 points

        Args:
            contact: EnrichedContact to score
            enrichment_data: Optional additional data (company size, industry, etc.)

        Returns:
            LeadScore with tier and InMail eligibility
        """
        score = 0
        breakdown = {}

        # === Title Seniority (0-40 points) ===
        title_score = self._score_title(contact.title)
        score += title_score
        breakdown["title"] = title_score

        # === Company Size (0-20 points) ===
        company_size_score = self._score_company_size(enrichment_data)
        score += company_size_score
        breakdown["company_size"] = company_size_score

        # === Email Availability (0-15 points) ===
        email_score = 15 if contact.email else 0
        score += email_score
        breakdown["email"] = email_score

        # === Discovery Source (0-15 points) ===
        source_score = self._score_discovery_source(contact.discovery_source)
        score += source_score
        breakdown["discovery_source"] = source_score

        # === Industry Match (0-10 points) ===
        industry_score = self._score_industry(enrichment_data)
        score += industry_score
        breakdown["industry"] = industry_score

        # Determine tier
        if score >= 80:
            tier = "HOT"
        elif score >= 50:
            tier = "WARM"
        else:
            tier = "COLD"

        # InMail eligibility: HOT contacts without email
        inmail_eligible = (tier == "HOT" and not contact.email)

        logger.info(f"Scored {contact.name}: {score}/100 ({tier}) - InMail: {inmail_eligible}")

        return LeadScore(
            score=score,
            tier=tier,
            inmail_eligible=inmail_eligible,
            scoring_breakdown=breakdown
        )

    def _score_title(self, title: str) -> int:
        """Score based on title seniority"""
        title_lower = title.lower()

        if "ceo" in title_lower or "chief executive" in title_lower:
            return 40
        elif "president" in title_lower:
            return 35
        elif "vp" in title_lower or "vice president" in title_lower:
            return 30
        elif "director" in title_lower:
            return 20
        elif "founder" in title_lower or "owner" in title_lower:
            return 35
        else:
            return 10

    def _score_company_size(self, enrichment_data: Optional[dict]) -> int:
        """Score based on company size"""
        if not enrichment_data:
            return 10  # Default if unknown

        size = enrichment_data.get("company_size", "unknown")

        if size == "enterprise" or size == "500+":
            return 20
        elif size == "mid-market" or "50" in size:
            return 15
        elif size == "smb" or "small" in size.lower():
            return 10
        else:
            return 10

    def _score_discovery_source(self, source: str) -> int:
        """Score based on how contact was discovered"""
        if source == "existing_connection":
            return 15  # Already connected, highest value
        elif source == "sales_nav_search":
            return 10
        elif source == "company_page":
            return 5
        else:
            return 0

    def _score_industry(self, enrichment_data: Optional[dict]) -> int:
        """Score based on industry match"""
        if not enrichment_data:
            return 5  # Default if unknown

        industry = enrichment_data.get("industry", "").lower()

        # Target industries (customize based on ICP)
        target_industries = [
            "construction",
            "contractor",
            "hvac",
            "plumbing",
            "electrical",
            "commercial services"
        ]

        if any(target in industry for target in target_industries):
            return 10
        else:
            return 5
```

---

## Stage 5: CRM Export (Close API)

### Implementation: CloseCRMExportService

```python
class CloseCRMExportService:
    """Export ATL contacts to Close CRM"""

    def __init__(self, close_api: CloseAPIClient):
        self.close_api = close_api

    async def export_batch(
        self,
        contacts: List[EnrichedContact],
        dedup_results: List[DeduplicationResult],
        lead_scores: List[LeadScore]
    ) -> ExportResult:
        """
        Export contacts to Close CRM

        Flow:
        1. Filter for "create" and "update" statuses (skip duplicates)
        2. Create new leads in Close
        3. Update existing leads with new data
        4. Add custom fields (linkedin_url, lead_score, discovery_source, etc.)
        5. Tag with "ATL", "LinkedIn Discovery", and tier (HOT/WARM/COLD)

        Args:
            contacts: List of EnrichedContact objects
            dedup_results: Deduplication results (skip/update/create)
            lead_scores: Lead scores for each contact

        Returns:
            ExportResult with counts (created, updated, skipped, errors)

        Performance: ~200ms per contact (Close API)
        Rate Limit: 600 requests/minute (Close API)
        """
        created = 0
        updated = 0
        skipped = 0
        errors = []

        for contact, dedup, score in zip(contacts, dedup_results, lead_scores):
            try:
                if dedup.status == "skip":
                    logger.info(f"Skipping duplicate: {contact.name} (match: {dedup.match_type})")
                    skipped += 1
                    continue

                if dedup.status == "create":
                    # Create new lead
                    lead = await self.close_api.create_lead(
                        name=contact.name,
                        company=contact.company,
                        email=contact.email,
                        custom_fields={
                            "linkedin_url": contact.linkedin_url,
                            "title": contact.title,
                            "lead_score": score.score,
                            "lead_tier": score.tier,
                            "discovery_source": contact.discovery_source,
                            "discovery_timestamp": contact.discovery_timestamp.isoformat(),
                            "email_confidence": contact.email_confidence,
                            "inmail_eligible": score.inmail_eligible
                        },
                        tags=["ATL", "LinkedIn Discovery", score.tier]
                    )

                    logger.info(f"Created lead: {contact.name} (ID: {lead.id}, Score: {score.score})")
                    created += 1

                elif dedup.status == "update":
                    # Update existing lead with new data
                    await self.close_api.update_lead(
                        lead_id=dedup.close_lead_id,
                        updates={
                            "email": contact.email if contact.email else None,
                            "custom_fields": {
                                "linkedin_url": contact.linkedin_url,
                                "lead_score": score.score,
                                "lead_tier": score.tier,
                                "last_enriched": datetime.utcnow().isoformat(),
                                "email_confidence": contact.email_confidence
                            },
                            "tags": ["ATL", "LinkedIn Discovery", score.tier]
                        }
                    )

                    logger.info(f"Updated lead: {contact.name} (ID: {dedup.close_lead_id})")
                    updated += 1

            except Exception as e:
                logger.error(f"Export error for {contact.name}: {e}")
                errors.append({
                    "contact": contact.name,
                    "error": str(e)
                })

        logger.info(f"Export complete: {created} created, {updated} updated, {skipped} skipped, {len(errors)} errors")

        return ExportResult(
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors
        )
```

---

## Stage 6: Smart Outreach (InMail Quota Management)

### Implementation: SmartOutreachService

```python
class SmartOutreachService:
    """Manage InMail quota and route outreach accordingly"""

    def __init__(
        self,
        sales_nav_client: SalesNavigatorClient,
        browserbase_automation: BrowserbaseAutomation
    ):
        self.sales_nav_client = sales_nav_client
        self.browserbase_automation = browserbase_automation

        # InMail quota (Sales Navigator plan-dependent)
        self.inmail_quota_per_month = 50  # Sales Navigator Premium
        # self.inmail_quota_per_month = 20  # Sales Navigator Core

        # Connection invite limits (LinkedIn safe limits)
        self.connection_invite_daily_limit = 20  # Conservative limit
        self.connection_invite_weekly_limit = 100

    async def plan_outreach(
        self,
        contacts: List[ScoredContact]
    ) -> OutreachPlan:
        """
        Plan outreach strategy based on InMail quota and lead scores

        Strategy:
        1. HOT contacts without email → InMail (limited quota - 50/month)
        2. HOT contacts with email → Email campaign (unlimited)
        3. WARM/COLD contacts → Connection invite with note (rate-limited - 20/day)

        Args:
            contacts: List of ScoredContact objects

        Returns:
            OutreachPlan with categorized actions
        """
        # Check current InMail usage
        inmails_used_this_month = await self._get_inmails_used()
        inmails_remaining = self.inmail_quota_per_month - inmails_used_this_month

        logger.info(f"InMail quota: {inmails_remaining}/{self.inmail_quota_per_month} remaining")

        # Categorize contacts
        inmail_candidates = []
        email_candidates = []
        connection_invite_candidates = []

        for contact in contacts:
            score = contact.lead_score

            if score.tier == "HOT" and not contact.email:
                # HOT, no email → InMail candidate
                inmail_candidates.append(contact)

            elif score.tier == "HOT" and contact.email:
                # HOT, has email → Email campaign
                email_candidates.append(contact)

            else:
                # WARM/COLD → Connection invite
                connection_invite_candidates.append(contact)

        # Allocate InMails (prioritize by score)
        inmail_candidates.sort(key=lambda c: c.lead_score.score, reverse=True)
        inmails_to_send = inmail_candidates[:inmails_remaining]
        overflow_to_connection = inmail_candidates[inmails_remaining:]

        # Overflow contacts (exceeded InMail quota) → connection invites
        connection_invite_candidates.extend(overflow_to_connection)

        logger.info(f"Outreach plan: {len(inmails_to_send)} InMails, {len(email_candidates)} emails, {len(connection_invite_candidates)} connection invites")

        return OutreachPlan(
            inmails=[
                OutreachAction(
                    contact=c,
                    action_type="inmail",
                    message_template=self._get_inmail_template(c),
                    priority=c.lead_score.score
                )
                for c in inmails_to_send
            ],
            emails=[
                OutreachAction(
                    contact=c,
                    action_type="email",
                    message_template=self._get_email_template(c),
                    priority=c.lead_score.score
                )
                for c in email_candidates
            ],
            connection_invites=[
                OutreachAction(
                    contact=c,
                    action_type="connection_invite",
                    message_template=self._get_connection_note_template(c),
                    priority=c.lead_score.score
                )
                for c in connection_invite_candidates
            ],
            inmails_remaining=inmails_remaining - len(inmails_to_send),
            total_contacts=len(contacts),
            estimated_completion_date=self._estimate_completion(
                len(inmails_to_send),
                len(connection_invite_candidates)
            )
        )

    async def send_inmail(
        self,
        contact: ScoredContact,
        message_template: str
    ) -> InMailResult:
        """
        Send InMail via Sales Navigator API

        Template variables:
        - {first_name}: Contact's first name
        - {company}: Company name
        - {title}: Job title

        Args:
            contact: ScoredContact to send InMail to
            message_template: Message template with variables

        Returns:
            InMailResult with status

        Rate Limit: No explicit API limit, but quota enforced server-side
        Performance: ~1000ms per InMail
        """
        # Format message
        message = message_template.format(
            first_name=contact.name.split()[0],
            company=contact.company,
            title=contact.title
        )

        # Send via Sales Navigator API
        result = await self.sales_nav_client.send_inmail(
            linkedin_url=contact.linkedin_url,
            subject="Quick question about [relevant topic]",
            message=message
        )

        # Track InMail usage
        await self._track_inmail_usage(contact, result)

        logger.info(f"Sent InMail to {contact.name} ({contact.company})")

        return result

    async def send_connection_invite(
        self,
        contact: ScoredContact,
        note_template: str
    ) -> ConnectionResult:
        """
        Send connection invite with personalized note

        LinkedIn limits:
        - 300 characters max for connection note
        - Recommended: 20 invites/day (conservative)

        Args:
            contact: ScoredContact to send invite to
            note_template: Note template (max 300 chars after formatting)

        Returns:
            ConnectionResult with status

        Performance: ~2000ms per invite (browser automation)
        """
        # Format note (enforce 300 char limit)
        note = note_template.format(
            first_name=contact.name.split()[0],
            company=contact.company
        )[:300]

        # Send via Browserbase automation
        result = await self.browserbase_automation.send_connection_request(
            linkedin_url=contact.linkedin_url,
            note=note
        )

        # Track for rate limiting
        await self._track_connection_request(contact, result)

        logger.info(f"Sent connection invite to {contact.name} ({contact.company})")

        return result

    def _get_inmail_template(self, contact: ScoredContact) -> str:
        """Get InMail template for contact"""
        return """Hi {first_name},

I noticed you're the {title} at {company} and thought you might be interested in [value proposition].

We help [target companies] achieve [specific outcome] through [solution].

Would you be open to a brief 15-minute call next week to explore if this could benefit {company}?

Best regards,
[Your Name]"""

    def _get_email_template(self, contact: ScoredContact) -> str:
        """Get email template for contact"""
        return """Subject: Quick question for {company}

Hi {first_name},

I'm reaching out because [personalized reason based on company/role].

We've helped [similar company] achieve [specific result]. I'd love to share how we could do the same for {company}.

Are you available for a quick 15-minute call this week?

Best,
[Your Name]"""

    def _get_connection_note_template(self, contact: ScoredContact) -> str:
        """Get connection note template (max 300 chars)"""
        return "Hi {first_name}, I'd love to connect and learn more about {company}'s [relevant area]. Looking forward to connecting!"

    async def _get_inmails_used(self) -> int:
        """Get InMails used this month"""
        # Query database for InMails sent this month
        from datetime import datetime
        from app.models import OutreachLog

        first_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        count = await OutreachLog.query.filter(
            OutreachLog.action_type == "inmail",
            OutreachLog.sent_at >= first_of_month
        ).count()

        return count

    async def _track_inmail_usage(
        self,
        contact: ScoredContact,
        result: InMailResult
    ):
        """Track InMail usage in database"""
        from app.models import OutreachLog

        await OutreachLog.create(
            contact_id=contact.close_lead_id,
            action_type="inmail",
            status=result.status,
            sent_at=datetime.utcnow()
        )

    async def _track_connection_request(
        self,
        contact: ScoredContact,
        result: ConnectionResult
    ):
        """Track connection request in database"""
        from app.models import OutreachLog

        await OutreachLog.create(
            contact_id=contact.close_lead_id,
            action_type="connection_invite",
            status=result.status,
            sent_at=datetime.utcnow()
        )

    def _estimate_completion(
        self,
        inmails_count: int,
        connection_invites_count: int
    ) -> datetime:
        """Estimate completion date for outreach"""
        # InMails: Can send all immediately (no rate limit, only quota)
        # Connection invites: 20/day limit

        days_needed = connection_invites_count // self.connection_invite_daily_limit
        if connection_invites_count % self.connection_invite_daily_limit > 0:
            days_needed += 1

        return datetime.utcnow() + timedelta(days=days_needed)
```

### InMail Quota Tracking Dashboard

```python
class InMailQuotaTracker:
    """Track InMail usage and provide analytics"""

    async def get_quota_status(self) -> QuotaStatus:
        """
        Get current InMail quota status

        Returns:
          - total_quota: 50 (Sales Navigator Premium)
          - used_this_month: 23
          - remaining: 27
          - reset_date: "2025-11-01"
          - hot_contacts_pending: 45  # Contacts eligible for InMail
          - recommendation: Action to take
        """
        used = await self._count_inmails_this_month()
        total = 50  # Sales Navigator Premium quota
        pending_hot = await self._count_hot_contacts_without_email()

        return QuotaStatus(
            total_quota=total,
            used_this_month=used,
            remaining=total - used,
            reset_date=self._get_next_reset_date(),
            hot_contacts_pending=pending_hot,
            recommendation=self._get_recommendation(total - used, pending_hot)
        )

    def _get_recommendation(
        self,
        remaining: int,
        pending_hot: int
    ) -> str:
        """Recommend InMail strategy based on quota"""
        if remaining >= pending_hot:
            return "✅ Send InMails now - sufficient quota for all HOT contacts"

        elif remaining >= pending_hot * 0.5:
            return f"⚠️ Send to top {remaining} HOT contacts only (50% of pending)"

        elif remaining > 0:
            return f"⚠️ Critically low - send to top {remaining} only, use connection invites for rest"

        else:
            return "🛑 Quota exhausted - wait for reset or use connection invites"

    def _get_next_reset_date(self) -> str:
        """Get next quota reset date (first of next month)"""
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        next_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month += relativedelta(months=1)

        return next_month.strftime("%Y-%m-%d")

    async def _count_inmails_this_month(self) -> int:
        """Count InMails sent this month"""
        from datetime import datetime
        from app.models import OutreachLog

        first_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        count = await OutreachLog.query.filter(
            OutreachLog.action_type == "inmail",
            OutreachLog.sent_at >= first_of_month,
            OutreachLog.status.in_(["sent", "delivered", "opened", "replied"])
        ).count()

        return count

    async def _count_hot_contacts_without_email(self) -> int:
        """Count HOT contacts without email (InMail candidates)"""
        from app.models import Lead

        count = await Lead.query.filter(
            Lead.lead_tier == "HOT",
            Lead.email == None,
            Lead.inmail_eligible == True
        ).count()

        return count
```

---

## Error Handling & Rate Limiting

### Pipeline Error Handler

```python
class PipelineErrorHandler:
    """Comprehensive error handling for the pipeline"""

    async def execute_stage_with_retry(
        self,
        stage_name: str,
        stage_func: callable,
        max_retries: int = 3
    ):
        """
        Execute pipeline stage with exponential backoff retry

        Handles:
        - Rate limit errors (429) → Wait and retry with exponential backoff
        - Timeout errors → Retry with increased timeout
        - API errors → Log and continue with partial results
        - Network errors → Retry with backoff

        Args:
            stage_name: Name of stage (for logging)
            stage_func: Async function to execute
            max_retries: Max retry attempts

        Returns:
            Result from stage_func

        Raises:
            Exception if all retries exhausted
        """
        for attempt in range(max_retries):
            try:
                result = await stage_func()
                logger.info(f"{stage_name} completed successfully")
                return result

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited - exponential backoff
                    wait_time = 2 ** attempt * 60  # 1min, 2min, 4min
                    logger.warning(f"{stage_name} rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue

                elif e.response.status_code in [500, 502, 503, 504]:
                    # Server error - retry
                    wait_time = 2 ** attempt * 5  # 5s, 10s, 20s
                    logger.warning(f"{stage_name} server error {e.response.status_code}, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue

                else:
                    logger.error(f"{stage_name} HTTP error: {e}")
                    raise

            except asyncio.TimeoutError:
                logger.warning(f"{stage_name} timeout on attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt * 5)
                    continue
                else:
                    raise

            except Exception as e:
                logger.error(f"{stage_name} unexpected error: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt * 5)
                    continue
                else:
                    raise

        raise Exception(f"{stage_name} failed after {max_retries} attempts")
```

### Rate Limiter

```python
class RateLimiter:
    """Rate limiter for API calls using sliding window"""

    def __init__(self, max_requests: int, window: int):
        """
        Initialize rate limiter

        Args:
            max_requests: Max requests allowed in window
            window: Time window in seconds

        Examples:
        - RateLimiter(100, 3600) → 100 requests per hour
        - RateLimiter(20, 86400) → 20 requests per day
        """
        self.max_requests = max_requests
        self.window = window
        self.requests = []  # Timestamps of requests

    async def wait_if_needed(self):
        """
        Wait if rate limit would be exceeded

        Algorithm: Sliding window
        1. Remove requests outside current window
        2. Check if at limit
        3. If at limit, wait until oldest request expires
        4. Record this request timestamp
        """
        now = datetime.utcnow()

        # Remove old requests outside window
        self.requests = [
            req for req in self.requests
            if (now - req).total_seconds() < self.window
        ]

        # Check if at limit
        if len(self.requests) >= self.max_requests:
            oldest = self.requests[0]
            wait_time = self.window - (now - oldest).total_seconds()

            if wait_time > 0:
                logger.info(f"Rate limit: waiting {wait_time:.1f}s ({len(self.requests)}/{self.max_requests})")
                await asyncio.sleep(wait_time)

        # Record this request
        self.requests.append(now)
```

---

## Performance Targets & Benchmarks

### Stage Performance (1000 contacts)

| Stage | Operation | Time per Contact | Total Time | Bottleneck |
|-------|-----------|-----------------|------------|------------|
| 1. Discovery | Sales Nav search | 500ms | ~100s | API rate limit (100 req/hr) |
| 2. Enrichment | Hunter.io domain search | 500ms / 20 contacts | ~25s | API quota (25 domains/month free) |
| 3. Deduplication | Close CRM lookup | 50ms | ~50s | Email/LinkedIn exact match (fast), fuzzy match (slow) |
| 4. Lead Scoring | Algorithmic scoring | 5ms | ~5s | CPU-bound (fast) |
| 5. CRM Export | Close API create/update | 200ms | ~140s | API rate limit (600 req/min) |
| 6. Outreach | InMail/Connection automation | 1000ms (InMail), 2000ms (invite) | Variable | Daily limits (20 invites/day) |
| **TOTAL** | | | **~6 minutes** | |

### Optimization Opportunities

1. **Discovery Stage**:
   - Parallelize Sales Nav searches (100 concurrent requests)
   - Cache company → LinkedIn URL mappings
   - Reduce: ~100s → ~20s

2. **Enrichment Stage**:
   - Batch Hunter.io searches by domain (already implemented)
   - Upgrade Hunter.io plan (25 → 500 domains/month)
   - Current: Optimal

3. **Deduplication Stage**:
   - Index Close CRM custom fields (linkedin_url)
   - Cache fuzzy company name matches (Redis)
   - Reduce: ~50s → ~20s

4. **CRM Export Stage**:
   - Batch create/update operations (Close API supports bulk)
   - Parallelize requests (respect 600 req/min limit)
   - Reduce: ~140s → ~30s

**Optimized Total: ~2 minutes** (75% improvement)

---

## Implementation Roadmap

### Phase 1: Core Services (Week 1)

**Files to Create:**
```
backend/app/services/linkedin/
├── discovery_service.py          # LinkedInATLDiscoveryService
├── sales_navigator_client.py     # SalesNavigatorClient
├── deduplication_service.py      # DeduplicationService
└── lead_scoring_service.py       # LeadScoringService

backend/app/services/enrichment/
└── hunter_enrichment_service.py  # HunterEnrichmentService (extends existing)

backend/app/services/outreach/
├── smart_outreach_service.py     # SmartOutreachService
└── inmail_quota_tracker.py       # InMailQuotaTracker
```

**Dependencies:**
```bash
pip install fuzzywuzzy python-Levenshtein
pip install browserbase  # For connection automation
```

**Environment Variables:**
```bash
# Sales Navigator API
LINKEDIN_SALES_NAV_API_KEY=your_sales_nav_api_key_here

# Browserbase (for connection automation)
BROWSERBASE_API_KEY=your_browserbase_key_here
BROWSERBASE_PROJECT_ID=your_project_id_here
```

### Phase 2: Database Schema (Week 1)

**Migration: Add custom fields to Close CRM mapping**

```python
# backend/alembic/versions/xxx_add_linkedin_discovery_fields.py

def upgrade():
    # Add columns to crm_contacts table
    op.add_column('crm_contacts', sa.Column('linkedin_url', sa.String(500), nullable=True))
    op.add_column('crm_contacts', sa.Column('lead_score', sa.Integer, nullable=True))
    op.add_column('crm_contacts', sa.Column('lead_tier', sa.String(20), nullable=True))
    op.add_column('crm_contacts', sa.Column('discovery_source', sa.String(50), nullable=True))
    op.add_column('crm_contacts', sa.Column('inmail_eligible', sa.Boolean, default=False))

    # Create outreach_log table
    op.create_table(
        'outreach_log',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('contact_id', sa.Integer, sa.ForeignKey('crm_contacts.id')),
        sa.Column('action_type', sa.String(50)),  # inmail, email, connection_invite
        sa.Column('status', sa.String(50)),  # pending, sent, delivered, opened, replied, failed
        sa.Column('sent_at', sa.DateTime),
        sa.Column('message_template', sa.Text),
        sa.Column('created_at', sa.DateTime, default=datetime.utcnow)
    )

    # Create index for InMail quota tracking
    op.create_index('idx_outreach_log_action_sent', 'outreach_log', ['action_type', 'sent_at'])
```

### Phase 3: API Endpoints (Week 2)

```python
# backend/app/api/routes/linkedin_discovery.py

@router.post("/linkedin/discover/csv")
async def discover_from_csv(
    csv_file: UploadFile,
    limit_per_company: int = 5,
    db: Session = Depends(get_db)
):
    """
    Discover ATL contacts from CSV of target companies

    Request:
      - CSV file with company names
      - limit_per_company: Max contacts per company

    Response:
      - discovered_contacts: List of ATLContact
      - total_companies: Count
      - total_contacts: Count
    """
    pass

@router.post("/linkedin/discover/connections")
async def discover_from_connections(
    user_linkedin_id: str,
    db: Session = Depends(get_db)
):
    """Mine ATL contacts from user's existing LinkedIn connections"""
    pass

@router.post("/linkedin/enrich")
async def enrich_contacts(
    contact_ids: List[int],
    db: Session = Depends(get_db)
):
    """Enrich contacts with Hunter.io email discovery"""
    pass

@router.post("/linkedin/export-to-close")
async def export_to_close(
    contact_ids: List[int],
    db: Session = Depends(get_db)
):
    """Export contacts to Close CRM with deduplication"""
    pass

@router.post("/linkedin/outreach/plan")
async def plan_outreach(
    contact_ids: List[int],
    db: Session = Depends(get_db)
):
    """
    Plan outreach strategy (InMail vs Email vs Connection)

    Returns:
      - inmails: List of contacts for InMail
      - emails: List of contacts for email
      - connection_invites: List of contacts for connection
      - inmails_remaining: Current quota
    """
    pass

@router.get("/linkedin/inmail/quota")
async def get_inmail_quota(db: Session = Depends(get_db)):
    """Get current InMail quota status"""
    pass
```

### Phase 4: Testing (Week 2)

**Test Files:**
```
backend/tests/services/linkedin/
├── test_discovery_service.py
├── test_deduplication_service.py
├── test_lead_scoring_service.py
└── test_smart_outreach_service.py
```

**Test Scenarios:**
1. Discovery: Mock Sales Navigator API responses
2. Enrichment: Mock Hunter.io responses
3. Deduplication: Test fuzzy matching with known duplicates
4. Lead Scoring: Verify tier assignments (HOT/WARM/COLD)
5. Outreach Planning: Test InMail quota allocation

### Phase 5: Frontend Dashboard (Week 3)

**Components:**
```
frontend/src/components/linkedin/
├── DiscoveryDashboard.tsx        # Upload CSV, view discovered contacts
├── EnrichmentProgress.tsx        # Real-time enrichment progress
├── InMailQuotaWidget.tsx         # Quota status and recommendations
└── OutreachPlanReview.tsx        # Review outreach plan before execution
```

---

## Success Metrics

### Pipeline Efficiency
- **Discovery Rate**: 1000 contacts from 200 companies in <2 minutes
- **Email Match Rate**: >30% of contacts enriched with email
- **Deduplication Accuracy**: <5% false positives on fuzzy matching
- **Lead Scoring Precision**: >80% of HOT tier convert to opportunities

### InMail ROI
- **InMail Response Rate**: Target >20% (industry average: 10-25%)
- **InMail → Meeting Rate**: Target >10%
- **Cost Per Meeting**: Target <$50 (at $149/month Sales Nav)

### Automation Metrics
- **Daily Connection Invites**: 20 (at safe limit)
- **Weekly Pipeline Throughput**: 500+ new contacts
- **Close CRM Export Rate**: >95% success (with deduplication)

---

## Risk Mitigation

### LinkedIn Account Restrictions
**Risk**: Aggressive automation triggers LinkedIn account restrictions

**Mitigation**:
- Conservative rate limits (20 invites/day vs 100 LinkedIn max)
- Randomize delays between actions (2-5 seconds)
- Limit daily automation hours (9am-5pm local time)
- Monitor account health metrics

### API Quota Exhaustion
**Risk**: Running out of Hunter.io searches or Sales Navigator requests

**Mitigation**:
- Track usage in real-time dashboard
- Alert at 80% quota usage
- Implement waiting queue for when quota exhausted
- Upgrade plans proactively based on demand

### Deduplication False Negatives
**Risk**: Creating duplicate contacts in Close CRM despite fuzzy matching

**Mitigation**:
- Manual review queue for 80-90% similarity matches
- Admin approval required before creating >100 leads
- Weekly deduplication audit report

---

## Conclusion

This architecture provides a comprehensive, production-ready system for discovering and engaging with ATL contacts at scale. The 6-stage pipeline balances automation with control, ensuring high-quality leads while respecting API limits and maintaining LinkedIn account health.

**Key Differentiators**:
- Fuzzy deduplication prevents wasted effort on existing leads
- Lead scoring optimizes limited InMail quota allocation
- Smart outreach routing maximizes engagement channels
- Conservative rate limiting protects account longevity

**Next Steps**:
1. Obtain Sales Navigator subscription ($79.99-$149.99/month)
2. Set up Browserbase for connection automation
3. Implement Phase 1 core services
4. Test with sample batch (50 contacts)
5. Scale to full 1000+ contact pipeline
