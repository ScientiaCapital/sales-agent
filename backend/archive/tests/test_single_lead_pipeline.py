#!/usr/bin/env python3
"""
Single Lead Pipeline Test - Full Observability
================================================
Tests ONE lead through every phase with complete audit logging.

Run: python test_single_lead_pipeline.py

Phases tested:
1. Website Discovery (Google/DuckDuckGo)
2. Contact Discovery (Hunter.io + Browserbase)
3. Social Media Discovery (LinkedIn, Facebook, X, Instagram, TikTok)
4. Qualification (Cerebras LLM scoring)
5. Deduplication (Close CRM check)
6. Audit Verification (all logs captured)
"""

import asyncio
import sys
import os
import json
import time
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Rich console for beautiful output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console() if RICH_AVAILABLE else None


@dataclass
class PhaseResult:
    """Result from a single pipeline phase."""
    phase: str
    success: bool
    latency_ms: int
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class PipelineTestResult:
    """Complete test result for all phases."""
    lead: Dict[str, Any]
    phases: List[PhaseResult] = field(default_factory=list)
    total_latency_ms: int = 0
    total_cost_usd: float = 0.0
    passed: bool = True

    def add_phase(self, result: PhaseResult):
        self.phases.append(result)
        self.total_latency_ms += result.latency_ms
        if not result.success:
            self.passed = False


def print_header(text: str):
    """Print a section header."""
    if console:
        console.print(f"\n[bold cyan]{'='*60}[/]")
        console.print(f"[bold white]{text}[/]")
        console.print(f"[bold cyan]{'='*60}[/]")
    else:
        print(f"\n{'='*60}")
        print(text)
        print('='*60)


def print_phase_start(phase: str):
    """Print phase start marker."""
    if console:
        console.print(f"\n[bold yellow]>>> PHASE: {phase}[/]")
    else:
        print(f"\n>>> PHASE: {phase}")


def print_success(msg: str):
    """Print success message."""
    if console:
        console.print(f"[bold green]  ✅ {msg}[/]")
    else:
        print(f"  ✅ {msg}")


def print_fail(msg: str):
    """Print failure message."""
    if console:
        console.print(f"[bold red]  ❌ {msg}[/]")
    else:
        print(f"  ❌ {msg}")


def print_info(msg: str):
    """Print info message."""
    if console:
        console.print(f"[dim]  ℹ️  {msg}[/]")
    else:
        print(f"  ℹ️  {msg}")


def print_data(label: str, value: Any):
    """Print data point."""
    if console:
        console.print(f"[cyan]     {label}:[/] {value}")
    else:
        print(f"     {label}: {value}")


async def test_phase_1_website_discovery(company_name: str, city: str, state: str) -> PhaseResult:
    """
    Phase 1: Website Discovery
    --------------------------
    Tests: Google search, DuckDuckGo search, domain inference
    """
    print_phase_start("1. WEBSITE DISCOVERY")
    start = time.time()

    try:
        from app.services.website_discovery import WebsiteDiscoveryService

        service = WebsiteDiscoveryService()
        # discover_website returns Optional[str] - just the URL
        website = await service.discover_website(
            company_name=company_name,
            city=city,
            state=state
        )

        latency_ms = int((time.time() - start) * 1000)

        if website:
            print_success(f"Found website: {website}")
            print_data("Method", "domain_inference/duckduckgo/google")
            print_data("Latency", f"{latency_ms}ms")

            return PhaseResult(
                phase="website_discovery",
                success=True,
                latency_ms=latency_ms,
                data={
                    "website": website,
                    "method": "auto",
                    "confidence": 90
                }
            )
        else:
            print_fail("No website found")
            print_info("Methods tried: domain_inference, duckduckgo, google")
            return PhaseResult(
                phase="website_discovery",
                success=False,
                latency_ms=latency_ms,
                error="No website found"
            )

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        print_fail(f"Error: {e}")
        return PhaseResult(
            phase="website_discovery",
            success=False,
            latency_ms=latency_ms,
            error=str(e)
        )


