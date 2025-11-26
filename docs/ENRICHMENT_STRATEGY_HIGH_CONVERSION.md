# Enrichment Strategy: High-Conversion Outreach

**Author**: Tim Kipper | GTM Engineering
**Date**: November 26, 2025
**Goal**: Find the BEST contact data for highest conversion rates

---

## The Enrichment Philosophy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ENRICHMENT = SUCCESS SETUP                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   "The quality of your enrichment determines your conversion rate"     │
│                                                                         │
│   Bad enrichment → Main line → Gatekeeper → Voicemail → Lost deal      │
│   Good enrichment → Mobile → Decision maker → Conversation → CLOSE     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Contact Priority Hierarchy

### Phone Numbers (Best to Worst)

```
┌────────────────────────────────────────────────────────────────────────┐
│  PHONE PRIORITY FOR HIGH CONVERSION                                    │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  1. 📱 MOBILE/CELL (GOLD)                                             │
│     • Direct to decision maker's pocket                                │
│     • No gatekeeper                                                    │
│     • Can text/SMS                                                     │
│     • 5x higher connection rate                                        │
│     → Sources: Apollo reveal, LinkedIn, personal website               │
│                                                                        │
│  2. 📞 OFFICE DIRECT LINE (SILVER)                                    │
│     • Rings on their desk                                              │
│     • Usually answered personally                                      │
│     • Can leave direct voicemail                                       │
│     → Sources: Hunter.io, company directory, email signature           │
│                                                                        │
│  3. 🏢 MAIN LINE + EXTENSION (BRONZE)                                 │
│     • Need extension to bypass gatekeeper                              │
│     • "I'm returning John's call, ext 234"                            │
│     → Sources: Company website, public records                         │
│                                                                        │
│  4. 🚪 MAIN LINE ONLY (LAST RESORT)                                   │
│     • Must get through CSR/gatekeeper                                  │
│     • Use: "I have a quick question for [Name] about [specific]"      │
│     • Never say "sales" or "I want to tell them about..."             │
│     → Sources: Google, BBB, license records                            │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Phone Type Detection

```python
def classify_phone_type(phone: str) -> str:
    """
    Classify phone number type for priority sorting.

    Mobile prefixes vary by area but common patterns:
    - Personal cell: Often different area code than business
    - Direct dial: Usually same area code as main + sequential
    """
    # Check against known VOIP/mobile carriers
    # Check if different area code than company main
    # Check if sequential to main line (likely extension)
    pass
