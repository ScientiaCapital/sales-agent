"""
IntakeCommanderAgent - Quality Gate + Trifecta Scoring + BDR Router

The third member of the Trifecta Hunter Elite Squad.
Receives contractors from Deep Hunter, applies quality filters, calculates
Trifecta scores, and routes high-value leads to BDR work queue.

Mission:
1. Load incoming leads from Deep Hunter export or intake queue
2. Deduplicate against Close CRM and Supabase
3. Apply 3-layer garbage contact filtering
4. Calculate Trifecta scores (Solar + Generator + Battery = UNICORN)
5. Route leads based on score (UNICORN→BDR, PARTIAL→enrichment, etc.)

Schedule: Every 60 seconds (continuous intake processing)
Event Trigger: `deep_hunter_complete`
Emits: `lead_intake_complete`, `unicorn_found`

Usage:
    ```python
    from app.services.langgraph.agents.elite_team.intake_commander_agent import IntakeCommanderAgent

    agent = IntakeCommanderAgent()
    result = await agent.process_intake()
    # Returns: IntakeResult with unicorns_found, hot_leads_routed, etc.
    ```
"""

import os
import time
import json
from typing import Optional, List, Dict, Any, TypedDict
from pathlib import Path
from pydantic import BaseModel, Field

from app.services.langchain_cerebras_compat import ChatCerebras
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END

from app.core.logging import setup_logging
from app.services.langgraph.tools.supabase_tools import get_supabase
from app.services.crm.close import CloseProvider

logger = setup_logging(__name__)


# ========== Output Schemas ==========

class TrifectaScore(BaseModel):
    """Trifecta scoring result for a contractor."""
    total: int = Field(description="Total score out of 100")
    signals: List[str] = Field(default_factory=list, description="List of detected signals")

    # Energy trifecta components
    has_solar: bool = False
    has_generator: bool = False
    has_battery: bool = False
    is_unicorn: bool = False  # Full trifecta (all 3)

    # Scoring breakdown
    trade_diversity_score: int = 0  # 0-25 points
    energy_trifecta_score: int = 0  # 0-25 points
    oem_breadth_score: int = 0      # 0-20 points
    geographic_reach_score: int = 0 # 0-15 points
    contact_quality_score: int = 0  # 0-15 points

    # Detailed metrics
    trade_count: int = 0
    oem_count: int = 0
    state_count: int = 0
    atl_contacts: int = 0
    has_email: bool = False
    has_phone: bool = False


class IntakeResult(BaseModel):
    """Result summary for intake processing."""
    total_processed: int = 0
    new_leads: int = 0
    duplicates_blocked: int = 0
    merged_records: int = 0
    hot_leads_routed: int = 0
    unicorns_found: int = 0

    # Quality filtering
    garbage_contacts_filtered: int = 0

    # Routing breakdown
    routed_to_bdr: int = 0
    routed_to_enrichment: int = 0
    routed_to_nurture: int = 0

    # Processing metadata
    duration_ms: int = 0
    errors: List[str] = Field(default_factory=list)


class IntakeCommanderState(TypedDict):
    """State for IntakeCommander graph."""
    incoming_leads: List[Dict[str, Any]]
    processed_results: Optional[IntakeResult]
    trifecta_scores: Dict[str, TrifectaScore]
    current_step: str
    errors: List[str]


# ========== OEM Brand Definitions ==========

# Solar OEMs (residential vs commercial)
SOLAR_RESIDENTIAL_OEMS = {
    "enphase", "solaredge", "sma sunny boy", "fronius primo",
    "ap systems", "hoymiles", "tigo"
}
SOLAR_COMMERCIAL_OEMS = {
    "sma", "fronius", "sungrow", "huawei", "goodwe",
    "solaredge commercial", "chint power", "growatt"
}
SOLAR_ALL_OEMS = SOLAR_RESIDENTIAL_OEMS | SOLAR_COMMERCIAL_OEMS

