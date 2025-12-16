# Hunter.io API Reference

## Endpoints

| Endpoint | Method | URL | Credits | Use Case |
|----------|--------|-----|---------|----------|
| **Discover** | POST | `https://api.hunter.io/v2/discover` | ? | AI-powered contact discovery |
| **Domain Search** | GET | `https://api.hunter.io/v2/domain-search?domain={domain}` | 1 | Find all contacts at a company |
| **Email Finder** | GET | `https://api.hunter.io/v2/email-finder?domain={domain}&first_name={first}&last_name={last}` | 1 | Find specific person's email |
| **Email Verification** | GET | `https://api.hunter.io/v2/email-verifier?email={email}` | 1 | Verify email deliverability |
| **Company Enrichment** | GET | `https://api.hunter.io/v2/companies/find?domain={domain}` | ? | Get company info |
| **Person Enrichment** | GET | `https://api.hunter.io/v2/people/find?email={email}` | ? | Get person info from email |
| **Combined Enrichment** | GET | `https://api.hunter.io/v2/combined/find?email={email}` | ? | Company + Person enrichment |

## Primary Use Cases for Sales Agent

### 1. Domain Search (Main Method)
Find all emails at a company domain:
```bash
curl "https://api.hunter.io/v2/domain-search?domain=acmeheating.com&api_key=$HUNTER_API_KEY"
```

Returns:
- All discovered emails at domain
- Names, titles, confidence scores
- LinkedIn URLs
- Sources where email was found

### 2. Email Finder
When we have a name but need email:
```bash
curl "https://api.hunter.io/v2/email-finder?domain=acme.com&first_name=John&last_name=Smith&api_key=$HUNTER_API_KEY"
```

### 3. Email Verification
Verify before sending:
```bash
curl "https://api.hunter.io/v2/email-verifier?email=john@acme.com&api_key=$HUNTER_API_KEY"
```

## Integration Points

- **Service**: `backend/app/services/hunter_service.py`
- **CLI**: `backend/enrich_hunter.py`
- **Env Var**: `HUNTER_API_KEY`

## Rate Limits & Credits

- ~2000 credits available
- 1 credit per domain search
- 1 credit per email finder
- 1 credit per verification
- Hourly rate limits apply

## Full Documentation

https://hunter.io/api-documentation