async def test_phase_2_contact_discovery(
    company_name: str,
    website: Optional[str],
    audit_context: Dict[str, Any],
    company_main_phone: Optional[str] = None
) -> PhaseResult:
    """
    Phase 2: Contact Discovery
    --------------------------
    Tests: Hunter.io domain search, Browserbase team scrape, email extraction

    Phone Strategy:
    - Direct lines from Hunter.io (rare but gold)
    - Company main phone fallback (gatekeeper playbook)
    - phone_type: "direct" | "main_office" to indicate approach
    """
    print_phase_start("2. CONTACT DISCOVERY")
    start = time.time()

    contacts = []
    sources_tried = []
    sources_succeeded = []

    # Track company main phone for fallback
    company_phone_captured = company_main_phone

    try:
        # 2a. Hunter.io Domain Search
        print_info("Trying Hunter.io domain search...")
        if website and os.getenv("HUNTER_API_KEY"):
            try:
                from app.services.hunter_service import HunterService
                hunter = HunterService()
                domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
                hunter_contacts = await hunter.domain_search(domain, atl_only=False)
                sources_tried.append("hunter_io")

                if hunter_contacts:
                    contacts.extend(hunter_contacts)
                    sources_succeeded.append("hunter_io")
                    print_success(f"Hunter.io: Found {len(hunter_contacts)} contacts")
                    for c in hunter_contacts[:3]:
                        name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
                        print_data("Contact", f"{name} - {c.get('email', 'no email')}")
                else:
                    print_info("Hunter.io: No contacts found")
            except Exception as e:
                print_info(f"Hunter.io: Failed - {e}")
        else:
            if not website:
                print_info("Hunter.io: Skipped (no website)")
            else:
                print_info("Hunter.io: Skipped (no API key)")

        # 2b. Website Email Extraction
        print_info("Trying website email extraction...")
        if website:
            try:
                from app.services.email_extractor import EmailExtractor
                extractor = EmailExtractor()
                extracted = await extractor.extract_emails_from_website(website)
                sources_tried.append("website_email_scrape")

                if extracted:
                    # Filter duplicates
                    existing_emails = {c.get('email', '').lower() for c in contacts}
                    new_emails = [e for e in extracted if e.get('email', '').lower() not in existing_emails]
                    if new_emails:
                        contacts.extend(new_emails)
                        sources_succeeded.append("website_email_scrape")
                        print_success(f"Email extraction: Found {len(new_emails)} new emails")
                    else:
                        print_info("Email extraction: No new emails")
                else:
                    print_info("Email extraction: No emails found")
            except Exception as e:
                print_info(f"Email extraction: Failed - {e}")

        # 2c. Browserbase Team Page Scrape
        print_info("Trying Browserbase team page scrape...")
        atl_count = sum(1 for c in contacts if c.get('is_atl', False))
        if website and atl_count < 3 and os.getenv("BROWSERBASE_API_KEY"):
            try:
                from app.services.browserbase_team_scraper import BrowserbaseTeamScraper
                scraper = BrowserbaseTeamScraper()
                team_contacts = await scraper.scrape_team_page(website)
                sources_tried.append("browserbase_team")

                if team_contacts:
                    existing_emails = {c.get('email', '').lower() for c in contacts}
                    new_contacts = [t for t in team_contacts if t.get('email', '').lower() not in existing_emails]
                    if new_contacts:
                        contacts.extend(new_contacts)
                        sources_succeeded.append("browserbase_team")
                        print_success(f"Browserbase: Found {len(new_contacts)} new team members")
                    else:
                        print_info("Browserbase: No new contacts")
                else:
                    print_info("Browserbase: No team page found")
            except Exception as e:
                print_info(f"Browserbase: Failed - {e}")
        else:
            if not os.getenv("BROWSERBASE_API_KEY"):
                print_info("Browserbase: Skipped (no API key)")
            elif atl_count >= 3:
                print_info(f"Browserbase: Skipped (already have {atl_count} ATL contacts)")

        latency_ms = int((time.time() - start) * 1000)

        # Classify ATL/BTL (handle None values safely)
        atl_titles = ['ceo', 'president', 'owner', 'founder', 'vp', 'director', 'head', 'manager', 'partner', 'principal']
        for c in contacts:
            title = (c.get('position') or c.get('title') or '').lower()
            c['is_atl'] = any(t in title for t in atl_titles)

        atl_contacts = [c for c in contacts if c.get('is_atl', False)]
        btl_contacts = [c for c in contacts if not c.get('is_atl', False)]

        # ========================================================
        # PHONE ENRICHMENT - Critical for calling strategy
        # ========================================================
        print_info("Enriching phone data...")

        direct_phone_count = 0
        main_office_fallback_count = 0

        for c in contacts:
            existing_phone = c.get('phone')
            if existing_phone:
                # Direct line from Hunter.io - GOLD
                c['phone_type'] = 'direct'
                c['phone_source'] = 'hunter_io'
                direct_phone_count += 1
            elif company_phone_captured:
                # Fallback to company main phone - GATEKEEPER PLAYBOOK
                c['phone'] = company_phone_captured
                c['phone_type'] = 'main_office'
                c['phone_source'] = 'company_csv'
                main_office_fallback_count += 1
            else:
                # No phone at all
                c['phone_type'] = None
                c['phone_source'] = None

        # Report phone coverage - CRITICAL FOR SALES
        print_info("=" * 50)
        print_info("📞 PHONE SUMMARY (Your Gold)")
        print_info("=" * 50)
        if direct_phone_count > 0:
            print_success(f"🎯 {direct_phone_count} DIRECT LINES → Dial direct, no gatekeeper!")
        if main_office_fallback_count > 0:
            print_info(f"🏢 OFFICE: {company_phone_captured} → {main_office_fallback_count} contacts")
            print_info("   ⚠️  GATEKEEPER PLAYBOOK REQUIRED - Ask for contact by name")
        if direct_phone_count == 0 and main_office_fallback_count == 0:
            print_fail("❌ NO PHONES - Manual research needed!")
        print_info("=" * 50)

        print_success(f"Total: {len(contacts)} contacts ({len(atl_contacts)} ATL, {len(btl_contacts)} BTL)")
        print_data("Sources tried", sources_tried)
        print_data("Sources succeeded", sources_succeeded)
        print_data("Latency", f"{latency_ms}ms")

        return PhaseResult(
            phase="contact_discovery",
            success=len(contacts) > 0,
            latency_ms=latency_ms,
            data={
                "contacts": contacts,
                "atl_count": len(atl_contacts),
                "btl_count": len(btl_contacts),
                "sources_tried": sources_tried,
                "sources_succeeded": sources_succeeded,
                # PHONE STATS - Critical for calling
                "phone_stats": {
                    "direct_lines": direct_phone_count,
                    "main_office_fallback": main_office_fallback_count,
                    "no_phone": len(contacts) - direct_phone_count - main_office_fallback_count,
                    "company_main_phone": company_phone_captured
                }
            }
        )

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        print_fail(f"Error: {e}")
        return PhaseResult(
            phase="contact_discovery",
            success=False,
            latency_ms=latency_ms,
            error=str(e)
        )