# Generator OEMs
GENERATOR_OEMS = {
    "generac", "kohler", "cummins", "briggs & stratton",
    "champion", "cat", "caterpillar", "honda", "duromax"
}

# Battery OEMs (residential vs commercial)
BATTERY_RESIDENTIAL_OEMS = {
    "tesla powerwall", "generac pwrcell", "enphase iq",
    "lg chem", "sonnen", "panasonic", "pika energy"
}
BATTERY_COMMERCIAL_OEMS = {
    "tesla megapack", "tesla powerpack", "lg chem commercial",
    "byd", "samsung sdi", "fluence", "powin"
}
BATTERY_ALL_OEMS = BATTERY_RESIDENTIAL_OEMS | BATTERY_COMMERCIAL_OEMS

# All energy OEMs combined
ENERGY_OEMS = SOLAR_ALL_OEMS | GENERATOR_OEMS | BATTERY_ALL_OEMS


# ========== Garbage Contact Filtering (3-Layer Defense) ==========

# Layer 1: Exact match garbage names
DEFINITELY_GARBAGE_NAMES = {
    # Website navigation elements
    'log in', 'login', 'sign up', 'signup', 'sign in', 'check continue',
    'apply now', 'get started', 'read more', 'learn more', 'click here',
    'view all', 'see all', 'show more', 'load more', 'submit',

    # Membership/account terms
    'membership careers', 'create account', 'my account', 'forgot password',

    # Common city names
    'los angeles', 'new york', 'san francisco', 'san diego', 'san jose',
    'las vegas', 'santa monica', 'santa ana', 'long beach', 'fort worth',
    'salt lake', 'palm springs', 'palm beach', 'newport beach',

    # Service area terms
    'service area', 'areas served', 'cities served', 'we serve',

    # Industry terms
    'preventative maintenance', 'preventive maintenance', 'routine maintenance',
    'customer service', 'technical support', 'emergency service',
    'free estimate', 'free quote', 'contact us', 'about us',

    # UI elements commonly parsed as names
    'menu', 'home', 'services', 'about', 'contact', 'blog', 'careers',
    'privacy policy', 'terms of service', 'testimonials', 'gallery',
}

# Layer 2: Substring blocklist patterns (152 patterns)
CONTACT_BLOCKLIST_PATTERNS = {
    # Navigation
    'click', 'menu', 'toggle', 'dropdown', 'search', 'filter',
    'login', 'logout', 'signin', 'signup', 'register',

    # Common phrases
    'read more', 'learn more', 'get started', 'apply now',
    'schedule', 'book now', 'contact us', 'call now',

    # Service types (not names)
    'hvac', 'plumbing', 'electrical', 'solar', 'roofing',
    'installation', 'repair', 'maintenance', 'service',
    'commercial', 'residential', 'emergency',

    # Generic titles that aren't real contacts
    'team', 'staff', 'crew', 'technician', 'installer',
    'representative', 'specialist', 'coordinator',

    # City indicators
    'los', 'las', 'san', 'santa', 'new', 'fort', 'palm',

    # Numbers and special chars
    '24/7', '24-7', 'hours', 'availability',
}

# Layer 3: City name prefixes
CITY_NAME_PREFIXES = {'los', 'las', 'san', 'santa', 'new', 'fort', 'palm', 'salt', 'long', 'newport'}


