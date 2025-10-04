"""
Multi-Agent Research Pipeline

5-agent pipeline for ultra-fast research synthesis:
1. QueryGenerator: Creates optimized search queries
2. WebSearcher: Executes parallel web searches
3. Summarizer: Extracts key information
4. Synthesizer: Combines insights
5. Formatter: Produces final polished output

Target: <10s total execution time using Cerebras ultra-fast inference.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import json

from app.services.cerebras_routing import CerebrasRouter, CerebrasAccessMethod

logger = logging.getLogger(__name__)


class ResearchAgent(str, Enum):
    """Research pipeline agents."""
    QUERY_GENERATOR = "query_generator"
    WEB_SEARCHER = "web_searcher"
    SUMMARIZER = "summarizer"
    SYNTHESIZER = "synthesizer"
    FORMATTER = "formatter"


@dataclass
class AgentExecution:
    """Single agent execution result."""
    agent: ResearchAgent
    input_data: Any
    output_data: Any
    latency_ms: int
    cost_usd: float
    timestamp: str
    success: bool
    error: Optional[str] = None


@dataclass
class ResearchResult:
    """Complete research pipeline result."""
    research_topic: str
    final_output: str
    agent_executions: List[AgentExecution]
    total_latency_ms: int
    total_cost_usd: float
    queries_generated: List[str]
    search_results_count: int
    metadata: Dict[str, Any]


class ResearchPipeline:
    """
    Multi-agent research pipeline with ultra-fast execution.

    Pipeline:
    1. QueryGenerator: Create 3-5 optimized search queries
    2. WebSearcher: Execute searches (simulated/external API)
    3. Summarizer: Extract key points from each result
    4. Synthesizer: Combine insights into coherent narrative
    5. Formatter: Polish final output

    Target: <10s total execution
    """

    def __init__(
        self,
        router: Optional[CerebrasRouter] = None,
        preferred_method: CerebrasAccessMethod = CerebrasAccessMethod.DIRECT,
        max_queries: int = 5,
        max_results_per_query: int = 3,
        timeout_seconds: float = 10.0
    ):
        """
        Initialize research pipeline.

        Args:
            router: CerebrasRouter instance
            preferred_method: Preferred Cerebras access method
            max_queries: Maximum search queries to generate
            max_results_per_query: Max results per search query
            timeout_seconds: Total pipeline timeout
        """
        self.router = router or CerebrasRouter()
        self.preferred_method = preferred_method
        self.max_queries = max_queries
        self.max_results_per_query = max_results_per_query
        self.timeout_seconds = timeout_seconds

        self.executions: List[AgentExecution] = []
        self.total_cost = 0.0
        self.total_latency = 0

        logger.info(
            f"Initialized ResearchPipeline: "
            f"method={preferred_method.value}, "
            f"max_queries={max_queries}, "
            f"timeout={timeout_seconds}s"
        )

    async def research(
        self,
        topic: str,
        depth: str = "medium",
        format_style: str = "markdown",
        temperature: float = 0.7
    ) -> ResearchResult:
        """
        Execute complete research pipeline.

        Args:
            topic: Research topic or question
            depth: Research depth (shallow|medium|deep)
            format_style: Output format (markdown|json|plain)
            temperature: Model temperature

        Returns:
            ResearchResult with final output and execution metrics
        """
        start_time = datetime.now()
        self.executions = []
        self.total_cost = 0.0
        self.total_latency = 0

        logger.info(f"Starting research pipeline: {topic[:100]}...")

        try:
            # Execute pipeline with timeout
            result = await asyncio.wait_for(
                self._execute_pipeline(topic, depth, format_style, temperature),
                timeout=self.timeout_seconds
            )

            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds() * 1000

            result.total_latency_ms = int(total_duration)
            result.metadata["pipeline_timeout"] = self.timeout_seconds
            result.metadata["completed_within_timeout"] = True

            logger.info(
                f"Research complete: {total_duration:.0f}ms "
                f"(target: <{self.timeout_seconds * 1000}ms), "
                f"${result.total_cost_usd:.6f}"
            )

            return result

        except asyncio.TimeoutError:
            logger.error(f"Pipeline timeout after {self.timeout_seconds}s")
            # Return partial results
            return ResearchResult(
                research_topic=topic,
                final_output="[TIMEOUT] Research pipeline exceeded time limit",
                agent_executions=self.executions,
                total_latency_ms=int(self.timeout_seconds * 1000),
                total_cost_usd=self.total_cost,
                queries_generated=[],
                search_results_count=0,
                metadata={
                    "completed_within_timeout": False,
                    "timeout_seconds": self.timeout_seconds,
                    "agents_completed": len(self.executions)
                }
            )

    async def stream_research(
        self,
        topic: str,
        depth: str = "medium",
        format_style: str = "markdown",
        temperature: float = 0.7
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute research pipeline with streaming progress.

        Yields:
            Dict with type ("agent_start"|"agent_complete"|"final"|"error")
        """
        yield {
            "type": "pipeline_start",
            "topic": topic,
            "target_time": f"<{self.timeout_seconds}s"
        }

        try:
            # Agent 1: Query Generator
            yield {"type": "agent_start", "agent": ResearchAgent.QUERY_GENERATOR.value}
            queries = await self._generate_queries(topic, depth, temperature)
            yield {
                "type": "agent_complete",
                "agent": ResearchAgent.QUERY_GENERATOR.value,
                "queries": queries
            }

            # Agent 2: Web Searcher (simulated)
            yield {"type": "agent_start", "agent": ResearchAgent.WEB_SEARCHER.value}
            search_results = await self._execute_searches(queries, temperature)
            yield {
                "type": "agent_complete",
                "agent": ResearchAgent.WEB_SEARCHER.value,
                "results_count": len(search_results)
            }

            # Agent 3: Summarizer
            yield {"type": "agent_start", "agent": ResearchAgent.SUMMARIZER.value}
            summaries = await self._summarize_results(search_results, temperature)
            yield {
                "type": "agent_complete",
                "agent": ResearchAgent.SUMMARIZER.value,
                "summaries_count": len(summaries)
            }

            # Agent 4: Synthesizer
            yield {"type": "agent_start", "agent": ResearchAgent.SYNTHESIZER.value}
            synthesis = await self._synthesize_insights(topic, summaries, temperature)
            yield {
                "type": "agent_complete",
                "agent": ResearchAgent.SYNTHESIZER.value,
                "synthesis_preview": synthesis[:200] + "..."
            }

            # Agent 5: Formatter
            yield {"type": "agent_start", "agent": ResearchAgent.FORMATTER.value}
            formatted_output = await self._format_output(
                topic, synthesis, format_style, temperature
            )
            yield {
                "type": "agent_complete",
                "agent": ResearchAgent.FORMATTER.value
            }

            # Final result
            yield {
                "type": "final",
                "final_output": formatted_output,
                "total_latency_ms": self.total_latency,
                "total_cost_usd": self.total_cost,
                "queries_generated": queries,
                "search_results_count": len(search_results)
            }

        except Exception as e:
            logger.error(f"Streaming research failed: {str(e)}", exc_info=True)
            yield {
                "type": "error",
                "message": str(e),
                "agent_executions": len(self.executions)
            }

    async def _execute_pipeline(
        self,
        topic: str,
        depth: str,
        format_style: str,
        temperature: float
    ) -> ResearchResult:
        """Execute full research pipeline."""
        # Agent 1: Generate queries
        queries = await self._generate_queries(topic, depth, temperature)

        # Agent 2: Execute searches
        search_results = await self._execute_searches(queries, temperature)

        # Agent 3: Summarize results
        summaries = await self._summarize_results(search_results, temperature)

        # Agent 4: Synthesize insights
        synthesis = await self._synthesize_insights(topic, summaries, temperature)

        # Agent 5: Format output
        formatted_output = await self._format_output(
            topic, synthesis, format_style, temperature
        )

        return ResearchResult(
            research_topic=topic,
            final_output=formatted_output,
            agent_executions=self.executions,
            total_latency_ms=self.total_latency,
            total_cost_usd=self.total_cost,
            queries_generated=queries,
            search_results_count=len(search_results),
            metadata={
                "depth": depth,
                "format_style": format_style,
                "agents_executed": len(self.executions),
                "preferred_method": self.preferred_method.value
            }
        )

    async def _generate_queries(
        self,
        topic: str,
        depth: str,
        temperature: float
    ) -> List[str]:
        """Agent 1: Generate optimized search queries."""
        start_time = datetime.now()

        prompt = f"""Generate {self.max_queries} optimized search queries for researching this topic:

TOPIC: {topic}
DEPTH: {depth}

Create queries that:
1. Cover different aspects of the topic
2. Are specific and actionable
3. Will yield high-quality results
4. Range from broad to specific

Format: Return ONLY a JSON array of query strings, like: ["query 1", "query 2", ...]"""

        try:
            response = await self.router.route_inference(
                prompt=prompt,
                preferred_method=self.preferred_method,
                temperature=temperature,
                max_tokens=300
            )

            # Parse JSON array from response
            queries = self._extract_json_array(response.content)

            # Record execution
            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._record_execution(
                agent=ResearchAgent.QUERY_GENERATOR,
                input_data={"topic": topic, "depth": depth},
                output_data=queries,
                latency_ms=latency_ms,
                cost_usd=response.cost_usd,
                success=True
            )

            return queries[:self.max_queries]

        except Exception as e:
            logger.error(f"Query generation failed: {str(e)}")
            # Fallback to simple query
            fallback_queries = [topic]
            self._record_execution(
                agent=ResearchAgent.QUERY_GENERATOR,
                input_data={"topic": topic},
                output_data=fallback_queries,
                latency_ms=0,
                cost_usd=0.0,
                success=False,
                error=str(e)
            )
            return fallback_queries

    async def _execute_searches(
        self,
        queries: List[str],
        temperature: float
    ) -> List[Dict[str, str]]:
        """Agent 2: Execute web searches (simulated with LLM knowledge)."""
        start_time = datetime.now()

        # Simulate search by asking LLM to provide relevant information
        search_prompt = f"""For these search queries, provide factual information from your knowledge:

QUERIES:
{json.dumps(queries, indent=2)}

For EACH query, provide:
1. Key facts and data
2. Relevant concepts
3. Important context

Format: Return a JSON array of objects with 'query' and 'findings' keys.
Example: [{{"query": "...", "findings": "..."}}]"""

        try:
            response = await self.router.route_inference(
                prompt=search_prompt,
                preferred_method=self.preferred_method,
                temperature=temperature,
                max_tokens=800
            )

            # Parse search results
            results = self._extract_json_array(response.content)

            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._record_execution(
                agent=ResearchAgent.WEB_SEARCHER,
                input_data=queries,
                output_data=results,
                latency_ms=latency_ms,
                cost_usd=response.cost_usd,
                success=True
            )

            return results

        except Exception as e:
            logger.error(f"Search execution failed: {str(e)}")
            fallback_results = [{"query": q, "findings": "No results"} for q in queries]
            self._record_execution(
                agent=ResearchAgent.WEB_SEARCHER,
                input_data=queries,
                output_data=fallback_results,
                latency_ms=0,
                cost_usd=0.0,
                success=False,
                error=str(e)
            )
            return fallback_results

    async def _summarize_results(
        self,
        search_results: List[Dict[str, str]],
        temperature: float
    ) -> List[str]:
        """Agent 3: Summarize search results."""
        start_time = datetime.now()

        summarize_prompt = f"""Summarize these research findings concisely:

FINDINGS:
{json.dumps(search_results, indent=2)}

For each finding:
1. Extract 2-3 key points
2. Focus on facts and insights
3. Be concise but complete

Format: Return a JSON array of summary strings."""

        try:
            response = await self.router.route_inference(
                prompt=summarize_prompt,
                preferred_method=self.preferred_method,
                temperature=temperature,
                max_tokens=600
            )

            summaries = self._extract_json_array(response.content)

            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._record_execution(
                agent=ResearchAgent.SUMMARIZER,
                input_data=search_results,
                output_data=summaries,
                latency_ms=latency_ms,
                cost_usd=response.cost_usd,
                success=True
            )

            return summaries

        except Exception as e:
            logger.error(f"Summarization failed: {str(e)}")
            fallback_summaries = [r.get("findings", "") for r in search_results]
            self._record_execution(
                agent=ResearchAgent.SUMMARIZER,
                input_data=search_results,
                output_data=fallback_summaries,
                latency_ms=0,
                cost_usd=0.0,
                success=False,
                error=str(e)
            )
            return fallback_summaries

    async def _synthesize_insights(
        self,
        topic: str,
        summaries: List[str],
        temperature: float
    ) -> str:
        """Agent 4: Synthesize insights into coherent narrative."""
        start_time = datetime.now()

        synthesize_prompt = f"""Synthesize these research summaries into a coherent answer:

TOPIC: {topic}

SUMMARIES:
{json.dumps(summaries, indent=2)}

Create a comprehensive synthesis that:
1. Directly addresses the topic
2. Integrates insights from all summaries
3. Provides clear, actionable information
4. Maintains logical flow

Write the synthesis:"""

        try:
            response = await self.router.route_inference(
                prompt=synthesize_prompt,
                preferred_method=self.preferred_method,
                temperature=temperature,
                max_tokens=1000
            )

            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._record_execution(
                agent=ResearchAgent.SYNTHESIZER,
                input_data={"topic": topic, "summaries": summaries},
                output_data=response.content,
                latency_ms=latency_ms,
                cost_usd=response.cost_usd,
                success=True
            )

            return response.content

        except Exception as e:
            logger.error(f"Synthesis failed: {str(e)}")
            fallback_synthesis = "\n\n".join(summaries)
            self._record_execution(
                agent=ResearchAgent.SYNTHESIZER,
                input_data={"topic": topic, "summaries": summaries},
                output_data=fallback_synthesis,
                latency_ms=0,
                cost_usd=0.0,
                success=False,
                error=str(e)
            )
            return fallback_synthesis

    async def _format_output(
        self,
        topic: str,
        synthesis: str,
        format_style: str,
        temperature: float
    ) -> str:
        """Agent 5: Format final output."""
        start_time = datetime.now()

        format_prompt = f"""Format this research synthesis in {format_style} style:

TOPIC: {topic}

SYNTHESIS:
{synthesis}

Requirements:
- Professional and clear
- Well-structured with headings
- Easy to read and actionable
- Format: {format_style}

Provide the formatted output:"""

        try:
            response = await self.router.route_inference(
                prompt=format_prompt,
                preferred_method=self.preferred_method,
                temperature=temperature,
                max_tokens=1200
            )

            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._record_execution(
                agent=ResearchAgent.FORMATTER,
                input_data={"synthesis": synthesis, "format_style": format_style},
                output_data=response.content,
                latency_ms=latency_ms,
                cost_usd=response.cost_usd,
                success=True
            )

            return response.content

        except Exception as e:
            logger.error(f"Formatting failed: {str(e)}")
            # Return synthesis as-is
            self._record_execution(
                agent=ResearchAgent.FORMATTER,
                input_data={"synthesis": synthesis},
                output_data=synthesis,
                latency_ms=0,
                cost_usd=0.0,
                success=False,
                error=str(e)
            )
            return synthesis

    def _extract_json_array(self, text: str) -> List:
        """Extract JSON array from text response."""
        import re

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON array in text
        array_pattern = r'\[.*?\]'
        match = re.search(array_pattern, text, re.DOTALL)

        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Fallback: split by lines
        logger.warning(f"Could not parse JSON array, using fallback")
        return [text]

    def _record_execution(
        self,
        agent: ResearchAgent,
        input_data: Any,
        output_data: Any,
        latency_ms: int,
        cost_usd: float,
        success: bool,
        error: Optional[str] = None
    ):
        """Record agent execution."""
        execution = AgentExecution(
            agent=agent,
            input_data=input_data,
            output_data=output_data,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            timestamp=datetime.now().isoformat(),
            success=success,
            error=error
        )

        self.executions.append(execution)
        self.total_cost += cost_usd
        self.total_latency += latency_ms

        logger.debug(
            f"Agent {agent.value}: {latency_ms}ms, "
            f"${cost_usd:.6f}, success={success}"
        )

    def get_status(self) -> Dict[str, Any]:
        """Get pipeline status."""
        return {
            "preferred_method": self.preferred_method.value,
            "max_queries": self.max_queries,
            "timeout_seconds": self.timeout_seconds,
            "executions_completed": len(self.executions),
            "total_cost_usd": self.total_cost,
            "total_latency_ms": self.total_latency,
            "router_status": self.router.get_status()
        }
