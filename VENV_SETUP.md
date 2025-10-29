# Virtual Environment Setup - Complete Instructions

## Quick Setup

```bash
# 1. Create virtual environment
python3 -m venv venv

# 2. Activate it
source venv/bin/activate

# 3. Install dependencies (install in this order to avoid conflicts)
pip install --upgrade pip setuptools wheel

# Core dependencies
pip install fastapi uvicorn sqlalchemy "psycopg[binary]==3.2.3" python-dotenv httpx beautifulsoup4 requests pydantic

# LangChain dependencies (install in order)
pip install "langchain-core>=1.0.0"
pip install langchain langchain-openai langchain-anthropic langchain-community langgraph
pip install langchain-cerebras langgraph-checkpoint-redis

# Redis (optional but recommended)
pip install redis

# Or use the automated script:
./setup.sh
```

## Daily Usage

```bash
# Always activate venv first
source venv/bin/activate

# Then start server
python3 start_server.py
```

## Troubleshooting

**Version conflicts:**
- Make sure langchain-core >= 1.0.0 before installing other langchain packages
- If you get conflicts, reinstall: `pip install --force-reinstall langchain-core>=1.0.0`

**Missing dependencies:**
```bash
source venv/bin/activate
pip install <package-name>
```

**Reset environment:**
```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
# Then reinstall dependencies
```

## Installation Order Matters

1. Core Python packages first
2. LangChain core (1.0.0+) before other LangChain packages
3. LangChain integrations after core
4. Optional packages last
