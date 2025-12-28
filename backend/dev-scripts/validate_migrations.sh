#!/bin/bash
# Migration Validation Script
# Tests Alembic migrations for conflicts and integrity
# Author: Agent 10
# Date: 2025-12-01

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Migration Validation Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if backend directory exists
if [ ! -d "$BACKEND_DIR" ]; then
    echo -e "${RED}ERROR: Backend directory not found: $BACKEND_DIR${NC}"
    exit 1
fi

cd "$BACKEND_DIR"

# Check if .env file exists
if [ ! -f "../.env" ]; then
    echo -e "${RED}ERROR: .env file not found${NC}"
    echo "Please create .env file with database credentials"
    exit 1
fi

# Load environment variables
source ../.env 2>/dev/null || true

# Check if database is accessible
echo -e "${YELLOW}[1/6] Checking database connection...${NC}"
if ! psql "$DATABASE_URL" -c "SELECT 1" &>/dev/null; then
    echo -e "${RED}ERROR: Cannot connect to database${NC}"
    echo "Database URL: $DATABASE_URL"
    echo "Make sure Docker containers are running: docker compose up -d postgres"
    exit 1
fi
echo -e "${GREEN}✓ Database connection successful${NC}"
echo ""

# Check Alembic is installed
echo -e "${YELLOW}[2/6] Checking Alembic installation...${NC}"
if ! command -v alembic &> /dev/null; then
    echo -e "${RED}ERROR: Alembic not found${NC}"
    echo "Install with: pip install alembic"
    exit 1
fi
echo -e "${GREEN}✓ Alembic is installed${NC}"
echo ""

# Show current database state
echo -e "${YELLOW}[3/6] Checking current migration state...${NC}"
echo "Current Alembic version:"
alembic current || echo "No migrations applied yet"
echo ""

# Check for migration conflicts
echo -e "${YELLOW}[4/6] Checking for migration conflicts...${NC}"
if alembic check 2>&1 | grep -i "error\|conflict"; then
    echo -e "${RED}ERROR: Migration conflicts detected${NC}"
    alembic check
    exit 1
else
    echo -e "${GREEN}✓ No migration conflicts detected${NC}"
fi
echo ""

# List all migrations
echo -e "${YELLOW}[5/6] Listing all migrations...${NC}"
alembic history | head -30
echo ""

# Validate migration chain
echo -e "${YELLOW}[6/6] Validating migration chain...${NC}"
echo "This will check that all migrations can be applied in sequence."
echo ""

# Get current revision
CURRENT_REV=$(alembic current 2>/dev/null | grep -oP '(?<=^)[a-f0-9]+' | head -1)

if [ -z "$CURRENT_REV" ]; then
    echo -e "${YELLOW}No migrations applied yet. Starting fresh validation.${NC}"
    echo ""

    # Test upgrade to head
    echo -e "${BLUE}Testing: alembic upgrade head${NC}"
    if alembic upgrade head; then
        echo -e "${GREEN}✓ All migrations applied successfully${NC}"
    else
        echo -e "${RED}ERROR: Migration failed${NC}"
        exit 1
    fi
else
    echo "Current revision: $CURRENT_REV"
    echo ""

    # Test upgrade to head
    echo -e "${BLUE}Testing: alembic upgrade head${NC}"
    if alembic upgrade head; then
        echo -e "${GREEN}✓ All migrations applied successfully${NC}"
    else
        echo -e "${RED}ERROR: Migration failed${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Migration Validation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Summary:"
echo "  - Database connection: OK"
echo "  - Alembic installation: OK"
echo "  - Migration conflicts: NONE"
echo "  - Migration chain: VALID"
echo ""
echo "Current database schema:"
alembic current

# Optional: Show tables created
echo ""
echo -e "${BLUE}Tables in database:${NC}"
psql "$DATABASE_URL" -c "\dt" 2>/dev/null | grep "public" || echo "No tables found"

echo ""
echo -e "${YELLOW}Note: To test rollback, run:${NC}"
echo "  alembic downgrade -1    # Rollback one migration"
echo "  alembic upgrade head     # Re-apply migration"
echo ""
echo -e "${YELLOW}To test full migration cycle:${NC}"
echo "  alembic downgrade base   # Remove all migrations"
echo "  alembic upgrade head     # Apply all migrations"
echo ""