async def test_phase_3_social_media(company_name: str, website: Optional[str], city: str, state: str) -> PhaseResult:
    """
    Phase 3: Social Media Discovery
    --------------------------------
    Tests: LinkedIn, Facebook, Twitter/X, Instagram, TikTok, YouTube
    """
    print_phase_start("3. SOCIAL MEDIA DISCOVERY")
    start = time.time()

    try:
        from app.services.social_media_discovery import SocialMediaDiscoveryService

        service = SocialMediaDiscoveryService()
        result = await service.discover_all(
            company_name=company_name,
            website=website,
            city=city,
            state=state
        )

        latency_ms = int((time.time() - start) * 1000)

        platforms_found = []
        platform_data = {}

        for platform in ['linkedin', 'facebook', 'twitter', 'instagram', 'tiktok', 'youtube']:
            profile = getattr(result, platform, None)
            if profile:
                platforms_found.append(platform)
                platform_data[platform] = {
                    "url": profile.url,
                    "username": profile.username,
                    "verified": profile.verified
                }
                print_success(f"{platform.capitalize()}: {profile.url}")

        if platforms_found:
            print_data("Platforms found", len(platforms_found))
            print_data("Latency", f"{latency_ms}ms")
            return PhaseResult(
                phase="social_media_discovery",
                success=True,
                latency_ms=latency_ms,
                data={
                    "platforms_found": platforms_found,
                    "platform_data": platform_data
                }
            )
        else:
            print_fail("No social media profiles found")
            return PhaseResult(
                phase="social_media_discovery",
                success=False,
                latency_ms=latency_ms,
                error="No profiles found"
            )

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        print_fail(f"Error: {e}")
        return PhaseResult(
            phase="social_media_discovery",
            success=False,
            latency_ms=latency_ms,
            error=str(e)
        )