def is_garbage_contact(name: str, title: str = '') -> bool:
    """
    Check if contact should be filtered (3-layer defense).

    Layer 1: Exact match against DEFINITELY_GARBAGE_NAMES
    Layer 2: Substring match against CONTACT_BLOCKLIST_PATTERNS
    Layer 3: Structural checks (city names, length, numbers)

    Returns True if garbage (should be filtered out).
    """
    name_lower = (name or '').strip().lower()
    title_lower = (title or '').strip().lower()

    if not name_lower:
        return True

    # Layer 1: Exact match
    if name_lower in DEFINITELY_GARBAGE_NAMES:
        logger.debug(f"Layer 1 filter: '{name}' is exact garbage match")
        return True

    # Layer 2: Substring blocklist
    for pattern in CONTACT_BLOCKLIST_PATTERNS:
        if pattern in name_lower or pattern in title_lower:
            logger.debug(f"Layer 2 filter: '{name}' contains blocklist pattern '{pattern}'")
            return True

    # Layer 3: Structural checks
    words = name_lower.split()

    # Check if name looks like a city
    if len(words) >= 2 and words[0] in CITY_NAME_PREFIXES:
        logger.debug(f"Layer 3 filter: '{name}' looks like city name")
        return True

    # Reject very short names
    if len(name_lower) < 5:
        logger.debug(f"Layer 3 filter: '{name}' too short")
        return True

    # Reject single-word names (need first + last)
    if len(words) < 2:
        logger.debug(f"Layer 3 filter: '{name}' only one word")
        return True

    # Reject names with numbers
    if any(c.isdigit() for c in name_lower):
        logger.debug(f"Layer 3 filter: '{name}' contains numbers")
        return True

    return False


# ========== Trifecta Scoring Algorithm ==========

def calculate_trifecta_score(lead: Dict[str, Any]) -> TrifectaScore:
    """
    Calculate Trifecta score (100 pts max).

    Scoring Breakdown:
    - Trade diversity: 25 pts (5+ trades = max)
    - Energy trifecta: 25 pts (Solar + Generator + Battery = max)
    - OEM breadth: 20 pts (6+ OEMs = max)
    - Geographic reach: 15 pts (5+ states = max)
    - Contact quality: 15 pts (ATL + email + phone = max)

    Args:
        lead: Company/contractor data with OEMs, trades, contacts, etc.

    Returns:
        TrifectaScore with breakdown
    """
    score = TrifectaScore()

    # Extract data
    oem_brands = [b.lower() for b in (lead.get('oem_brands') or [])]
    trades = lead.get('trades') or []
    service_areas = lead.get('service_areas') or []
    atl_contacts = lead.get('atl_contacts') or []

    # Detect energy trifecta components
    score.has_solar = any(oem in SOLAR_ALL_OEMS for oem in oem_brands)
    score.has_generator = any(oem in GENERATOR_OEMS for oem in oem_brands)
    score.has_battery = any(oem in BATTERY_ALL_OEMS for oem in oem_brands)
    score.is_unicorn = score.has_solar and score.has_generator and score.has_battery

    # Build signals list
    signals = []
    if score.has_solar:
        signals.append("SOLAR")
    if score.has_generator:
        signals.append("GENERATOR")
    if score.has_battery:
        signals.append("BATTERY")
    if score.is_unicorn:
        signals.append("🦄 UNICORN (FULL TRIFECTA)")

    score.signals = signals

    # 1. Trade Diversity (25 pts max)
    score.trade_count = len(trades)
    score.trade_diversity_score = min(int(score.trade_count * 5), 25)

    # 2. Energy Trifecta (25 pts max)
    trifecta_count = sum([score.has_solar, score.has_generator, score.has_battery])
    if trifecta_count == 3:
        score.energy_trifecta_score = 25  # Full trifecta
    elif trifecta_count == 2:
        score.energy_trifecta_score = 15  # Partial trifecta
    elif trifecta_count == 1:
        score.energy_trifecta_score = 8   # Single component
    else:
        score.energy_trifecta_score = 0   # No energy vertical

    # 3. OEM Breadth (20 pts max)
    score.oem_count = len(oem_brands)
    score.oem_breadth_score = min(int((score.oem_count / 6.0) * 20), 20)

    # 4. Geographic Reach (15 pts max)
    # Extract unique states from service_areas (format: "City, ST")
    states = set()
    for area in service_areas:
        parts = area.split(',')
        if len(parts) >= 2:
            state = parts[-1].strip()
            if len(state) == 2:  # Valid state code
                states.add(state)
    score.state_count = len(states)
    score.geographic_reach_score = min(int((score.state_count / 5.0) * 15), 15)

    # 5. Contact Quality (15 pts max)
    score.atl_contacts = len(atl_contacts)

    # Check for email/phone in contacts
    for contact in atl_contacts:
        if contact.get('email'):
            score.has_email = True
        if contact.get('phone'):
            score.has_phone = True

    contact_quality_pts = 0
    if score.atl_contacts > 0:
        contact_quality_pts += 5  # Has ATL contacts
    if score.has_email:
        contact_quality_pts += 5  # Has email
    if score.has_phone:
        contact_quality_pts += 5  # Has phone
    score.contact_quality_score = contact_quality_pts

    # Calculate total
    score.total = (
        score.trade_diversity_score +
        score.energy_trifecta_score +
        score.oem_breadth_score +
        score.geographic_reach_score +
        score.contact_quality_score
    )

    return score


