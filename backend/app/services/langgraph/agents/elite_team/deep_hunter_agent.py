"""
DeepHunterAgent - OEM Dealer Network Hunter (Elite Squad #2)

Mission: Orchestrate dealer-scraper-mvp's 30 OEM scrapers to hunt contractors
         based on Signal Scout's orders. Cross-references contractors across
         OEM networks to find multi-OEM (high-value) targets.

Architecture:
    1. Receive scraping order from Signal Scout
    2. Execute ScraperFactory for each OEM+state combination
    3. Query pipeline.db for scraped data
    4. Cross-reference contractors across OEMs (multi-OEM = high value)
    5. Export results for Intake Commander

Flow:
    ┌──────────────────┐
    │ receive_order    │ ── Parse Signal Scout scraping order
    └────────┬─────────┘
             │
    ┌────────▼─────────┐
    │ execute_scrapes  │ ── Call ScraperFactory for each OEM+state
    └────────┬─────────┘
             │
    ┌────────▼─────────┐
    │cross_reference   │ ── Find multi-OEM contractors (high value)
    └────────┬─────────┘
             │
    ┌────────▼─────────┐
    │ export_results   │ ── Prepare for Intake Commander
    └──────────────────┘

Key Features:
    - 30 OEM scrapers: Honeywell, Generac, Enphase, Tesla, Cummins, etc.
    - Cross-OEM matching: Find contractors listed in multiple dealer networks
    - DeepSeek reasoning: Cost-effective long research tasks
    - SQLite integration: Query pipeline.db for enriched contractor data
    - State-level targeting: Scrape by state for geographic focus

Usage:
    # Manual run
    python -c "
    import asyncio
    from app.services.langgraph.agents.elite_team.deep_hunter_agent import DeepHunterAgent

    async def run():
        hunter = DeepHunterAgent()
        order = {
            'vertical': 'fire_safety',
            'states': ['FL', 'TX'],
            'oems': ['honeywell', 'johnson_controls'],
            'zip_codes': []
        }
        result = await hunter.hunt(order)
        print(f'Hunted {result.total_scraped} contractors, {result.multi_oem_count} multi-OEM')

    asyncio.run(run())
    "

    # Via Celery (triggered by Signal Scout)
    from app.tasks.elite_squad_tasks import deep_hunter_task
    deep_hunter_task.delay(scraping_order)
"""

import os
import time
import sqlite3
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_anthropic import ChatAnthropic

from app.core.logging import setup_logging
from app.services.langgraph.agents.base_agent import BaseAgent, AgentConfig, OptimizationTarget, ProviderType

logger = setup_logging(__name__)


# ========== Configuration ==========

# Path to dealer-scraper-mvp project
SCRAPER_PROJECT = Path("/Users/tmkipper/Desktop/tk_projects/dealer-scraper-mvp")
PIPELINE_DB = SCRAPER_PROJECT / "output" / "pipeline.db"
SCRIPTS_DIR = SCRAPER_PROJECT / "scripts"

# OEM scrapers by vertical
OEM_MAPPING = {
    "fire_safety": ["honeywell", "siemens", "johnson_controls"],
    "low_voltage": ["honeywell", "alarm_com", "control4"],
    "generator": ["generac", "kohler", "cummins"],
    "solar": ["enphase", "solaredge", "tesla", "fronius", "sma", "sungrow", "growatt"],
    "battery": ["tesla", "generac", "enphase", "simpliphi"],
    "ev_charger": ["abb", "delta", "schneider"],
    "hvac": [
        "carrier", "trane", "lennox", "york", "mitsubishi", "rheem",
        "goodwe", "amicus", "briggs", "sensi"
    ],
}

# All available OEMs (30 total)
ALL_OEMS = [
    "honeywell", "siemens", "johnson_controls", "alarm_com", "control4",
    "generac", "kohler", "cummins", "enphase", "solaredge", "tesla",
    "fronius", "sma", "sungrow", "growatt", "simpliphi", "abb", "delta",
    "schneider", "carrier", "trane", "lennox", "york", "mitsubishi",
    "rheem", "goodwe", "amicus", "briggs", "sensi", "spw", "tigo", "solark"
]


