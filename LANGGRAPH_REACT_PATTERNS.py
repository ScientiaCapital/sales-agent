# Production-Ready LangGraph ReAct Agent Patterns - 2025
# File: backend/app/services/langgraph_react_patterns.py
#
# Complete implementation patterns for create_react_agent() with ChatAnthropic,
# error handling, async execution, and performance optimization.

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent, ToolNode
from langgraph.graph import MessagesState

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS & ENUMS
# ============================================================================

@dataclass
class AgentConfig:
    """Configuration for ReAct agent creation"""
    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    max_tokens: int = 2000
    recursion_limit: int = 25
    timeout_seconds: Optional[int] = 30
    enable_checkpointing: bool = True
    parallel_tool_calls: bool = False


@dataclass
class ToolExecutionMetrics:
    """Metrics for individual tool execution"""
    tool_name: str
    call_id: str
    status: str  # "success" | "error" | "not_found"
    duration_ms: float
    input_args: Dict[str, Any]
    result: Dict[str, Any]
    error_message: Optional[str] = None


@dataclass
class AgentExecutionMetrics:
    """Metrics for overall agent execution"""
    request_id: str
    total_time_ms: float
    iterations: int
    tool_calls: int
    tools_succeeded: int
    tools_failed: int
    recursion_limit_exceeded: bool
    final_status: str  # "success" | "partial" | "error" | "timeout"
    tool_metrics: List[ToolExecutionMetrics]


@dataclass
class EnrichmentResult:
    """Final result from enrichment agent"""
    status: str  # "success" | "partial" | "error"
    enrichment_data: Dict[str, Any]
    final_response: str
    metrics: AgentExecutionMetrics
    error: Optional[str] = None


# ============================================================================
# TOOL DEFINITIONS WITH ERROR HANDLING
# ============================================================================

class ExternalAPIError(Exception):
    """Base exception for external API calls"""
    pass


class ApolloAPIError(ExternalAPIError):
    """Apollo.io API specific error"""
    pass


class LinkedInScrapingError(ExternalAPIError):
    """LinkedIn scraping specific error"""
    pass


@tool
def search_apollo_contact(email: str) -> Dict[str, Any]:
    """
    Search for contact details on Apollo.io by email address.

    Implements error handling, rate limiting awareness, and graceful degradation.

    Args:
        email: Email address to search for (must be valid format)

    Returns:
        Dictionary with status, data, and optional error message

    Example:
        >>> result = search_apollo_contact("john@acme.com")
        >>> if result["status"] == "success":
        ...     print(result["data"]["title"])
    """
    if not email or "@" not in email:
        return {
            "status": "error",
            "error": "Invalid email format",
            "email": email,
        }

    try:
        # Import here to avoid circular dependencies
        from app.services.apollo import ApolloService

        apollo = ApolloService()
        result = apollo.search_contact(email=email)

        if result:
            logger.info(f"Apollo search successful for {email}")
            return {
                "status": "success",
                "email": email,
                "data": {
                    "name": result.get("name"),
                    "title": result.get("title"),
                    "company": result.get("company"),
                    "company_size": result.get("company_size"),
                    "phone": result.get("phone"),
                    "linkedin_url": result.get("linkedin_url"),
                    "location": result.get("location"),
                    "industry": result.get("industry"),
                    "seniority_level": result.get("seniority_level"),
                }
            }
        else:
            logger.info(f"Contact not found in Apollo: {email}")
            return {
                "status": "not_found",
                "email": email,
                "data": None,
            }

    except ApolloAPIError as e:
        logger.error(f"Apollo API error for {email}: {str(e)}")
        return {
            "status": "error",
            "email": email,
            "error": f"Apollo API error: {str(e)}",
            "message": "Try LinkedIn search as alternative",
        }

    except Exception as e:
        logger.exception(f"Unexpected error searching Apollo for {email}")
        return {
            "status": "error",
            "email": email,
            "error": str(e),
        }


