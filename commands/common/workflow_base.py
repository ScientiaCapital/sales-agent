#!/usr/bin/env python3
"""
Base workflow class for all command workflows.

Provides common functionality:
- Environment validation
- Database/Redis connection checks
- Test execution helpers
- Progress indicators
- MCP workflow integration
"""

import os
import sys
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Add backend to Python path
backend_path = Path(__file__).parent.parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from app.core.config import Settings
from app.models.database import get_db
import redis.asyncio as redis


@dataclass
class WorkflowResult:
    """Result of workflow execution."""
    success: bool
    message: str
    files_created: List[str] = None
    tests_run: List[str] = None
    metrics: Dict[str, Any] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.files_created is None:
            self.files_created = []
        if self.tests_run is None:
            self.tests_run = []
        if self.metrics is None:
            self.metrics = {}
        if self.errors is None:
            self.errors = []


class WorkflowBase:
    """Base class for all workflow commands."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.settings = None
        self.redis_client = None
        self.db_session = None
        self.start_time = None
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp."""
        if not self.verbose:
            return
            
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
    
    def start_progress(self, task: str):
        """Start progress tracking."""
        self.start_time = time.time()
        self.log_info(f"Starting: {task}")
    
    def end_progress(self, task: str):
        """End progress tracking."""
        if self.start_time:
            duration = time.time() - self.start_time
            self.log_success(f"Completed: {task} ({duration:.2f}s)")
    
    def load_environment(self) -> bool:
        """Load environment variables from .env file."""
        try:
            env_path = Path(__file__).parent.parent.parent / '.env'
            load_dotenv(env_path)
            
            # Load settings
            self.settings = Settings()
            
            self.log_success("Environment loaded successfully")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to load environment: {e}")
            return False
    
    def check_environment(self) -> bool:
        """Check required environment variables."""
        required_vars = [
            'CEREBRAS_API_KEY',
            'DATABASE_URL',
            'REDIS_URL'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.log_error(f"Missing required environment variables: {', '.join(missing_vars)}")
            return False
        
        self.log_success("Environment variables validated")
        return True
    
    async def check_database(self) -> bool:
        """Check database connection."""
        try:
            db = next(get_db())
            # Simple query to test connection
            db.execute("SELECT 1")
            db.close()
            
            self.log_success("Database connection verified")
            return True
            
        except Exception as e:
            self.log_error(f"Database connection failed: {e}")
            return False
    
    async def check_redis(self) -> bool:
        """Check Redis connection."""
        try:
            self.redis_client = redis.from_url(self.settings.REDIS_URL)
            await self.redis_client.ping()
            
            self.log_success("Redis connection verified")
            return True
            
        except Exception as e:
            self.log_error(f"Redis connection failed: {e}")
            return False
    
    async def run_checks(self) -> bool:
        """Run all prerequisite checks."""
        self.log_info("Running prerequisite checks...")
        
        if not self.load_environment():
            return False
        
        if not self.check_environment():
            return False
        
        if not await self.check_database():
            return False
        
        if not await self.check_redis():
            return False
        
        self.log_success("All checks passed")
        return True
    
    def run_tests(self, test_paths: List[str] = None) -> bool:
        """Run test suite."""
        if test_paths is None:
            test_paths = ["backend/tests/"]
        
        self.log_info("Running tests...")
        
        try:
            import subprocess
            
            cmd = ["python", "-m", "pytest", "-v"]
            cmd.extend(test_paths)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log_success("All tests passed")
                return True
            else:
                self.log_error(f"Tests failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.log_error(f"Failed to run tests: {e}")
            return False
    
    def run_linting(self) -> bool:
        """Run linting checks."""
        self.log_info("Running linting checks...")
        
        try:
            import subprocess
            
            # Run Black
            result = subprocess.run(
                ["python", "-m", "black", "--check", "backend/"],
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                self.log_error(f"Black linting failed: {result.stderr}")
                return False
            
            # Run mypy
            result = subprocess.run(
                ["python", "-m", "mypy", "backend/"],
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                self.log_warning(f"mypy found issues: {result.stderr}")
                # Don't fail on mypy warnings, just warn
            
            self.log_success("Linting checks completed")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to run linting: {e}")
            return False
    
    def create_file(self, file_path: str, content: str) -> bool:
        """Create file with content."""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w') as f:
                f.write(content)
            
            self.log_success(f"Created file: {file_path}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to create file {file_path}: {e}")
            return False
    
    def read_file(self, file_path: str) -> Optional[str]:
        """Read file content."""
        try:
            with open(file_path, 'r') as f:
                return f.read()
        except Exception as e:
            self.log_error(f"Failed to read file {file_path}: {e}")
            return None
    
    def find_files(self, pattern: str, directory: str = None) -> List[str]:
        """Find files matching pattern."""
        if directory is None:
            directory = str(Path(__file__).parent.parent.parent)
        
        import glob
        return glob.glob(f"{directory}/{pattern}", recursive=True)
    
    def get_project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent
    
    def get_backend_path(self) -> Path:
        """Get backend directory path."""
        return self.get_project_root() / 'backend'
    
    def get_frontend_path(self) -> Path:
        """Get frontend directory path."""
        return self.get_project_root() / 'frontend'
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.redis_client:
            await self.redis_client.close()
        
        if self.db_session:
            self.db_session.close()
    
    def run(self) -> WorkflowResult:
        """Main workflow execution method - to be overridden."""
        raise NotImplementedError("Subclasses must implement run() method")
    
    async def run_async(self) -> WorkflowResult:
        """Async workflow execution method - to be overridden."""
        raise NotImplementedError("Subclasses must implement run_async() method")