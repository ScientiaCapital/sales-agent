"""
MorningReportAgent - Daily Scout Summary with Outreach Drafts

Generates a morning report at 9 AM EST summarizing overnight scout results.
Includes signals discovered, draft emails, SMS, and call scripts.

Output:
- Total leads scouted
- HOT/WARM/COLD breakdown
- Top 10 leads with full details
- For each lead: email draft, SMS draft, call opener

Usage:
    # Manual run
    python -c "
    import asyncio
    from app.services.langgraph.agents.morning_report_agent import MorningReportAgent

    async def run():
        agent = MorningReportAgent()
        report = await agent.generate_report()
        print(report['summary'])

    asyncio.run(run())
    "

    # Scheduled via Celery Beat at 9 AM EST (14:00 UTC)
"""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

from langchain_core.prompts import ChatPromptTemplate
from langchain_cerebras import ChatCerebras
from langchain_anthropic import ChatAnthropic

from app.core.logging import setup_logging
from app.services.langgraph.tools.supabase_tools import get_supabase

logger = setup_logging(__name__)


# ========== Output Schemas ==========

class LeadOutreach(BaseModel):
    """Outreach drafts for a single lead."""
    company_name: str
    domain: Optional[str]
    icp_score: float
    priority: str
    why_call: str
    signals: List[str]
    best_contact: Optional[str]
    email_draft: str
    sms_draft: str
    call_opener: str


class MorningReport(BaseModel):
    """Complete morning report."""
    generated_at: str
    report_date: str
    summary: str
    total_scouted: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    top_leads: List[LeadOutreach]
    signals_summary: Dict[str, int]


# ========== MorningReportAgent ==========

class MorningReportAgent:
    """
    Generates daily morning report with scout results and outreach drafts.
    """

    # Prompt for generating outreach drafts
    OUTREACH_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert BDR (Business Development Representative) for Tim, who sells to HVAC/MEP service companies.

Given the company research below, generate THREE outreach drafts:

1. **Email** (150-200 words): Professional but personalized. Reference specific signals. Clear value prop. Soft CTA.

2. **SMS** (under 160 characters): Casual, human. One specific hook. Simple question to start conversation.

3. **Call Opener** (2-3 sentences): Natural conversation starter. Reference something specific about their business. Transition to discovery question.

Be specific. Use the signals provided. Make it feel like Tim actually researched them."""),
        ("human", """Company: {company_name}
Domain: {domain}
Location: {city}, {state}
Phone: {phone}

ICP Score: {icp_score}/100
Priority: {priority}

WHY CALL: {why_call}

SIGNALS DISCOVERED:
- OEM Brands: {oem_brands}
- Service Areas: {service_areas}
- Certifications: {certifications}
- Events Attended: {events_attended}
- Google Rating: {google_rating} ({google_review_count} reviews)
- Maintenance Plans: {maintenance_plans}

BEST CONTACT: {best_contact}

