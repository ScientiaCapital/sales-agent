# HubSpot API Access Request

**Requestor**: Tim Kipper, Sales Team
**Date**: January 26, 2025
**Project**: Sales Agent AI Pipeline - Coperniq Integration

---

## Executive Summary

We need HubSpot API access to enable **bidirectional sync between Close CRM (Sales) and HubSpot (GTM/Marketing)**. This integration will:

1. **Eliminate manual data entry** between sales and marketing teams
2. **Ensure lead attribution** from marketing campaigns flows to sales pipeline
3. **Enable automated handoffs** at lifecycle stage transitions
4. **Provide unified reporting** across the entire funnel

**Time to Value**: Integration code is already written and tested - we just need the API credentials.

---

## Business Case

### Problem Statement

Currently, Sales (Close CRM) and Marketing (HubSpot) operate in silos:
- Marketing generates leads in HubSpot via forms, ads, content
- Sales qualifies and works leads in Close CRM
- **No automatic sync** = manual copy/paste, data inconsistency, lost attribution

### Solution Impact

| Metric | Current State | With Integration |
|--------|--------------|------------------|
| Lead handoff time | 1-2 days manual | Real-time automated |
| Data accuracy | ~70% (manual entry) | 99%+ (API sync) |
| Marketing attribution | Incomplete | Full funnel tracking |
| Rep productivity | -2 hrs/day on data entry | Automated |

### ROI Calculation

**Conservative Estimate (50 leads/week)**:
- Manual entry time saved: 10 hrs/week × $50/hr = **$500/week**
- Faster lead response: +15% conversion = **$X,XXX/week** (varies by ACV)
- Better attribution: Optimized marketing spend

**Annual Savings**: **$26,000+** in time savings alone

---

## Technical Requirements

### What We Need

1. **HubSpot Private App API Key** (recommended for backend integrations)
   - Simpler setup than OAuth
   - No token refresh needed
   - Scoped permissions

2. **Required API Scopes**:
   ```
   crm.objects.contacts.read
   crm.objects.contacts.write
   crm.objects.companies.read
   crm.objects.companies.write
   crm.objects.deals.read
   crm.objects.deals.write
   ```

3. **Portal ID** (HubSpot account identifier)

### Optional (For Advanced Features)

4. **Webhook Secret** (for real-time form submission handling)
5. **Marketing Email API** (for campaign tracking)

---

## How to Generate API Key

### Step 1: Create Private App

1. Go to HubSpot → Settings → Integrations → Private Apps
2. Click "Create a private app"
3. Name: `sales-agent-integration`
4. Description: `Close CRM bidirectional sync for sales pipeline`

### Step 2: Configure Scopes

Select these scopes:
- **CRM**: Contacts (Read/Write), Companies (Read/Write), Deals (Read/Write)
- **Standard**: Account Information (Read)

### Step 3: Create & Copy Token

1. Click "Create app"
2. Copy the access token (starts with `pat-na1-...`)
3. Share token securely via 1Password or encrypted channel

---

## Integration Architecture

```
┌─────────────────┐                      ┌─────────────────┐
│   CLOSE CRM     │                      │    HUBSPOT      │
│   (Sales)       │                      │   (Marketing)   │
│                 │                      │                 │
│  ・Leads        │◄────────────────────►│  ・Contacts     │
│  ・Contacts     │    Bidirectional     │  ・Companies    │
│  ・Deals        │       Sync           │  ・Deals        │
│  ・Smart Views  │                      │  ・Forms        │
└────────┬────────┘                      └────────┬────────┘
         │                                        │
         │                                        │
         ▼                                        ▼
┌─────────────────────────────────────────────────────────┐
│                 SALES AGENT PIPELINE                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │Qualify  │─►│ Enrich  │─►│ Score   │─►│ Route   │   │
│  │(AI)     │  │(Hunter) │  │(ATL/BTL)│  │(Close)  │   │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │
│                                                         │
│  Features:                                              │
│  ・AI qualification (Cerebras, 633ms)                  │
│  ・Automatic enrichment (Hunter.io)                     │
│  ・ATL/BTL classification                               │
│  ・Deduplication (85% fuzzy match)                     │
│  ・Smart View routing                                   │
└─────────────────────────────────────────────────────────┘
```

---

## Sync Behavior

### HubSpot → Close (Marketing to Sales)

**Trigger**: Form submission, lifecycle stage = MQL
**Action**: Create lead in Close with:
- Contact info (name, email, phone)
- Company info
- Source attribution (campaign, form, UTM)
- Lifecycle stage: "Marketing Qualified Lead"

### Close → HubSpot (Sales to Marketing)

**Trigger**: Lead status change (SQL, Opportunity, Won, Lost)
**Action**: Update HubSpot contact with:
- Updated lifecycle stage
- Deal information (if created)
- Win/loss reason for attribution

### Bidirectional Fields

| Field | Direction | Notes |
|-------|-----------|-------|
| Email | Both | Primary key for matching |
| Name | Both | First/Last name |
| Company | Both | Company name |
| Phone | Both | Primary phone |
| Lifecycle Stage | Close → HubSpot | MQL, SQL, Customer |
| Lead Status | Both | Sync status changes |
| Deal Amount | Close → HubSpot | For revenue attribution |
| Source | HubSpot → Close | Original lead source |

---

## Security & Compliance

### Data Handling

- **No PII stored** outside of CRMs - pipeline is stateless
- **Encrypted in transit** (HTTPS/TLS 1.3)
- **API key stored** in environment variables (.env), never in code
- **Rate limiting** respects HubSpot limits (100 req/10 sec)

### Access Control

- Only designated team members have access to .env files
- API key can be rotated anytime in HubSpot settings
- Webhook signatures verified for incoming events

### Audit Trail

- All sync operations logged with timestamps
- Error tracking via Sentry (optional)
- Sync metrics dashboard available

---

## Implementation Timeline

| Phase | Timeline | Deliverables |
|-------|----------|--------------|
| **Phase 1** (Done) | Complete | HubSpot service code written and tested |
| **Phase 2** (Pending) | 1 day | API key configuration, live testing |
| **Phase 3** | 1-2 days | Webhook setup for form submissions |
| **Phase 4** | Ongoing | Monitoring and optimization |

**Total Time to Live**: 2-3 days after receiving API key

---

## Next Steps

1. **CTO/GTM**: Generate HubSpot Private App API key
2. **Tim**: Add key to `.env` configuration
3. **Tim**: Run integration tests
4. **Team**: Verify sync working both directions
5. **Team**: Set up webhook for form submissions

---

## Support & Questions

**Technical Contact**: Tim Kipper
**Code Repository**: `sales-agent` project
**Relevant Files**:
- `backend/app/services/crm/hubspot.py` - HubSpot service
- `backend/app/api/hubspot.py` - API endpoints
- `backend/app/core/config.py` - Configuration

---

## Appendix: API Endpoints Available

Once API key is configured, these endpoints will be available:

```
GET  /api/v1/hubspot/health           # Check HubSpot connection
POST /api/v1/hubspot/contacts         # Create contact in HubSpot
GET  /api/v1/hubspot/contacts/{email} # Get contact by email
GET  /api/v1/hubspot/contacts         # List contacts
POST /api/v1/hubspot/sync             # Trigger sync operation
POST /api/v1/hubspot/sync/from-close  # Push Close lead to HubSpot
POST /api/v1/hubspot/webhooks         # Receive HubSpot webhooks
POST /api/v1/hubspot/companies        # Create company
POST /api/v1/hubspot/deals            # Create deal
```

---

**Document Version**: 1.0
**Last Updated**: January 26, 2025
