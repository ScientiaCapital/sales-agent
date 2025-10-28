# API Keys Setup Guide

## Quick Start

1. **Copy the template:**
   ```bash
   cp .env.example .env
   ```

2. **Fill in your API keys** (see sections below)

3. **Verify security:**
   ```bash
   # Make sure .env is in .gitignore
   grep "^\.env$" .gitignore

   # Should output: .env
   ```

---

## Required API Keys

### 1. Cerebras Cloud API (Ultra-Fast Inference)
**Cost:** $0.000006 per request (~633ms latency)
**Get it:** https://cloud.cerebras.ai/

```env
CEREBRAS_API_KEY=csk-xxxxxxxxxxxxx
CEREBRAS_API_BASE=https://api.cerebras.ai/v1
```

### 2. LangSmith (Agent Observability)
**Cost:** Free tier available
**Get it:** https://smith.langchain.com/

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=ls__xxxxxxxxxxxxxxxx
LANGCHAIN_PROJECT=sales-agent-development
```

**Steps:**
1. Sign up at https://smith.langchain.com
2. Create new project: "sales-agent-development"
3. Go to Settings → API Keys → Create API Key
4. Copy key to `.env`

### 3. Cartesia TTS (Voice Agents)
**Cost:** Pay-per-use
**Get it:** https://cartesia.ai/

```env
CARTESIA_API_KEY=your_cartesia_key_here
```

### 4. Database & Infrastructure
**No API keys needed** - these run in Docker:

```env
POSTGRES_USER=sales_agent
POSTGRES_PASSWORD=CHANGE_ME_TO_SECURE_PASSWORD  # ⚠️ Change this!
POSTGRES_DB=sales_agent_db
DATABASE_URL=postgresql+psycopg://sales_agent:CHANGE_ME_TO_SECURE_PASSWORD@localhost:5433/sales_agent_db

REDIS_URL=redis://localhost:6379/0
```

---

## CRM Integration Keys

### 5. Close CRM (Primary CRM)
**Get it:** https://app.close.com/settings/api/

```env
CLOSE_API_KEY=api_xxxxxxxxxxxxxxxxxx
```

**Steps:**
1. Log into Close CRM
2. Go to Settings → API Keys
3. Create new API key with name "sales-agent-dev"
4. Copy to `.env`

### 6. Apollo.io (Contact Enrichment)
**Get it:** https://app.apollo.io/settings/integrations

```env
APOLLO_API_KEY=your_apollo_api_key_here
```

**Rate Limit:** 600 requests/hour

### 7. LinkedIn Integration (Optional)
**Get it:** https://www.linkedin.com/developers/apps

```env
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret
LINKEDIN_REDIRECT_URI=http://localhost:8001/api/linkedin/callback
```

### 8. Browserbase (LinkedIn Scraping - Optional)
**Get it:** https://www.browserbase.com/

```env
BROWSERBASE_API_KEY=your_browserbase_key
BROWSERBASE_PROJECT_ID=your_project_id
```

**Rate Limit:** 100 requests/day

### 9. CRM Encryption Key (Required)
**Generate locally:**

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Copy output to:
```env
CRM_ENCRYPTION_KEY=generated_key_here
```

---

## Optional AI Providers

### Anthropic Claude (Fallback)
**Cost:** $0.001743 per request
**Get it:** https://console.anthropic.com/

```env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
```

### DeepSeek (Cost-Effective Research)
**Cost:** $0.00027 per request
**Get it:** https://platform.deepseek.com/

```env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### OpenRouter (Multi-Model Access)
**Get it:** https://openrouter.ai/

```env
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxx
```

---

## Monitoring & Observability (Optional)

### Sentry (Error Tracking)
**Get it:** https://sentry.io/

```env
SENTRY_DSN=https://xxxxx@xxxxx.ingest.sentry.io/xxxxx
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1
```

### Datadog (APM)
**Get it:** https://www.datadoghq.com/

```env
DATADOG_ENABLED=true
DATADOG_API_KEY=your_datadog_api_key
DATADOG_APP_KEY=your_datadog_app_key
DATADOG_SERVICE_NAME=sales-agent-api
DATADOG_SITE=datadoghq.com
```

---

## PgAdmin (Database UI)

```env
PGADMIN_DEFAULT_EMAIL=admin@salesagent.local
PGADMIN_DEFAULT_PASSWORD=CHANGE_ME_TO_SECURE_PASSWORD  # ⚠️ Change this!
```

---

## Verification Checklist

After setting up `.env`, verify everything works:

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Verify environment variables loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('✓ CEREBRAS_API_KEY:', os.getenv('CEREBRAS_API_KEY', 'NOT SET')[:20]+'...')"

# 3. Start server
python start_server.py

# 4. Check health endpoint
curl http://localhost:8001/api/health

# 5. Verify LangSmith tracing
# Go to https://smith.langchain.com/o/YOUR_ORG/projects/sales-agent-development
# You should see traces appear when you run agents
```

---

## Security Best Practices

### ✅ Do's
- Keep `.env` in `.gitignore` (already configured)
- Use different keys for development/production
- Rotate API keys periodically
- Use environment-specific `.env` files (`.env.development`, `.env.production`)
- Generate strong passwords for database/PgAdmin

### ❌ Don'ts
- **Never** commit `.env` to git
- **Never** share API keys in code/comments
- **Never** use production keys in development
- **Never** hardcode API keys anywhere

---

## Minimal Setup for Quick Start

If you want to start quickly with basic functionality:

**Required:**
```env
# AI
CEREBRAS_API_KEY=your_key_here
LANGCHAIN_API_KEY=your_key_here
LANGCHAIN_TRACING_V2=true

# Database
POSTGRES_PASSWORD=secure_password_here
DATABASE_URL=postgresql+psycopg://sales_agent:secure_password_here@localhost:5433/sales_agent_db

# Redis
REDIS_URL=redis://localhost:6379/0
```

**Optional (add as needed):**
- Cartesia TTS (for voice agents)
- Close CRM (for CRM sync)
- Apollo.io (for enrichment)

---

## Troubleshooting

### "API key not found" errors
1. Verify `.env` file exists: `ls -la .env`
2. Check key is set: `cat .env | grep CEREBRAS_API_KEY`
3. Restart server after adding keys

### LangSmith not showing traces
1. Verify `LANGCHAIN_TRACING_V2=true` (no quotes)
2. Check project name matches: `LANGCHAIN_PROJECT=sales-agent-development`
3. API key should start with `ls__`

### Database connection errors
1. Ensure Docker is running: `docker ps`
2. Check PostgreSQL container: `docker-compose ps postgres`
3. Verify DATABASE_URL password matches POSTGRES_PASSWORD

---

## Cost Estimates (Monthly)

Based on 10,000 leads/month:

| Service | Usage | Cost |
|---------|-------|------|
| Cerebras | 10k qualifications | ~$60 |
| LangSmith | Tracing | Free tier OK |
| Cartesia TTS | 1k voice calls | Variable |
| Close CRM | CRM operations | Free tier / plan |
| Apollo.io | 5k enrichments | Plan dependent |

**Total:** ~$60-100/month for 10k leads

---

## Need Help?

- **LangChain Docs**: https://python.langchain.com/docs/
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **Cerebras Docs**: https://inference-docs.cerebras.ai/
- **Close CRM API**: https://developer.close.com/

Remember: Start with free tiers, scale as you grow! 🚀
