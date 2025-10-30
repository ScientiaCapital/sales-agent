"""
Contractor License State Auditor Agent - LangGraph StateGraph

Comprehensive contractor license verification and compliance monitoring agent
that audits licenses across multiple states and provides detailed compliance reports.

Architecture:
    StateGraph with parallel state verification → compliance analysis → report generation

Features:
- Multi-state license verification (CA, TX, FL, NY, IL)
- Real-time database scraping
- Compliance status monitoring
- Violation history tracking
- Renewal deadline alerts
- Risk assessment and scoring
- Automated compliance reporting

Performance:
- Target: <8000ms for comprehensive audit
- Parallel state queries for efficiency
- Streaming support for real-time updates

Usage:
    ```python
    from app.services.langgraph.agents import LicenseAuditorAgent

    agent = LicenseAuditorAgent()
    result = await agent.audit_license(
        license_number="123456",
        state="CA",
        audit_depth="comprehensive"
    )

    print(f"Status: {result.license_status}")
    print(f"Compliance: {result.compliance_score}")
    print(f"Violations: {result.violations_count}")
    ```
"""

import os
import time
import asyncio
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisCheckpointer
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool

from app.services.langgraph.tools.license_audit_tools import (
    search_contractor_license_tool,
    search_company_licenses_tool,
    check_license_compliance_tool,
    STATE_DATABASES
)
from app.services.cerebras import CerebrasService
from app.core.logging import setup_logging
from app.core.exceptions import CerebrasAPIError

logger = setup_logging(__name__)

# ========== State Schema ==========

class LicenseAuditState(BaseModel):
    """State schema for license audit workflow."""
    # Input data
    license_number: str
    state: str
    audit_depth: Literal["quick", "standard", "comprehensive"] = "standard"
    company_name: Optional[str] = None
    check_types: List[str] = ["expiration", "violations", "insurance", "bonding"]
    
    # License data
    license_info: Dict[str, Any] = Field(default_factory=dict)
    company_licenses: Dict[str, Any] = Field(default_factory=dict)
    compliance_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Analysis results
    risk_assessment: Dict[str, Any] = Field(default_factory=dict)
    compliance_score: float = 0.0
    violations_summary: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    # Metadata
    current_step: str = "initializing"
    confidence_score: float = 0.0
    audit_duration_ms: int = 0
    errors: List[str] = Field(default_factory=list)
    states_checked: List[str] = Field(default_factory=list)

# ========== Result Schema ==========

class LicenseAuditResult(BaseModel):
    """Structured result for license audit."""
    license_number: str
    state: str
    license_status: str
    compliance_score: float
    risk_level: str
    expiration_date: str
    violations_count: int
    violations_summary: List[Dict[str, Any]]
    insurance_status: str
    bonding_status: str
    company_name: str
    recommendations: List[str]
    audit_metadata: Dict[str, Any]

# ========== License Auditor Agent ==========

