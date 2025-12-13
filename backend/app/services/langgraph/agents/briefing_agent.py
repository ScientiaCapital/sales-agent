"""
BriefingAgent - Consolidated Morning Intelligence Briefing
==========================================================

Merges MorningBriefingAgent and MorningReportAgent functionality.

This agent generates a comprehensive daily briefing at 7:30 AM EST (12:30 UTC) that:
1. Gets top-N leads by prediction rank (call-worthiness)
2. Generates "why call now" reasoning for each lead
3. Creates outreach drafts (email, SMS, call opener)
4. Compiles a summary with actionable insights
5. Sends formatted Slack message to BDR channel

Schedule: Daily 7:30 AM EST (12:30 UTC) - Time-based only
Event Trigger: None

Pipeline:
    get_top_leads → generate_why_now → create_drafts → compile_summary → send_to_slack

Author: Claude + Tim (GTM Automation Team)
Date: Dec 7, 2025
"""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

from langchain_core.prompts import ChatPromptTemplate
from app.services.langchain_cerebras_compat import ChatCerebras
from langchain_anthropic import ChatAnthropic

from app.core.logging import setup_logging
from app.services.langgraph.tools.supabase_tools import get_supabase

logger = setup_logging(__name__)


# ========== Output Schemas ==========

class LeadBriefing(BaseModel):
    """Complete briefing for a single lead."""
    company_id: str
    company_name: str
    domain: Optional[str]
    phone: Optional[str]
    city: Optional[str]
    state: Optional[str]

    # Scoring
    icp_score: float
    icp_tier: Optional[str]
    prediction_rank: Optional[int]
    prediction_score: Optional[float]
    current_stage: Optional[str]

    # AI-generated insights
    why_call_now: str  # LLM-generated reasoning
    signals: List[str]  # Extracted from company data
    personal_hooks: Optional[str]  # From ai_personal_hooks

    # Outreach drafts
    email_draft: str
    sms_draft: str
    call_opener: str

    # Contact info
    best_contact_name: Optional[str]
    best_contact_title: Optional[str]
    best_contact_email: Optional[str]


class BriefingReport(BaseModel):
    """Complete morning briefing report."""
    generated_at: str
    report_date: str
    summary: str  # Executive summary paragraph

    # Statistics
    total_leads: int
    hot_leads: int
    warm_leads: int
    cold_leads: int

    # Top leads with full briefings
    top_leads: List[LeadBriefing]

    # Processing metadata
    processing_time_ms: int
    errors: List[str]


# ========== BriefingAgent ==========

class BriefingAgent:
    """
    Consolidated morning briefing agent.

    Generates comprehensive daily intelligence briefing with:
    - Top leads by prediction rank (call-worthiness)
    - "Why call now" reasoning for each lead
    - Personalized outreach drafts (email, SMS, call opener)
    - Executive summary with actionable insights
    - Slack notification to BDR channel
    """

    # Prompt for "why call now" reasoning
    WHY_CALL_NOW_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are Tim's AI sales strategist. Given a lead's details, generate a concise "why call NOW" reasoning (2-3 sentences max).

Focus on:
- TIMING: Why this moment matters (recent activity, season, market conditions)
- MOMENTUM: What signals indicate readiness to engage
- OPPORTUNITY: Why this lead is worth Tim's time RIGHT NOW

Be specific. Reference actual data. Make it actionable."""),
        ("human", """Company: {company_name}
Location: {city}, {state}
ICP Score: {icp_score}/100
ICP Tier: {icp_tier}
Prediction Rank: #{prediction_rank} (out of 1000)
Current Stage: {current_stage}

Recent Signals:
- OEM Brands: {oem_brands}
- Service Areas: {service_areas}
- Certifications: {certifications}
- Google Rating: {google_rating} ({google_review_count} reviews)
- Phone Available: {has_phone}
- Email Available: {has_email}
- Last Enriched: {last_enriched}

Company Story: {company_story}

Personal Hooks: {personal_hooks}