```

---

## Free-First Enrichment Strategy

### Priority Order (Cheapest First)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FREE-FIRST ENRICHMENT WATERFALL                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  STAGE 1: WEBSITE DISCOVERY ($0)                                       │
│  ─────────────────────────────────                                      │
│  • Domain inference from company name                                   │
│  • Google search: "{company} {city} {state}"                           │
│  • Success rate: ~60%                                                   │
│  • Time: ~2 seconds                                                     │
│                                                                         │
│          ↓ If website found                                             │
│                                                                         │
│  STAGE 2: EMAIL EXTRACTION ($0)                                        │
│  ───────────────────────────────                                        │
│  • Scrape contact page, about page, team page                          │
│  • Extract mailto: links                                                │
│  • Pattern detection: info@, contact@, [name]@                         │
│  • Success rate: 30-40%                                                 │
│  • Time: 3-5 seconds                                                    │
│                                                                         │
│          ↓ If no contacts found                                         │
│                                                                         │
│  STAGE 3: LINKEDIN PEOPLE SEARCH ($0)                                  │
│  ─────────────────────────────────────                                  │
│  • Google: "site:linkedin.com {company} {title}"                       │
│  • Find decision makers by title                                        │
│  • Get names for email guessing                                         │
│  • Rate limited: ~100/day                                               │
│  • Time: 1-2 seconds                                                    │
│                                                                         │
│          ↓ If LinkedIn profiles found                                   │
│                                                                         │
│  STAGE 4: EMAIL PATTERN GUESSING ($0)                                  │
│  ─────────────────────────────────────                                  │
│  • Try common patterns:                                                 │
│    - first.last@domain.com                                              │
│    - firstlast@domain.com                                               │
│    - first@domain.com                                                   │
│    - flast@domain.com                                                   │
│  • Verify with MX record check                                          │
│  • Time: <1 second                                                      │
│                                                                         │
│          ↓ ONLY if all free methods fail                                │
│                                                                         │
│  STAGE 5: HUNTER.IO DOMAIN SEARCH ($0.01/domain)                       │
│  ─────────────────────────────────────────────────                      │
│  • Returns ALL public emails for domain                                 │
│  • Includes names, titles, confidence scores                            │
│  • ATL filter: seniority=executive                                      │
│  • Success rate: 70-80%                                                 │
│  • Time: ~500ms                                                         │
│                                                                         │
│          ↓ For highest-value leads ONLY                                 │
│                                                                         │
│  STAGE 6: APOLLO REVEAL (EXPENSIVE - Use Sparingly)                    │
│  ──────────────────────────────────────────────────                     │
│  • ~$1/contact for full reveal                                          │
│  • Gets mobile phones, verified emails                                  │
│  • Only use for:                                                        │
│    - Hot leads (score > 80)                                             │
│    - When mobile is critical                                            │
│    - High ACV opportunities                                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Cost Comparison

| Method | Cost | Success Rate | Phone Quality |
|--------|------|--------------|---------------|
| Website Discovery | $0 | 60% | Main line |
| Email Extraction | $0 | 30-40% | N/A |
| LinkedIn Search | $0 | 50% | Profile link |
| Email Guessing | $0 | 40% | N/A |
| Hunter.io | $0.01/domain | 70-80% | Some direct |
| Apollo Reveal | ~$1/contact | 90%+ | Mobile! |

---

## ATL Contact Targeting

### Who to Find (Above-The-Line)

```
┌────────────────────────────────────────────────────────────────────────┐
│  DECISION MAKER TITLES - PRIORITY ORDER                                │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  TIER 1: ULTIMATE DECISION MAKERS (Always reach first)                │
│  ─────────────────────────────────────────────────────                 │
│  • Owner / Co-Owner                                                    │
│  • CEO / President                                                     │
│  • Founder / Co-Founder                                                │
│  • Principal                                                           │
│  • Managing Partner                                                    │
│                                                                        │
│  TIER 2: SENIOR LEADERSHIP (Great alternatives)                       │
│  ──────────────────────────────────────────────                        │
│  • Vice President (VP)                                                 │
│  • General Manager (GM)                                                │
│  • Director of Operations                                              │
│  • COO / CFO / CTO                                                     │
│                                                                        │
│  TIER 3: DEPARTMENT HEADS (Can champion deal)                         │
│  ─────────────────────────────────────────────                         │
│  • Operations Manager                                                  │
│  • Sales Manager                                                       │
│  • Service Manager                                                     │
│  • Business Development                                                │
│                                                                        │
│  AVOID: BTL (Below-The-Line)                                          │
│  ───────────────────────────────                                       │
│  • Technicians, Installers                                             │
│  • Administrative assistants                                           │
│  • Receptionists                                                       │
│  • Project managers (without budget authority)                         │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### ATL Detection Code

```python
ATL_TITLES = [
    # Tier 1
    "owner", "ceo", "president", "founder", "principal", "partner",
    # Tier 2
    "vp", "vice president", "gm", "general manager", "director", "coo", "cfo",
    # Tier 3
    "manager", "head of", "lead"
]

BTL_TITLES = [
    "technician", "installer", "assistant", "receptionist", "admin",
    "coordinator", "specialist", "analyst", "associate"
]

def is_atl(title: str) -> bool:
    """Check if title indicates decision-making authority."""
    title_lower = title.lower()

    # Reject BTL first
    if any(btl in title_lower for btl in BTL_TITLES):
        return False

    # Accept ATL
    return any(atl in title_lower for atl in ATL_TITLES)
```

---

## Signal Watching: Know When to Strike

### High-Intent Signals (CALL IMMEDIATELY)

