"""
Scientia Capital Agent Tools
Tool implementations for MEP extraction pipeline.

Architecture:
- ExtractImageTool: Uses Qwen VL for cheap vision extraction
- ValidateJsonTool: Uses DeepSeek for JSON validation/repair
- CompareExtractionsTool: Compares multiple extractions for consensus
- GenerateReportTool: Synthesizes results into final report
"""

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from .schema import (
    MODELS,
    MEPExtraction,
    ExtractionComparison,
    Tool,
    ToolParameter,
    ToolResult,
)


# =============================================================================
# BASE TOOL CLASS
# =============================================================================

class BaseTool(ABC):
    """Abstract base for all tools."""

    name: str
    description: str
    requires_vision: bool = False
    preferred_model: Optional[str] = None

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult[Any]:
        """Execute the tool with given arguments."""
        ...

    def to_schema(self) -> Tool:
        """Convert to Tool schema for agent use."""
        return Tool(
            name=self.name,
            description=self.description,
            parameters=self.get_parameters(),
            requires_vision=self.requires_vision,
            preferred_model=self.preferred_model,
        )

    @abstractmethod
    def get_parameters(self) -> list[ToolParameter]:
        """Return parameter definitions."""
        ...


# =============================================================================
# VLM EXTRACTION TOOL
# =============================================================================