Generate "why call NOW" reasoning:""")
    ])

    # Prompt for outreach drafts
    OUTREACH_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are Tim's BDR assistant. Generate THREE personalized outreach drafts for this lead:

1. **Email** (150-200 words): Professional but warm. Reference specific signals. Clear value prop. Soft CTA.

2. **SMS** (under 160 chars): Casual, human. One specific hook. Simple question to start conversation.

3. **Call Opener** (2-3 sentences): Natural conversation starter. Reference something specific. Transition to discovery.

Be authentic. Use the company's actual data. Make Tim sound like he did his homework."""),
        ("human", """Company: {company_name}
Contact: {contact_name} ({contact_title})
Location: {city}, {state}
Phone: {phone}

WHY CALL NOW: {why_call_now}

SIGNALS:
- OEM Brands: {oem_brands}
- Service Areas: {service_areas}
- Certifications: {certifications}
- Maintenance Plans: {maintenance_plans}
- Google: {google_rating}★ ({google_review_count} reviews)

PERSONAL HOOKS: {personal_hooks}

Generate the three outreach drafts:""")
    ])

    # Prompt for executive summary
    SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are Tim's AI assistant summarizing today's top calling opportunities.

Write a concise morning briefing (3-4 paragraphs) that:
1. Highlights the #1 opportunity and why it's top priority
2. Notes interesting patterns across the top leads
3. Suggests calling strategy for the day (who to call first, what angles to use)
4. Ends with a motivational note

Be specific. Reference actual companies. Make it actionable and energizing."""),
        ("human", """TODAY'S TOP LEADS ({total_leads} total):
- HOT: {hot_count}
- WARM: {warm_count}
- COLD: {cold_count}

TOP 10 LEADS:
{top_leads_summary}

COMMON SIGNALS:
- OEM Brands: {brands_mentioned}
- Certifications: {certs_mentioned}
- Service Areas: {areas_mentioned}