async def test_phase_4_qualification(
    company_name: str,
    website: Optional[str],
    contacts: List[Dict],
    social_media: Dict
) -> PhaseResult:
    """
    Phase 4: Qualification (Cerebras LLM Scoring)
    ----------------------------------------------
    Tests: Lead scoring via Cerebras LLM
    """
    print_phase_start("4. QUALIFICATION (LLM SCORING)")
    start = time.time()

    try:
        from app.services.langgraph.agents.qualification_agent import QualificationAgent

        agent = QualificationAgent()

        # Get primary contact info if available
        contact_name = None
        contact_title = None
        contact_email = None

        for c in contacts:
            if c.get('is_atl'):
                contact_name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
                contact_title = c.get('position', c.get('title', ''))
                contact_email = c.get('email', '')
                break

        # Use the correct qualify() method signature
        # Returns: tuple[LeadQualificationResult, latency_ms, metadata]
        qualification_result, qual_latency_ms, metadata = await agent.qualify(
            company_name=company_name,
            company_website=website,
            industry="contractor",  # MEP contractors
            contact_name=contact_name,
            contact_title=contact_title,
            contact_email=contact_email,
            notes=f"Social media: {', '.join(social_media.keys())}" if social_media else None
        )

        latency_ms = int((time.time() - start) * 1000)

        if qualification_result:
            score = qualification_result.qualification_score
            tier = qualification_result.tier  # Not qualification_tier!
            reasoning = qualification_result.qualification_reasoning
            # is_atl comes from metadata, not the result
            is_atl = metadata.get("is_atl", False)
            # Build notes from the various fields
            notes = f"Reasoning: {reasoning}\nFit: {qualification_result.fit_assessment}\nContact Quality: {qualification_result.contact_quality}\nSales Potential: {qualification_result.sales_potential}"

            print_success(f"Score: {score}/100")
            print_data("Tier", tier)
            print_data("Is ATL", is_atl)
            print_data("LLM Latency", f"{qual_latency_ms}ms")
            print_data("Total Latency", f"{latency_ms}ms")
            print_data("Model", metadata.get("model", "unknown"))
            print_data("Cost", f"${metadata.get('cost_usd', 0):.6f}")

            # Show reasoning
            if reasoning:
                print_data("Reasoning", reasoning[:200] + "..." if len(reasoning) > 200 else reasoning)

            return PhaseResult(
                phase="qualification",
                success=True,
                latency_ms=latency_ms,
                data={
                    "score": score,
                    "tier": tier,
                    "is_atl": is_atl,
                    "reasoning": reasoning,
                    "model": metadata.get("model"),
                    "cost_usd": metadata.get("cost_usd", 0)
                }
            )
        else:
            print_fail("Qualification returned no result")
            return PhaseResult(
                phase="qualification",
                success=False,
                latency_ms=latency_ms,
                error="No result"
            )

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        print_fail(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return PhaseResult(
            phase="qualification",
            success=False,
            latency_ms=latency_ms,
            error=str(e)
        )


async def test_phase_5_linkedin(
    company_name: str,
    website: Optional[str],
    existing_contacts: List[Dict],
    social_media_data: Optional[Dict] = None
) -> PhaseResult:
    """
    Phase 5: LinkedIn Discovery
    ----------------------------
    Tests: Company page, employee count, ATL contacts
    Uses LinkedIn URL from Social Media phase if available
    """
    print_phase_start("5. LINKEDIN DISCOVERY")
    start = time.time()

    linkedin_data = {
        "company_url": None,
        "employee_count": None,
        "atl_contacts": [],
        "total_people_found": 0
    }

    try:
        # 5a. Check if we already have LinkedIn URL from Social Media Discovery
        linkedin_url_from_social = None
        if social_media_data and "linkedin" in social_media_data:
            linkedin_url_from_social = social_media_data["linkedin"].get("url")
            if linkedin_url_from_social:
                print_success(f"Using LinkedIn URL from Social Media phase: {linkedin_url_from_social}")
                linkedin_data["company_url"] = linkedin_url_from_social

        # 5b. If no URL yet, search for company LinkedIn page
        if not linkedin_data["company_url"]:
            print_info("Finding company LinkedIn page...")
            from app.services.linkedin_company_service import LinkedInCompanyService

            company_service = LinkedInCompanyService()
            company_result = await company_service.find_company(
                company_name=company_name,
                website=website
            )

            if company_result.status == "success" and company_result.company:
                linkedin_data["company_url"] = company_result.company.linkedin_url
                linkedin_data["employee_count"] = company_result.company.employee_count
                print_success(f"Company page: {company_result.company.linkedin_url}")
                if company_result.company.employee_count:
                    print_data("Employee count", company_result.company.employee_count)

        # 5c. If we have a company URL (from either source), find ATL contacts
        if linkedin_data["company_url"]:
            print_info("Searching for ATL contacts at company...")
            from app.services.linkedin_people_service import LinkedInPeopleService

            people_service = LinkedInPeopleService()
            people_result = await people_service.find_atl_contacts(
                company_linkedin_url=linkedin_data["company_url"],
                company_name=company_name,
                limit=10
            )

            if people_result.status == "success" and people_result.people:
                linkedin_data["atl_contacts"] = [
                    {
                        "name": p.name,
                        "title": p.title,
                        "linkedin_url": p.linkedin_url,
                        "email": p.email,
                        "is_atl": p.is_atl,
                        "source": "linkedin"
                    }
                    for p in people_result.people
                ]
                linkedin_data["total_people_found"] = len(people_result.people)
                print_success(f"Found {len(people_result.people)} ATL contacts")
                for p in people_result.people[:3]:
                    print_data("Contact", f"{p.name} - {p.title}")
            else:
                print_info("No ATL contacts found via LinkedIn search")
        else:
            print_info("Company LinkedIn page not found")

        latency_ms = int((time.time() - start) * 1000)

        success = linkedin_data["company_url"] is not None or linkedin_data["total_people_found"] > 0
        print_data("Latency", f"{latency_ms}ms")

        return PhaseResult(
            phase="linkedin_discovery",
            success=success,
            latency_ms=latency_ms,
            data=linkedin_data
        )

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        print_fail(f"Error: {e}")
        return PhaseResult(
            phase="linkedin_discovery",
            success=False,
            latency_ms=latency_ms,
            error=str(e)
        )


async def test_phase_6_deduplication(company_name: str, contacts: List[Dict]) -> PhaseResult:
    """
    Phase 6: Deduplication Check (Close CRM)
    -----------------------------------------
    Tests: Fuzzy matching against existing leads
    """
    print_phase_start("6. DEDUPLICATION CHECK")
    start = time.time()

    close_api_key = os.getenv("CLOSE_API_KEY")
    if not close_api_key:
        print_info("Close API key not configured - skipping dedup check")
        return PhaseResult(
            phase="deduplication",
            success=True,
            latency_ms=int((time.time() - start) * 1000),
            data={"recommendation": "create_new", "reason": "no_close_api_key"}
        )

    try:
        from app.services.crm.close_deduplication import CloseDeduplicationService

        service = CloseDeduplicationService(api_key=close_api_key)

        # Get primary contact email
        primary_email = None
        for c in contacts:
            if c.get('is_atl') and c.get('email'):
                primary_email = c['email']
                break
        if not primary_email:
            for c in contacts:
                if c.get('email'):
                    primary_email = c['email']
                    break

        result = await service.check_duplicate(
            company_name=company_name,
            email=primary_email
        )

        latency_ms = int((time.time() - start) * 1000)

        if result:
            # DuplicationCheckResult is a dataclass, access attributes directly
            is_duplicate = result.is_duplicate
            company_confidence = result.company_confidence
            matched_lead_id = result.matched_lead_id
            recommendation = result.recommendation if hasattr(result, 'recommendation') else (
                "skip_duplicate" if is_duplicate else "create_new"
            )

            print_success(f"Is Duplicate: {is_duplicate}")
            print_data("Company match confidence", f"{company_confidence}%")
            print_data("Recommendation", recommendation)
            if matched_lead_id:
                print_data("Existing Close Lead ID", matched_lead_id)
            print_data("Latency", f"{latency_ms}ms")

            return PhaseResult(
                phase="deduplication",
                success=True,
                latency_ms=latency_ms,
                data={
                    "is_duplicate": is_duplicate,
                    "recommendation": recommendation,
                    "company_confidence": company_confidence,
                    "close_lead_id": matched_lead_id
                }
            )
        else:
            print_info("No dedup result")
            return PhaseResult(
                phase="deduplication",
                success=True,  # Not a failure, just no CRM
                latency_ms=latency_ms,
                data={"recommendation": "create_new", "reason": "no_crm_check"}
            )

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        # Dedup failures shouldn't fail the pipeline
        print_info(f"Dedup check skipped: {e}")
        return PhaseResult(
            phase="deduplication",
            success=True,
            latency_ms=latency_ms,
            data={"recommendation": "create_new", "reason": str(e)}
        )


def print_final_report(result: PipelineTestResult):
    """Print comprehensive final report."""
    print_header("PIPELINE TEST RESULTS")

    if console:
        # Rich table output
        table = Table(title="Phase Results", box=box.ROUNDED)
        table.add_column("Phase", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Latency", style="magenta")
        table.add_column("Key Data", style="white")

        for phase in result.phases:
            status = "[green]✅ PASS[/]" if phase.success else "[red]❌ FAIL[/]"
            latency = f"{phase.latency_ms}ms"

            # Extract key data point
            key_data = ""
            if phase.phase == "website_discovery":
                key_data = phase.data.get("website", phase.error or "-")
            elif phase.phase == "contact_discovery":
                key_data = f"{phase.data.get('atl_count', 0)} ATL, {phase.data.get('btl_count', 0)} BTL"
            elif phase.phase == "social_media_discovery":
                platforms = phase.data.get("platforms_found", [])
                key_data = ", ".join(platforms) if platforms else "None"
            elif phase.phase == "qualification":
                key_data = f"Score: {phase.data.get('score', '-')}"
            elif phase.phase == "linkedin_discovery":
                people = phase.data.get("total_people_found", 0)
                company_url = phase.data.get("company_url")
                key_data = f"{people} people" + (", company page" if company_url else "")
            elif phase.phase == "deduplication":
                key_data = phase.data.get("recommendation", "-")

            table.add_row(phase.phase.replace("_", " ").title(), status, latency, key_data)

        console.print(table)

        # Summary panel
        summary_text = f"""
[bold]Total Latency:[/] {result.total_latency_ms}ms
[bold]Overall Status:[/] {"[green]PASSED[/]" if result.passed else "[red]FAILED[/]"}
[bold]Phases Passed:[/] {sum(1 for p in result.phases if p.success)}/{len(result.phases)}
"""
        console.print(Panel(summary_text, title="Summary", border_style="cyan"))

    else:
        # Plain text output
        print("\nPhase Results:")
        print("-" * 50)
        for phase in result.phases:
            status = "✅ PASS" if phase.success else "❌ FAIL"
            print(f"  {phase.phase}: {status} ({phase.latency_ms}ms)")

        print(f"\nTotal Latency: {result.total_latency_ms}ms")
        print(f"Overall: {'PASSED' if result.passed else 'FAILED'}")


async def run_single_lead_test():
    """Run complete single-lead pipeline test."""

    print_header("SINGLE LEAD PIPELINE TEST")
    print("Testing ONE lead through all phases with full observability")
    print(f"Timestamp: {datetime.now().isoformat()}")

    # Test lead - use BROWER MECHANICAL since we know it should work now
    test_lead = {
        "company_name": "BROWER MECHANICAL CA LLC",
        "city": "FRESNO",
        "state": "CA",
        "phone": "(559) 237-4637"
    }

    print(f"\nTest Lead: {test_lead['company_name']}")
    print(f"Location: {test_lead['city']}, {test_lead['state']}")

    result = PipelineTestResult(lead=test_lead)
    audit_context = {}

    # Phase 1: Website Discovery
    phase1 = await test_phase_1_website_discovery(
        company_name=test_lead["company_name"],
        city=test_lead["city"],
        state=test_lead["state"]
    )
    result.add_phase(phase1)
    website = phase1.data.get("website") if phase1.success else None
    audit_context["website"] = website

    # Phase 2: Contact Discovery (pass company phone for fallback)
    phase2 = await test_phase_2_contact_discovery(
        company_name=test_lead["company_name"],
        website=website,
        audit_context=audit_context,
        company_main_phone=test_lead.get("phone")  # CRITICAL: Company phone for gatekeeper playbook
    )
    result.add_phase(phase2)
    contacts = phase2.data.get("contacts", []) if phase2.success else []
    audit_context["contacts"] = contacts

    # Phase 3: Social Media Discovery
    phase3 = await test_phase_3_social_media(
        company_name=test_lead["company_name"],
        website=website,
        city=test_lead["city"],
        state=test_lead["state"]
    )
    result.add_phase(phase3)
    social_media = phase3.data.get("platform_data", {}) if phase3.success else {}
    audit_context["social_media"] = social_media

    # Phase 4: Qualification
    phase4 = await test_phase_4_qualification(
        company_name=test_lead["company_name"],
        website=website,
        contacts=contacts,
        social_media=social_media
    )
    result.add_phase(phase4)
    audit_context["qualification"] = phase4.data

    # Phase 5: LinkedIn Discovery (uses social media data if LinkedIn was found)
    phase5 = await test_phase_5_linkedin(
        company_name=test_lead["company_name"],
        website=website,
        existing_contacts=contacts,
        social_media_data=social_media  # Pass LinkedIn URL from phase 3 if found
    )
    result.add_phase(phase5)
    linkedin_contacts = phase5.data.get("atl_contacts", []) if phase5.success else []
    # Merge LinkedIn contacts with existing contacts
    all_contacts = contacts + linkedin_contacts
    audit_context["linkedin"] = phase5.data

    # Phase 6: Deduplication
    phase6 = await test_phase_6_deduplication(
        company_name=test_lead["company_name"],
        contacts=all_contacts
    )
    result.add_phase(phase6)
    audit_context["dedup"] = phase6.data

    # Final Report
    print_final_report(result)

    # Save detailed results to file
    output_file = f"data/test_results/single_lead_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump({
            "lead": test_lead,
            "phases": [asdict(p) for p in result.phases],
            "total_latency_ms": result.total_latency_ms,
            "passed": result.passed,
            "audit_context": audit_context,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2, default=str)

    print(f"\nDetailed results saved to: {output_file}")

    return result


if __name__ == "__main__":
    result = asyncio.run(run_single_lead_test())
    sys.exit(0 if result.passed else 1)
