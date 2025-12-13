"""
SignalScoutAgent - Market Signal Detection for Elite Team

Mission: Detect emerging market opportunities by analyzing Close CRM inbound patterns
        and Supabase pipeline signals, then generate scraping orders for Deep Hunter.

Detection Patterns:
- NEW VERTICAL EMERGENCE: 3+ leads from same category in 7 days
- WIN RATE SPIKE: >50% close rate in specific vertical
- GEOGRAPHIC CLUSTER: 5+ leads from same state/region
- TRIFECTA SIGNAL: Companies with 2+ MEP services (HVAC + Solar + Battery)

Outputs:
- VerticalSignal: Detected pattern with confidence score
- ScrapingOrder: Actionable scraping mission for Deep Hunter

Scheduled: Hourly at :15 via Celery Beat

Architecture:
    ┌─────────────────┐
    │ scan_close_crm  │ ─── Query recent inbound leads (last 7 days)
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ detect_patterns │ ─── Classify by vertical using regex
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ analyze_signals │ ─── Calculate confidence scores, find clusters
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ generate_orders │ ─── Create scraping missions for Deep Hunter
    └─────────────────┘

Usage:
    # Manual run
    python -c "
    import asyncio
    from app.services.langgraph.agents.elite_team.signal_scout_agent import SignalScoutAgent

    async def run():
        scout = SignalScoutAgent()
        result = await scout.scan()
        print(f'Detected {len(result.signals)} signals')
        for order in result.scraping_orders:
            print(f'ORDER: {order.vertical} - {order.priority}')

    asyncio.run(run())
    "
"""

import os
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from app.services.langchain_cerebras_compat import ChatCerebras
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END

from app.core.logging import setup_logging
from app.services.crm.close import CloseProvider

logger = setup_logging(__name__)


# ========== Output Models ==========

class VerticalSignal(BaseModel):
    """Detected vertical/market signal."""

    vertical: str = Field(
        ...,
        description="Vertical category (e.g., fire_safety, low_voltage, trifecta)"
    )
    signal_type: str = Field(
        ...,
        description="Type of signal (NEW_VERTICAL, WIN_SPIKE, GEO_CLUSTER, TRIFECTA)"
    )
    lead_count: int = Field(
        ...,
        description="Number of leads in this vertical (last 7 days)"
    )
    sample_companies: List[str] = Field(
        default_factory=list,
        description="Sample company names from this vertical"
    )
    confidence: float = Field(
        ...,
        description="Confidence score (0.0-1.0)"
    )
    recommended_action: str = Field(
        ...,
        description="AI recommendation for next steps"
    )
    states: List[str] = Field(
        default_factory=list,
        description="States where these leads are concentrated"
    )
    win_rate: Optional[float] = Field(
        None,
        description="Win rate for this vertical (if calculable)"
    )


class ScrapingOrder(BaseModel):
    """Scraping order for Deep Hunter agent."""

    order_id: str = Field(
        ...,
        description="Unique order ID (timestamp-based)"
    )
    vertical: str = Field(
        ...,
        description="Target vertical to scrape"
    )
    states: List[str] = Field(
        default_factory=list,
        description="Target states to scrape"
    )
    oems: List[str] = Field(
        default_factory=list,
        description="OEM brands to look for"
    )
    priority: str = Field(
        ...,
        description="Priority level: HIGH, MEDIUM, LOW"
    )
    target_count: int = Field(
        default=100,
        description="Target number of leads to scrape"
    )
    reasoning: str = Field(
        ...,
        description="Why this scraping order was generated"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Order creation timestamp"
    )