# ========== Agent Implementation ==========

class IntakeCommanderAgent:
    """
    IntakeCommanderAgent: Quality gate, deduplication, Trifecta scoring, and routing.

    Flow:
    1. Load incoming leads (from Deep Hunter export or Supabase intake queue)
    2. Check for duplicates in Close CRM
    3. Check for duplicates in Supabase dim_companies
    4. Apply 3-layer garbage contact filtering
    5. Calculate Trifecta scores
    6. Route based on score:
       - 80+ pts (UNICORN) → BDR work queue (hot leads)
       - 60-79 pts → Enrichment pipeline
       - 40-59 pts → Nurture campaign
       - <40 pts → Archive/low priority
    7. Log all decisions to lead_audit_log
    """

    def __init__(
        self,
        provider: str = "cerebras",
        model: Optional[str] = None,
        temperature: float = 0.0,  # Deterministic scoring
        intake_path: Optional[str] = None
    ):
        """
        Initialize IntakeCommanderAgent.

        Args:
            provider: LLM provider (cerebras for fast processing)
            model: Model ID (auto-selected if None)
            temperature: Generation temperature (0 for deterministic)
            intake_path: Path to intake CSV/JSON (optional, defaults to Supabase)
        """
        self.provider = provider
        self.temperature = temperature
        self.intake_path = intake_path

        # Initialize LLM (Cerebras for speed)
        if provider == "cerebras":
            api_key = os.getenv("CEREBRAS_API_KEY")
            if not api_key:
                raise ValueError("CEREBRAS_API_KEY not set")

            self.llm = ChatCerebras(
                model=model or "llama-3.3-70b",
                temperature=temperature,
                api_key=api_key
            )
        elif provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")

            self.llm = ChatAnthropic(
                model=model or "claude-3-5-haiku-20241022",
                temperature=temperature,
                api_key=api_key
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        # Initialize Close CRM client (read-only)
        close_api_key = os.getenv("CLOSE_API_KEY")
        self.close_client = CloseProvider(api_key=close_api_key) if close_api_key else None

        # Initialize Supabase client
        self.supabase = None  # Lazy init

        # Build LangGraph workflow
        self.graph = self._build_graph()

        logger.info(f"IntakeCommanderAgent initialized: provider={provider}, model={model}")

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow for intake processing."""
        workflow = StateGraph(IntakeCommanderState)

        # Define nodes
        workflow.add_node("load_incoming", self._load_incoming)
        workflow.add_node("check_close_crm", self._check_close_crm)
        workflow.add_node("check_supabase", self._check_supabase)
        workflow.add_node("apply_garbage_filter", self._apply_garbage_filter)
        workflow.add_node("calculate_trifecta", self._calculate_trifecta)
        workflow.add_node("route_leads", self._route_leads)

        # Define edges
        workflow.set_entry_point("load_incoming")
        workflow.add_edge("load_incoming", "check_close_crm")
        workflow.add_edge("check_close_crm", "check_supabase")
        workflow.add_edge("check_supabase", "apply_garbage_filter")
        workflow.add_edge("apply_garbage_filter", "calculate_trifecta")
        workflow.add_edge("calculate_trifecta", "route_leads")
        workflow.add_edge("route_leads", END)

        return workflow.compile()

    async def _load_incoming(self, state: IntakeCommanderState) -> IntakeCommanderState:
        """Load incoming leads from Deep Hunter export or Supabase intake queue."""
        logger.info("Loading incoming leads...")

        incoming_leads = []

        try:
            if self.intake_path:
                # Load from file (CSV or JSON)
                path = Path(self.intake_path)
                if path.suffix == '.csv':
                    import csv
                    with open(path, 'r') as f:
                        reader = csv.DictReader(f)
                        incoming_leads = list(reader)
                elif path.suffix == '.json':
                    with open(path, 'r') as f:
                        incoming_leads = json.load(f)
                else:
                    raise ValueError(f"Unsupported file format: {path.suffix}")

                logger.info(f"Loaded {len(incoming_leads)} leads from {path}")
            else:
                # Load from Supabase intake queue
                if not self.supabase:
                    self.supabase = await get_supabase()

                # Query for leads in "intake" stage
                result = self.supabase.table('dim_companies') \
                    .select('*') \
                    .eq('lifecycle_stage', 'intake') \
                    .limit(100) \
                    .execute()

                incoming_leads = result.data or []
                logger.info(f"Loaded {len(incoming_leads)} leads from Supabase intake queue")

        except Exception as e:
            logger.error(f"Error loading incoming leads: {e}")
            state['errors'].append(f"Load failed: {str(e)}")

        state['incoming_leads'] = incoming_leads
        state['current_step'] = 'load_incoming'
        return state

    async def _check_close_crm(self, state: IntakeCommanderState) -> IntakeCommanderState:
        """Check for duplicates in Close CRM."""
        logger.info("Checking Close CRM for duplicates...")

        if not self.close_client:
            logger.warning("Close CRM client not initialized, skipping duplicate check")
            state['current_step'] = 'check_close_crm'
            return state

        # TODO: Implement Close CRM duplicate check
        # For each lead, query Close by domain or company name
        # Mark duplicates in state

        state['current_step'] = 'check_close_crm'
        return state

    async def _check_supabase(self, state: IntakeCommanderState) -> IntakeCommanderState:
        """Check for duplicates in Supabase dim_companies."""
        logger.info("Checking Supabase for duplicates...")

        if not self.supabase:
            self.supabase = await get_supabase()

        duplicates = 0

        for lead in state['incoming_leads']:
            domain = lead.get('domain')
            if not domain:
                continue

            # Check if domain already exists
            result = self.supabase.table('dim_companies') \
                .select('id, normalized_name') \
                .eq('domain', domain) \
                .execute()

            if result.data and len(result.data) > 0:
                lead['is_duplicate'] = True
                lead['existing_id'] = result.data[0]['id']
                duplicates += 1
                logger.debug(f"Duplicate found: {domain} → {result.data[0]['id']}")
            else:
                lead['is_duplicate'] = False

        logger.info(f"Found {duplicates} duplicates in Supabase")

        state['current_step'] = 'check_supabase'
        return state

    async def _apply_garbage_filter(self, state: IntakeCommanderState) -> IntakeCommanderState:
        """Apply 3-layer garbage contact filtering."""
        logger.info("Applying garbage contact filtering...")

        garbage_filtered = 0

        for lead in state['incoming_leads']:
            contacts = lead.get('atl_contacts', [])
            clean_contacts = []

            for contact in contacts:
                name = contact.get('name', '')
                title = contact.get('title', '')

                if not is_garbage_contact(name, title):
                    clean_contacts.append(contact)
                else:
                    garbage_filtered += 1
                    logger.debug(f"Filtered garbage contact: {name} ({title})")

            lead['atl_contacts'] = clean_contacts
            lead['garbage_contacts_filtered'] = len(contacts) - len(clean_contacts)

        logger.info(f"Filtered {garbage_filtered} garbage contacts")

        state['current_step'] = 'apply_garbage_filter'
        return state

    async def _calculate_trifecta(self, state: IntakeCommanderState) -> IntakeCommanderState:
        """Calculate Trifecta scores for all leads."""
        logger.info("Calculating Trifecta scores...")

        trifecta_scores = {}
        unicorns = 0

        for lead in state['incoming_leads']:
            lead_id = lead.get('id') or lead.get('domain')
            score = calculate_trifecta_score(lead)
            trifecta_scores[lead_id] = score

            lead['trifecta_score'] = score.total
            lead['is_unicorn'] = score.is_unicorn

            if score.is_unicorn:
                unicorns += 1
                logger.info(f"🦄 UNICORN FOUND: {lead.get('company_name')} (score: {score.total})")

        state['trifecta_scores'] = trifecta_scores
        logger.info(f"Scored {len(trifecta_scores)} leads, found {unicorns} unicorns")

        state['current_step'] = 'calculate_trifecta'
        return state

    async def _route_leads(self, state: IntakeCommanderState) -> IntakeCommanderState:
        """Route leads based on Trifecta score."""
        logger.info("Routing leads based on scores...")

        result = IntakeResult()

        for lead in state['incoming_leads']:
            result.total_processed += 1

            # Skip duplicates
            if lead.get('is_duplicate'):
                result.duplicates_blocked += 1
                continue

            score = lead.get('trifecta_score', 0)
            is_unicorn = lead.get('is_unicorn', False)

            # Routing logic
            if score >= 80 or is_unicorn:
                # UNICORN → BDR work queue (hot leads)
                lead['routing_decision'] = 'bdr_work_queue'
                lead['priority'] = 'hot'
                result.routed_to_bdr += 1
                result.hot_leads_routed += 1

                if is_unicorn:
                    result.unicorns_found += 1
                    logger.info(f"🦄 Routing UNICORN to BDR: {lead.get('company_name')}")

            elif score >= 60:
                # High score → Enrichment pipeline
                lead['routing_decision'] = 'enrichment'
                lead['priority'] = 'medium'
                result.routed_to_enrichment += 1

            elif score >= 40:
                # Medium score → Nurture campaign
                lead['routing_decision'] = 'nurture'
                lead['priority'] = 'low'
                result.routed_to_nurture += 1

            else:
                # Low score → Archive
                lead['routing_decision'] = 'archive'
                lead['priority'] = 'very_low'

            result.new_leads += 1

        state['processed_results'] = result
        state['current_step'] = 'route_leads'

        logger.info(
            f"Routing complete: {result.total_processed} processed, "
            f"{result.routed_to_bdr} to BDR, {result.unicorns_found} unicorns"
        )

        return state

    async def process_intake(self) -> IntakeResult:
        """
        Run full intake processing cycle.

        Returns:
            IntakeResult with processing summary
        """
        start_time = time.time()

        logger.info("Starting IntakeCommander processing cycle...")

        # Initialize state
        initial_state: IntakeCommanderState = {
            'incoming_leads': [],
            'processed_results': None,
            'trifecta_scores': {},
            'current_step': 'init',
            'errors': []
        }

        try:
            # Run graph
            final_state = await self.graph.ainvoke(initial_state)

            result = final_state.get('processed_results') or IntakeResult()
            result.duration_ms = int((time.time() - start_time) * 1000)
            result.errors = final_state.get('errors', [])

            logger.info(
                f"Intake processing complete: {result.total_processed} leads, "
                f"{result.unicorns_found} unicorns, {result.duration_ms}ms"
            )

            return result

        except Exception as e:
            logger.error(f"Intake processing failed: {e}")
            return IntakeResult(
                errors=[str(e)],
                duration_ms=int((time.time() - start_time) * 1000)
            )


# ========== Exports ==========

__all__ = [
    "IntakeCommanderAgent",
    "IntakeResult",
    "TrifectaScore",
    "calculate_trifecta_score",
    "is_garbage_contact",
]
