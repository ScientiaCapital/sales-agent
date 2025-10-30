#!/usr/bin/env bash
set -euo pipefail

# Colors
GREEN="\033[0;32m"; RED="\033[0;31m"; YELLOW="\033[1;33m"; NC="\033[0m"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Load backend/.env if present
if [[ -f "$ROOT_DIR/.env" ]]; then
  echo -e "${YELLOW}==> Loading environment from backend/.env...${NC}"
  set -a
  # shellcheck disable=SC1090
  . "$ROOT_DIR/.env"
  set +a
fi

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
ALEMBIC_CMD="alembic"
if ! command -v alembic >/dev/null 2>&1; then
  if [[ -x "$ROOT_DIR/venv/bin/alembic" ]]; then
    ALEMBIC_CMD="$ROOT_DIR/venv/bin/alembic -c $ROOT_DIR/alembic.ini"
  else
    ALEMBIC_CMD=""
  fi
fi

if [[ -n "$ALEMBIC_CMD" ]]; then
  # Try migration, on password auth failure optionally prompt or use DBPASS env
  set +e
  MIGRATION_OUTPUT=$($ALEMBIC_CMD upgrade head 2>&1)
  MIGRATION_STATUS=$?
  set -e
  if [[ $MIGRATION_STATUS -ne 0 ]]; then
    echo -e "${YELLOW}Alembic reported an error. Inspecting...${NC}"
    echo "$MIGRATION_OUTPUT" | grep -qi "password authentication failed"
    if [[ $? -eq 0 ]]; then
      echo -e "${YELLOW}Password authentication failed for current DATABASE_URL.${NC}"
      if [[ -n "${DBPASS:-}" ]]; then
        echo -e "${YELLOW}Using DBPASS from environment to rebuild DATABASE_URL...${NC}"
        export DBURL="$DATABASE_URL" DBPASS="$DBPASS"
        NEW_URL=$(python3 - <<'PY'
import os, urllib.parse
u=os.environ['DBURL']
p=os.environ['DBPASS']
parts=urllib.parse.urlsplit(u)
netloc=parts.netloc
if '@' in netloc:
    userinfo, host = netloc.split('@',1)
    if ':' in userinfo:
        user, _ = userinfo.split(':',1)
    else:
        user = userinfo
    netloc = f"{user}:{p}@{host}"
else:
    netloc = netloc
print(urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment)))
PY
)
        export DATABASE_URL="$NEW_URL"
      elif [[ -t 0 ]]; then
        read -s -p "Enter DB password to retry migration: " NEWPASS; echo
        export DBURL="$DATABASE_URL" DBPASS="$NEWPASS"
        NEW_URL=$(python3 - <<'PY'
import os, urllib.parse
u=os.environ['DBURL']
p=os.environ['DBPASS']
parts=urllib.parse.urlsplit(u)
netloc=parts.netloc
if '@' in netloc:
    userinfo, host = netloc.split('@',1)
    if ':' in userinfo:
        user, _ = userinfo.split(':',1)
    else:
        user = userinfo
    netloc = f"{user}:{p}@{host}"
else:
    netloc = netloc
print(urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment)))
PY
)
        export DATABASE_URL="$NEW_URL"
      else
        echo -e "${RED}Non-interactive session and no DBPASS provided. Cannot prompt for password. Set DBPASS and rerun.${NC}"
        exit 1
      fi
      echo -e "${YELLOW}Retrying Alembic migration...${NC}"
      $ALEMBIC_CMD upgrade head || { echo -e "${RED}Alembic upgrade failed again${NC}"; exit 1; }
    else
      echo "$MIGRATION_OUTPUT"
      echo -e "${RED}Alembic upgrade failed.${NC}"
      exit 1
    fi
  fi
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