class SignalScoutResult(BaseModel):
    """Result from a signal scout scan."""

    scan_timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="When the scan was performed"
    )
    total_inbound_leads: int = Field(
        ...,
        description="Total inbound leads scanned (last 7 days)"
    )
    signals_detected: int = Field(
        ...,
        description="Number of actionable signals detected"
    )
    signals: List[VerticalSignal] = Field(
        default_factory=list,
        description="Detected vertical signals"
    )
    scraping_orders: List[ScrapingOrder] = Field(
        default_factory=list,
        description="Generated scraping orders for Deep Hunter"
    )
    duration_ms: int = Field(
        ...,
        description="Scan execution time in milliseconds"
    )
    next_scan_at: str = Field(
        ...,
        description="Recommended next scan time (hourly)"
    )


# ========== State Model ==========

class SignalScoutState(BaseModel):
    """State for SignalScoutAgent workflow."""

    # Input
    lookback_days: int = Field(
        default=7,
        description="How many days to look back for signals"
    )
    min_lead_threshold: int = Field(
        default=3,
        description="Minimum leads to trigger a signal"
    )

    # Intermediate
    inbound_leads: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Raw inbound leads from Close CRM"
    )
    classified_leads: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Leads classified by vertical"
    )

    # Output
    detected_signals: List[VerticalSignal] = Field(
        default_factory=list,
        description="Detected market signals"
    )
    scraping_orders: List[ScrapingOrder] = Field(
        default_factory=list,
        description="Generated scraping orders"
    )

    # Metadata
    scan_timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Scan start time"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Any errors encountered"
    )


# ========== Vertical Detection Patterns ==========

VERTICAL_PATTERNS = {
    "fire_safety": [
        r"\bfire\s*(protection|alarm|sprinkler|suppression)\b",
        r"\blife\s*safety\b",
        r"\bfire\s*extinguish",
        r"\bsprinkler\s*system",
        r"\bfire\s*inspection",
    ],
    "low_voltage": [
        r"\blow\s*voltage\b",
        r"\bsecurity\s*system",
        r"\baccess\s*control",
        r"\bcamera\s*system",
        r"\bsurveillance\b",
        r"\balarm\s*system",
        r"\bintercom\b",
    ],
    "trifecta": [
        r"\bsolar.*generator\b",
        r"\bgenerator.*battery\b",
        r"\bsolar.*battery\b",
        r"\benergy\s*storage",
        r"\bmicrogrid\b",
        r"\bresilienc(e|y)",
    ],
    "commercial_hvac": [
        r"\bvrf\b",
        r"\bchiller\b",
        r"\bcommercial\s*hvac\b",
        r"\brooftop\s*unit",
        r"\bboiler\b",
        r"\bcooling\s*tower",
    ],
    "electrical": [
        r"\belectrical\s*contract",
        r"\belectrician\b",
        r"\belectric\s*service",
        r"\bpanel\s*upgrad",
        r"\brewiring\b",
    ],
    "plumbing": [
        r"\bplumb(ing|er)\b",
        r"\bwater\s*heater",
        r"\bpipe\s*repair",
        r"\bdrain\s*clean",
        r"\bbackflow\b",
    ],
    "solar": [
        r"\bsolar\s*panel",
        r"\bsolar\s*instal",
        r"\bphotovoltaic\b",
        r"\bpv\s*system",
        r"\bsolar\s*energy",
    ],
    "generator": [
        r"\bgenerator\s*install",
        r"\bbackup\s*power",
        r"\bstandby\s*generator",
        r"\bgenerac\b",
        r"\bkohler\b",
    ],
}

# OEM brands by vertical (for scraping orders)
VERTICAL_OEMS = {
    "fire_safety": ["Honeywell", "Tyco", "Simplex", "Notifier", "Edwards"],
    "low_voltage": ["Honeywell", "Bosch", "Hikvision", "Axis", "Avigilon"],
    "commercial_hvac": ["Carrier", "Trane", "Daikin VRV", "Mitsubishi", "York"],
    "solar": ["Enphase", "SolarEdge", "SMA", "Fronius", "Tesla"],
    "generator": ["Generac", "Kohler", "Cummins", "Caterpillar", "Briggs & Stratton"],
    "trifecta": ["Tesla Powerwall", "Generac PWRcell", "Enphase IQ Battery"],
}


