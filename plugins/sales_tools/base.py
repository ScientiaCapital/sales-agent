"""Base tool classes for conductor-ai compatibility.

This module provides base classes that match the conductor-ai SDK interface,
allowing the plugin to work standalone or with the full SDK.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
import time


class ToolCategory(Enum):
    """Category of tool for organization."""
    WEB = "web"
    DATA = "data"
    CODE = "code"
    FILE = "file"
    SYSTEM = "system"
    SALES = "sales"


@dataclass
class ToolDefinition:
    """Definition of a tool's interface.

    Describes the tool's name, description, parameters, and metadata
    for LLM function calling.
    """
    name: str
    description: str
    category: ToolCategory
    parameters: dict  # JSON Schema
    requires_approval: bool = False


@dataclass
class ToolResult:
    """Result of a tool execution.

    Contains success status, result data or error, and execution metadata.
    """
    tool_name: str
    success: bool
    result: Any
    execution_time_ms: int
    error: Optional[str] = None


class BaseTool(ABC):
    """Abstract base class for all tools.

    Tools must implement:
    - definition property: Returns ToolDefinition
    - run method: Executes the tool with given arguments
    """

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return the tool's definition."""
        pass

    @abstractmethod
    async def run(self, arguments: dict) -> ToolResult:
        """Execute the tool with given arguments.

        Args:
            arguments: Dictionary of argument name to value

        Returns:
            ToolResult with success/failure and result data
        """
        pass

    async def execute(self, arguments: dict) -> ToolResult:
        """Execute with timing wrapper.

        Args:
            arguments: Dictionary of argument name to value

        Returns:
            ToolResult with execution time filled in
        """
        start = time.time()
        try:
            result = await self.run(arguments)
            result.execution_time_ms = int((time.time() - start) * 1000)
            return result
        except Exception as e:
            return ToolResult(
                tool_name=self.definition.name,
                success=False,
                result=None,
                execution_time_ms=int((time.time() - start) * 1000),
                error=str(e),
            )
