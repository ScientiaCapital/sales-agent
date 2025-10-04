#!/usr/bin/env python3
"""
Start the FastAPI server with environment variables loaded from .env
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Add backend to Python path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

# Verify critical environment variables
required_vars = ['CEREBRAS_API_KEY', 'DATABASE_URL']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
    sys.exit(1)

print("✓ Environment variables loaded successfully")
print(f"✓ CEREBRAS_API_KEY: {os.getenv('CEREBRAS_API_KEY')[:10]}...")
print(f"✓ DATABASE_URL: {os.getenv('DATABASE_URL')[:30]}...")

# Start uvicorn server
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        reload_dirs=[str(backend_path)]
    )