# ========== SignalScoutAgent ==========

class SignalScoutAgent:
    """
    Signal detection agent for emerging market opportunities.

    Scans Close CRM inbound leads + Supabase pipeline to detect:
    - New verticals with 3+ leads
    - Win rate spikes (>50% close rate)
    - Geographic clusters (5+ in same state)
    - Trifecta opportunities (multi-service companies)

    Outputs scraping orders for Deep Hunter agent.
    """

    # Prompt for analyzing signals and generating recommendations
    ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are a market intelligence analyst for an HVAC/MEP sales team.

Analyze the detected vertical patterns and recommend scraping priorities.

Consider:
1. Lead quality (are these decision-makers or tire-kickers?)
2. Market size (is this a big enough vertical to pursue?)
3. Win rate potential (high-intent signals)
4. Geographic concentration (easier to target)
5. Service expansion opportunity (existing customers could add services)

Provide:
- Confidence score (0.0-1.0) for each signal
- Recommended action (what to do next)
- Priority level for scraping orders (HIGH/MEDIUM/LOW)

Be conservative. Only recommend HIGH priority for truly compelling opportunities."""),
        ("human", """Vertical Pattern Analysis:
---
Vertical: {vertical}
Lead Count (7 days): {lead_count}
Sample Companies: {sample_companies}
States: {states}
Win Rate: {win_rate}%
Signal Type: {signal_type}
---

