# Quick Start Guide - Virtual Environment

## Setup (One-Time)

```bash
# 1. Create virtual environment
python3 -m venv venv

# 2. Activate it
source venv/bin/activate

# 3. Install core dependencies
pip install fastapi uvicorn sqlalchemy "psycopg[binary]" python-dotenv httpx beautifulsoup4 requests pydantic

# 4. Install LangChain dependencies
pip install langchain langchain-core langchain-openai langchain-anthropic langchain-community langgraph

# 5. Install optional dependencies (if needed)
pip install redis celery

# OR use the setup script:
./setup.sh
```

## Daily Usage

```bash
# Always activate venv first
source venv/bin/activate

# Then start server
python3 start_server.py

# Or run scripts
python3 scripts/import_csv_simple.py
python3 scripts/discover_atl_contacts.py
```

## Troubleshooting

**If you get "command not found" after closing terminal:**
- Reactivate venv: `source venv/bin/activate`

**If dependencies are missing:**
```bash
source venv/bin/activate
pip install <package-name>
```

**To install all dependencies:**
```bash
source venv/bin/activate
pip install -r backend/requirements.txt
```

## Note

The virtual environment is in `venv/` directory (gitignored).
Activate it each time you open a new terminal session.

