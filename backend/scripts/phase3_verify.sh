#!/usr/bin/env bash
set -euo pipefail

# Colors
GREEN="\033[0;32m"; RED="\033[0;31m"; YELLOW="\033[1;33m"; NC="\033[0m"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo -e "${YELLOW}==> Starting infrastructure (Redis)...${NC}"
# Prefer 'docker compose', fallback to 'docker-compose'; if neither exists, skip with warning
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose up -d redis || true
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose up -d redis || true
else
  echo -e "${YELLOW}Docker not available. Skipping container startup. Ensure Redis/Postgres are running.${NC}"
fi

# Wait for Postgres to be ready
PG_HOST="localhost"; PG_PORT="5433"
echo -e "${YELLOW}==> Waiting for Postgres on ${PG_HOST}:${PG_PORT}...${NC}"
for i in {1..30}; do
  if command -v nc >/dev/null 2>&1 && nc -z "$PG_HOST" "$PG_PORT" 2>/dev/null; then echo -e "${GREEN}Postgres is up${NC}"; break; fi
  # If nc not present, attempt a quick psql check if available
  if command -v psql >/dev/null 2>&1; then
    if PGPASSWORD="${PGPASSWORD:-}" psql "${DATABASE_URL//postgresql+psycopg:/postgresql:}" -c 'SELECT 1' >/dev/null 2>&1; then
      echo -e "${GREEN}Postgres is up (psql)${NC}"; break; fi
  fi
  sleep 1
  if [[ $i -eq 30 ]]; then echo -e "${YELLOW}Could not verify Postgres readiness; continuing anyway${NC}"; break; fi
done

export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://sales_agent:password@localhost:5433/sales_agent_db}"

echo -e "${YELLOW}==> Applying Alembic migration...${NC}"
if command -v alembic >/dev/null 2>&1; then
  alembic upgrade head || { echo -e "${RED}Alembic upgrade failed${NC}"; exit 1; }
else
  echo -e "${YELLOW}alembic not found. Skipping migration. Run manually after activating venv.${NC}"
fi

# Start API
echo -e "${YELLOW}==> Starting API on :8001...${NC}"
if command -v uvicorn >/dev/null 2>&1; then
  UVICORN_CMD="uvicorn app.main:app --port 8001 --host 0.0.0.0"
  $UVICORN_CMD >/tmp/sales-agent-api.log 2>&1 &
  API_PID=$!
  trap 'kill $API_PID >/dev/null 2>&1 || true' EXIT

  for i in {1..30}; do
    if curl -sf "http://localhost:8001/api/v1/health" >/dev/null; then echo -e "${GREEN}API is up${NC}"; break; fi
    sleep 1
    if [[ $i -eq 30 ]]; then echo -e "${YELLOW}API did not become ready in time; continuing${NC}"; break; fi
  done
else
  echo -e "${YELLOW}uvicorn not found. Skipping API start; run manually after activating venv.${NC}"
fi

# Verify Prometheus metrics
echo -e "${YELLOW}==> Checking /metrics...${NC}"
if curl -sf "http://localhost:8001/metrics" | head -n 5; then
  echo -e "${GREEN}Metrics endpoint OK${NC}"
else
  echo -e "${RED}Metrics endpoint check failed${NC}" && exit 1
fi

# Verify JSON summary
echo -e "${YELLOW}==> Checking /api/v1/metrics/summary...${NC}"
if curl -sf "http://localhost:8001/api/v1/metrics/summary" | jq .; then
  echo -e "${GREEN}Metrics summary OK${NC}"
else
  echo -e "${RED}Metrics summary check failed (ensure jq installed or omit jq)${NC}"
  curl -sf "http://localhost:8001/api/v1/metrics/summary" || true
fi

# Populate Redis cache (smoke)
echo -e "${YELLOW}==> Populating Redis cache (smoke test)...${NC}"
python3 - <<'PY' || true
import asyncio
from app.core.cache import get_cache_manager
async def main():
    cache = get_cache_manager()
    await cache.cache_qualification("TestCo","SaaS",{"score":88})
    print(await cache.get_cached_qualification("TestCo","SaaS"))
asyncio.run(main())
PY

echo -e "${GREEN}All checks completed. Logs: /tmp/sales-agent-api.log${NC}"