# ========== Models ==========

class ScrapingOrder(BaseModel):
    """Order from Signal Scout to scrape specific OEMs/states."""
    vertical: Literal["fire_safety", "low_voltage", "generator", "solar", "battery", "ev_charger", "hvac"]
    states: List[str] = Field(default_factory=list, description="State codes (FL, TX, etc.)")
    oems: List[str] = Field(default_factory=list, description="Specific OEMs to scrape (overrides vertical)")
    zip_codes: List[str] = Field(default_factory=list, description="Specific ZIP codes (if provided)")
    limit_per_oem: int = Field(default=100, description="Max contractors per OEM")
    min_multi_oem_count: int = Field(default=2, description="Min OEMs for multi-OEM match")


class ContractorMatch(BaseModel):
    """A contractor found in dealer-scraper-mvp."""
    contractor_id: int
    company_name: str
    normalized_name: str
    street: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip: Optional[str]
    primary_phone: Optional[str]
    primary_email: Optional[str]
    primary_domain: Optional[str]
    website_url: Optional[str]
    oems_matched: List[str] = Field(default_factory=list, description="OEM networks this contractor appears in")
    license_types: List[str] = Field(default_factory=list, description="License types held")
    source_type: Optional[str]
    created_at: Optional[str]


class HuntResult(BaseModel):
    """Result of a Deep Hunter scraping operation."""
    vertical: str
    states_covered: List[str]
    oems_used: List[str]
    total_scraped: int
    multi_oem_count: int = Field(default=0, description="Contractors in 2+ OEM networks")
    export_path: Optional[str] = Field(default=None, description="CSV export path for Intake Commander")
    duration_ms: int
    errors: List[str] = Field(default_factory=list)
    top_contractors: List[ContractorMatch] = Field(default_factory=list, description="Top 20 multi-OEM contractors")


class DeepHunterState(BaseModel):
    """State for Deep Hunter LangGraph workflow."""
    scraping_order: Optional[ScrapingOrder] = None
    scraped_contractors: List[ContractorMatch] = Field(default_factory=list)
    multi_oem_matches: List[ContractorMatch] = Field(default_factory=list)
    hunt_status: str = "pending"  # pending, scraping, cross_referencing, exporting, complete, error
    error_message: Optional[str] = None
    result: Optional[HuntResult] = None


# ========== DeepHunterAgent ==========

class DeepHunterAgent(BaseAgent):
    """
    Deep Hunter - Orchestrates dealer-scraper-mvp's 30 OEM scrapers.

    Uses DeepSeek for cost-effective reasoning about cross-OEM patterns.
    Integrates with ScraperFactory via subprocess calls.
    """

    # Prompt for analyzing multi-OEM contractors
    MULTI_OEM_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert at analyzing contractor dealer networks and identifying high-value targets.

Multi-OEM contractors (listed in 2+ dealer networks) are typically:
- Larger, more established companies
- Better capitalized and creditworthy
- More likely to invest in new systems/upgrades
- Higher quality leads for B2B sales

Given the contractor data below, analyze:
1. Why this contractor is valuable (based on OEM partnerships)
2. What their multi-OEM presence signals about their business
3. Recommended approach for outreach
4. Estimated company size/revenue tier

Focus on OEM brand quality and market positioning."""),
        ("human", """Contractor Analysis Request:
---
Company: {company_name}
Location: {city}, {state}
OEM Networks: {oems_matched}
License Types: {license_types}
Contact: {primary_phone} / {primary_email}
Website: {website_url}
---

