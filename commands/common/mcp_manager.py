#!/usr/bin/env python3
"""
MCP Manager for coordinating MCP servers and workflows.

Provides:
- MCP server initialization and management
- Mandatory workflow execution (Sequential Thinking → Serena → Context7)
- Subagent orchestration
- Token usage tracking
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Add backend to Python path
backend_path = Path(__file__).parent.parent.parent / 'backend'
sys.path.insert(0, str(backend_path))


class MCPStatus(Enum):
    """MCP server status."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class MCPInfo:
    """Information about an MCP server."""
    name: str
    status: MCPStatus
    description: str
    token_cost: int = 0
    last_used: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class WorkflowResult:
    """Result of MCP workflow execution."""
    success: bool
    sequential_thinking: Dict[str, Any] = None
    serena_patterns: Dict[str, Any] = None
    context7_docs: Dict[str, Any] = None
    total_tokens: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.sequential_thinking is None:
            self.sequential_thinking = {}
        if self.serena_patterns is None:
            self.serena_patterns = {}
        if self.context7_docs is None:
            self.context7_docs = {}


class MCPManager:
    """Manages MCP servers and workflows."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.mcps: Dict[str, MCPInfo] = {}
        self.token_usage: Dict[str, int] = {}
        self.workflow_history: List[WorkflowResult] = []
        
        # Initialize MCP definitions
        self._initialize_mcp_definitions()
    
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp."""
        if not self.verbose:
            return
            
        import time
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
    def log_success(self, message: str):
        """Log success message."""
        self.log(f"✅ {message}", "SUCCESS")
    
    def log_error(self, message: str):
        """Log error message."""
        self.log(f"❌ {message}", "ERROR")
    
    def log_warning(self, message: str):
        """Log warning message."""
        self.log(f"⚠️  {message}", "WARNING")
    
    def log_info(self, message: str):
        """Log info message."""
        self.log(f"ℹ️  {message}", "INFO")
    
    def _initialize_mcp_definitions(self):
        """Initialize MCP server definitions."""
        self.mcps = {
            "sequential_thinking": MCPInfo(
                name="Sequential Thinking",
                status=MCPStatus.UNINITIALIZED,
                description="Problem decomposition and step-by-step analysis",
                token_cost=2000
            ),
            "serena": MCPInfo(
                name="Serena",
                status=MCPStatus.UNINITIALIZED,
                description="Codebase navigation and pattern discovery",
                token_cost=3000
            ),
            "context7": MCPInfo(
                name="Context7",
                status=MCPStatus.UNINITIALIZED,
                description="Library documentation and best practices",
                token_cost=4000
            ),
            "task_master": MCPInfo(
                name="Task Master",
                status=MCPStatus.UNINITIALIZED,
                description="Task management and progress tracking",
                token_cost=1000
            ),
            "desktop_commander": MCPInfo(
                name="Desktop Commander",
                status=MCPStatus.UNINITIALIZED,
                description="File operations and system commands",
                token_cost=500
            )
        }
    
    async def initialize_all(self) -> bool:
        """Initialize all MCP servers."""
        self.log_info("Initializing all MCP servers...")
        
        success_count = 0
        total_count = len(self.mcps)
        
        for mcp_name, mcp_info in self.mcps.items():
            try:
                self.log_info(f"Initializing {mcp_info.name}...")
                mcp_info.status = MCPStatus.INITIALIZING
                
                # Simulate MCP initialization
                await asyncio.sleep(0.1)  # Simulate async initialization
                
                # Check if MCP is available (simplified check)
                if await self._check_mcp_availability(mcp_name):
                    mcp_info.status = MCPStatus.READY
                    self.log_success(f"{mcp_info.name} initialized successfully")
                    success_count += 1
                else:
                    mcp_info.status = MCPStatus.ERROR
                    mcp_info.error_message = "MCP server not available"
                    self.log_error(f"{mcp_info.name} initialization failed")
                    
            except Exception as e:
                mcp_info.status = MCPStatus.ERROR
                mcp_info.error_message = str(e)
                self.log_error(f"{mcp_info.name} initialization failed: {e}")
        
        if success_count == total_count:
            self.log_success(f"All {total_count} MCP servers initialized successfully")
            return True
        else:
            self.log_warning(f"Only {success_count}/{total_count} MCP servers initialized")
            return False
    
    async def _check_mcp_availability(self, mcp_name: str) -> bool:
        """Check if MCP server is available."""
        # Simplified availability check
        # In real implementation, this would check actual MCP server status
        
        if mcp_name == "sequential_thinking":
            # Check if Sequential Thinking MCP is available
            return True  # Assume available for now
        
        elif mcp_name == "serena":
            # Check if Serena MCP is available
            return True  # Assume available for now
        
        elif mcp_name == "context7":
            # Check if Context7 MCP is available
            return True  # Assume available for now
        
        elif mcp_name == "task_master":
            # Check if Task Master MCP is available
            return True  # Assume available for now
        
        elif mcp_name == "desktop_commander":
            # Check if Desktop Commander MCP is available
            return True  # Assume available for now
        
        return False
    
    def get_mcp_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all MCP servers."""
        status = {}
        for name, info in self.mcps.items():
            status[name] = {
                "name": info.name,
                "status": info.status.value,
                "description": info.description,
                "token_cost": info.token_cost,
                "last_used": info.last_used,
                "error_message": info.error_message
            }
        return status
    
    def get_ready_mcps(self) -> List[str]:
        """Get list of ready MCP servers."""
        return [name for name, info in self.mcps.items() if info.status == MCPStatus.READY]
    
    def get_failed_mcps(self) -> List[str]:
        """Get list of failed MCP servers."""
        return [name for name, info in self.mcps.items() if info.status == MCPStatus.ERROR]
    
    async def run_sequential_thinking(self, task: str) -> Dict[str, Any]:
        """Run Sequential Thinking analysis."""
        if self.mcps["sequential_thinking"].status != MCPStatus.READY:
            raise RuntimeError("Sequential Thinking MCP not ready")
        
        self.log_info("Running Sequential Thinking analysis...")
        
        # Simulate Sequential Thinking analysis
        # In real implementation, this would call the actual MCP
        
        analysis = {
            "task": task,
            "thoughts": [
                "Analyzing task requirements and breaking down into components",
                "Identifying key technical challenges and dependencies",
                "Creating step-by-step implementation plan",
                "Documenting assumptions and edge cases"
            ],
            "components": [
                "Backend API endpoint",
                "Database model updates",
                "Frontend component",
                "Test cases"
            ],
            "dependencies": [
                "FastAPI framework",
                "SQLAlchemy ORM",
                "React components",
                "pytest testing"
            ],
            "challenges": [
                "Async database operations",
                "State management",
                "Error handling",
                "Performance optimization"
            ],
            "plan": [
                "1. Create database model",
                "2. Implement API endpoint",
                "3. Build frontend component",
                "4. Write tests",
                "5. Update documentation"
            ]
        }
        
        self.mcps["sequential_thinking"].last_used = "now"
        self.token_usage["sequential_thinking"] = self.mcps["sequential_thinking"].token_cost
        
        return analysis
    
    async def run_serena_analysis(self, task: str, components: List[str]) -> Dict[str, Any]:
        """Run Serena codebase analysis."""
        if self.mcps["serena"].status != MCPStatus.READY:
            raise RuntimeError("Serena MCP not ready")
        
        self.log_info("Running Serena codebase analysis...")
        
        # Simulate Serena analysis
        # In real implementation, this would call the actual MCP
        
        patterns = {
            "task": task,
            "components": components,
            "existing_patterns": [
                {
                    "file": "backend/app/api/leads.py",
                    "pattern": "FastAPI endpoint with Pydantic validation",
                    "relevance": "high"
                },
                {
                    "file": "backend/app/models/lead.py",
                    "pattern": "SQLAlchemy model with relationships",
                    "relevance": "high"
                },
                {
                    "file": "frontend/src/components/LeadForm.tsx",
                    "pattern": "React form with TypeScript",
                    "relevance": "medium"
                }
            ],
            "integration_points": [
                "backend/app/api/",
                "backend/app/models/",
                "backend/app/services/",
                "frontend/src/components/"
            ],
            "dependencies": [
                "FastAPI router",
                "SQLAlchemy model",
                "Pydantic schema",
                "React component"
            ],
            "suggestions": [
                "Follow existing API endpoint pattern",
                "Use similar database model structure",
                "Implement consistent error handling",
                "Add proper type annotations"
            ]
        }
        
        self.mcps["serena"].last_used = "now"
        self.token_usage["serena"] = self.mcps["serena"].token_cost
        
        return patterns
    
    async def run_context7_research(self, libraries: List[str]) -> Dict[str, Any]:
        """Run Context7 library documentation research."""
        if self.mcps["context7"].status != MCPStatus.READY:
            raise RuntimeError("Context7 MCP not ready")
        
        self.log_info("Running Context7 library research...")
        
        # Simulate Context7 research
        # In real implementation, this would call the actual MCP
        
        docs = {
            "libraries": libraries,
            "documentation": {
                "fastapi": {
                    "version": "0.115.0",
                    "patterns": [
                        "Dependency injection with Depends()",
                        "Async route handlers",
                        "Pydantic model validation",
                        "OpenAPI documentation"
                    ],
                    "best_practices": [
                        "Use async/await for I/O operations",
                        "Implement proper error handling",
                        "Add request/response models",
                        "Use dependency injection"
                    ]
                },
                "sqlalchemy": {
                    "version": "2.0.0",
                    "patterns": [
                        "Async session management",
                        "Model relationships",
                        "Query optimization",
                        "Migration handling"
                    ],
                    "best_practices": [
                        "Use async sessions",
                        "Implement proper indexing",
                        "Handle connection pooling",
                        "Use Alembic for migrations"
                    ]
                }
            },
            "recommendations": [
                "Use FastAPI 0.115.0 with async patterns",
                "Implement SQLAlchemy 2.0 async sessions",
                "Follow Pydantic v2 validation patterns",
                "Use proper error handling with HTTPException"
            ]
        }
        
        self.mcps["context7"].last_used = "now"
        self.token_usage["context7"] = self.mcps["context7"].token_cost
        
        return docs
    
    async def run_mandatory_workflow(self, task: str) -> WorkflowResult:
        """Run the mandatory MCP workflow: Sequential Thinking → Serena → Context7."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            self.log_info("Starting mandatory MCP workflow...")
            
            # Phase 1: Sequential Thinking
            self.log_info("Phase 1: Sequential Thinking analysis")
            sequential_result = await self.run_sequential_thinking(task)
            
            # Phase 2: Serena
            self.log_info("Phase 2: Serena codebase analysis")
            serena_result = await self.run_serena_analysis(
                task, 
                sequential_result.get("components", [])
            )
            
            # Phase 3: Context7
            self.log_info("Phase 3: Context7 library research")
            context7_result = await self.run_context7_research(
                sequential_result.get("dependencies", [])
            )
            
            # Calculate total tokens and duration
            total_tokens = sum(self.token_usage.values())
            duration = asyncio.get_event_loop().time() - start_time
            
            result = WorkflowResult(
                success=True,
                sequential_thinking=sequential_result,
                serena_patterns=serena_result,
                context7_docs=context7_result,
                total_tokens=total_tokens,
                duration_seconds=duration
            )
            
            self.workflow_history.append(result)
            self.log_success(f"MCP workflow completed successfully ({total_tokens} tokens, {duration:.2f}s)")
            
            return result
            
        except Exception as e:
            duration = asyncio.get_event_loop().time() - start_time
            result = WorkflowResult(
                success=False,
                error_message=str(e),
                duration_seconds=duration
            )
            
            self.workflow_history.append(result)
            self.log_error(f"MCP workflow failed: {e}")
            
            return result
    
    def get_token_usage(self) -> Dict[str, int]:
        """Get token usage statistics."""
        return self.token_usage.copy()
    
    def get_total_tokens(self) -> int:
        """Get total token usage."""
        return sum(self.token_usage.values())
    
    def get_workflow_history(self) -> List[WorkflowResult]:
        """Get workflow execution history."""
        return self.workflow_history.copy()
    
    def reset_token_usage(self):
        """Reset token usage counters."""
        self.token_usage.clear()
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get comprehensive status summary."""
        ready_count = len(self.get_ready_mcps())
        failed_count = len(self.get_failed_mcps())
        total_count = len(self.mcps)
        
        return {
            "mcp_status": {
                "ready": ready_count,
                "failed": failed_count,
                "total": total_count,
                "success_rate": f"{(ready_count/total_count)*100:.1f}%"
            },
            "token_usage": {
                "current": self.get_total_tokens(),
                "by_mcp": self.get_token_usage()
            },
            "workflow_history": {
                "total_executions": len(self.workflow_history),
                "successful": len([w for w in self.workflow_history if w.success]),
                "failed": len([w for w in self.workflow_history if not w.success])
            }
        }