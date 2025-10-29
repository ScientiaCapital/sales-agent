#!/bin/bash
# Quick setup script for sales-agent project

set -e

echo "🚀 Setting up sales-agent environment..."

# Check if venv exists, create if not
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install dependencies
echo "📥 Installing dependencies..."
if [ -f "backend/requirements.txt" ]; then
    pip install -r backend/requirements.txt
else
    echo "⚠️  requirements.txt not found, installing minimal dependencies..."
    pip install fastapi uvicorn sqlalchemy psycopg3-binary python-dotenv httpx beautifulsoup4 requests pydantic
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To activate the virtual environment in the future, run:"
echo "  source venv/bin/activate"
echo ""
echo "Then start the server:"
echo "  python3 start_server.py"
echo ""

