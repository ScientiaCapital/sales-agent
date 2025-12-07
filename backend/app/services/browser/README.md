# Browser Automation Services

Cloud browser automation for LinkedIn social selling and web scraping using Browserbase + Playwright.

## Architecture

```
LinkedInAgent (high-level API)
       ↓
LinkedInSessionManager (authentication + rate limiting)
       ↓
BrowserbaseClient (cloud browser + Playwright)
       ↓
Browserbase Cloud (persistent sessions, stealth mode)
```

## Features

### BrowserbaseClient
- **Cloud Browser**: Browserbase-hosted Chrome instances
- **Persistent Contexts**: Sessions survive between runs (stay logged in)
- **Stealth Mode**: Advanced bot detection avoidance
- **Accessibility Trees**: Navigate DOM without VLM (no vision model needed)
- **Realistic Delays**: Human-like interaction timing

### LinkedInSessionManager
- **Persistent Login**: Stays authenticated between runs
- **Session Validation**: Checks if logged in before actions
- **Rate Limit Enforcement**: Minimum 3 seconds between actions

### LinkedInAgent
- **Connection Requests**: With personalized notes (max 300 chars)
- **Direct Messages**: To 1st-degree connections
- **Post Reactions**: Like, celebrate, support, love, insightful, curious
- **Post Comments**: Add comments to LinkedIn posts
- **Profile Scraping**: Extract profile data using accessibility tree

## Rate Limits (Conservative)

| Action | Daily Limit | Why |
|--------|-------------|-----|
| Connections | 10 | Very conservative - LinkedIn bans are permanent |
| Messages | 25 | Moderate - for engaged leads only |
| Profile Views | 50 | Tracking visibility |
| Reactions | 30 | Low risk, but still limited |
| Comments | 20 | Medium risk - requires thoughtful content |