Analyze this pattern and provide:
1. Confidence score (0.0-1.0)
2. Recommended action
3. Scraping priority (HIGH/MEDIUM/LOW)""")
    ])

    def __init__(
        self,
        provider: str = "cerebras",
        model: Optional[str] = None,
        temperature: float = 0.2,
        close_api_key: Optional[str] = None
    ):
        """
        Initialize SignalScoutAgent.

        Args:
            provider: LLM provider (cerebras, claude)
            model: Model ID (auto-selected if None)
            temperature: Generation temperature (0.2 for focused analysis)
            close_api_key: Close CRM API key (defaults to env var)
        """
        self.provider = provider
        self.model = model or self._default_model(provider)
        self.temperature = temperature

        # Initialize LLM (Cerebras for speed)
        if provider == "cerebras":
            api_key = os.getenv("CEREBRAS_API_KEY")
            if not api_key:
                raise ValueError("CEREBRAS_API_KEY not set")
            self.llm = ChatCerebras(
                api_key=api_key,
                model=self.model,
                temperature=temperature,
                max_tokens=500
            )
        elif provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            self.llm = ChatAnthropic(
                api_key=api_key,
                model=self.model,
                temperature=temperature,
                max_tokens=500
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        # Build analysis chain
        self.analysis_chain = self.ANALYSIS_PROMPT | self.llm

        # Initialize Close CRM client
        close_key = close_api_key or os.getenv("CLOSE_API_KEY")
        if not close_key:
            raise ValueError("CLOSE_API_KEY not set")

        self.close_client = CloseProvider(api_key=close_key)

        # Build LangGraph workflow
        self.workflow = self._build_workflow()

        logger.info(f"SignalScoutAgent initialized: provider={provider}, model={self.model}")

    def _default_model(self, provider: str) -> str:
        """Get default model for provider."""
        defaults = {
            "cerebras": "llama-3.3-70b",  # Fast, good reasoning
            "claude": "claude-3-haiku-20240307"
        }
        return defaults.get(provider, "llama-3.3-70b")

    def _build_workflow(self) -> StateGraph:
        """Build LangGraph workflow for signal detection."""
        workflow = StateGraph(SignalScoutState)

        # Add nodes
        workflow.add_node("scan_close_crm", self._scan_close_crm)
        workflow.add_node("detect_patterns", self._detect_vertical_patterns)
        workflow.add_node("analyze_signals", self._analyze_signals)
        workflow.add_node("generate_orders", self._generate_scraping_orders)

        # Define flow
        workflow.set_entry_point("scan_close_crm")
        workflow.add_edge("scan_close_crm", "detect_patterns")
        workflow.add_edge("detect_patterns", "analyze_signals")
        workflow.add_edge("analyze_signals", "generate_orders")
        workflow.add_edge("generate_orders", END)

        return workflow.compile()

    async def _scan_close_crm(self, state: SignalScoutState) -> SignalScoutState:
        """
        Scan Close CRM for recent inbound leads.

        Queries leads created in the last N days (default 7).
        """
        logger.info(f"Scanning Close CRM: lookback={state.lookback_days} days")

        try:
            # Calculate date range
            since_date = datetime.now() - timedelta(days=state.lookback_days)

            # Query Close CRM for recent leads
            # Note: Close API filters by date_created using ISO format
            leads = await self._query_close_leads(since_date)

            state.inbound_leads = leads
            logger.info(f"Found {len(leads)} inbound leads in last {state.lookback_days} days")

        except Exception as e:
            error_msg = f"Failed to scan Close CRM: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)

        return state

    async def _query_close_leads(self, since_date: datetime) -> List[Dict[str, Any]]:
        """
        Query Close CRM leads created after a given date.

        Args:
            since_date: Only return leads created after this date

        Returns:
            List of lead dictionaries
        """
        # Format date for Close API query
        date_str = since_date.strftime("%Y-%m-%d")

        # Close API query format: date_created >= YYYY-MM-DD
        query = f'date_created >= "{date_str}"'

        # Make API request
        # Note: This uses the Close API's search endpoint
        import httpx

        leads = []
        has_more = True
        skip = 0
        limit = 100

        async with httpx.AsyncClient() as client:
            while has_more:
                response = await client.get(
                    f"{self.close_client.BASE_URL}/lead/",
                    headers={
                        "Authorization": self.close_client.auth_header,
                        "Content-Type": "application/json",
                    },
                    params={
                        "query": query,
                        "_limit": limit,
                        "_skip": skip,
                    },
                    timeout=30.0
                )

                if response.status_code != 200:
                    logger.error(f"Close API error: {response.status_code} - {response.text}")
                    break

                data = response.json()
                batch = data.get("data", [])
                leads.extend(batch)

                has_more = data.get("has_more", False)
                skip += limit

        return leads

    def _detect_vertical_patterns(self, state: SignalScoutState) -> SignalScoutState:
        """
        Classify leads by vertical using regex patterns.

        Analyzes company names, descriptions, and custom fields.
        """
        logger.info(f"Classifying {len(state.inbound_leads)} leads by vertical")

        classified = defaultdict(list)

        for lead in state.inbound_leads:
            # Extract searchable text
            company_name = lead.get("name", "").lower()
            description = lead.get("description", "").lower()

            # Get custom fields (might contain vertical info)
            custom_fields = lead.get("custom", {})
            custom_text = " ".join([str(v).lower() for v in custom_fields.values()])

            # Combine all searchable text
            search_text = f"{company_name} {description} {custom_text}"

            # Check against each vertical pattern
            matched_verticals = []
            for vertical, patterns in VERTICAL_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, search_text, re.IGNORECASE):
                        matched_verticals.append(vertical)
                        break

            # Add to classifications
            if matched_verticals:
                for vertical in matched_verticals:
                    classified[vertical].append(lead)
            else:
                # Default to hvac if no match (conservative)
                classified["hvac_general"].append(lead)

        state.classified_leads = dict(classified)

        logger.info(
            f"Classified into {len(classified)} verticals: "
            f"{', '.join([f'{v}({len(leads)})' for v, leads in classified.items()])}"
        )

        return state

    async def _analyze_signals(self, state: SignalScoutState) -> SignalScoutState:
        """
        Analyze classified leads for actionable signals.

        Calculates confidence scores and generates recommendations.
        """
        logger.info(f"Analyzing signals from {len(state.classified_leads)} verticals")

        signals = []

        for vertical, leads in state.classified_leads.items():
            lead_count = len(leads)

            # Skip if below threshold
            if lead_count < state.min_lead_threshold:
                continue

            # Determine signal type
            signal_type = self._determine_signal_type(vertical, leads)

            # Extract metadata
            sample_companies = [lead.get("name", "Unknown") for lead in leads[:5]]
            states = self._extract_states(leads)
            win_rate = self._calculate_win_rate(leads)

            # Get AI analysis
            try:
                analysis = await self.analysis_chain.ainvoke({
                    "vertical": vertical,
                    "lead_count": lead_count,
                    "sample_companies": ", ".join(sample_companies),
                    "states": ", ".join(states) if states else "N/A",
                    "win_rate": win_rate if win_rate else "Unknown",
                    "signal_type": signal_type,
                })

                # Parse AI response
                analysis_text = analysis.content if hasattr(analysis, 'content') else str(analysis)
                confidence, action = self._parse_analysis(analysis_text)

            except Exception as e:
                logger.error(f"Failed to analyze {vertical}: {e}")
                confidence = 0.5  # Default medium confidence
                action = f"Review {lead_count} leads in {vertical} vertical"

            # Create signal
            signal = VerticalSignal(
                vertical=vertical,
                signal_type=signal_type,
                lead_count=lead_count,
                sample_companies=sample_companies,
                confidence=confidence,
                recommended_action=action,
                states=states,
                win_rate=win_rate,
            )

            signals.append(signal)

        state.detected_signals = signals
        logger.info(f"Detected {len(signals)} actionable signals")

        return state

    def _determine_signal_type(self, vertical: str, leads: List[Dict[str, Any]]) -> str:
        """Determine type of signal based on vertical and lead characteristics."""
        lead_count = len(leads)

        # Check for trifecta (multi-service companies)
        if "trifecta" in vertical:
            return "TRIFECTA"

        # Check for geographic clustering
        states = self._extract_states(leads)
        if states and len(states) <= 2 and lead_count >= 5:
            return "GEO_CLUSTER"

        # Check for new vertical emergence
        if lead_count >= 3 and vertical not in ["hvac_general"]:
            return "NEW_VERTICAL"

        # Default
        return "NEW_VERTICAL"

    def _extract_states(self, leads: List[Dict[str, Any]]) -> List[str]:
        """Extract unique states from leads."""
        states = []
        for lead in leads:
            addresses = lead.get("addresses", [])
            for addr in addresses:
                state = addr.get("state")
                if state and state not in states:
                    states.append(state)
        return sorted(states)

    def _calculate_win_rate(self, leads: List[Dict[str, Any]]) -> Optional[float]:
        """Calculate win rate for leads (if status available)."""
        total = len(leads)
        if total == 0:
            return None

        won = sum(1 for lead in leads if lead.get("status_label", "").lower() in ["won", "closed won"])

        if won == 0:
            return None

        return round((won / total) * 100, 1)

    def _parse_analysis(self, analysis_text: str) -> Tuple[float, str]:
        """Parse AI analysis response for confidence and action."""
        # Extract confidence score (0.0-1.0)
        confidence_match = re.search(r"confidence[:\s]*([0-9.]+)", analysis_text, re.IGNORECASE)
        confidence = float(confidence_match.group(1)) if confidence_match else 0.5

        # Extract recommended action
        action_match = re.search(r"action[:\s]*(.+?)(?:\n|$)", analysis_text, re.IGNORECASE)
        action = action_match.group(1).strip() if action_match else "Review leads"

        return confidence, action

    def _generate_scraping_orders(self, state: SignalScoutState) -> SignalScoutState:
        """
        Generate scraping orders for Deep Hunter agent.

        Only creates orders for high-confidence signals.
        """
        logger.info(f"Generating scraping orders from {len(state.detected_signals)} signals")

        orders = []

        # Import hub for deduplication
        from app.services.langgraph.agents.elite_team.elite_team_hub import get_elite_hub
        hub = get_elite_hub()

        for signal in state.detected_signals:
            # Only create orders for medium+ confidence
            if signal.confidence < 0.5:
                logger.debug(f"Skipping {signal.vertical} (low confidence: {signal.confidence})")
                continue

            # Check for duplicate orders (per Anthropic best practices)
            if hub.has_recent_order_for_vertical(signal.vertical, lookback_hours=24):
                logger.info(
                    f"Skipping duplicate order for {signal.vertical} "
                    "(already ordered in last 24h)"
                )
                continue

            # Determine priority
            if signal.confidence >= 0.75:
                priority = "HIGH"
                target_count = 200
            elif signal.confidence >= 0.6:
                priority = "MEDIUM"
                target_count = 100
            else:
                priority = "LOW"
                target_count = 50

            # Get OEMs for this vertical
            oems = VERTICAL_OEMS.get(signal.vertical, [])

            # Create order
            order = ScrapingOrder(
                order_id=f"SO-{datetime.now().strftime('%Y%m%d%H%M%S')}-{signal.vertical}",
                vertical=signal.vertical,
                states=signal.states[:5],  # Limit to top 5 states
                oems=oems,
                priority=priority,
                target_count=target_count,
                reasoning=signal.recommended_action,
            )

            orders.append(order)

            # Record to history for deduplication (per Anthropic best practices)
            hub.record_order_history(order)

            logger.info(
                f"Created {priority} scraping order: {signal.vertical} "
                f"({target_count} targets in {len(signal.states)} states)"
            )

        state.scraping_orders = orders
        return state

    async def scan(
        self,
        lookback_days: int = 7,
        min_lead_threshold: int = 3
    ) -> SignalScoutResult:
        """
        Execute full signal detection scan.

        Args:
            lookback_days: How many days to look back
            min_lead_threshold: Minimum leads to trigger signal

        Returns:
            SignalScoutResult with detected signals and orders
        """
        start_time = time.time()

        logger.info(f"Starting signal scout scan: lookback={lookback_days} days")

        # Initialize state
        initial_state = SignalScoutState(
            lookback_days=lookback_days,
            min_lead_threshold=min_lead_threshold,
        )

        # Run workflow
        try:
            final_state = await self.workflow.ainvoke(initial_state)
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            # Convert initial_state to dict for consistent handling
            final_state = initial_state.model_dump()
            final_state["errors"] = [str(e)]

        duration_ms = int((time.time() - start_time) * 1000)

        # Calculate next scan time (1 hour from now)
        next_scan = datetime.now() + timedelta(hours=1)

        # LangGraph returns AddableValuesDict, access with dict notation
        # (Also works with dict from error branch)
        inbound_leads = final_state.get("inbound_leads", []) if isinstance(final_state, dict) else getattr(final_state, "inbound_leads", [])
        detected_signals = final_state.get("detected_signals", []) if isinstance(final_state, dict) else getattr(final_state, "detected_signals", [])
        scraping_orders = final_state.get("scraping_orders", []) if isinstance(final_state, dict) else getattr(final_state, "scraping_orders", [])

        result = SignalScoutResult(
            total_inbound_leads=len(inbound_leads),
            signals_detected=len(detected_signals),
            signals=detected_signals,
            scraping_orders=scraping_orders,
            duration_ms=duration_ms,
            next_scan_at=next_scan.isoformat(),
        )

        logger.info(
            f"Signal scout complete: {result.signals_detected} signals, "
            f"{len(result.scraping_orders)} orders, {duration_ms}ms"
        )

        return result


# ========== Exports ==========

__all__ = [
    "SignalScoutAgent",
    "VerticalSignal",
    "ScrapingOrder",
    "SignalScoutResult",
    "SignalScoutState",
    "VERTICAL_PATTERNS",
    "VERTICAL_OEMS",
]