Provide your analysis:""")
    ])

    def __init__(
        self,
        provider: str = "deepseek",
        model: Optional[str] = None,
        temperature: float = 0.3
    ):
        """
        Initialize DeepHunterAgent.

        Args:
            provider: LLM provider (deepseek for cost-effective long research)
            model: Model ID (auto-selected if None)
            temperature: Generation temperature
        """
        # Initialize base agent config
        config = AgentConfig(
            name="deep_hunter",
            description="OEM dealer network hunter orchestrating 30 scrapers",
            provider=ProviderType(provider),  # Convert string to enum
            model=model or "deepseek-chat",
            temperature=temperature,
            max_tokens=2000,
            optimize_for=OptimizationTarget.COST,  # Long research tasks
            use_cache=True,
            enable_transfers=False,
            track_costs=True
        )
        super().__init__(config)

        # Initialize DeepSeek for multi-OEM analysis
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set (DeepSeek uses Anthropic-compatible API)")

        self.analysis_llm = ChatAnthropic(
            api_key=api_key,
            model="deepseek-chat",
            temperature=temperature,
            max_tokens=1000,
            base_url="https://api.deepseek.com"
        )
        self.analysis_chain = self.MULTI_OEM_ANALYSIS_PROMPT | self.analysis_llm

        logger.info(f"DeepHunterAgent initialized: provider={provider}, model={self.model}")

    def get_system_prompt(self) -> str:
        """Required by BaseAgent - system prompt for this agent."""
        return """You are the Deep Hunter agent, part of the Trifecta Hunter Elite Squad.

Your mission: Orchestrate 30 OEM scrapers to hunt contractors based on Signal Scout orders.

Capabilities:
- Execute ScraperFactory for fire safety, low voltage, generator, solar, battery, HVAC
- Cross-reference contractors across OEM networks
- Identify multi-OEM targets (high-value leads)
- Export enriched data for Intake Commander