Generate the morning briefing summary:""")
    ])

    def __init__(
        self,
        provider: str = "cerebras",
        model: Optional[str] = None
    ):
        """Initialize BriefingAgent."""
        self.provider = provider
        self.model = model or ("llama-3.3-70b" if provider == "cerebras" else "claude-3-haiku-20240307")

        if provider == "cerebras":
            api_key = os.getenv("CEREBRAS_API_KEY")
            if not api_key:
                raise ValueError("CEREBRAS_API_KEY not set in environment")
            self.llm = ChatCerebras(
                api_key=api_key,
                model=self.model,
                temperature=0.4,
                max_tokens=1000
            )
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set in environment")
            self.llm = ChatAnthropic(
                api_key=api_key,
                model=self.model,
                temperature=0.4,
                max_tokens=1000
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self.why_now_chain = self.WHY_CALL_NOW_PROMPT | self.llm
        self.outreach_chain = self.OUTREACH_PROMPT | self.llm
        self.summary_chain = self.SUMMARY_PROMPT | self.llm

        logger.info(f"BriefingAgent initialized: provider={provider}, model={self.model}")

    async def generate_briefing(
        self,
        top_n: int = 10
    ) -> BriefingReport:
        """
        Generate morning briefing for top-N leads.

        Pipeline:
        1. Get top-N leads by prediction_rank (ascending)
        2. For each lead, generate "why call now" reasoning
        3. For each lead, generate outreach drafts
        4. Compile executive summary
        5. Return complete briefing

        Args:
            top_n: Number of top leads to include (default: 10)

        Returns:
            BriefingReport with summary and lead briefings
        """
        start_time = datetime.utcnow()
        logger.info(f"Generating morning briefing: top_n={top_n}")

        supabase = get_supabase()
        errors = []

        # Query top-N leads by prediction rank
        # Filter: Must have ICP score, prediction rank, and ideally some AI data
        result = supabase.table('dim_companies').select(
            'company_id, company_name, domain, phone, city, state, '
            'icp_tier, icp_score, current_stage, '
            'prediction_rank, prediction_score, prediction_why_now, '
            'ai_company_story, ai_personal_hooks, ai_pain_points, '
            'oem_brands, service_areas, certifications, events_attended, '
            'google_rating, google_review_count, maintenance_plans, '
            'ai_enriched_at'
        ).not_.is_('prediction_rank', 'null').order(
            'prediction_rank', desc=False  # Lower rank = higher priority
        ).limit(top_n).execute()

        leads = result.data or []

        if not leads:
            logger.warning("No leads found with prediction ranks")
            return BriefingReport(
                generated_at=datetime.utcnow().isoformat(),
                report_date=datetime.utcnow().strftime("%Y-%m-%d"),
                summary="No ranked leads available for briefing. The PredictionAgent may not be running.",
                total_leads=0,
                hot_leads=0,
                warm_leads=0,
                cold_leads=0,
                top_leads=[],
                processing_time_ms=0,
                errors=["No leads with prediction_rank found"]
            )

        # Count by stage
        hot_count = sum(1 for l in leads if l.get('current_stage') == 'HOT')
        warm_count = sum(1 for l in leads if l.get('current_stage') == 'WARM')
        cold_count = sum(1 for l in leads if l.get('current_stage') == 'COLD')

        # Get contacts for top leads
        company_ids = [l['company_id'] for l in leads]
        contacts_result = supabase.table('dim_contacts').select(
            'contact_id, company_id, first_name, last_name, title, email, is_atl'
        ).in_('company_id', company_ids).execute()

        contacts_by_company = {}
        for contact in (contacts_result.data or []):
            cid = contact['company_id']
            if cid not in contacts_by_company:
                contacts_by_company[cid] = []
            contacts_by_company[cid].append(contact)

        # Generate briefings for each lead
        top_leads = []
        for lead in leads:
            try:
                briefing = await self._generate_lead_briefing(lead, contacts_by_company.get(lead['company_id'], []))
                top_leads.append(briefing)
            except Exception as e:
                error_msg = f"Error generating briefing for {lead.get('company_name')}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Generate executive summary
        try:
            summary = await self._generate_summary(leads, top_leads, hot_count, warm_count, cold_count)
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            summary = f"Morning briefing for {len(leads)} top leads. See details below."
            errors.append(f"Summary generation failed: {str(e)}")

        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        report = BriefingReport(
            generated_at=datetime.utcnow().isoformat(),
            report_date=datetime.utcnow().strftime("%Y-%m-%d"),
            summary=summary,
            total_leads=len(leads),
            hot_leads=hot_count,
            warm_leads=warm_count,
            cold_leads=cold_count,
            top_leads=top_leads,
            processing_time_ms=processing_time_ms,
            errors=errors
        )

        logger.info(
            f"Morning briefing generated: {len(leads)} leads, "
            f"{len(top_leads)} briefings created, {len(errors)} errors, "
            f"{processing_time_ms}ms"
        )

        return report

    async def _generate_lead_briefing(
        self,
        lead: Dict[str, Any],
        contacts: List[Dict[str, Any]]
    ) -> LeadBriefing:
        """Generate complete briefing for a single lead."""

        # Find best contact (ATL first, then any)
        best_contact = None
        for contact in contacts:
            if contact.get('is_atl'):
                best_contact = contact
                break
        if not best_contact and contacts:
            best_contact = contacts[0]

        contact_name = "Owner"
        contact_title = "Owner"
        contact_email = None
        if best_contact:
            fname = best_contact.get('first_name', '')
            lname = best_contact.get('last_name', '')
            contact_name = f"{fname} {lname}".strip() or "Owner"
            contact_title = best_contact.get('title', 'Owner')
            contact_email = best_contact.get('email')

        # Extract signals as list
        signals = []
        if lead.get('oem_brands'):
            signals.append(f"OEM Brands: {lead['oem_brands']}")
        if lead.get('certifications'):
            signals.append(f"Certifications: {lead['certifications']}")
        if lead.get('service_areas'):
            signals.append(f"Service Areas: {lead['service_areas']}")
        if lead.get('google_rating'):
            signals.append(f"Google: {lead['google_rating']}★ ({lead.get('google_review_count', 0)} reviews)")
        if lead.get('maintenance_plans'):
            signals.append(f"Maintenance Plans: {lead['maintenance_plans']}")
        if lead.get('events_attended'):
            signals.append(f"Trade Shows: {lead['events_attended']}")

        # Generate "why call now" reasoning (if not already in DB)
        why_call_now = lead.get('prediction_why_now', '')
        if not why_call_now:
            try:
                why_response = await self.why_now_chain.ainvoke({
                    "company_name": lead.get('company_name', 'Unknown'),
                    "city": lead.get('city', 'N/A'),
                    "state": lead.get('state', 'N/A'),
                    "icp_score": lead.get('icp_score', 0),
                    "icp_tier": lead.get('icp_tier', 'N/A'),
                    "prediction_rank": lead.get('prediction_rank', 999),
                    "current_stage": lead.get('current_stage', 'WARM'),
                    "oem_brands": lead.get('oem_brands', 'N/A'),
                    "service_areas": lead.get('service_areas', 'N/A'),
                    "certifications": lead.get('certifications', 'N/A'),
                    "google_rating": lead.get('google_rating', 'N/A'),
                    "google_review_count": lead.get('google_review_count', 0),
                    "has_phone": "Yes" if lead.get('phone') else "No",
                    "has_email": "Yes" if contact_email else "No",
                    "last_enriched": lead.get('ai_enriched_at', 'Never'),
                    "company_story": lead.get('ai_company_story', 'N/A')[:500],
                    "personal_hooks": lead.get('ai_personal_hooks', 'N/A')[:300]
                })
                why_call_now = why_response.content if hasattr(why_response, 'content') else str(why_response)
            except Exception as e:
                logger.error(f"Error generating 'why call now' for {lead.get('company_name')}: {e}")
                why_call_now = f"Ranked #{lead.get('prediction_rank', 999)} by prediction model. High ICP score: {lead.get('icp_score', 0)}/100."

        # Generate outreach drafts
        email_draft = ""
        sms_draft = ""
        call_opener = ""

        try:
            outreach_response = await self.outreach_chain.ainvoke({
                "company_name": lead.get('company_name', 'Unknown'),
                "contact_name": contact_name,
                "contact_title": contact_title,
                "city": lead.get('city', 'N/A'),
                "state": lead.get('state', 'N/A'),
                "phone": lead.get('phone', 'N/A'),
                "why_call_now": why_call_now,
                "oem_brands": lead.get('oem_brands', 'N/A'),
                "service_areas": lead.get('service_areas', 'N/A'),
                "certifications": lead.get('certifications', 'N/A'),
                "maintenance_plans": lead.get('maintenance_plans', 'N/A'),
                "google_rating": lead.get('google_rating', 'N/A'),
                "google_review_count": lead.get('google_review_count', 0),
                "personal_hooks": lead.get('ai_personal_hooks', 'N/A')[:300]
            })

            content = outreach_response.content if hasattr(outreach_response, 'content') else str(outreach_response)

            # Parse response (simple section extraction)
            sections = content.split("**")
            for i, section in enumerate(sections):
                lower = section.lower()
                if "email" in lower and i + 1 < len(sections):
                    email_draft = sections[i + 1].strip()
                elif "sms" in lower and i + 1 < len(sections):
                    sms_draft = sections[i + 1].strip()
                elif "call" in lower and i + 1 < len(sections):
                    call_opener = sections[i + 1].strip()

            # Fallback if parsing failed
            if not email_draft:
                email_draft = content[:500]
            if not sms_draft:
                sms_draft = f"Hi {contact_name.split()[0]}! Noticed {lead.get('company_name', 'your company')} services {lead.get('oem_brands', 'HVAC')}. Quick question - got 2 min?"
            if not call_opener:
                call_opener = f"Hi {contact_name}, this is Tim. I was looking at {lead.get('company_name')}'s website and noticed you service {lead.get('oem_brands', 'commercial equipment')}. How's business been?"

        except Exception as e:
            logger.error(f"Error generating outreach for {lead.get('company_name')}: {e}")
            # Use fallback templates
            email_draft = f"Hi {contact_name},\n\nI noticed {lead.get('company_name')} services {lead.get('oem_brands', 'HVAC equipment')} in {lead.get('city', 'your area')}. I work with similar companies to help them [value prop]. Would love to chat briefly. Are you free for a quick call this week?\n\nBest,\nTim"
            sms_draft = f"Hi {contact_name.split()[0]}! Quick question about {lead.get('company_name')} - got 2 min?"
            call_opener = f"Hi {contact_name}, this is Tim. How's business been this quarter?"

        return LeadBriefing(
            company_id=lead.get('company_id', ''),
            company_name=lead.get('company_name', 'Unknown'),
            domain=lead.get('domain'),
            phone=lead.get('phone'),
            city=lead.get('city'),
            state=lead.get('state'),
            icp_score=lead.get('icp_score', 0),
            icp_tier=lead.get('icp_tier'),
            prediction_rank=lead.get('prediction_rank'),
            prediction_score=lead.get('prediction_score'),
            current_stage=lead.get('current_stage'),
            why_call_now=why_call_now[:500],
            signals=signals,
            personal_hooks=lead.get('ai_personal_hooks'),
            email_draft=email_draft[:1000],
            sms_draft=sms_draft[:160],
            call_opener=call_opener[:300],
            best_contact_name=contact_name,
            best_contact_title=contact_title,
            best_contact_email=contact_email
        )

    async def _generate_summary(
        self,
        leads: List[Dict[str, Any]],
        briefings: List[LeadBriefing],
        hot_count: int,
        warm_count: int,
        cold_count: int
    ) -> str:
        """Generate executive summary paragraph."""

        # Build top leads summary
        top_leads_summary = "\n".join([
            f"#{b.prediction_rank}: {b.company_name} ({b.current_stage}, ICP {b.icp_score}/100)\n   WHY: {b.why_call_now[:150]}..."
            for b in briefings[:10]
        ])

        # Extract common signals
        all_brands = [l.get('oem_brands', '') for l in leads if l.get('oem_brands')]
        all_certs = [l.get('certifications', '') for l in leads if l.get('certifications')]
        all_areas = [l.get('service_areas', '') for l in leads if l.get('service_areas')]

        brands_mentioned = ', '.join(list(set(all_brands)))[:200] if all_brands else 'None'
        certs_mentioned = ', '.join(list(set(all_certs)))[:200] if all_certs else 'None'
        areas_mentioned = ', '.join(list(set(all_areas)))[:200] if all_areas else 'None'

        summary_response = await self.summary_chain.ainvoke({
            "total_leads": len(leads),
            "hot_count": hot_count,
            "warm_count": warm_count,
            "cold_count": cold_count,
            "top_leads_summary": top_leads_summary,
            "brands_mentioned": brands_mentioned,
            "certs_mentioned": certs_mentioned,
            "areas_mentioned": areas_mentioned
        })

        return summary_response.content if hasattr(summary_response, 'content') else str(summary_response)

    async def save_briefing_to_file(
        self,
        report: BriefingReport,
        output_dir: str = "data/briefings"
    ) -> str:
        """Save briefing to markdown file."""
        from pathlib import Path

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filename = f"morning_briefing_{report.report_date}.md"
        filepath = output_path / filename

        content = f"""# Morning Briefing - {report.report_date}