```
┌────────────────────────────────────────────────────────────────────────┐
│  🔥 HIGH-INTENT SIGNALS - DROP EVERYTHING AND CALL                    │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  EMAIL ENGAGEMENT                                                      │
│  • 3+ email opens in 24 hours                                          │
│  • Clicked pricing link                                                │
│  • Forwarded to colleague                                              │
│  • Replied (even "not interested" = engaged)                           │
│                                                                        │
│  WEBSITE BEHAVIOR                                                      │
│  • Visited pricing page                                                │
│  • Downloaded case study / whitepaper                                  │
│  • Watched demo video                                                  │
│  • Returned visitor (2+ sessions)                                      │
│                                                                        │
│  SOCIAL SIGNALS                                                        │
│  • Liked/commented on your post                                        │
│  • Viewed your LinkedIn profile                                        │
│  • Connected with you                                                  │
│  • Posted about relevant pain points                                   │
│                                                                        │
│  BUSINESS SIGNALS                                                      │
│  • Hiring for roles you solve                                          │
│  • Announced expansion / growth                                        │
│  • Leadership change (new decision maker)                              │
│  • Competitor mentioned in news                                        │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Social Intelligence Integration

Your existing Social Intelligence system watches for signals:

```python
# From social_intelligence_runner.py

class HighIntentDetector:
    """
    Monitors LinkedIn/Twitter for buying signals.

    When detected:
    1. Sets "High Intent Flag" = Yes in Close CRM
    2. Drafts personalized email referencing the signal
    3. Alerts sales rep to call immediately
    """

    HIGH_INTENT_KEYWORDS = [
        "looking for", "evaluating", "considering",
        "need help with", "struggling with",
        "anyone recommend", "does anyone know",
        "hiring", "expanding", "growing"
    ]
```

---

## Multi-Channel Outreach Sequence

### Optimal Sequence for High Conversion

```
┌────────────────────────────────────────────────────────────────────────┐
│  DAY-BY-DAY OUTREACH SEQUENCE                                          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  DAY 1: EMAIL #1 (Value-First)                                        │
│  ──────────────────────────────                                        │
│  • Subject: Specific to their business/industry                        │
│  • Body: Quick value prop + one question                               │
│  • CTA: "Worth a quick call?"                                          │
│  • Track: Opens, clicks                                                │
│                                                                        │
│  DAY 2: LINKEDIN CONNECTION                                           │
│  ───────────────────────────────                                       │
│  • Personalized note referencing email                                 │
│  • "Sent you a note about {specific thing}"                           │
│  • Builds familiarity before call                                      │
│                                                                        │
│  DAY 3: PHONE CALL #1                                                 │
│  ─────────────────────────                                             │
│  • Morning (8-9 AM) or late afternoon (4-5 PM)                        │
│  • "Hi {Name}, this is Tim from Coperniq..."                          │
│  • Reference email: "I sent you a note about..."                      │
│  • Leave voicemail if no answer                                        │
│                                                                        │
│  DAY 5: EMAIL #2 (Follow-up)                                          │
│  ───────────────────────────                                           │
│  • Reply to thread (keeps context)                                     │
│  • "Wanted to bump this up..."                                        │
│  • Add new value (case study, stat)                                    │
│                                                                        │
│  DAY 7: SMS (If mobile available)                                     │
│  ─────────────────────────────────                                     │
│  • Short: "Hi {Name}, Tim from Coperniq. Tried reaching you about     │
│           {topic}. Worth 5 min?"                                       │
│  • Only if you have mobile number                                      │
│  • Highest response rate channel!                                      │
│                                                                        │
│  DAY 8: PHONE CALL #2                                                 │
│  ─────────────────────────                                             │
│  • Different time of day                                               │
│  • Try mobile if available                                             │
│  • Try direct line if main didn't work                                 │
│                                                                        │
│  DAY 10: EMAIL #3 (Break-up)                                          │
│  ───────────────────────────                                           │
│  • "Closing the loop" / "Last attempt"                                │
│  • Creates urgency without being pushy                                 │
│  • Often gets response!                                                │
│                                                                        │
│  DAY 14+: NURTURE                                                     │
│  ─────────────────────                                                 │
│  • Monthly value content                                               │
│  • Watch for signals                                                   │
│  • Re-engage when signal detected                                      │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Channel Effectiveness Stats