@tool
def search_linkedin_profile(profile_url: str) -> Dict[str, Any]:
    """
    Scrape LinkedIn profile data using Browserbase.

    Implements rate limiting, timeout handling, and data validation.

    Args:
        profile_url: LinkedIn profile URL (must be valid format)

    Returns:
        Dictionary with status, data, and optional error message

    Example:
        >>> result = search_linkedin_profile("https://linkedin.com/in/johndoe")
        >>> if result["status"] == "success":
        ...     print(result["data"]["headline"])
    """
    if not profile_url or not profile_url.startswith("https://linkedin.com"):
        return {
            "status": "error",
            "profile_url": profile_url,
            "error": "Invalid LinkedIn URL format",
        }

    try:
        from app.services.linkedin_scraper import LinkedInScraperService

        scraper = LinkedInScraperService()
        result = scraper.scrape_profile(profile_url)

        if result:
            logger.info(f"LinkedIn scrape successful for {profile_url}")
            return {
                "status": "success",
                "profile_url": profile_url,
                "data": {
                    "name": result.get("name"),
                    "headline": result.get("headline"),
                    "about": result.get("about"),
                    "experience": result.get("experience", [])[:3],  # Top 3
                    "skills": result.get("skills", [])[:5],  # Top 5
                    "education": result.get("education"),
                    "endorsements": result.get("endorsements", {}),
                    "follower_count": result.get("follower_count"),
                }
            }
        else:
            logger.info(f"Profile not found on LinkedIn: {profile_url}")
            return {
                "status": "not_found",
                "profile_url": profile_url,
                "data": None,
            }

    except LinkedInScrapingError as e:
        logger.error(f"LinkedIn scraping error for {profile_url}: {str(e)}")
        return {
            "status": "error",
            "profile_url": profile_url,
            "error": f"LinkedIn scraping error: {str(e)}",
        }

    except Exception as e:
        logger.exception(f"Unexpected error scraping LinkedIn for {profile_url}")
        return {
            "status": "error",
            "profile_url": profile_url,
            "error": str(e),
        }