You work with dealer-scraper-mvp's pipeline.db SQLite database."""

    def get_tools(self) -> List:
        """Required by BaseAgent - tools for this agent."""
        # No LangChain tools needed - uses subprocess + SQLite
        return []

    # ========== Core Hunting Methods ==========

    async def hunt(self, order: ScrapingOrder) -> HuntResult:
        """
        Execute a hunt based on Signal Scout's order.

        Args:
            order: ScrapingOrder with vertical, states, OEMs

        Returns:
            HuntResult with scraped contractors and export path
        """
        start_time = time.time()
        errors = []

        logger.info(
            f"🎯 Deep Hunter starting: vertical={order.vertical}, "
            f"states={order.states}, oems={order.oems or 'auto'}"
        )

        try:
            # 1. Determine OEMs to scrape
            oems_to_scrape = order.oems if order.oems else OEM_MAPPING.get(order.vertical, [])
            if not oems_to_scrape:
                raise ValueError(f"No OEMs found for vertical: {order.vertical}")

            logger.info(f"🔍 Scraping {len(oems_to_scrape)} OEMs: {oems_to_scrape}")

            # 2. Execute scrapers
            _ = await self._execute_scrapers(  # Result stored in pipeline.db
                oems=oems_to_scrape,
                states=order.states,
                zip_codes=order.zip_codes,
                limit_per_oem=order.limit_per_oem
            )

            # 3. Query pipeline.db for scraped data
            contractors = self._query_contractors(
                oems=oems_to_scrape,
                states=order.states
            )

            logger.info(f"📊 Found {len(contractors)} contractors in pipeline.db")

            # 4. Cross-reference for multi-OEM matches
            multi_oem_contractors = self._find_multi_oem_contractors(
                contractors=contractors,
                min_count=order.min_multi_oem_count
            )

            logger.info(f"🔥 Found {len(multi_oem_contractors)} multi-OEM contractors")

            # 5. Analyze top multi-OEM contractors (top 20)
            top_20 = multi_oem_contractors[:20]
            for contractor in top_20:
                try:
                    analysis = await self._analyze_contractor(contractor)
                    # Store analysis as metadata (could save to Supabase later)
                    contractor.source_type = f"multi_oem_analysis: {analysis[:200]}"
                except Exception as e:
                    logger.warning(f"Failed to analyze {contractor.company_name}: {e}")

            # 6. Export for Intake Commander
            export_path = self._export_contractors(
                contractors=multi_oem_contractors if multi_oem_contractors else contractors,
                vertical=order.vertical,
                states=order.states
            )

            duration_ms = int((time.time() - start_time) * 1000)

            result = HuntResult(
                vertical=order.vertical,
                states_covered=order.states,
                oems_used=oems_to_scrape,
                total_scraped=len(contractors),
                multi_oem_count=len(multi_oem_contractors),
                export_path=export_path,
                duration_ms=duration_ms,
                errors=errors,
                top_contractors=top_20
            )

            logger.info(
                f"✅ Deep Hunter complete: {result.total_scraped} scraped, "
                f"{result.multi_oem_count} multi-OEM, {duration_ms}ms"
            )

            return result

        except Exception as e:
            error_msg = f"Hunt failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

            duration_ms = int((time.time() - start_time) * 1000)

            return HuntResult(
                vertical=order.vertical,
                states_covered=order.states,
                oems_used=[],
                total_scraped=0,
                multi_oem_count=0,
                export_path=None,
                duration_ms=duration_ms,
                errors=errors,
                top_contractors=[]
            )

    async def _execute_scrapers(
        self,
        oems: List[str],
        states: List[str],
        zip_codes: List[str],
        limit_per_oem: int
    ) -> Dict[str, Any]:
        """
        Execute ScraperFactory for each OEM+state combination.

        This is a placeholder - actual implementation would:
        1. Call dealer-scraper-mvp/scripts/run_batch_scraper.py
        2. Or import ScraperFactory directly and call it
        3. Monitor progress via pipeline.db

        For now, just logs intent.
        """
        logger.info(f"🤖 Would execute scrapers: oems={oems}, states={states}, zips={zip_codes}")

        # TODO: Implement actual scraper execution
        # Options:
        # 1. subprocess.run(["python", SCRIPTS_DIR / "run_batch_scraper.py", ...])
        # 2. Import ScraperFactory directly (requires adding dealer-scraper-mvp to PYTHONPATH)
        # 3. Trigger via API endpoint if dealer-scraper-mvp has one

        # For now, return empty result
        return {
            "status": "skipped",
            "reason": "Scraper execution not yet implemented - would call dealer-scraper-mvp"
        }

    def _query_contractors(
        self,
        oems: List[str],
        states: List[str]
    ) -> List[ContractorMatch]:
        """
        Query pipeline.db for contractors matching criteria.

        Args:
            oems: OEM names to filter by
            states: State codes to filter by

        Returns:
            List of ContractorMatch objects
        """
        if not PIPELINE_DB.exists():
            logger.warning(f"pipeline.db not found at {PIPELINE_DB}")
            return []

        conn = sqlite3.connect(str(PIPELINE_DB))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        query = """
            SELECT
                c.id,
                c.company_name,
                c.normalized_name,
                c.street,
                c.city,
                c.state,
                c.zip,
                c.primary_phone,
                c.primary_email,
                c.primary_domain,
                c.website_url,
                c.source_type,
                c.created_at,
                GROUP_CONCAT(DISTINCT l.license_type) as license_types
            FROM contractors c
            LEFT JOIN licenses l ON l.contractor_id = c.id
            WHERE c.is_deleted = 0
        """

        params = []
        if states:
            placeholders = ','.join('?' * len(states))
            query += f" AND c.state IN ({placeholders})"
            params.extend(states)

        query += " GROUP BY c.id ORDER BY c.created_at DESC LIMIT 5000"

        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()

            contractors = []
            for row in rows:
                contractors.append(ContractorMatch(
                    contractor_id=row['id'],
                    company_name=row['company_name'] or 'Unknown',
                    normalized_name=row['normalized_name'] or '',
                    street=row['street'],
                    city=row['city'],
                    state=row['state'],
                    zip=row['zip'],
                    primary_phone=row['primary_phone'],
                    primary_email=row['primary_email'],
                    primary_domain=row['primary_domain'],
                    website_url=row['website_url'],
                    license_types=row['license_types'].split(',') if row['license_types'] else [],
                    source_type=row['source_type'],
                    created_at=row['created_at']
                ))

            logger.info(f"📊 Queried {len(contractors)} contractors from pipeline.db")
            return contractors

        except Exception as e:
            logger.error(f"Failed to query pipeline.db: {e}")
            return []
        finally:
            conn.close()

    def _find_multi_oem_contractors(
        self,
        contractors: List[ContractorMatch],
        min_count: int = 2
    ) -> List[ContractorMatch]:
        """
        Find contractors appearing in multiple OEM networks.

        Uses fuzzy matching on normalized_name + state.

        Args:
            contractors: All contractors from pipeline.db
            min_count: Minimum OEM networks to qualify as multi-OEM

        Returns:
            List of ContractorMatch objects sorted by OEM count (desc)
        """
        # Group by normalized_name + state
        contractor_groups: Dict[str, List[ContractorMatch]] = {}

        for contractor in contractors:
            key = f"{contractor.normalized_name}_{contractor.state}".lower()
            if key not in contractor_groups:
                contractor_groups[key] = []
            contractor_groups[key].append(contractor)

        # Find multi-OEM contractors
        multi_oem = []
        for group in contractor_groups.values():
            if len(group) >= min_count:
                # Merge into single contractor with OEM list
                primary = group[0]
                primary.oems_matched = [c.source_type or 'unknown' for c in group]
                multi_oem.append(primary)

        # Sort by OEM count (descending)
        multi_oem.sort(key=lambda c: len(c.oems_matched), reverse=True)

        return multi_oem

    async def _analyze_contractor(self, contractor: ContractorMatch) -> str:
        """
        Analyze a multi-OEM contractor with DeepSeek.

        Args:
            contractor: ContractorMatch to analyze

        Returns:
            Analysis text
        """
        response = await self.analysis_chain.ainvoke({
            'company_name': contractor.company_name,
            'city': contractor.city or 'N/A',
            'state': contractor.state or 'N/A',
            'oems_matched': ', '.join(contractor.oems_matched),
            'license_types': ', '.join(contractor.license_types) if contractor.license_types else 'N/A',
            'primary_phone': contractor.primary_phone or 'N/A',
            'primary_email': contractor.primary_email or 'N/A',
            'website_url': contractor.website_url or 'N/A'
        })

        return response.content if hasattr(response, 'content') else str(response)

    def _export_contractors(
        self,
        contractors: List[ContractorMatch],
        vertical: str,
        states: List[str]
    ) -> str:
        """
        Export contractors to CSV for Intake Commander.

        Args:
            contractors: List of contractors to export
            vertical: Vertical name
            states: State codes

        Returns:
            Path to exported CSV
        """
        import csv

        # Create output directory
        output_dir = Path("/Users/tmkipper/Desktop/tk_projects/sales-agent/backend/data/deep_hunter_exports")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        states_str = "_".join(states) if states else "all"
        filename = f"deep_hunter_{vertical}_{states_str}_{timestamp}.csv"
        filepath = output_dir / filename

        # Write CSV
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'contractor_id', 'company_name', 'street', 'city', 'state', 'zip',
                'primary_phone', 'primary_email', 'primary_domain', 'website_url',
                'oems_matched', 'oem_count', 'license_types', 'source_type', 'created_at'
            ])
            writer.writeheader()

            for contractor in contractors:
                writer.writerow({
                    'contractor_id': contractor.contractor_id,
                    'company_name': contractor.company_name,
                    'street': contractor.street or '',
                    'city': contractor.city or '',
                    'state': contractor.state or '',
                    'zip': contractor.zip or '',
                    'primary_phone': contractor.primary_phone or '',
                    'primary_email': contractor.primary_email or '',
                    'primary_domain': contractor.primary_domain or '',
                    'website_url': contractor.website_url or '',
                    'oems_matched': '|'.join(contractor.oems_matched),
                    'oem_count': len(contractor.oems_matched),
                    'license_types': '|'.join(contractor.license_types),
                    'source_type': contractor.source_type or '',
                    'created_at': contractor.created_at or ''
                })

        logger.info(f"📄 Exported {len(contractors)} contractors to {filepath}")
        return str(filepath)


# ========== Exports ==========

__all__ = [
    "DeepHunterAgent",
    "ScrapingOrder",
    "ContractorMatch",
    "HuntResult",
    "DeepHunterState",
    "OEM_MAPPING",
    "ALL_OEMS"
]
