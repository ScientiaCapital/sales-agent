#!/usr/bin/env python3
"""
Common validation checks for workflow commands.

Provides:
- Environment validation
- Service health checks
- File existence checks
- Configuration validation
"""

import os
import sys
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Add backend to Python path
backend_path = Path(__file__).parent.parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from app.core.config import Settings
from app.models.database import get_db
import redis.asyncio as redis


@dataclass
class CheckResult:
    """Result of a validation check."""
    name: str
    success: bool
    message: str
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class Checks:
    """Collection of validation checks for workflows."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.settings = None
        self.results: List[CheckResult] = []
    
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
    
    def add_result(self, result: CheckResult):
        """Add check result."""
        self.results.append(result)
        
        if result.success:
            self.log_success(f"{result.name}: {result.message}")
        else:
            self.log_error(f"{result.name}: {result.message}")
    
    def check_environment_file(self) -> CheckResult:
        """Check if .env file exists and is readable."""
        env_path = Path(__file__).parent.parent.parent / '.env'
        
        if not env_path.exists():
            return CheckResult(
                name="Environment File",
                success=False,
                message=".env file not found",
                details={"path": str(env_path)}
            )
        
        if not env_path.is_file():
            return CheckResult(
                name="Environment File",
                success=False,
                message=".env is not a file",
                details={"path": str(env_path)}
            )
        
        return CheckResult(
            name="Environment File",
            success=True,
            message=".env file found",
            details={"path": str(env_path)}
        )
    
    def check_environment_variables(self) -> CheckResult:
        """Check required environment variables."""
        required_vars = {
            'CEREBRAS_API_KEY': 'Cerebras API key for AI inference',
            'DATABASE_URL': 'PostgreSQL database connection string',
            'REDIS_URL': 'Redis connection string',
            'DEEPSEEK_API_KEY': 'DeepSeek API key for research',
            'OPENROUTER_API_KEY': 'OpenRouter API key for DeepSeek'
        }
        
        missing_vars = []
        present_vars = []
        
        for var, description in required_vars.items():
            value = os.getenv(var)
            if value:
                present_vars.append(var)
            else:
                missing_vars.append(var)
        
        if missing_vars:
            return CheckResult(
                name="Environment Variables",
                success=False,
                message=f"Missing required variables: {', '.join(missing_vars)}",
                details={
                    "missing": missing_vars,
                    "present": present_vars,
                    "required": list(required_vars.keys())
                }
            )
        
        return CheckResult(
            name="Environment Variables",
            success=True,
            message="All required environment variables present",
            details={
                "present": present_vars,
                "required": list(required_vars.keys())
            }
        )
    
    def check_database_connection(self) -> CheckResult:
        """Check database connection."""
        try:
            db = next(get_db())
            # Simple query to test connection
            result = db.execute("SELECT 1 as test").fetchone()
            db.close()
            
            if result and result[0] == 1:
                return CheckResult(
                    name="Database Connection",
                    success=True,
                    message="Database connection successful",
                    details={"test_query": "SELECT 1"}
                )
            else:
                return CheckResult(
                    name="Database Connection",
                    success=False,
                    message="Database test query failed",
                    details={"test_query": "SELECT 1", "result": result}
                )
                
        except Exception as e:
            return CheckResult(
                name="Database Connection",
                success=False,
                message=f"Database connection failed: {e}",
                details={"error": str(e)}
            )
    
    async def check_redis_connection(self) -> CheckResult:
        """Check Redis connection."""
        try:
            redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
            pong = await redis_client.ping()
            await redis_client.close()
            
            if pong:
                return CheckResult(
                    name="Redis Connection",
                    success=True,
                    message="Redis connection successful",
                    details={"ping_response": pong}
                )
            else:
                return CheckResult(
                    name="Redis Connection",
                    success=False,
                    message="Redis ping failed",
                    details={"ping_response": pong}
                )
                
        except Exception as e:
            return CheckResult(
                name="Redis Connection",
                success=False,
                message=f"Redis connection failed: {e}",
                details={"error": str(e)}
            )
    
    def check_docker_services(self) -> CheckResult:
        """Check if Docker services are running."""
        try:
            result = subprocess.run(
                ["docker-compose", "ps"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent
            )
            
            if result.returncode != 0:
                return CheckResult(
                    name="Docker Services",
                    success=False,
                    message="Failed to check Docker services",
                    details={"error": result.stderr}
                )
            
            # Check if PostgreSQL and Redis are running
            output = result.stdout.lower()
            postgres_running = "postgres" in output and "up" in output
            redis_running = "redis" in output and "up" in output
            
            if postgres_running and redis_running:
                return CheckResult(
                    name="Docker Services",
                    success=True,
                    message="PostgreSQL and Redis services running",
                    details={
                        "postgres_running": postgres_running,
                        "redis_running": redis_running
                    }
                )
            else:
                return CheckResult(
                    name="Docker Services",
                    success=False,
                    message="Required services not running",
                    details={
                        "postgres_running": postgres_running,
                        "redis_running": redis_running
                    }
                )
                
        except Exception as e:
            return CheckResult(
                name="Docker Services",
                success=False,
                message=f"Failed to check Docker services: {e}",
                details={"error": str(e)}
            )
    
    def check_python_dependencies(self) -> CheckResult:
        """Check if required Python packages are installed."""
        required_packages = [
            'fastapi',
            'sqlalchemy',
            'redis',
            'pydantic',
            'uvicorn',
            'pytest',
            'black',
            'mypy'
        ]
        
        missing_packages = []
        present_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
                present_packages.append(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            return CheckResult(
                name="Python Dependencies",
                success=False,
                message=f"Missing packages: {', '.join(missing_packages)}",
                details={
                    "missing": missing_packages,
                    "present": present_packages,
                    "required": required_packages
                }
            )
        
        return CheckResult(
            name="Python Dependencies",
            success=True,
            message="All required packages installed",
            details={
                "present": present_packages,
                "required": required_packages
            }
        )
    
    def check_project_structure(self) -> CheckResult:
        """Check if project has required directory structure."""
        project_root = Path(__file__).parent.parent.parent
        required_dirs = [
            'backend',
            'backend/app',
            'backend/app/api',
            'backend/app/models',
            'backend/app/services',
            'backend/tests',
            'frontend',
            'frontend/src'
        ]
        
        missing_dirs = []
        present_dirs = []
        
        for dir_path in required_dirs:
            full_path = project_root / dir_path
            if full_path.exists() and full_path.is_dir():
                present_dirs.append(dir_path)
            else:
                missing_dirs.append(dir_path)
        
        if missing_dirs:
            return CheckResult(
                name="Project Structure",
                success=False,
                message=f"Missing directories: {', '.join(missing_dirs)}",
                details={
                    "missing": missing_dirs,
                    "present": present_dirs,
                    "required": required_dirs
                }
            )
        
        return CheckResult(
            name="Project Structure",
            success=True,
            message="Project structure is valid",
            details={
                "present": present_dirs,
                "required": required_dirs
            }
        )
    
    def check_git_repository(self) -> CheckResult:
        """Check if project is a git repository."""
        project_root = Path(__file__).parent.parent.parent
        git_dir = project_root / '.git'
        
        if not git_dir.exists():
            return CheckResult(
                name="Git Repository",
                success=False,
                message="Not a git repository",
                details={"git_dir": str(git_dir)}
            )
        
        try:
            result = subprocess.run(
                ["git", "status"],
                capture_output=True,
                text=True,
                cwd=project_root
            )
            
            if result.returncode == 0:
                return CheckResult(
                    name="Git Repository",
                    success=True,
                    message="Git repository is valid",
                    details={"status": "clean" if "nothing to commit" in result.stdout else "dirty"}
                )
            else:
                return CheckResult(
                    name="Git Repository",
                    success=False,
                    message="Git repository is corrupted",
                    details={"error": result.stderr}
                )
                
        except Exception as e:
            return CheckResult(
                name="Git Repository",
                success=False,
                message=f"Failed to check git status: {e}",
                details={"error": str(e)}
            )
    
    async def run_all_checks(self) -> List[CheckResult]:
        """Run all validation checks."""
        self.log_info("Running all validation checks...")
        
        # Basic checks
        self.add_result(self.check_environment_file())
        self.add_result(self.check_environment_variables())
        self.add_result(self.check_python_dependencies())
        self.add_result(self.check_project_structure())
        self.add_result(self.check_git_repository())
        
        # Service checks
        self.add_result(self.check_database_connection())
        self.add_result(await self.check_redis_connection())
        self.add_result(self.check_docker_services())
        
        # Summary
        passed = sum(1 for r in self.results if r.success)
        total = len(self.results)
        
        self.log_info(f"Checks completed: {passed}/{total} passed")
        
        return self.results
    
    def get_failed_checks(self) -> List[CheckResult]:
        """Get list of failed checks."""
        return [r for r in self.results if not r.success]
    
    def get_passed_checks(self) -> List[CheckResult]:
        """Get list of passed checks."""
        return [r for r in self.results if r.success]
    
    def has_critical_failures(self) -> bool:
        """Check if there are any critical failures."""
        critical_checks = [
            "Environment Variables",
            "Database Connection",
            "Redis Connection"
        ]
        
        failed_critical = [
            r for r in self.get_failed_checks()
            if r.name in critical_checks
        ]
        
        return len(failed_critical) > 0