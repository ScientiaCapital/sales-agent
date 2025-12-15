"""
Scientia Capital MEP Orchestrator
Agentic loop for multi-model VLM extraction pipeline.

Architecture Pattern:
1. Sonnet/Opus (Orchestrator): Plans tasks, routes to tools, synthesizes
2. Qwen VL (Extractors): Cheap parallel vision extraction
3. DeepSeek (Reasoners): JSON validation and structured reasoning

The orchestrator runs an ReAct-style loop:
- Receive task
- Plan extraction strategy
- Dispatch N parallel extractions to Qwen VL
- Validate/repair with DeepSeek
- Compare results for consensus
- Synthesize final output
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from .schema import (
    MODELS,
    AgentConfig,
    AgentRole,
    AgentRun,
    AgentState,
    MEPExtraction,
    Message,
    MessageRole,
    Pipeline,
    Task,
    TaskType,
    ToolCall,
    ToolResult,
)
from .tools import (
    BaseTool,
    ExtractImageTool,
    ValidateJsonTool,
    CompareExtractionsTool,
    GenerateReportTool,
    get_tool,
)


class MEPOrchestrator:
    """
    Orchestrator for MEP extraction pipeline.

    Implements a ReAct-style agent loop:
    1. Observe: Receive task or tool results
    2. Think: Plan next action
    3. Act: Call tools or return final result

    Cost Optimization:
    - Uses Sonnet for orchestration (smart but expensive)
    - Dispatches to Qwen VL for extraction (cheap, parallel)
    - Uses DeepSeek for JSON validation (cheapest text)
    """

    def __init__(
        self,
        vlm_provider: Any = None,
        text_provider: Any = None,
        orchestrator_model: str = "claude-sonnet-4",
        extractor_model: str = "qwen-vl-72b",
        reasoner_model: str = "deepseek-chat",
        max_parallel_extractions: int = 3,
        verbose: bool = False,
    ):
        """
        Initialize the orchestrator.

        Args:
            vlm_provider: Provider for vision models (OpenRouter)
            text_provider: Provider for text models (Anthropic/OpenRouter)
            orchestrator_model: Model key for orchestration
            extractor_model: Model key for VLM extraction
            reasoner_model: Model key for JSON reasoning
            max_parallel_extractions: Max concurrent VLM calls
            verbose: Enable verbose logging
        """
        self.vlm_provider = vlm_provider
        self.text_provider = text_provider
        self.orchestrator_model = orchestrator_model
        self.extractor_model = extractor_model
        self.reasoner_model = reasoner_model
        self.max_parallel = max_parallel_extractions
        self.verbose = verbose

        # Initialize tools
        self._tools: dict[str, BaseTool] = {
            "extract_image": ExtractImageTool(provider=vlm_provider),
            "validate_json": ValidateJsonTool(provider=text_provider),
            "compare_extractions": CompareExtractionsTool(),
            "generate_report": GenerateReportTool(),
        }

        # Track runs
        self._runs: dict[str, AgentRun] = {}

    def log(self, message: str) -> None:
        """Log message if verbose."""
        if self.verbose:
            print(f"[Orchestrator] {message}")

    # =========================================================================
    # HIGH-LEVEL API
    # =========================================================================

    async def extract_image(
        self,
        image_path: Path,
        trade: Optional[str] = None,
        num_extractions: int = 1,
    ) -> MEPExtraction:
        """
        Extract data from a single image.

        Simple API for single-image extraction without full pipeline.

        Args:
            image_path: Path to image
            trade: Expected trade type
            num_extractions: Number of parallel extractions for consensus

        Returns:
            MEPExtraction result
        """
        if num_extractions == 1:
            # Single extraction
            tool = self._tools["extract_image"]
            result = await tool.execute(
                image_path=str(image_path),
                trade=trade,
                tool_call_id=str(uuid4())[:8],
            )

            if not result.success:
                raise RuntimeError(f"Extraction failed: {result.error}")

            return result.result

        # Multiple extractions for consensus
        extractions = await self._parallel_extract(
            image_path=image_path,
            trade=trade,
            num_extractions=num_extractions,
        )

        # Compare for consensus
        compare_tool = self._tools["compare_extractions"]
        comparison = await compare_tool.execute(
            extractions=[e.model_dump() for e in extractions],
            tool_call_id=str(uuid4())[:8],
        )

        if comparison.success and comparison.result:
            return comparison.result.consensus_extraction or extractions[0]

        return extractions[0]

    async def run_pipeline(
        self,
        image_paths: list[Path],
        trade: Optional[str] = None,
        parallel_images: int = 2,
        extractions_per_image: int = 1,
    ) -> dict[str, Any]:
        """
        Run extraction pipeline on multiple images.

        Args:
            image_paths: List of image paths
            trade: Expected trade type
            parallel_images: How many images to process in parallel
            extractions_per_image: Extractions per image for consensus

        Returns:
            Pipeline results with all extractions
        """
        pipeline_id = str(uuid4())
        self.log(f"Starting pipeline {pipeline_id[:8]} with {len(image_paths)} images")

        pipeline = Pipeline(
            pipeline_id=pipeline_id,
            name=f"MEP Extraction - {trade or 'multi-trade'}",
            status="running",
            started_at=datetime.utcnow(),
        )

        # Create tasks for each image
        for path in image_paths:
            task = Task(
                task_type=TaskType.EXTRACT_IMAGE,
                input_data={
                    "image_path": str(path),
                    "trade": trade,
                    "num_extractions": extractions_per_image,
                },
            )
            pipeline.add_task(task)

        # Process images in batches
        results = []
        for i in range(0, len(image_paths), parallel_images):
            batch = image_paths[i:i + parallel_images]
            batch_results = await asyncio.gather(*[
                self.extract_image(
                    image_path=path,
                    trade=trade,
                    num_extractions=extractions_per_image,
                )
                for path in batch
            ], return_exceptions=True)

            for path, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    self.log(f"Error on {path.name}: {result}")
                    results.append({
                        "path": str(path),
                        "success": False,
                        "error": str(result),
                    })
                else:
                    results.append({
                        "path": str(path),
                        "success": True,
                        "extraction": result.model_dump(),
                    })

        pipeline.status = "completed"
        pipeline.completed_at = datetime.utcnow()
        pipeline.total_cost_usd = sum(
            r.get("extraction", {}).get("cost_usd", 0)
            for r in results
            if r["success"]
        )

        # Generate report
        successful = [
            MEPExtraction(**r["extraction"])
            for r in results
            if r["success"]
        ]

        report_tool = self._tools["generate_report"]
        report_result = await report_tool.execute(
            extractions=[e.model_dump() for e in successful],
            format="json",
            tool_call_id=str(uuid4())[:8],
        )

        return {
            "pipeline_id": pipeline_id,
            "status": pipeline.status,
            "total_images": len(image_paths),
            "successful": len(successful),
            "failed": len(image_paths) - len(successful),
            "results": results,
            "report": report_result.result if report_result.success else None,
            "total_cost_usd": pipeline.total_cost_usd,
        }

    # =========================================================================
    # AGENT LOOP
    # =========================================================================

    async def run_agent_loop(
        self,
        initial_message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> AgentRun:
        """
        Run a full ReAct-style agent loop.

        This is the most flexible API - the orchestrator plans
        and executes based on the initial message.

        Args:
            initial_message: User request
            context: Optional context (image paths, trade, etc.)

        Returns:
            AgentRun with full history and results
        """
        # Create agent config
        config = AgentConfig(
            name="MEP Orchestrator",
            role=AgentRole.ORCHESTRATOR,
            model_config_key=self.orchestrator_model,
            system_prompt=self._get_system_prompt(),
            tools=[t.to_schema() for t in self._tools.values()],
        )

        # Initialize run
        run = AgentRun(
            agent_config=config,
            state=AgentState.PLANNING,
            started_at=datetime.utcnow(),
        )

        # Add initial message
        run.add_message(Message(
            role=MessageRole.USER,
            content=initial_message,
        ))

        self._runs[run.run_id] = run

        # Run loop
        try:
            while run.state not in [AgentState.COMPLETE, AgentState.ERROR]:
                # Check limits
                can_continue, reason = run.check_limits()
                if not can_continue:
                    run.state = AgentState.ERROR
                    run.errors.append(reason or "Unknown limit exceeded")
                    break

                # Execute one iteration
                await self._agent_iteration(run, context)
                run.iteration += 1

        except Exception as e:
            run.state = AgentState.ERROR
            run.errors.append(str(e))

        run.completed_at = datetime.utcnow()
        return run

    async def _agent_iteration(
        self,
        run: AgentRun,
        context: Optional[dict[str, Any]],
    ) -> None:
        """Execute one iteration of the agent loop."""
        self.log(f"Iteration {run.iteration}: State={run.state.value}")

        if run.state == AgentState.PLANNING:
            # Generate plan (in real impl, would call orchestrator LLM)
            await self._plan_next_action(run, context)

        elif run.state == AgentState.EXECUTING:
            # Execute pending tool calls
            await self._execute_tools(run)

        elif run.state == AgentState.PROCESSING_RESULT:
            # Process tool results (in real impl, would call orchestrator LLM)
            await self._process_results(run)

        elif run.state == AgentState.SYNTHESIZING:
            # Generate final output
            await self._synthesize_output(run)

    async def _plan_next_action(
        self,
        run: AgentRun,
        context: Optional[dict[str, Any]],
    ) -> None:
        """Plan the next action based on conversation state."""
        # For now, use simple heuristics
        # In production, would call the orchestrator LLM

        last_user_msg = None
        for msg in reversed(run.messages):
            if msg.role == MessageRole.USER:
                last_user_msg = msg.content
                break

        if context and "image_path" in context:
            # We have an image to extract
            tool_call = ToolCall(
                tool_name="extract_image",
                arguments={
                    "image_path": context["image_path"],
                    "trade": context.get("trade"),
                },
            )
            run.pending_tool_calls.append(tool_call)
            run.state = AgentState.EXECUTING
        else:
            # No clear action, complete
            run.state = AgentState.SYNTHESIZING

    async def _execute_tools(self, run: AgentRun) -> None:
        """Execute pending tool calls."""
        if not run.pending_tool_calls:
            run.state = AgentState.PROCESSING_RESULT
            return

        # Execute tools in parallel (up to limit)
        batch = run.pending_tool_calls[:self.max_parallel]
        run.pending_tool_calls = run.pending_tool_calls[self.max_parallel:]

        results = await asyncio.gather(*[
            self._execute_single_tool(call)
            for call in batch
        ], return_exceptions=True)

        for call, result in zip(batch, results):
            if isinstance(result, Exception):
                run.add_tool_result(ToolResult(
                    tool_call_id=call.id,
                    tool_name=call.tool_name,
                    success=False,
                    error=str(result),
                ))
            else:
                run.add_tool_result(result)

        # Continue executing if more pending
        if run.pending_tool_calls:
            run.state = AgentState.EXECUTING
        else:
            run.state = AgentState.PROCESSING_RESULT

    async def _execute_single_tool(self, call: ToolCall) -> ToolResult[Any]:
        """Execute a single tool call."""
        if call.tool_name not in self._tools:
            return ToolResult(
                tool_call_id=call.id,
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        tool = self._tools[call.tool_name]
        return await tool.execute(
            **call.arguments,
            tool_call_id=call.id,
        )

    async def _process_results(self, run: AgentRun) -> None:
        """Process tool results and decide next action."""
        # Check for errors
        errors = [r for r in run.tool_results if not r.success]
        if errors:
            self.log(f"Tool errors: {[e.error for e in errors]}")

        # Decide next state
        # In production, would call orchestrator LLM to decide

        # For now, if we have extraction results, synthesize
        extractions = [
            r.result
            for r in run.tool_results
            if r.success and r.tool_name == "extract_image"
        ]

        if extractions:
            run.state = AgentState.SYNTHESIZING
        elif run.pending_tool_calls:
            run.state = AgentState.EXECUTING
        else:
            run.state = AgentState.COMPLETE

    async def _synthesize_output(self, run: AgentRun) -> None:
        """Generate final output from results."""
        # Gather all extraction results
        extractions = [
            r.result
            for r in run.tool_results
            if r.success and r.tool_name == "extract_image"
        ]

        if extractions:
            # Generate report
            report_tool = self._tools["generate_report"]
            report = await report_tool.execute(
                extractions=[e.model_dump() for e in extractions],
                format="summary",
                tool_call_id=str(uuid4())[:8],
            )

            run.add_message(Message(
                role=MessageRole.ASSISTANT,
                content=f"Extraction complete. {report.result}",
            ))
        else:
            run.add_message(Message(
                role=MessageRole.ASSISTANT,
                content="No extractions completed.",
            ))

        run.state = AgentState.COMPLETE

    # =========================================================================
    # HELPERS
    # =========================================================================

    async def _parallel_extract(
        self,
        image_path: Path,
        trade: Optional[str],
        num_extractions: int,
    ) -> list[MEPExtraction]:
        """Run parallel extractions on same image."""
        tool = self._tools["extract_image"]

        # Run extractions in parallel
        results = await asyncio.gather(*[
            tool.execute(
                image_path=str(image_path),
                trade=trade,
                tool_call_id=str(uuid4())[:8],
            )
            for _ in range(num_extractions)
        ], return_exceptions=True)

        # Collect successful extractions
        extractions = []
        for result in results:
            if isinstance(result, Exception):
                self.log(f"Extraction error: {result}")
            elif result.success and result.result:
                extractions.append(result.result)

        return extractions

    def _get_system_prompt(self) -> str:
        """Get system prompt for orchestrator."""
        return """You are an MEP (Mechanical, Electrical, Plumbing) extraction orchestrator.