| Channel | Response Rate | Best For |
|---------|---------------|----------|
| SMS | 45% | Mobile, quick response |
| Phone (Mobile) | 35% | Conversations, objection handling |
| Phone (Direct) | 25% | When mobile unavailable |
| Email | 15-20% | Initial outreach, follow-up |
| LinkedIn | 10-15% | Building familiarity |
| Phone (Main) | 5-10% | Last resort |

---

## Gatekeeper Strategy

### When You Hit a Receptionist/CSR

```
┌────────────────────────────────────────────────────────────────────────┐
│  GATEKEEPER SCRIPTS                                                    │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  SCRIPT 1: Direct & Professional                                      │
│  ────────────────────────────────                                      │
│  "Hi, this is Tim calling for [Name]. Is he/she available?"           │
│  • Simple, assumes you belong                                          │
│  • Don't explain why                                                   │
│                                                                        │
│  SCRIPT 2: Returning Call                                             │
│  ─────────────────────────────                                         │
│  "Hi, I'm returning [Name]'s call. Can you put me through?"           │
│  • Only use if you've left voicemail                                   │
│  • Creates sense of existing relationship                              │
│                                                                        │
│  SCRIPT 3: Quick Question                                             │
│  ──────────────────────────                                            │
│  "Hi, I have a quick question about [specific topic] for [Name].      │
│   Is he/she available for 2 minutes?"                                  │
│  • Topic should be relevant to their role                              │
│  • Time-bound reduces resistance                                       │
│                                                                        │
│  SCRIPT 4: Referral Drop                                              │
│  ─────────────────────────                                             │
│  "Hi, [Referrer Name] suggested I reach out to [Name] about           │
│   [topic]. Is he/she in?"                                              │
│  • Only if you have actual referral                                    │
│  • Very effective                                                      │
│                                                                        │
│  NEVER SAY:                                                           │
│  ───────────                                                           │
│  • "I'm a sales rep from..."                                          │
│  • "I want to tell them about our product..."                         │
│  • "Can I speak to the person in charge of..."                        │
│  • "Who handles purchasing decisions?"                                 │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Gold Standard Output Schema

### Enriched Lead CSV Columns

```csv
company_name,domain,company_website,company_phone,
contact_name,contact_email,contact_phone,contact_phone_type,contact_title,
linkedin_url,is_atl,
qualification_score,tier,
dedup_status,
source,enrichment_cost,
city,state,zip,
last_signal,signal_date,high_intent_flag
```

### Phone Type Values

| Value | Meaning | Priority |
|-------|---------|----------|
| `mobile` | Cell/Mobile phone | 1 (BEST) |
| `direct` | Office direct line | 2 |
| `extension` | Main + extension | 3 |
| `main` | Company main line | 4 |
| `unknown` | Type not determined | 5 |

---

## Implementation Files

| File | Purpose |
|------|---------|
| `free_first_enrichment.py` | Cost-optimized enrichment |
| `hunter_service.py` | Hunter.io API integration |
| `apollo.py` | Apollo reveal (expensive) |
| `email_extractor.py` | Website email scraping |
| `website_discovery.py` | Domain inference |
| `social_intelligence_runner.py` | Signal monitoring |
| `close.py` | CRM integration |

---

## Success Metrics

### Track These KPIs

| Metric | Target | Formula |
|--------|--------|---------|
| Contact Rate | >30% | Conversations / Dials |
| Email Open Rate | >40% | Opens / Sent |
| Reply Rate | >10% | Replies / Sent |
| Meeting Book Rate | >5% | Meetings / Contacts |
| Mobile Coverage | >20% | Leads with Mobile / Total |
| ATL Coverage | >60% | Leads with ATL / Total |
| Cost per Contact | <$0.05 | Total Spend / Contacts Found |

---

**"The enrichment stage is where you WIN or LOSE the deal before it even starts"**

*Last Updated: November 26, 2025*