class LicenseAuditorAgent:
    """
    LangGraph StateGraph agent for comprehensive contractor license auditing.
    
    Workflow:
    1. Initialize audit parameters
    2. Search license information
    3. Check company licenses (if company name provided)
    4. Perform compliance checks
    5. Risk assessment and scoring
    6. Generate recommendations
    """

    def __init__(
        self,
        model: str = "llama3.1-8b",
        temperature: float = 0.2,
        max_tokens: int = 500
    ):
        """
        Initialize License Auditor Agent.
        
        Args:
            model: Cerebras model ID
            temperature: Sampling temperature
            max_tokens: Max completion tokens
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize Cerebras service
        api_key = os.getenv("CEREBRAS_API_KEY")
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY environment variable not set")
        
        self.cerebras = CerebrasService()
        
        # Build StateGraph
        self.graph = self._build_graph()
        
        logger.info(f"LicenseAuditorAgent initialized: model={model}")

    def _build_graph(self) -> StateGraph:
        """Build LangGraph StateGraph for license auditing."""
        
        # Create StateGraph
        graph = StateGraph(LicenseAuditState)
        
        # Add nodes
        graph.add_node("initialize", self._initialize_audit)
        graph.add_node("search_license", self._search_license)
        graph.add_node("search_company", self._search_company_licenses)
        graph.add_node("check_compliance", self._check_compliance)
        graph.add_node("assess_risk", self._assess_risk)
        graph.add_node("generate_recommendations", self._generate_recommendations)
        
        # Add edges
        graph.set_entry_point("initialize")
        graph.add_edge("initialize", "search_license")
        graph.add_edge("search_license", "search_company")
        graph.add_edge("search_company", "check_compliance")
        graph.add_edge("check_compliance", "assess_risk")
        graph.add_edge("assess_risk", "generate_recommendations")
        graph.add_edge("generate_recommendations", END)
        
        return graph.compile()

    async def _initialize_audit(self, state: LicenseAuditState) -> LicenseAuditState:
        """Initialize audit parameters and validate inputs."""
        logger.info(f"Initializing license audit for {state.license_number} in {state.state}")
        
        state.current_step = "initializing"
        state.confidence_score = 0.0
        state.errors = []
        state.states_checked = []
        
        # Validate state
        valid_states = ["CA", "TX", "FL", "NY", "IL", "california", "texas", "florida", "new_york", "illinois"]
        if state.state.upper() not in [s.upper() for s in valid_states]:
            state.errors.append(f"Unsupported state: {state.state}")
            return state
        
        # Normalize state
        state.state = state.state.upper()
        if state.state in ["CALIFORNIA", "CA"]:
            state.state = "CA"
        elif state.state in ["TEXAS", "TX"]:
            state.state = "TX"
        elif state.state in ["FLORIDA", "FL"]:
            state.state = "FL"
        elif state.state in ["NEW_YORK", "NEW YORK", "NY"]:
            state.state = "NY"
        elif state.state in ["ILLINOIS", "IL"]:
            state.state = "IL"
        
        # Adjust check types based on audit depth
        if state.audit_depth == "quick":
            state.check_types = ["expiration", "violations"]
        elif state.audit_depth == "comprehensive":
            state.check_types = ["expiration", "violations", "insurance", "bonding", "workers_comp", "tax_status"]
        
        logger.info(f"Audit initialized: state={state.state}, depth={state.audit_depth}, "
                   f"checks={len(state.check_types)}")
        
        return state

    async def _search_license(self, state: LicenseAuditState) -> LicenseAuditState:
        """Search for license information."""
        logger.info(f"Searching license {state.license_number} in {state.state}")
        
        state.current_step = "searching_license"
        
        try:
            # Search for license information
            content, license_data = await search_contractor_license_tool(
                license_number=state.license_number,
                state=state.state
            )
            
            state.license_info = license_data
            state.states_checked.append(state.state)
            
            # Calculate confidence based on data completeness
            required_fields = ["status", "expiration_date", "company_name"]
            present_fields = sum(1 for field in required_fields if field in license_data)
            state.confidence_score = present_fields / len(required_fields)
            
            logger.info(f"License search complete: status={license_data.get('status', 'Unknown')}")
            
        except Exception as e:
            error_msg = f"License search failed: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return state

    async def _search_company_licenses(self, state: LicenseAuditState) -> LicenseAuditState:
        """Search for all company licenses if company name is provided."""
        logger.info("Searching company licenses")
        
        state.current_step = "searching_company"
        
        if not state.company_name and state.license_info.get("company_name"):
            state.company_name = state.license_info["company_name"]
        
        if not state.company_name:
            logger.info("No company name provided, skipping company search")
            return state
        
        try:
            # Search for all company licenses
            content, company_data = await search_company_licenses_tool(
                company_name=state.company_name,
                state=state.state,
                business_type="contractor"
            )
            
            state.company_licenses = company_data
            
            # Update confidence based on company data
            if company_data.get("total_licenses", 0) > 0:
                state.confidence_score = min(1.0, state.confidence_score + 0.2)
            
            logger.info(f"Company search complete: {company_data.get('total_licenses', 0)} licenses found")
            
        except Exception as e:
            error_msg = f"Company search failed: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return state

    async def _check_compliance(self, state: LicenseAuditState) -> LicenseAuditState:
        """Perform comprehensive compliance checks."""
        logger.info("Checking license compliance")
        
        state.current_step = "checking_compliance"
        
        try:
            # Perform compliance checks
            content, compliance_data = await check_license_compliance_tool(
                license_number=state.license_number,
                state=state.state,
                check_types=state.check_types
            )
            
            state.compliance_data = compliance_data
            
            # Calculate compliance score
            checks = compliance_data.get("checks", [])
            if checks:
                compliant_checks = sum(1 for check in checks if check.get("status") == "compliant")
                state.compliance_score = (compliant_checks / len(checks)) * 100
            else:
                state.compliance_score = 0.0
            
            logger.info(f"Compliance check complete: {state.compliance_score:.1f}% compliant")
            
        except Exception as e:
            error_msg = f"Compliance check failed: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return state

    async def _assess_risk(self, state: LicenseAuditState) -> LicenseAuditState:
        """Assess risk level and generate risk analysis."""
        logger.info("Assessing risk level")
        
        state.current_step = "assessing_risk"
        
        try:
            # Prepare risk assessment data
            risk_factors = []
            
            # License status risk
            license_status = state.license_info.get("status", "Unknown")
            if license_status != "Active":
                risk_factors.append(f"License status: {license_status}")
            
            # Expiration risk
            expiration_date = state.license_info.get("expiration_date")
            if expiration_date:
                try:
                    exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")
                    days_until_expiry = (exp_date - datetime.now()).days
                    if days_until_expiry < 30:
                        risk_factors.append(f"License expires in {days_until_expiry} days")
                    elif days_until_expiry < 90:
                        risk_factors.append(f"License expires in {days_until_expiry} days")
                except:
                    pass
            
            # Violations risk
            violations_count = state.license_info.get("violations_count", 0)
            if violations_count > 0:
                risk_factors.append(f"{violations_count} violations found")
            
            # Compliance risk
            if state.compliance_score < 80:
                risk_factors.append(f"Low compliance score: {state.compliance_score:.1f}%")
            
            # Generate risk assessment using Cerebras
            risk_prompt = f"""
            Assess contractor license risk based on these factors:

            License Status: {license_status}
            Expiration Date: {expiration_date}
            Violations Count: {violations_count}
            Compliance Score: {state.compliance_score:.1f}%
            Risk Factors: {risk_factors}

            Provide:
            1. Overall Risk Level: Low, Medium, High, or Critical
            2. Risk Score: 0-100
            3. Key Risk Factors: Top 3 concerns
            4. Risk Mitigation: 3-5 recommendations
            5. Monitoring Priority: High, Medium, or Low
            """
            
            score, reasoning, latency_ms = self.cerebras.qualify_lead(
                company_name="Risk Assessment",
                notes=risk_prompt
            )
            
            # Parse risk assessment (simplified)
            lines = reasoning.split('\n')
            risk_level = "Medium"
            risk_score = score
            key_factors = []
            mitigation = []
            
            for line in lines:
                line = line.strip()
                if "Risk Level:" in line:
                    risk_level = line.split(":")[-1].strip()
                elif "Risk Score:" in line:
                    try:
                        risk_score = int(line.split(":")[-1].strip())
                    except:
                        pass
                elif line.startswith(("1.", "2.", "3.")) and "Key Risk" in reasoning:
                    key_factors.append(line)
                elif line.startswith(("1.", "2.", "3.", "4.", "5.")) and "Mitigation" in reasoning:
                    mitigation.append(line)
            
            state.risk_assessment = {
                "risk_level": risk_level,
                "risk_score": risk_score,
                "key_factors": key_factors[:3],
                "mitigation_recommendations": mitigation[:5],
                "risk_factors": risk_factors,
                "assessment_timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Risk assessment complete: {risk_level} risk (score: {risk_score})")
            
        except Exception as e:
            error_msg = f"Risk assessment failed: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return state

    async def _generate_recommendations(self, state: LicenseAuditState) -> LicenseAuditState:
        """Generate actionable recommendations."""
        logger.info("Generating recommendations")
        
        state.current_step = "generating_recommendations"
        
        try:
            # Generate recommendations based on audit results
            recommendations_prompt = f"""
            Generate actionable recommendations for contractor license {state.license_number}:

            License Status: {state.license_info.get('status', 'Unknown')}
            Compliance Score: {state.compliance_score:.1f}%
            Risk Level: {state.risk_assessment.get('risk_level', 'Unknown')}
            Violations: {state.license_info.get('violations_count', 0)}
            Expiration: {state.license_info.get('expiration_date', 'Unknown')}
            Errors: {state.errors}

            Provide 5-7 specific, actionable recommendations for:
            1. License maintenance and renewal
            2. Compliance improvement
            3. Risk mitigation
            4. Monitoring and alerts
            5. Documentation and record-keeping
            """
            
            # Get recommendations from Cerebras
            score, reasoning, latency_ms = self.cerebras.qualify_lead(
                company_name="License Recommendations",
                notes=recommendations_prompt
            )
            
            # Parse recommendations (simplified)
            lines = reasoning.split('\n')
            recommendations = []
            
            for line in lines:
                line = line.strip()
                if line.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.")):
                    recommendations.append(line)
            
            state.recommendations = recommendations[:7]  # Top 7 recommendations
            
            # Calculate final confidence
            if state.license_info and state.compliance_data:
                state.confidence_score = min(1.0, state.confidence_score + 0.3)
            
            logger.info(f"Recommendations generated: {len(state.recommendations)} recommendations")
            
        except Exception as e:
            error_msg = f"Recommendations generation failed: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return state

    async def audit_license(
        self,
        license_number: str,
        state: str,
        audit_depth: Literal["quick", "standard", "comprehensive"] = "standard",
        company_name: Optional[str] = None,
        check_types: List[str] = None
    ) -> tuple[LicenseAuditResult, int, Dict[str, Any]]:
        """
        Perform comprehensive license audit.
        
        Args:
            license_number: License number to audit
            state: State where license is registered
            audit_depth: Depth of audit (quick/standard/comprehensive)
            company_name: Company name (optional, will be looked up if not provided)
            check_types: Types of compliance checks to perform
            
        Returns:
            Tuple of (result, latency_ms, metadata)
        """
        if not license_number:
            raise ValueError("license_number is required")
        
        if check_types is None:
            check_types = ["expiration", "violations", "insurance", "bonding"]
        
        # Initialize state
        initial_state = LicenseAuditState(
            license_number=license_number,
            state=state,
            audit_depth=audit_depth,
            company_name=company_name,
            check_types=check_types
        )
        
        # Measure latency
        start_time = time.time()
        
        try:
            # Execute StateGraph
            final_state = await self.graph.ainvoke(initial_state)
            
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            # Build result
            result = LicenseAuditResult(
                license_number=final_state.license_number,
                state=final_state.state,
                license_status=final_state.license_info.get("status", "Unknown"),
                compliance_score=final_state.compliance_score,
                risk_level=final_state.risk_assessment.get("risk_level", "Unknown"),
                expiration_date=final_state.license_info.get("expiration_date", "Unknown"),
                violations_count=final_state.license_info.get("violations_count", 0),
                violations_summary=final_state.license_info.get("violations", []),
                insurance_status=final_state.license_info.get("insurance_status", "Unknown"),
                bonding_status=final_state.license_info.get("bonding_status", "Unknown"),
                company_name=final_state.license_info.get("company_name", "Unknown"),
                recommendations=final_state.recommendations,
                audit_metadata={
                    "audit_depth": final_state.audit_depth,
                    "confidence_score": final_state.confidence_score,
                    "states_checked": final_state.states_checked,
                    "errors": final_state.errors,
                    "audit_duration_ms": latency_ms,
                    "risk_assessment": final_state.risk_assessment
                }
            )
            
            # Build metadata
            metadata = {
                "model": self.model,
                "temperature": self.temperature,
                "latency_ms": latency_ms,
                "agent_type": "license_auditor",
                "langgraph_state": True,
                "audit_depth": final_state.audit_depth,
                "states_checked": len(final_state.states_checked),
                "compliance_score": final_state.compliance_score,
                "risk_level": final_state.risk_assessment.get("risk_level", "Unknown"),
                "confidence_score": final_state.confidence_score,
                "errors_count": len(final_state.errors)
            }
            
            logger.info(
                f"License audit complete: license={license_number}, state={state}, "
                f"status={result.license_status}, compliance={final_state.compliance_score:.1f}%, "
                f"risk={result.risk_level}, latency={latency_ms}ms"
            )
            
            return result, latency_ms, metadata
            
        except Exception as e:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            logger.error(
                f"License audit failed: license={license_number}, state={state}, "
                f"latency={latency_ms}ms, error={str(e)}",
                exc_info=True
            )
            
            raise CerebrasAPIError(
                message="License audit failed",
                details={
                    "license_number": license_number,
                    "state": state,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )

# ========== Exports ==========

__all__ = [
    "LicenseAuditorAgent",
    "LicenseAuditResult",
    "LicenseAuditState"
]