Your role is to coordinate the extraction of structured data from construction images.

Available tools:
- extract_image: Extract MEP data from an image using vision models
- validate_json: Validate and repair JSON extraction results
- compare_extractions: Compare multiple extractions for consensus
- generate_report: Generate final extraction report

Cost optimization:
- Use extract_image for vision tasks (uses cheap Qwen VL models)
- Use validate_json for JSON repair (uses cheap DeepSeek models)
- Only use your own reasoning for planning and synthesis

Process:
1. Receive extraction request
2. Plan extraction strategy
3. Dispatch extraction tools
4. Validate and compare results
5. Synthesize final output

Always aim for accuracy while minimizing costs."""

    def get_run(self, run_id: str) -> Optional[AgentRun]:
        """Get a run by ID."""
        return self._runs.get(run_id)

    def get_metrics(self) -> dict[str, Any]:
        """Get orchestrator metrics."""
        total_runs = len(self._runs)
        completed = sum(1 for r in self._runs.values() if r.state == AgentState.COMPLETE)
        failed = sum(1 for r in self._runs.values() if r.state == AgentState.ERROR)
        total_cost = sum(r.total_cost_usd for r in self._runs.values())

        return {
            "total_runs": total_runs,
            "completed": completed,
            "failed": failed,
            "in_progress": total_runs - completed - failed,
            "total_cost_usd": total_cost,
            "avg_cost_per_run": total_cost / total_runs if total_runs > 0 else 0,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def quick_extract(
    image_path: Path,
    trade: Optional[str] = None,
    vlm_provider: Any = None,
) -> MEPExtraction:
    """
    Quick extraction without full orchestrator setup.

    Args:
        image_path: Path to image
        trade: Expected trade type
        vlm_provider: VLM provider instance

    Returns:
        MEPExtraction result
    """
    orchestrator = MEPOrchestrator(vlm_provider=vlm_provider)
    return await orchestrator.extract_image(image_path, trade)


async def batch_extract(
    image_paths: list[Path],
    trade: Optional[str] = None,
    vlm_provider: Any = None,
    parallel: int = 2,
) -> dict[str, Any]:
    """
    Batch extraction for multiple images.

    Args:
        image_paths: List of image paths
        trade: Expected trade type
        vlm_provider: VLM provider instance
        parallel: Number of parallel extractions

    Returns:
        Pipeline results
    """
    orchestrator = MEPOrchestrator(vlm_provider=vlm_provider)
    return await orchestrator.run_pipeline(
        image_paths=image_paths,
        trade=trade,
        parallel_images=parallel,
    )