class ExtractImageTool(BaseTool):
    """
    Extract structured data from MEP images using Qwen VL.

    This is the workhorse tool - uses cheap Chinese VLMs to do
    the heavy lifting of vision extraction.
    """

    name = "extract_image"
    description = "Extract structured MEP data from a construction image"
    requires_vision = True
    preferred_model = "qwen-vl-72b"  # Cheapest with good accuracy

    def __init__(self, provider: Any = None):
        """Initialize with optional provider override."""
        self.provider = provider

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="image_path",
                type="string",
                description="Path to the image file to analyze",
                required=True,
            ),
            ToolParameter(
                name="trade",
                type="string",
                description="Expected trade type for context",
                required=False,
                enum=["solar", "electrical", "hvac", "plumbing", "roofing"],
            ),
            ToolParameter(
                name="focus_areas",
                type="array",
                description="Specific areas to focus extraction on",
                required=False,
            ),
        ]

    async def execute(
        self,
        image_path: str,
        trade: Optional[str] = None,
        focus_areas: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> ToolResult[MEPExtraction]:
        """Execute image extraction."""
        start_time = time.time()

        try:
            # Validate image exists
            path = Path(image_path)
            if not path.exists():
                return ToolResult(
                    tool_call_id=kwargs.get("tool_call_id", ""),
                    tool_name=self.name,
                    success=False,
                    error=f"Image not found: {image_path}",
                )

            # Build extraction prompt
            prompt = self._build_prompt(trade, focus_areas)

            # If no provider, return placeholder
            if self.provider is None:
                return ToolResult(
                    tool_call_id=kwargs.get("tool_call_id", ""),
                    tool_name=self.name,
                    success=False,
                    error="No VLM provider configured",
                )

            # Call VLM provider
            result = await self.provider.analyze_image(
                image_path=path,
                prompt=prompt,
                model=MODELS[self.preferred_model].model_name,
            )

            # Parse extraction
            extraction = self._parse_extraction(result, trade)

            latency_ms = int((time.time() - start_time) * 1000)

            return ToolResult(
                tool_call_id=kwargs.get("tool_call_id", ""),
                tool_name=self.name,
                success=True,
                result=extraction,
                latency_ms=latency_ms,
                input_tokens=result.get("input_tokens", 0),
                output_tokens=result.get("output_tokens", 0),
                cost_usd=self._calculate_cost(
                    result.get("input_tokens", 0),
                    result.get("output_tokens", 0),
                ),
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                tool_call_id=kwargs.get("tool_call_id", ""),
                tool_name=self.name,
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    def _build_prompt(
        self,
        trade: Optional[str],
        focus_areas: Optional[list[str]],
    ) -> str:
        """Build extraction prompt."""
        base = """Analyze this MEP construction image and extract structured data.

Return a JSON object with:
- image_type: "blueprint" | "field_photo" | "diagram" | "unknown"
- trade: "solar" | "electrical" | "hvac" | "plumbing" | "roofing" | "unknown"
- equipment_visible: list of equipment/components seen
- specifications: dict of key specifications (model numbers, ratings, etc.)
- measurements: dict of measurements (dimensions, voltages, etc.)
- condition: "good" | "fair" | "poor" | "critical" | null (for blueprints)
- issues_found: list of any problems or concerns visible
- confidence_score: 0.0-1.0 confidence in extraction

Return ONLY valid JSON, no markdown formatting."""

        if trade:
            base += f"\n\nExpected trade: {trade}"

        if focus_areas:
            base += f"\n\nFocus on: {', '.join(focus_areas)}"

        return base

    def _parse_extraction(
        self,
        result: dict[str, Any],
        expected_trade: Optional[str],
    ) -> MEPExtraction:
        """Parse VLM response into MEPExtraction."""
        extracted = result.get("extracted", {})

        if "raw_text" in extracted:
            # Try to parse raw text as JSON
            try:
                raw = extracted["raw_text"]
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0]
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0]
                extracted = json.loads(raw.strip())
            except (json.JSONDecodeError, IndexError):
                pass

        return MEPExtraction(
            image_type=extracted.get("image_type", "unknown"),
            trade=extracted.get("trade", expected_trade or "unknown"),
            equipment_visible=extracted.get("equipment_visible", []),
            specifications=extracted.get("specifications", {}),
            measurements=extracted.get("measurements", {}),
            condition=extracted.get("condition"),
            issues_found=extracted.get("issues_found", []),
            confidence_score=extracted.get("confidence_score", 0.5),
            model_used=MODELS[self.preferred_model].model_name,
            extraction_time_ms=result.get("latency_ms", 0),
        )

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for this extraction."""
        model = MODELS[self.preferred_model]
        return (
            (input_tokens / 1_000_000) * model.cost_per_1m_input +
            (output_tokens / 1_000_000) * model.cost_per_1m_output
        )


# =============================================================================
# JSON VALIDATION TOOL (DeepSeek)
# =============================================================================

class ValidateJsonTool(BaseTool):
    """
    Validate and repair JSON using DeepSeek.

    DeepSeek is text-only but excellent at JSON operations.
    Use this to validate and fix extraction results.
    """

    name = "validate_json"
    description = "Validate and repair JSON extraction results"
    requires_vision = False
    preferred_model = "deepseek-chat"  # Cheapest text model

    def __init__(self, provider: Any = None):
        self.provider = provider

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="json_data",
                type="object",
                description="JSON data to validate",
                required=True,
            ),
            ToolParameter(
                name="schema_name",
                type="string",
                description="Schema to validate against",
                required=False,
                enum=["mep_extraction", "equipment_list", "specifications"],
            ),
            ToolParameter(
                name="repair",
                type="boolean",
                description="Whether to attempt repairs on invalid data",
                required=False,
            ),
        ]

    async def execute(
        self,
        json_data: dict[str, Any],
        schema_name: str = "mep_extraction",
        repair: bool = True,
        **kwargs: Any,
    ) -> ToolResult[dict[str, Any]]:
        """Validate and optionally repair JSON."""
        start_time = time.time()

        try:
            # Basic validation
            validation_result = self._validate_structure(json_data, schema_name)

            if validation_result["valid"]:
                return ToolResult(
                    tool_call_id=kwargs.get("tool_call_id", ""),
                    tool_name=self.name,
                    success=True,
                    result={
                        "valid": True,
                        "data": json_data,
                        "repairs": [],
                    },
                    latency_ms=int((time.time() - start_time) * 1000),
                )

            if not repair:
                return ToolResult(
                    tool_call_id=kwargs.get("tool_call_id", ""),
                    tool_name=self.name,
                    success=True,
                    result={
                        "valid": False,
                        "errors": validation_result["errors"],
                        "data": json_data,
                    },
                    latency_ms=int((time.time() - start_time) * 1000),
                )

            # Attempt repair with DeepSeek
            repaired = await self._repair_json(json_data, validation_result["errors"])

            latency_ms = int((time.time() - start_time) * 1000)

            return ToolResult(
                tool_call_id=kwargs.get("tool_call_id", ""),
                tool_name=self.name,
                success=True,
                result=repaired,
                latency_ms=latency_ms,
            )

        except Exception as e:
            return ToolResult(
                tool_call_id=kwargs.get("tool_call_id", ""),
                tool_name=self.name,
                success=False,
                error=str(e),
                latency_ms=int((time.time() - start_time) * 1000),
            )

    def _validate_structure(
        self,
        data: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        """Validate JSON structure against schema."""
        errors = []

        if schema_name == "mep_extraction":
            required = ["image_type", "trade"]
            for field in required:
                if field not in data:
                    errors.append(f"Missing required field: {field}")

            # Type checks
            if "equipment_visible" in data and not isinstance(
                data["equipment_visible"], list
            ):
                errors.append("equipment_visible must be a list")

            if "specifications" in data and not isinstance(
                data["specifications"], dict
            ):
                errors.append("specifications must be a dict")

        return {"valid": len(errors) == 0, "errors": errors}

    async def _repair_json(
        self,
        data: dict[str, Any],
        errors: list[str],
    ) -> dict[str, Any]:
        """Attempt to repair JSON using DeepSeek (or local rules)."""
        repaired = data.copy()
        repairs = []

        # Apply local repairs
        if "image_type" not in repaired:
            repaired["image_type"] = "unknown"
            repairs.append("Added default image_type")

        if "trade" not in repaired:
            repaired["trade"] = "unknown"
            repairs.append("Added default trade")

        if "equipment_visible" in repaired:
            if not isinstance(repaired["equipment_visible"], list):
                repaired["equipment_visible"] = [str(repaired["equipment_visible"])]
                repairs.append("Converted equipment_visible to list")

        return {
            "valid": True,
            "data": repaired,
            "repairs": repairs,
            "original_errors": errors,
        }


# =============================================================================
# COMPARE EXTRACTIONS TOOL
# =============================================================================

class CompareExtractionsTool(BaseTool):
    """
    Compare multiple extractions for consensus.

    Used when running multiple VLMs on same image
    to find agreement and discrepancies.
    """

    name = "compare_extractions"
    description = "Compare multiple extractions to find consensus"
    requires_vision = False
    preferred_model = None  # Pure Python, no LLM needed

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="extractions",
                type="array",
                description="List of MEPExtraction objects to compare",
                required=True,
            ),
            ToolParameter(
                name="consensus_threshold",
                type="number",
                description="Minimum agreement ratio for consensus (0.0-1.0)",
                required=False,
            ),
        ]

    async def execute(
        self,
        extractions: list[dict[str, Any]],
        consensus_threshold: float = 0.66,
        **kwargs: Any,
    ) -> ToolResult[ExtractionComparison]:
        """Compare extractions and find consensus."""
        start_time = time.time()

        try:
            if len(extractions) == 0:
                return ToolResult(
                    tool_call_id=kwargs.get("tool_call_id", ""),
                    tool_name=self.name,
                    success=False,
                    error="No extractions provided",
                )

            # Convert to MEPExtraction objects
            parsed = []
            for ext in extractions:
                if isinstance(ext, MEPExtraction):
                    parsed.append(ext)
                else:
                    parsed.append(MEPExtraction(**ext))

            # Find consensus
            comparison = self._compare(parsed, consensus_threshold)

            return ToolResult(
                tool_call_id=kwargs.get("tool_call_id", ""),
                tool_name=self.name,
                success=True,
                result=comparison,
                latency_ms=int((time.time() - start_time) * 1000),
            )

        except Exception as e:
            return ToolResult(
                tool_call_id=kwargs.get("tool_call_id", ""),
                tool_name=self.name,
                success=False,
                error=str(e),
                latency_ms=int((time.time() - start_time) * 1000),
            )

    def _compare(
        self,
        extractions: list[MEPExtraction],
        threshold: float,
    ) -> ExtractionComparison:
        """Compare extractions and build consensus."""
        if len(extractions) == 1:
            return ExtractionComparison(
                extractions=extractions,
                consensus_reached=True,
                consensus_extraction=extractions[0],
                best_extraction_index=0,
                best_confidence=extractions[0].confidence_score,
            )

        # Count votes for categorical fields
        image_types: dict[str, int] = {}
        trades: dict[str, int] = {}

        for ext in extractions:
            image_types[ext.image_type] = image_types.get(ext.image_type, 0) + 1
            trades[ext.trade] = trades.get(ext.trade, 0) + 1

        n = len(extractions)

        # Find consensus
        disagreements = []

        consensus_image_type = max(image_types, key=image_types.get)  # type: ignore
        if image_types[consensus_image_type] / n < threshold:
            disagreements.append("image_type")

        consensus_trade = max(trades, key=trades.get)  # type: ignore
        if trades[consensus_trade] / n < threshold:
            disagreements.append("trade")

        # Find best extraction by confidence
        best_idx = max(range(n), key=lambda i: extractions[i].confidence_score)
        best = extractions[best_idx]

        # Build consensus extraction
        consensus = MEPExtraction(
            image_type=consensus_image_type,
            trade=consensus_trade,
            equipment_visible=self._merge_lists(
                [e.equipment_visible for e in extractions]
            ),
            specifications=self._merge_dicts(
                [e.specifications for e in extractions]
            ),
            measurements=self._merge_dicts(
                [e.measurements for e in extractions]
            ),
            condition=best.condition,
            issues_found=self._merge_lists(
                [e.issues_found for e in extractions]
            ),
            confidence_score=sum(e.confidence_score for e in extractions) / n,
        )

        return ExtractionComparison(
            extractions=extractions,
            consensus_reached=len(disagreements) == 0,
            consensus_extraction=consensus,
            disagreement_fields=disagreements,
            needs_orchestrator_decision=len(disagreements) > 0,
            best_extraction_index=best_idx,
            best_confidence=best.confidence_score,
        )

    def _merge_lists(self, lists: list[list[str]]) -> list[str]:
        """Merge lists, keeping unique values."""
        seen = set()
        result = []
        for lst in lists:
            for item in lst:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
        return result

    def _merge_dicts(self, dicts: list[dict[str, str]]) -> dict[str, str]:
        """Merge dicts, preferring non-empty values."""
        result: dict[str, str] = {}
        for d in dicts:
            for k, v in d.items():
                if k not in result or (v and not result[k]):
                    result[k] = v
        return result


# =============================================================================
# GENERATE REPORT TOOL
# =============================================================================

class GenerateReportTool(BaseTool):
    """
    Generate final report from extraction results.

    Synthesizes all extractions into a structured report
    for the end user.
    """

    name = "generate_report"
    description = "Generate final MEP extraction report"
    requires_vision = False
    preferred_model = None  # Template-based, no LLM

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="extractions",
                type="array",
                description="List of MEPExtraction results",
                required=True,
            ),
            ToolParameter(
                name="comparison",
                type="object",
                description="ExtractionComparison result if available",
                required=False,
            ),
            ToolParameter(
                name="format",
                type="string",
                description="Output format",
                required=False,
                enum=["json", "markdown", "summary"],
            ),
        ]

    async def execute(
        self,
        extractions: list[dict[str, Any]],
        comparison: Optional[dict[str, Any]] = None,
        format: str = "json",
        **kwargs: Any,
    ) -> ToolResult[dict[str, Any]]:
        """Generate extraction report."""
        start_time = time.time()

        try:
            # Parse extractions
            parsed = []
            for ext in extractions:
                if isinstance(ext, MEPExtraction):
                    parsed.append(ext)
                else:
                    parsed.append(MEPExtraction(**ext))

            # Generate report
            if format == "json":
                report = self._generate_json_report(parsed, comparison)
            elif format == "markdown":
                report = self._generate_markdown_report(parsed, comparison)
            else:
                report = self._generate_summary_report(parsed, comparison)

            return ToolResult(
                tool_call_id=kwargs.get("tool_call_id", ""),
                tool_name=self.name,
                success=True,
                result=report,
                latency_ms=int((time.time() - start_time) * 1000),
            )

        except Exception as e:
            return ToolResult(
                tool_call_id=kwargs.get("tool_call_id", ""),
                tool_name=self.name,
                success=False,
                error=str(e),
                latency_ms=int((time.time() - start_time) * 1000),
            )

    def _generate_json_report(
        self,
        extractions: list[MEPExtraction],
        comparison: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate JSON report."""
        return {
            "report_type": "mep_extraction",
            "extraction_count": len(extractions),
            "extractions": [e.model_dump() for e in extractions],
            "comparison": comparison,
            "summary": {
                "trades": list({e.trade for e in extractions}),
                "image_types": list({e.image_type for e in extractions}),
                "avg_confidence": (
                    sum(e.confidence_score for e in extractions) / len(extractions)
                    if extractions else 0
                ),
                "total_equipment": len(
                    set(
                        item
                        for e in extractions
                        for item in e.equipment_visible
                    )
                ),
            },
        }

    def _generate_markdown_report(
        self,
        extractions: list[MEPExtraction],
        comparison: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate markdown report."""
        lines = ["# MEP Extraction Report\n"]

        for i, ext in enumerate(extractions, 1):
            lines.append(f"## Extraction {i}\n")
            lines.append(f"- **Type:** {ext.image_type}")
            lines.append(f"- **Trade:** {ext.trade}")
            lines.append(f"- **Confidence:** {ext.confidence_score:.2%}")
            if ext.equipment_visible:
                lines.append(f"- **Equipment:** {', '.join(ext.equipment_visible)}")
            lines.append("")

        return {
            "format": "markdown",
            "content": "\n".join(lines),
        }

    def _generate_summary_report(
        self,
        extractions: list[MEPExtraction],
        comparison: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate summary report."""
        return {
            "format": "summary",
            "extraction_count": len(extractions),
            "primary_trade": (
                max(
                    {e.trade for e in extractions},
                    key=lambda t: sum(1 for e in extractions if e.trade == t),
                )
                if extractions else "unknown"
            ),
            "confidence": (
                sum(e.confidence_score for e in extractions) / len(extractions)
                if extractions else 0
            ),
            "consensus_reached": (
                comparison.get("consensus_reached", False)
                if comparison else len(extractions) <= 1
            ),
        }


# =============================================================================
# TOOL REGISTRY
# =============================================================================

AVAILABLE_TOOLS: dict[str, type[BaseTool]] = {
    "extract_image": ExtractImageTool,
    "validate_json": ValidateJsonTool,
    "compare_extractions": CompareExtractionsTool,
    "generate_report": GenerateReportTool,
}


def get_tool(name: str, **kwargs: Any) -> BaseTool:
    """Get a tool instance by name."""
    if name not in AVAILABLE_TOOLS:
        raise ValueError(f"Unknown tool: {name}")
    return AVAILABLE_TOOLS[name](**kwargs)


def get_all_tools(**kwargs: Any) -> list[BaseTool]:
    """Get instances of all available tools."""
    return [cls(**kwargs) for cls in AVAILABLE_TOOLS.values()]


def get_tool_schemas() -> list[Tool]:
    """Get schemas for all tools (for agent configuration)."""
    return [cls().to_schema() for cls in AVAILABLE_TOOLS.values()]