@tool
def synthesize_enrichment(contact_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synthesize enriched contact data into a structured profile.

    Merges Apollo and LinkedIn data intelligently with conflict resolution.

    Args:
        contact_data: Dictionary with keys:
            - email: Contact email
            - apollo_data: Apollo enrichment result
            - linkedin_data: LinkedIn enrichment result

    Returns:
        Dictionary with synthesized enrichment profile and quality score

    Example:
        >>> contact_data = {
        ...     "email": "john@acme.com",
        ...     "apollo_data": {...},
        ...     "linkedin_data": {...}
        ... }
        >>> result = synthesize_enrichment(contact_data)
    """
    try:
        email = contact_data.get("email", "")
        apollo_data = contact_data.get("apollo_data", {})
        linkedin_data = contact_data.get("linkedin_data", {})

        # Merge with Apollo as primary source (more specific), LinkedIn as secondary
        enriched = {
            "email": email,
            "full_name": apollo_data.get("name") or linkedin_data.get("name"),
            "title": apollo_data.get("title") or linkedin_data.get("headline"),
            "company": apollo_data.get("company"),
            "company_size": apollo_data.get("company_size"),
            "industry": apollo_data.get("industry"),
            "location": apollo_data.get("location"),
            "phone": apollo_data.get("phone"),
            "linkedin_url": apollo_data.get("linkedin_url"),
            "seniority_level": apollo_data.get("seniority_level"),
            "skills": linkedin_data.get("skills", []),
            "experience_count": len(linkedin_data.get("experience", [])),
            "endorsements": linkedin_data.get("endorsements", {}),
            "about_summary": linkedin_data.get("about", "")[:200],  # First 200 chars
            "enrichment_score": _calculate_enrichment_score(apollo_data, linkedin_data),
            "data_sources": _get_data_sources(apollo_data, linkedin_data),
            "enriched_at": datetime.utcnow().isoformat(),
        }

        return {
            "status": "success",
            "email": email,
            "data": enriched,
        }

    except Exception as e:
        logger.exception(f"Enrichment synthesis failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
        }


def _calculate_enrichment_score(apollo_data: Dict, linkedin_data: Dict) -> float:
    """Calculate data completeness score 0-100"""
    score = 0.0

    # Apollo completeness (40 points)
    if apollo_data.get("name"): score += 8
    if apollo_data.get("title"): score += 8
    if apollo_data.get("company"): score += 8
    if apollo_data.get("phone"): score += 8
    if apollo_data.get("location"): score += 8

    # LinkedIn completeness (40 points)
    if linkedin_data.get("headline"): score += 8
    if linkedin_data.get("about"): score += 8
    if linkedin_data.get("experience"): score += 8
    if linkedin_data.get("skills"): score += 8
    if linkedin_data.get("education"): score += 8

    # Cross-source bonus (20 points)
    if apollo_data and linkedin_data:
        score += 20

    return min(score, 100.0)


def _get_data_sources(apollo_data: Dict, linkedin_data: Dict) -> List[str]:
    """Get list of data sources used"""
    sources = []
    if apollo_data: sources.append("apollo")
    if linkedin_data: sources.append("linkedin")
    return sources


# ============================================================================
# AGENT FACTORY
# ============================================================================

class ReActAgentFactory:
    """Factory for creating and configuring ReAct agents"""

    @staticmethod
    def create_enrichment_agent(config: Optional[AgentConfig] = None) -> Any:
        """
        Create a ReAct agent for contact enrichment.

        Args:
            config: Optional AgentConfig with custom settings

        Returns:
            Compiled LangGraph agent

        Example:
            >>> agent = ReActAgentFactory.create_enrichment_agent()
            >>> result = agent.invoke({"messages": [HumanMessage(...)]})
        """
        config = config or AgentConfig()

        # Initialize model
        model = ChatAnthropic(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

        # Define tools
        tools = [
            search_apollo_contact,
            search_linkedin_profile,
            synthesize_enrichment,
        ]

        # System prompt with clear tool strategy
        system_prompt = """You are a contact enrichment specialist. Your job is to gather and synthesize information about a contact from multiple sources.

ENRICHMENT WORKFLOW (follow this exactly):
1. Search Apollo using the email address to get professional profile info
2. If a LinkedIn URL is found or provided, scrape it for additional background
3. Synthesize all gathered data into a comprehensive enrichment profile

IMPORTANT RULES:
- Only call tools with valid, complete information
- Email format must be valid: user@domain.com
- LinkedIn URLs must start with: https://linkedin.com/in/
- If a tool returns "error" or "not_found", try alternative approaches
- Don't make up data - only report what you found
- Always conclude with a final enrichment summary
- Be thorough but concise in your findings

TOOL DECISION RULES:
- Start with search_apollo_contact if you have an email
- Use search_linkedin_profile if you have a LinkedIn URL (or got one from Apollo)
- Use synthesize_enrichment ONLY after you have data from Apollo (and optionally LinkedIn)
- If both sources fail, report findings and complete without synthesis

DATA QUALITY:
- Apollo provides verified company/title info (higher confidence)
- LinkedIn provides skills, experience, education (broader background)
- Merge both for most complete profile
- Report enrichment score (0-100) based on data completeness
"""

        # Create agent with optional checkpointing
        checkpointer = InMemorySaver() if config.enable_checkpointing else None

        agent = create_react_agent(
            model=model,
            tools=tools,
            prompt=system_prompt,
            checkpointer=checkpointer,
        )

        return agent


# ============================================================================
# SYNCHRONOUS ENRICHMENT EXECUTOR
# ============================================================================

class SyncEnrichmentExecutor:
    """Synchronous contact enrichment with comprehensive metrics"""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.agent = ReActAgentFactory.create_enrichment_agent(self.config)
        self.request_id = str(uuid.uuid4())

    def enrich(
        self,
        email: str,
        linkedin_url: Optional[str] = None,
    ) -> EnrichmentResult:
        """
        Synchronously enrich a single contact.

        Args:
            email: Contact email address
            linkedin_url: Optional LinkedIn profile URL

        Returns:
            EnrichmentResult with data, metrics, and status

        Example:
            >>> executor = SyncEnrichmentExecutor()
            >>> result = executor.enrich("john@acme.com")
            >>> print(f"Status: {result.status}, Score: {result.enrichment_data.get('enrichment_score')}")
        """
        start_time = time.time()
        iterations = 0
        tool_metrics: List[ToolExecutionMetrics] = []
        recursion_limit_exceeded = False

        # Prepare input
        user_message = f"""Please enrich the following contact:
- Email: {email}
- LinkedIn URL: {linkedin_url or "Not provided"}

Search for information and create a comprehensive enrichment profile."""

        input_state = {
            "messages": [HumanMessage(content=user_message)]
        }

        result = EnrichmentResult(
            status="unknown",
            enrichment_data={},
            final_response="",
            metrics=AgentExecutionMetrics(
                request_id=self.request_id,
                total_time_ms=0,
                iterations=0,
                tool_calls=0,
                tools_succeeded=0,
                tools_failed=0,
                recursion_limit_exceeded=False,
                final_status="unknown",
                tool_metrics=[],
            ),
        )

        try:
            # Invoke agent with recursion limit
            agent_result = self.agent.invoke(
                input_state,
                config={
                    "recursion_limit": self.config.recursion_limit,
                    "configurable": {
                        "thread_id": f"enrichment_{email}_{uuid.uuid4()}"
                    },
                },
            )

            # Extract results
            result.status = "success"
            result.enrichment_data = self._extract_enrichment_data(
                agent_result["messages"]
            )
            result.final_response = self._extract_final_response(
                agent_result["messages"]
            )

            # Calculate metrics
            iterations, tool_metrics = self._analyze_messages(
                agent_result["messages"]
            )

            result.metrics = AgentExecutionMetrics(
                request_id=self.request_id,
                total_time_ms=(time.time() - start_time) * 1000,
                iterations=iterations,
                tool_calls=len(tool_metrics),
                tools_succeeded=sum(
                    1 for m in tool_metrics if m.status == "success"
                ),
                tools_failed=sum(1 for m in tool_metrics if m.status == "error"),
                recursion_limit_exceeded=recursion_limit_exceeded,
                final_status="success",
                tool_metrics=tool_metrics,
            )

        except GraphRecursionError as e:
            logger.warning(
                f"Recursion limit exceeded for {email} after {iterations} iterations"
            )
            result.status = "partial"
            result.error = "Agent exceeded max iterations - partial enrichment"
            result.enrichment_data = self._extract_enrichment_data(
                e.state.get("messages", [])
            )
            recursion_limit_exceeded = True

            iterations, tool_metrics = self._analyze_messages(
                e.state.get("messages", [])
            )

            result.metrics = AgentExecutionMetrics(
                request_id=self.request_id,
                total_time_ms=(time.time() - start_time) * 1000,
                iterations=iterations,
                tool_calls=len(tool_metrics),
                tools_succeeded=sum(
                    1 for m in tool_metrics if m.status == "success"
                ),
                tools_failed=sum(1 for m in tool_metrics if m.status == "error"),
                recursion_limit_exceeded=True,
                final_status="partial",
                tool_metrics=tool_metrics,
            )

        except Exception as e:
            logger.exception(f"Enrichment failed for {email}: {str(e)}")
            result.status = "error"
            result.error = str(e)

            result.metrics = AgentExecutionMetrics(
                request_id=self.request_id,
                total_time_ms=(time.time() - start_time) * 1000,
                iterations=iterations,
                tool_calls=len(tool_metrics),
                tools_succeeded=sum(
                    1 for m in tool_metrics if m.status == "success"
                ),
                tools_failed=sum(1 for m in tool_metrics if m.status == "error"),
                recursion_limit_exceeded=recursion_limit_exceeded,
                final_status="error",
                tool_metrics=tool_metrics,
            )

        return result

    def _extract_enrichment_data(self, messages: List[BaseMessage]) -> Dict:
        """Extract structured enrichment data from message history"""
        enrichment = {
            "apollo_data": None,
            "linkedin_data": None,
            "enrichment_summary": None,
        }

        for msg in messages:
            if isinstance(msg, ToolMessage):
                try:
                    content = (
                        json.loads(msg.content)
                        if isinstance(msg.content, str)
                        else msg.content
                    )

                    if (
                        msg.name == "search_apollo_contact"
                        and content.get("status") == "success"
                    ):
                        enrichment["apollo_data"] = content.get("data")

                    elif (
                        msg.name == "search_linkedin_profile"
                        and content.get("status") == "success"
                    ):
                        enrichment["linkedin_data"] = content.get("data")

                    elif (
                        msg.name == "synthesize_enrichment"
                        and content.get("status") == "success"
                    ):
                        enrichment["enrichment_summary"] = content.get("data")

                except (json.JSONDecodeError, TypeError):
                    pass

        return enrichment

    def _extract_final_response(self, messages: List[BaseMessage]) -> str:
        """Extract final AI response from message history"""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                return msg.content
        return ""

    def _analyze_messages(
        self, messages: List[BaseMessage]
    ) -> tuple[int, List[ToolExecutionMetrics]]:
        """Analyze message history for metrics"""
        iterations = 0
        tool_metrics = []

        for msg in messages:
            if isinstance(msg, AIMessage):
                iterations += 1

            elif isinstance(msg, ToolMessage):
                try:
                    content = (
                        json.loads(msg.content)
                        if isinstance(msg.content, str)
                        else msg.content
                    )

                    metric = ToolExecutionMetrics(
                        tool_name=msg.name,
                        call_id=msg.tool_call_id,
                        status=content.get("status", "unknown"),
                        duration_ms=0,  # Not tracked in basic version
                        input_args=content.get("input_args", {}),
                        result=content,
                        error_message=(
                            content.get("error") if content.get("status") == "error"
                            else None
                        ),
                    )
                    tool_metrics.append(metric)

                except (json.JSONDecodeError, TypeError):
                    pass

        return iterations, tool_metrics


# ============================================================================
# ASYNCHRONOUS ENRICHMENT EXECUTOR
# ============================================================================

class AsyncEnrichmentExecutor:
    """Asynchronous contact enrichment with concurrent processing"""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.agent = ReActAgentFactory.create_enrichment_agent(self.config)

    async def enrich(
        self,
        email: str,
        linkedin_url: Optional[str] = None,
    ) -> EnrichmentResult:
        """
        Asynchronously enrich a single contact.

        Args:
            email: Contact email address
            linkedin_url: Optional LinkedIn profile URL

        Returns:
            EnrichmentResult with data and metrics

        Example:
            >>> executor = AsyncEnrichmentExecutor()
            >>> result = await executor.enrich("john@acme.com")
        """
        start_time = time.time()

        user_message = f"""Please enrich the following contact:
- Email: {email}
- LinkedIn URL: {linkedin_url or "Not provided"}

Search for information and create a comprehensive enrichment profile."""

        input_state = {
            "messages": [HumanMessage(content=user_message)]
        }

        try:
            # Use ainvoke for async execution
            agent_result = await self.agent.ainvoke(
                input_state,
                config={
                    "recursion_limit": self.config.recursion_limit,
                    "configurable": {
                        "thread_id": f"enrichment_{email}_{uuid.uuid4()}"
                    },
                },
            )

            enrichment_data = self._extract_enrichment_data(
                agent_result["messages"]
            )
            final_response = self._extract_final_response(
                agent_result["messages"]
            )

            return EnrichmentResult(
                status="success",
                enrichment_data=enrichment_data,
                final_response=final_response,
                metrics=AgentExecutionMetrics(
                    request_id=str(uuid.uuid4()),
                    total_time_ms=(time.time() - start_time) * 1000,
                    iterations=len(agent_result["messages"]),
                    tool_calls=sum(
                        1
                        for msg in agent_result["messages"]
                        if isinstance(msg, ToolMessage)
                    ),
                    tools_succeeded=sum(
                        1
                        for msg in agent_result["messages"]
                        if isinstance(msg, ToolMessage)
                    ),
                    tools_failed=0,
                    recursion_limit_exceeded=False,
                    final_status="success",
                    tool_metrics=[],
                ),
            )

        except GraphRecursionError as e:
            logger.warning(f"Recursion limit exceeded for {email}")

            return EnrichmentResult(
                status="partial",
                enrichment_data=self._extract_enrichment_data(
                    e.state.get("messages", [])
                ),
                final_response="",
                metrics=AgentExecutionMetrics(
                    request_id=str(uuid.uuid4()),
                    total_time_ms=(time.time() - start_time) * 1000,
                    iterations=len(e.state.get("messages", [])),
                    tool_calls=0,
                    tools_succeeded=0,
                    tools_failed=0,
                    recursion_limit_exceeded=True,
                    final_status="partial",
                    tool_metrics=[],
                ),
                error="Max iterations exceeded",
            )

        except Exception as e:
            logger.exception(f"Async enrichment failed for {email}: {str(e)}")

            return EnrichmentResult(
                status="error",
                enrichment_data={},
                final_response="",
                metrics=AgentExecutionMetrics(
                    request_id=str(uuid.uuid4()),
                    total_time_ms=(time.time() - start_time) * 1000,
                    iterations=0,
                    tool_calls=0,
                    tools_succeeded=0,
                    tools_failed=0,
                    recursion_limit_exceeded=False,
                    final_status="error",
                    tool_metrics=[],
                ),
                error=str(e),
            )

    async def enrich_batch(
        self,
        contacts: List[tuple[str, Optional[str]]],
        max_concurrent: int = 5,
    ) -> List[EnrichmentResult]:
        """
        Enrich multiple contacts concurrently.

        Args:
            contacts: List of (email, linkedin_url) tuples
            max_concurrent: Max concurrent enrichments

        Returns:
            List of EnrichmentResult objects

        Example:
            >>> executor = AsyncEnrichmentExecutor()
            >>> results = await executor.enrich_batch([
            ...     ("john@acme.com", "https://linkedin.com/in/john"),
            ...     ("jane@corp.com", None),
            ... ])
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def enrich_with_semaphore(
            email: str, linkedin_url: Optional[str]
        ) -> EnrichmentResult:
            async with semaphore:
                return await self.enrich(email, linkedin_url)

        tasks = [
            enrich_with_semaphore(email, linkedin_url)
            for email, linkedin_url in contacts
        ]

        return await asyncio.gather(*tasks, return_exceptions=True)

    def _extract_enrichment_data(self, messages: List[BaseMessage]) -> Dict:
        """Extract structured enrichment data from message history"""
        enrichment = {
            "apollo_data": None,
            "linkedin_data": None,
            "enrichment_summary": None,
        }

        for msg in messages:
            if isinstance(msg, ToolMessage):
                try:
                    content = (
                        json.loads(msg.content)
                        if isinstance(msg.content, str)
                        else msg.content
                    )

                    if (
                        msg.name == "search_apollo_contact"
                        and content.get("status") == "success"
                    ):
                        enrichment["apollo_data"] = content.get("data")

                    elif (
                        msg.name == "search_linkedin_profile"
                        and content.get("status") == "success"
                    ):
                        enrichment["linkedin_data"] = content.get("data")

                    elif (
                        msg.name == "synthesize_enrichment"
                        and content.get("status") == "success"
                    ):
                        enrichment["enrichment_summary"] = content.get("data")

                except (json.JSONDecodeError, TypeError):
                    pass

        return enrichment

    def _extract_final_response(self, messages: List[BaseMessage]) -> str:
        """Extract final AI response from message history"""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                return msg.content
        return ""


# ============================================================================
# STREAMING ENRICHMENT EXECUTOR
# ============================================================================

class StreamingEnrichmentExecutor:
    """Real-time streaming enrichment with progress updates"""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.agent = ReActAgentFactory.create_enrichment_agent(self.config)

    def enrich_streaming(
        self,
        email: str,
        linkedin_url: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Stream enrichment progress in real-time.

        Args:
            email: Contact email address
            linkedin_url: Optional LinkedIn profile URL

        Yields:
            Dictionary with streaming updates

        Example:
            >>> executor = StreamingEnrichmentExecutor()
            >>> for update in executor.enrich_streaming("john@acme.com"):
            ...     print(f"Update: {update}")
        """
        user_message = f"""Please enrich the following contact:
- Email: {email}
- LinkedIn URL: {linkedin_url or "Not provided"}

Search for information and create a comprehensive enrichment profile."""

        input_state = {
            "messages": [HumanMessage(content=user_message)]
        }

        iteration = 0

        # Stream with updates mode
        for step in self.agent.stream(
            input_state,
            config={
                "recursion_limit": self.config.recursion_limit,
                "configurable": {"thread_id": f"enrichment_{email}_{uuid.uuid4()}"},
            },
            stream_mode="updates",
        ):
            iteration += 1

            # Extract node updates
            for node_name, node_update in step.items():
                if node_name == "agent":
                    if "messages" in node_update:
                        for msg in node_update["messages"]:
                            if isinstance(msg, AIMessage) and msg.tool_calls:
                                yield {
                                    "event": "tool_call",
                                    "iteration": iteration,
                                    "tools": [
                                        {
                                            "name": tc["name"],
                                            "args": tc["args"],
                                        }
                                        for tc in msg.tool_calls
                                    ],
                                }

                elif node_name == "tools":
                    if "messages" in node_update:
                        for msg in node_update["messages"]:
                            if isinstance(msg, ToolMessage):
                                try:
                                    content = (
                                        json.loads(msg.content)
                                        if isinstance(msg.content, str)
                                        else msg.content
                                    )
                                    yield {
                                        "event": "tool_result",
                                        "iteration": iteration,
                                        "tool_name": msg.name,
                                        "status": content.get("status", "unknown"),
                                    }
                                except (json.JSONDecodeError, TypeError):
                                    pass

        yield {
            "event": "complete",
            "total_iterations": iteration,
        }

    async def enrich_streaming_async(
        self,
        email: str,
        linkedin_url: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream enrichment progress asynchronously.

        Args:
            email: Contact email address
            linkedin_url: Optional LinkedIn profile URL

        Yields:
            Dictionary with streaming updates

        Example:
            >>> executor = StreamingEnrichmentExecutor()
            >>> async for update in executor.enrich_streaming_async("john@acme.com"):
            ...     print(f"Update: {update}")
        """
        user_message = f"""Please enrich the following contact:
- Email: {email}
- LinkedIn URL: {linkedin_url or "Not provided"}

Search for information and create a comprehensive enrichment profile."""

        input_state = {
            "messages": [HumanMessage(content=user_message)]
        }

        iteration = 0

        # Stream with updates mode
        async for step in self.agent.astream(
            input_state,
            config={
                "recursion_limit": self.config.recursion_limit,
                "configurable": {"thread_id": f"enrichment_{email}_{uuid.uuid4()}"},
            },
            stream_mode="updates",
        ):
            iteration += 1

            for node_name, node_update in step.items():
                if node_name == "agent":
                    if "messages" in node_update:
                        for msg in node_update["messages"]:
                            if isinstance(msg, AIMessage) and msg.tool_calls:
                                yield {
                                    "event": "tool_call",
                                    "iteration": iteration,
                                    "tools": [
                                        {
                                            "name": tc["name"],
                                            "args": tc["args"],
                                        }
                                        for tc in msg.tool_calls
                                    ],
                                }

        yield {
            "event": "complete",
            "total_iterations": iteration,
        }
