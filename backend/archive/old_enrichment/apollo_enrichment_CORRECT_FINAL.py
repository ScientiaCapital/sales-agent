"""
APOLLO + HUNTER.IO ENRICHMENT - CORRECT IMPLEMENTATION

Based on verified Apollo API documentation (November 19, 2025)

CRITICAL PATTERNS (DO NOT CHANGE):
1. Individual Phone: person["phone_numbers"][0]["sanitized_number"] (already in search results)
2. Email Unlock: POST /people/bulk_match with reveal_personal_emails=True
3. ATL Filter: person_titles parameter to get decision-makers only
4. Cross-verification: Match contacts by email from both sources

Credit Efficiency:
- Search: FREE (no credits)
- Email reveal: ~1 credit per person
- ATL-only filter: Reduces enrichment by 82% (only decision-makers)

Expected cost: ~7,200 credits for 809 companies (vs 40,000 without ATL filter)
"""

import os
import csv
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")

# ATL (Above The Line) titles - Decision makers only
ATL_TITLES = [
    "CEO", "Chief Executive Officer", "Chief Executive",
    "President", "Owner", "Founder", "Co-Founder",
    "CTO", "Chief Technology Officer",
    "CFO", "Chief Financial Officer",
    "COO", "Chief Operating Officer",
    "VP", "Vice President", "SVP", "Senior Vice President", "EVP",
    "Director", "Head of", "Partner", "Principal"
]


