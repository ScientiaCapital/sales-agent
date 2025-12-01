# Quick Start: API Keys Setup

**5-Minute Guide to Get Started**

---

## 1. Generated Encryption Key (Ready to Use)

Add this to your `.env` file **immediately**:

```bash
CRM_ENCRYPTION_KEY=TjTRReLJHMQ4PmFmvNMh1mgdbUmE_IcY2ISRGMUHLy8=
```

---

## 2. Required API Keys (Get These First)

### Priority 1: Database (Required for Everything)

**Supabase** - Get in 2 minutes:
1. Go to: https://app.supabase.com/
2. Create new project
3. Go to Settings → API
4. Copy these values to `.env`:

```bash
SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGc...YOUR_JWT_TOKEN
```

5. Run database schema:
   - Open: https://app.supabase.com/project/YOUR_PROJECT/sql
   - Paste: `backend/supabase_schema.sql` contents
   - Click Run

---

### Priority 2: AI Models (Required for Agent Logic)

**Cerebras** - Ultra-fast AI:
1. Go to: https://cloud.cerebras.ai/
2. Sign up / Login
3. Generate API key
4. Add to `.env`:

```bash
CEREBRAS_API_KEY=csk-YOUR_KEY_HERE
```

**Anthropic** - Fallback AI:
1. Go to: https://console.anthropic.com/
2. Sign up / Login
3. Generate API key
4. Add to `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
```

---

### Priority 3: CRM Integration

**Close CRM** - Lead management:
1. Go to: https://app.close.com/settings/api/
2. Create new API key named "sales-agent-dev"
3. Add to `.env`:

```bash
CLOSE_API_KEY=api_YOUR_KEY_HERE
```

---

### Priority 4: Web Scraping

**Browserbase** - LinkedIn/web scraping:
1. Go to: https://www.browserbase.com/
2. Sign up / Login
3. Get API key and Project ID
4. Add to `.env`:

```bash
BROWSERBASE_API_KEY=YOUR_KEY_HERE
BROWSERBASE_PROJECT_ID=YOUR_PROJECT_ID_HERE
```

---

### Priority 5: Email Discovery (Optional but Recommended)

**Hunter.io** - Email finder:
1. Go to: https://hunter.io/api-keys
2. Sign up (Free tier: 25 searches/month)
3. Copy API key
4. Add to `.env`:

```bash
HUNTER_API_KEY=YOUR_40_CHAR_HEX_KEY_HERE
```

---

## 3. Validate Setup

```bash
# Check all keys are set correctly
python validate_api_keys.py

# Test database connection
python validate_api_keys.py --test-connection
```

**Expected Result:**
```
✅ Validated:  9
❌ Missing:    0
⚠️  Warnings:   0
```

---

## 4. Start Application

```bash
# Start infrastructure
docker-compose up -d

# Start server
python start_server.py

# Test health endpoint
curl http://localhost:8001/api/health
```

---

## Minimal Setup (Just to Test)

If you want to start quickly with basic functionality:

**Required Keys (Minimum):**
1. `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`
2. `CEREBRAS_API_KEY`
3. `CRM_ENCRYPTION_KEY` (use generated one above)

**Can Add Later:**
- `ANTHROPIC_API_KEY` (fallback)
- `CLOSE_API_KEY` (CRM sync)
- `BROWSERBASE_API_KEY` (web scraping)
- `HUNTER_API_KEY` (email discovery)

---

## Cost Summary (Monthly)

| Service | Free Tier | Paid Tier | Recommendation |
|---------|-----------|-----------|----------------|
| Supabase | 500 MB | $25/month | Start with free |
| Cerebras | Pay-per-use | ~$60/10k calls | Required |
| Anthropic | Pay-per-use | ~$17/1k calls | Required |
| Close CRM | Trial | Plan dependent | Trial first |
| Browserbase | Limited | Variable | Trial first |
| Hunter.io | 25/month | $49/month (500) | Start with free |

**Total to Start:** $0-25/month (using free tiers)
**Production:** ~$150-200/month (10k leads)

---

## Security Checklist

- [x] `.env` file in `.gitignore` (already done)
- [x] No hardcoded keys (verified)
- [x] Encryption infrastructure ready (cryptography installed)
- [ ] Add real API keys to `.env`
- [ ] Never commit `.env` to git
- [ ] Use different keys for production
- [ ] Rotate keys every 90 days

---

## Troubleshooting

**"ModuleNotFoundError: No module named 'supabase'"**
```bash
pip install supabase
```

**"Invalid API key format"**
- Check key has no extra spaces/quotes
- Verify entire key was copied (common truncation)
- Check required format in validation report

**"Connection refused" from Supabase**
- Verify URL format: `https://PROJECT.supabase.co`
- Check service key starts with `eyJ`
- Ensure database schema was created

---

## Quick Commands

```bash
# Generate new encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Validate all keys
python validate_api_keys.py

# Test connectivity
python validate_api_keys.py --test-connection

# Check what's missing
cat .env | grep -E "your_|CHANGE_ME"
```

---

## Need Help?

- **Full Documentation:** `API_KEYS_SETUP.md`
- **Validation Report:** `API_KEYS_VALIDATION_REPORT.md`
- **Database Schema:** `backend/supabase_schema.sql`

---

**Time to Complete:** 10-15 minutes for all keys
**Minimum to Start:** 5 minutes (Supabase + Cerebras + Encryption Key)