Generate the three outreach drafts:""")
    ])

    SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are Tim's AI assistant summarizing the overnight lead scouting results.

Write a concise morning briefing (3-4 paragraphs) that:
1. Highlights the top opportunities found
2. Notes interesting patterns in the signals
3. Suggests which leads to call first and why
4. Ends with a motivational note for the day

Be specific about companies and signals. Make it actionable."""),
        ("human", """OVERNIGHT SCOUT RESULTS:
- Total Scouted: {total_scouted}
- HOT Leads: {hot_count}
- WARM Leads: {warm_count}
- COLD Leads: {cold_count}

TOP LEADS:
{top_leads_summary}

SIGNALS FOUND:
- OEM Brands: {brand_count} companies with brand signals
- Certifications: {cert_count} companies with certs
- Events: {event_count} companies attending trade shows
- Reviews: {review_count} companies with Google reviews

Generate the morning briefing:""")
    ])

    def __init__(
        self,
        provider: str = "cerebras",
        model: Optional[str] = None
    ):
        """Initialize MorningReportAgent."""
        self.provider = provider
        self.model = model or ("llama3.1-8b" if provider == "cerebras" else "claude-3-haiku-20240307")

        if provider == "cerebras":
            api_key = os.getenv("CEREBRAS_API_KEY")
            self.llm = ChatCerebras(
                api_key=api_key,
                model=self.model,
                temperature=0.4,
                max_tokens=1000
            )
        else:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            self.llm = ChatAnthropic(
                api_key=api_key,
                model=self.model,
                temperature=0.4,
                max_tokens=1000
            )

        self.outreach_chain = self.OUTREACH_PROMPT | self.llm
        self.summary_chain = self.SUMMARY_PROMPT | self.llm

        logger.info(f"MorningReportAgent initialized: provider={provider}, model={self.model}")

    async def generate_report(
        self,
        hours_back: int = 24,
        top_n: int = 10
    ) -> MorningReport:
        """
        Generate morning report for leads scouted in the last N hours.

        Args:
            hours_back: Hours to look back for scouted leads (default: 24)
            top_n: Number of top leads to include with full details (default: 10)

        Returns:
            MorningReport with summary and outreach drafts
        """
        logger.info(f"Generating morning report: hours_back={hours_back}, top_n={top_n}")

        supabase = get_supabase()

        # Calculate time threshold
        threshold = (datetime.utcnow() - timedelta(hours=hours_back)).isoformat()

        # Query leads scouted in last N hours
        result = supabase.table('dim_companies').select(
            'company_id, company_name, domain, '
            'icp_tier, icp_score, current_stage, '
            'ai_company_story, ai_personal_hooks, ai_pain_points, '
            'oem_brands, service_areas, certifications, events_attended, '
            'google_rating, google_review_count, maintenance_plans, '
            'phone, state, city, ai_enriched_at'
        ).not_.is_('ai_company_story', 'null').gte(
            'ai_enriched_at', threshold
        ).order('icp_score', desc=True).limit(50).execute()

        leads = result.data or []

        if not leads:
            logger.info("No leads scouted in the last 24 hours")
            return MorningReport(
                generated_at=datetime.utcnow().isoformat(),
                report_date=datetime.utcnow().strftime("%Y-%m-%d"),
                summary="No new leads were scouted overnight. The Lead Scout agent may not be running.",
                total_scouted=0,
                hot_leads=0,
                warm_leads=0,
                cold_leads=0,
                top_leads=[],
                signals_summary={}
            )

        # Count by priority
        hot_count = sum(1 for l in leads if l.get('current_stage') == 'HOT')
        warm_count = sum(1 for l in leads if l.get('current_stage') == 'WARM')
        cold_count = sum(1 for l in leads if l.get('current_stage') == 'COLD')

        # Count signals
        brand_count = sum(1 for l in leads if l.get('oem_brands'))
        cert_count = sum(1 for l in leads if l.get('certifications'))
        event_count = sum(1 for l in leads if l.get('events_attended'))
        review_count = sum(1 for l in leads if l.get('google_rating'))

        signals_summary = {
            "oem_brands": brand_count,
            "certifications": cert_count,
            "events": event_count,
            "reviews": review_count
        }

        # Generate outreach for top N leads
        top_leads = []
        for lead in leads[:top_n]:
            try:
                outreach = await self._generate_outreach(lead)
                top_leads.append(outreach)
            except Exception as e:
                logger.error(f"Error generating outreach for {lead.get('company_name')}: {e}")

        # Generate summary
        top_leads_summary = "\n".join([
            f"- {l.company_name} ({l.priority}): {l.why_call[:100]}..."
            for l in top_leads
        ])

        summary_response = await self.summary_chain.ainvoke({
            "total_scouted": len(leads),
            "hot_count": hot_count,
            "warm_count": warm_count,
            "cold_count": cold_count,
            "top_leads_summary": top_leads_summary,
            "brand_count": brand_count,
            "cert_count": cert_count,
            "event_count": event_count,
            "review_count": review_count
        })

        summary = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)

        report = MorningReport(
            generated_at=datetime.utcnow().isoformat(),
            report_date=datetime.utcnow().strftime("%Y-%m-%d"),
            summary=summary,
            total_scouted=len(leads),
            hot_leads=hot_count,
            warm_leads=warm_count,
            cold_leads=cold_count,
            top_leads=top_leads,
            signals_summary=signals_summary
        )

        logger.info(f"Morning report generated: {len(leads)} leads, {len(top_leads)} with outreach")

        return report

    async def _generate_outreach(self, lead: Dict[str, Any]) -> LeadOutreach:
        """Generate outreach drafts for a single lead."""

        # Extract signals as list
        signals = []
        if lead.get('oem_brands'):
            signals.append(f"OEM Brands: {lead['oem_brands']}")
        if lead.get('certifications'):
            signals.append(f"Certifications: {lead['certifications']}")
        if lead.get('events_attended'):
            signals.append(f"Events: {lead['events_attended']}")
        if lead.get('google_rating'):
            signals.append(f"Google: {lead['google_rating']}★ ({lead.get('google_review_count', 0)} reviews)")
        if lead.get('service_areas'):
            signals.append(f"Service Areas: {lead['service_areas']}")
        if lead.get('maintenance_plans'):
            signals.append(f"Maintenance Plans: {lead['maintenance_plans']}")

        # Generate outreach
        response = await self.outreach_chain.ainvoke({
            "company_name": lead.get('company_name', 'Unknown'),
            "domain": lead.get('domain', 'N/A'),
            "city": lead.get('city', 'N/A'),
            "state": lead.get('state', 'N/A'),
            "phone": lead.get('phone', 'N/A'),
            "icp_score": lead.get('icp_score', 0),
            "priority": lead.get('current_stage', 'WARM'),
            "why_call": lead.get('ai_company_story', 'N/A'),
            "oem_brands": lead.get('oem_brands', 'N/A'),
            "service_areas": lead.get('service_areas', 'N/A'),
            "certifications": lead.get('certifications', 'N/A'),
            "events_attended": lead.get('events_attended', 'N/A'),
            "google_rating": lead.get('google_rating', 'N/A'),
            "google_review_count": lead.get('google_review_count', 0),
            "maintenance_plans": lead.get('maintenance_plans', 'N/A'),
            "best_contact": lead.get('ai_personal_hooks', 'N/A')
        })

        content = response.content if hasattr(response, 'content') else str(response)

        # Parse the response (simple extraction)
        email_draft = ""
        sms_draft = ""
        call_opener = ""

        sections = content.split("**")
        for i, section in enumerate(sections):
            lower = section.lower()
            if "email" in lower and i + 1 < len(sections):
                email_draft = sections[i + 1].strip()
            elif "sms" in lower and i + 1 < len(sections):
                sms_draft = sections[i + 1].strip()
            elif "call" in lower and i + 1 < len(sections):
                call_opener = sections[i + 1].strip()

        # Fallback: if parsing failed, use full content
        if not email_draft:
            email_draft = content[:500]

        return LeadOutreach(
            company_name=lead.get('company_name', 'Unknown'),
            domain=lead.get('domain'),
            icp_score=lead.get('icp_score', 0),
            priority=lead.get('current_stage', 'WARM'),
            why_call=lead.get('ai_company_story', '')[:300],
            signals=signals,
            best_contact=lead.get('ai_personal_hooks'),
            email_draft=email_draft[:1000],
            sms_draft=sms_draft[:160] or "Hey! Noticed you're a [Brand] dealer in [City]. Quick question about your service business - got 2 min?",
            call_opener=call_opener[:300] or f"Hi, this is Tim. I was looking at your website and noticed you service {lead.get('oem_brands', 'commercial equipment')}. How's business been this quarter?"
        )

    async def save_report_to_file(
        self,
        report: MorningReport,
        output_dir: str = "data/reports"
    ) -> str:
        """Save report to markdown file."""
        from pathlib import Path

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filename = f"morning_report_{report.report_date}.md"
        filepath = output_path / filename

        content = f"""# Morning Scout Report - {report.report_date}

Generated: {report.generated_at}

## Summary

{report.summary}

## Statistics

| Metric | Count |
|--------|-------|
| **Total Scouted** | {report.total_scouted} |
| **🔥 HOT** | {report.hot_leads} |
| **🌡️ WARM** | {report.warm_leads} |
| **❄️ COLD** | {report.cold_leads} |

### Signals Found

| Signal Type | Companies |
|-------------|-----------|
| OEM Brands | {report.signals_summary.get('oem_brands', 0)} |
| Certifications | {report.signals_summary.get('certifications', 0)} |
| Trade Events | {report.signals_summary.get('events', 0)} |
| Google Reviews | {report.signals_summary.get('reviews', 0)} |

---

## Top Leads with Outreach Drafts

"""

        for i, lead in enumerate(report.top_leads, 1):
            content += f"""
### {i}. {lead.company_name} ({lead.priority})

**Domain:** {lead.domain}
**ICP Score:** {lead.icp_score}/100

**Why Call:**
{lead.why_call}

**Signals:**
{chr(10).join(f'- {s}' for s in lead.signals)}

---

#### 📧 Email Draft

{lead.email_draft}

---

#### 📱 SMS Draft

> {lead.sms_draft}

---

#### 📞 Call Opener

> {lead.call_opener}

---

"""

        filepath.write_text(content)
        logger.info(f"Morning report saved to: {filepath}")

        return str(filepath)


# ========== Exports ==========

__all__ = [
    "MorningReportAgent",
    "MorningReport",
    "LeadOutreach"
]