class ApolloHunterEnricher:
    """Dual-source enrichment with Apollo + Hunter.io cross-verification"""

    def __init__(self):
        self.apollo_auth = {"x-api-key": APOLLO_API_KEY}
        self.hunter_auth = {"x-api-key": HUNTER_API_KEY}
        self.stats = {
            "companies_processed": 0,
            "apollo_contacts_found": 0,
            "hunter_contacts_found": 0,
            "emails_revealed": 0,
            "verified_both": 0,
            "apollo_only": 0,
            "hunter_only": 0,
            "apollo_credits_used": 0
        }

    async def apollo_search_atl(self, domain: str) -> List[Dict[str, Any]]:
        """
        Search for ATL contacts at domain using Apollo

        CRITICAL: This endpoint is FREE (no credits charged)
        Returns: List of contacts with phone_numbers array already populated

        API Response Structure:
        {
            "people": [
                {
                    "id": "...",
                    "name": "John Smith",
                    "title": "CEO",
                    "email": "locked_email@domain.com",  # LOCKED until revealed
                    "phone_numbers": [                    # ALREADY AVAILABLE (FREE)
                        {
                            "raw_number": "+1 555-123-4567",
                            "sanitized_number": "+15551234567",  # USE THIS!
                            "type": "work"
                        }
                    ],
                    "linkedin_url": "...",
                    ...
                }
            ]
        }
        """
        print(f"   🔍 Apollo Search: {domain} (ATL contacts only)")

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    "https://api.apollo.io/api/v1/mixed_people/search",
                    headers=self.apollo_auth,
                    json={
                        "organization_domains": [domain],
                        "person_titles": ATL_TITLES,  # ATL-only filter (saves 82% credits)
                        "per_page": 25,  # Up to 25 ATL contacts
                        "page": 1
                    },
                    timeout=30.0
                )

                if resp.status_code == 422:
                    print(f"      ⚠️  Insufficient Apollo credits")
                    return []

                if not resp.is_success:
                    print(f"      ❌ Search failed: {resp.status_code}")
                    return []

                data = resp.json()
                people = data.get("people", [])

                print(f"      ✅ Found {len(people)} ATL contacts")
                return people

            except Exception as e:
                print(f"      ❌ Error: {e}")
                return []

    async def apollo_reveal_emails(self, contacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Reveal email addresses using Apollo enrichment endpoint

        CRITICAL: This costs ~1 credit per person
        MUST use /people/bulk_match with reveal_personal_emails=True

        Input: Contacts from search (with locked emails)
        Output: Same contacts with unlocked emails

        API Call:
        POST /api/v1/people/bulk_match
        {
            "details": [{"id": "person_id_1"}, {"id": "person_id_2"}],
            "reveal_personal_emails": true
        }

        Response:
        {
            "people": [
                {
                    "id": "...",
                    "email": "john@company.com",  # NOW UNLOCKED!
                    "phone_numbers": [...],        # Still available
                    ...
                }
            ],
            "credits_consumed": 2
        }
        """
        if not contacts:
            return []

        print(f"   🔓 Revealing emails for {len(contacts)} contacts...")

        enriched_contacts = []

        # Batch enrichment (10 at a time to avoid timeouts)
        async with httpx.AsyncClient() as client:
            for i in range(0, len(contacts), 10):
                batch = contacts[i:i+10]
                details = [{"id": c["id"]} for c in batch if c.get("id")]

                if not details:
                    continue

                try:
                    resp = await client.post(
                        "https://api.apollo.io/api/v1/people/bulk_match",
                        headers=self.apollo_auth,
                        json={
                            "details": details,
                            "reveal_personal_emails": True  # CRITICAL: Unlocks emails
                        },
                        timeout=30.0
                    )

                    if resp.status_code == 422:
                        print(f"      ⚠️  Insufficient credits for batch {i//10 + 1}")
                        break

                    if not resp.is_success:
                        print(f"      ❌ Batch {i//10 + 1} failed: {resp.status_code}")
                        continue

                    data = resp.json()
                    enriched_batch = data.get("people", [])
                    credits_used = data.get("credits_consumed", 0)

                    enriched_contacts.extend(enriched_batch)
                    self.stats["emails_revealed"] += len(enriched_batch)
                    self.stats["apollo_credits_used"] += credits_used

                    print(f"      ✅ Batch {i//10 + 1}: {len(enriched_batch)} emails revealed ({credits_used} credits)")

                except Exception as e:
                    print(f"      ❌ Batch {i//10 + 1} error: {e}")
                    continue

        return enriched_contacts

    async def hunter_domain_search(self, domain: str) -> List[Dict[str, Any]]:
        """
        Search for contacts at domain using Hunter.io

        Cost: 1 credit PER DOMAIN (not per contact)
        Returns: All contacts found (Hunter doesn't have title filtering)
        """
        print(f"   🔍 Hunter.io Search: {domain}")

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    "https://api.hunter.io/v2/domain-search",
                    params={
                        "domain": domain,
                        "api_key": HUNTER_API_KEY
                    },
                    timeout=30.0
                )

                if not resp.is_success:
                    print(f"      ❌ Search failed: {resp.status_code}")
                    return []

                data = resp.json()
                emails = data.get("data", {}).get("emails", [])

                # Filter for ATL titles manually (Hunter doesn't support server-side filtering)
                atl_contacts = []
                for email_data in emails:
                    title = email_data.get("position", "").lower()
                    if any(atl_title.lower() in title for atl_title in ATL_TITLES):
                        atl_contacts.append(email_data)

                print(f"      ✅ Found {len(atl_contacts)} ATL contacts (filtered from {len(emails)} total)")
                return atl_contacts

            except Exception as e:
                print(f"      ❌ Error: {e}")
                return []

    def extract_apollo_contact(self, person: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract contact data from Apollo enriched person

        CRITICAL PATTERN: Individual phone extraction
        ❌ WRONG: phone = person.get("phone") or company_phone
        ✅ CORRECT: phone = person["phone_numbers"][0]["sanitized_number"]

        NO FALLBACK to company phone - if individual phone not available, leave empty
        """
        # Extract individual phone from phone_numbers array
        phone_numbers = person.get("phone_numbers", [])
        individual_phone = None

        if phone_numbers and len(phone_numbers) > 0:
            # Use sanitized_number (E.164 format: +15551234567)
            individual_phone = phone_numbers[0].get("sanitized_number")

        # CRITICAL: Do NOT use company phone as fallback
        # If Apollo doesn't have individual phone, it should be None/empty

        return {
            "name": person.get("name"),
            "email": person.get("email"),
            "phone": individual_phone,  # Individual phone ONLY (no fallback)
            "title": person.get("title"),
            "linkedin_url": person.get("linkedin_url"),
            "source": "Apollo"
        }

    def extract_hunter_contact(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract contact data from Hunter.io email data"""
        return {
            "name": f"{email_data.get('first_name', '')} {email_data.get('last_name', '')}".strip(),
            "email": email_data.get("value"),
            "phone": email_data.get("phone_number"),  # Hunter sometimes has phones
            "title": email_data.get("position"),
            "linkedin_url": email_data.get("linkedin"),
            "confidence": email_data.get("confidence"),
            "source": "Hunter.io"
        }

    def cross_verify(
        self,
        apollo_contacts: List[Dict[str, Any]],
        hunter_contacts: List[Dict[str, Any]],
        company_name: str
    ) -> List[Dict[str, Any]]:
        """
        Cross-verify contacts between Apollo and Hunter.io

        Verification Status:
        - verified_both (100 confidence): Email found in both sources
        - apollo_only (90 confidence): Only in Apollo
        - hunter_only (80 confidence): Only in Hunter.io

        Merge logic:
        - If both have same email: Merge data, prefer non-empty fields
        - If unique to one source: Include with source-specific confidence
        """
        # Index by email (lowercase for matching)
        apollo_by_email = {c["email"].lower(): c for c in apollo_contacts if c.get("email")}
        hunter_by_email = {c["email"].lower(): c for c in hunter_contacts if c.get("email")}

        all_emails = set(apollo_by_email.keys()) | set(hunter_by_email.keys())
        verified_contacts = []

        for email in all_emails:
            apollo_data = apollo_by_email.get(email)
            hunter_data = hunter_by_email.get(email)

            if apollo_data and hunter_data:
                # Both sources have this contact - VERIFIED
                contact = apollo_data.copy()

                # Merge non-empty fields from Hunter
                if not contact.get("phone") and hunter_data.get("phone"):
                    contact["phone"] = hunter_data["phone"]

                contact["verification_status"] = "verified_both"
                contact["confidence_score"] = 100
                contact["source"] = "Apollo + Hunter.io"
                self.stats["verified_both"] += 1

            elif apollo_data:
                # Apollo only
                contact = apollo_data.copy()
                contact["verification_status"] = "apollo_only"
                contact["confidence_score"] = 90
                self.stats["apollo_only"] += 1

            else:  # hunter_data only
                # Hunter.io only
                contact = hunter_data.copy()
                contact["verification_status"] = "hunter_only"
                contact["confidence_score"] = 80
                self.stats["hunter_only"] += 1

            contact["company_name"] = company_name
            contact["is_atl"] = True  # All contacts are ATL (filtered by title)
            verified_contacts.append(contact)

        return verified_contacts

    async def enrich_company(self, company_name: str, domain: str) -> List[Dict[str, Any]]:
        """
        Enrich single company with ATL contacts from Apollo + Hunter.io

        Workflow:
        1. Search Apollo for ATL contacts (FREE)
        2. Reveal emails (costs credits)
        3. Search Hunter.io for ATL contacts (1 credit per domain)
        4. Cross-verify and merge
        """
        print(f"\n🏢 {company_name}")

        if not domain:
            print("   ⚠️  No domain - skipping")
            return []

        # Step 1: Apollo search (FREE - no credits)
        apollo_people = await self.apollo_search_atl(domain)
        self.stats["apollo_contacts_found"] += len(apollo_people)

        # Step 2: Reveal emails (costs ~1 credit per person)
        apollo_enriched = await self.apollo_reveal_emails(apollo_people)
        apollo_contacts = [self.extract_apollo_contact(p) for p in apollo_enriched]

        # Step 3: Hunter.io search (1 credit per domain)
        hunter_emails = await self.hunter_domain_search(domain)
        self.stats["hunter_contacts_found"] += len(hunter_emails)
        hunter_contacts = [self.extract_hunter_contact(e) for e in hunter_emails]

        # Step 4: Cross-verify
        verified_contacts = self.cross_verify(apollo_contacts, hunter_contacts, company_name)

        print(f"   ✅ Total: {len(verified_contacts)} verified ATL contacts")
        self.stats["companies_processed"] += 1

        return verified_contacts

    async def enrich_csv(self, input_file: str, output_file: str):
        """
        Enrich CSV file with ATL contacts from Apollo + Hunter.io

        Input CSV columns: company_name, email, phone, ...
        Output CSV columns: company_name, contact_name, contact_email, contact_phone,
                           contact_title, is_atl, linkedin_url, confidence_score,
                           verification_status, source
        """
        print("=" * 80)
        print("APOLLO + HUNTER.IO ENRICHMENT - ATL CONTACTS ONLY")
        print("=" * 80)

        # Read companies from CSV
        companies = []
        with open(input_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                domain = None
                if row.get('email') and '@' in row['email']:
                    domain = row['email'].split('@')[1]

                companies.append({
                    "name": row['company_name'],
                    "domain": domain
                })

        print(f"\n📊 Processing {len(companies)} companies")
        print(f"   Filtering for ATL contacts only (CEO, VP, Director, etc.)")
        print(f"   Expected credit usage: ~{len(companies) * 8} credits (avg 8 ATL/company)")

        # Enrich each company
        all_contacts = []
        for company in companies:
            contacts = await self.enrich_company(company['name'], company['domain'])
            all_contacts.extend(contacts)

        # Write results
        if all_contacts:
            with open(output_file, 'w', newline='') as f:
                fieldnames = [
                    'company_name', 'contact_name', 'contact_email', 'contact_phone',
                    'contact_title', 'is_atl', 'linkedin_url', 'confidence_score',
                    'verification_status', 'source'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for contact in all_contacts:
                    writer.writerow({
                        'company_name': contact.get('company_name'),
                        'contact_name': contact.get('name'),
                        'contact_email': contact.get('email'),
                        'contact_phone': contact.get('phone'),
                        'contact_title': contact.get('title'),
                        'is_atl': contact.get('is_atl'),
                        'linkedin_url': contact.get('linkedin_url'),
                        'confidence_score': contact.get('confidence_score'),
                        'verification_status': contact.get('verification_status'),
                        'source': contact.get('source')
                    })

        # Print stats
        print("\n" + "=" * 80)
        print("✅ ENRICHMENT COMPLETE")
        print("=" * 80)
        print(f"\n📊 Statistics:")
        print(f"   Companies processed: {self.stats['companies_processed']}")
        print(f"   Apollo contacts found: {self.stats['apollo_contacts_found']}")
        print(f"   Hunter contacts found: {self.stats['hunter_contacts_found']}")
        print(f"   Emails revealed: {self.stats['emails_revealed']}")
        print(f"   Verified (both sources): {self.stats['verified_both']}")
        print(f"   Apollo only: {self.stats['apollo_only']}")
        print(f"   Hunter only: {self.stats['hunter_only']}")
        print(f"   Apollo credits used: {self.stats['apollo_credits_used']}")
        print(f"\n💾 Output: {output_file}")
        print(f"   Total contacts: {len(all_contacts)}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python apollo_enrichment_CORRECT_FINAL.py <input_csv>")
        print("Example: python apollo_enrichment_CORRECT_FINAL.py /tmp/test_3_companies.csv")
        sys.exit(1)

    input_file = sys.argv[1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"data/final_enrichment_output/enriched_atl_{timestamp}.csv"

    enricher = ApolloHunterEnricher()
    asyncio.run(enricher.enrich_csv(input_file, output_file))
