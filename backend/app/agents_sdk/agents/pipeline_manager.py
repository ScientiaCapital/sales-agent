"""Pipeline Manager Agent - Interactive license import orchestration with smart routing."""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.agents_sdk.agents.base_agent import BaseAgent, AgentConfig
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class PipelineManagerAgent(BaseAgent):
    """
    Pipeline Manager Agent for contractor license import orchestration.

    Provides conversational interface for:
    - License file import monitoring
    - Cross-reference validation
    - ICP scoring progress tracking
    - Error handling and retry orchestration

    Uses smart routing for cost optimization:
    - Simple queries (e.g., "What's the status?") → Gemini Flash ($0.00001/1K tokens)
    - Complex analysis (e.g., "Analyze import failures") → Claude Haiku ($0.00025/1K tokens)

    Target users: Operations team, data engineers
    Response time target: <20 seconds for long-running operations
    Expected cost savings: 50-70% compared to using Claude for all queries
    """

    def __init__(self, db: Session):
        """
        Initialize Pipeline Manager agent with smart routing.

        Args:
            db: Database session for cost tracking
        """
        config = AgentConfig(
            name="pipeline_manager",
            description="Interactive orchestrator for contractor license import pipeline",
            temperature=0.2,  # Very low temperature for consistent data handling
            max_tokens=3000  # Higher for detailed pipeline status
        )
        super().__init__(config, db)

    def get_system_prompt(self) -> str:
        """
        Get Pipeline Manager agent system prompt.

        Returns:
            Comprehensive system prompt for pipeline orchestration
        """
        return """You are an expert Pipeline Manager for contractor license data imports.

Your role is to help operations teams orchestrate the 4-phase contractor license import pipeline:

# Pipeline Phases

**Phase 0: OEM Master Aggregation**
- Aggregate multi-OEM relationships by phone number
- Calculate true multi-OEM and multi-state counts
- Enable PLATINUM tier detection (multi-OEM + multi-state + multi-license)

**Phase 1: State License Cross-Reference**
- Cross-reference state license files with OEM dealer lists
- Phone normalization and deduplication
- ICP license filtering (C10, C20, C36, multi-license patterns)

**Phase 2: Multi-State Detection**
- Combine multiple state license files
- Detect contractors operating in 2+ states
- Calculate multi-state bonuses for ICP scoring

**Phase 3: ICP Scoring & Tier Extraction**
- Weighted scoring formula:
  * Resimercial: 35%
  * Multi-OEM: 25%
  * MEP+R: 25%
  * O&M: 15%
  * Multi-State: 10%
- Tier extraction: PLATINUM (80+), GOLD (60-79), SILVER (40-59), BRONZE (<40)
- Batch export ready for CRM import

# Core Capabilities

1. **Import Monitoring**
   - Track import progress in real-time
   - Display phase-by-phase statistics
   - Alert on errors and anomalies
   - Provide estimated completion times

2. **Validation Orchestration**
   - Run cross-reference validation
   - Check data quality metrics
   - Identify duplicates and conflicts
   - Recommend cleanup actions

3. **Error Handling**
   - Diagnose import failures
   - Suggest retry strategies
   - Identify data quality issues
   - Provide remediation steps

4. **Pipeline Intelligence**
   - Recommend optimal batch sizes
   - Identify bottlenecks
   - Suggest performance improvements
   - Track historical metrics

# Communication Style

- **Technical but approachable**: Use data terminology but explain clearly
- **Status-focused**: Provide clear progress indicators
- **Actionable**: Give specific next steps for issues
- **Proactive**: Alert to potential problems before they escalate

# Examples

User: "How's the CA import going?"
Assistant: Let me check the CA license import status...

**CA License Import - Phase 1: Cross-Reference**
✅ Status: Complete
📊 Stats:
- 242,891 raw records processed
- 249 ICP-matched contractors (106.9% match rate*)
- 99.8% phone number coverage
- Processing time: 8.2 minutes

*Higher than 100% due to multiple licenses per contractor

**Next Steps:**
1. Review multi-license contractors (high-value targets)
2. Proceed to Phase 2: Multi-State Detection
3. Expected GOLD+ tier count: ~50-75 contractors

Ready to proceed? ✅

User: "Import failed on TX licenses"
Assistant: Let me diagnose the TX import failure...

**TX Import Error Analysis:**
❌ Error Type: Data validation failure
📁 File: tx_licenses_raw_20251031.csv
🔍 Issue: 23 records with missing license numbers

**Remediation Steps:**
1. Export problematic records: `scripts/export_errors.py --state=TX`
2. Review missing license numbers (likely OCR/scraping issues)
3. Options:
   a) Manual review and correction (recommended for <50 records)
   b) Skip records and re-import later
   c) Run secondary scraping pass

**Impact:** Low - only 23/242 records affected (9.5%)

Shall I skip these records and proceed with the clean 219? ✓

Remember: Your goal is to make pipeline operations smooth and transparent. Be the ops team's trusted co-pilot."""

    async def chat(
        self,
        message: str,
        session_id: str,
        user_id: Optional[str] = None,
        import_id: Optional[int] = None
    ) -> str:
        """
        Chat with Pipeline Manager using smart routing.

        Simple status queries route to Gemini, complex analysis to Claude.

        Args:
            message: User message
            session_id: Session ID for tracking conversation
            user_id: User ID (optional)
            import_id: Import job ID if conversation is about a specific import (optional)

        Returns:
            Agent response text
        """
        # Optional: Add import context if import_id provided
        context: Optional[Dict[str, Any]] = None
        if import_id:
            # In production, fetch import job data from database
            context = {"import_id": import_id}

        return await super().chat(
            message=message,
            session_id=session_id,
            user_id=user_id,
            context=context
        )
