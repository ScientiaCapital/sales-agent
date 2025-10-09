#!/usr/bin/env python3
"""
Generate Alembic migration for Lead model optimizations
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Add backend to Python path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

# Change to backend directory for alembic
os.chdir(backend_path)

# Run alembic command
from alembic.config import Config
from alembic import command

alembic_cfg = Config("alembic.ini")
command.revision(alembic_cfg, autogenerate=True, message="Add indexes and constraints to Lead model for optimization")

print("✓ Migration generated successfully")