Generated: {report.generated_at}

## Executive Summary

{report.summary}

---

## Statistics

| Metric | Count |
|--------|-------|
| **Total Leads** | {report.total_leads} |
| **🔥 HOT** | {report.hot_leads} |
| **🌡️ WARM** | {report.warm_leads} |
| **❄️ COLD** | {report.cold_leads} |

---

## Top {len(report.top_leads)} Leads to Call Today

"""

        for i, lead in enumerate(report.top_leads, 1):
            content += f"""
### {i}. {lead.company_name} (Rank #{lead.prediction_rank})

**Stage:** {lead.current_stage} | **ICP:** {lead.icp_tier} ({lead.icp_score}/100) | **Score:** {lead.prediction_score}

**Location:** {lead.city}, {lead.state}
**Phone:** {lead.phone or 'N/A'}
**Domain:** {lead.domain or 'N/A'}

**Contact:** {lead.best_contact_name} ({lead.best_contact_title})
**Email:** {lead.best_contact_email or 'N/A'}

#### 🎯 Why Call NOW

{lead.why_call_now}

#### 📊 Signals

{chr(10).join(f'- {s}' for s in lead.signals) if lead.signals else '- No signals captured yet'}

---

#### 📧 Email Draft

```
{lead.email_draft}
```

---

#### 📱 SMS Draft

> {lead.sms_draft}

---

#### 📞 Call Opener

> {lead.call_opener}

---

"""

        if report.errors:
            content += f"""
## Errors

{chr(10).join(f'- {e}' for e in report.errors)}
"""

        content += f"""
---

**Processing Time:** {report.processing_time_ms}ms
"""

        filepath.write_text(content)
        logger.info(f"Morning briefing saved to: {filepath}")

        return str(filepath)


# ========== Exports ==========

__all__ = [
    "BriefingAgent",
    "BriefingReport",
    "LeadBriefing"
]
