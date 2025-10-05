# LinkedIn OAuth 2.0 Implementation

## Overview

Complete OAuth 2.0 connector for LinkedIn API integration, following the same architecture patterns as the existing HubSpot integration.

**Status**: ✅ Implementation Complete

**Key Features:**
- OAuth 2.0 Authorization Code Flow with PKCE
- State parameter for CSRF protection
- Token refresh with graceful degradation
- Strict rate limiting (100 requests/day for basic tier)
- Profile and email API access
- Comprehensive error handling
- Full OpenAPI documentation

---

## Architecture

### 1. Service Layer (`app/services/linkedin_oauth.py`)

**Class:** `LinkedInProvider(CRMProvider)`

Implements the CRM provider interface with LinkedIn-specific OAuth 2.0 logic.

**Key Methods:**

#### OAuth Flow
```python
generate_authorization_url(scopes: List[str]) -> tuple[str, str, str]
# Returns: (auth_url, code_verifier, state)

exchange_code_for_token(authorization_code: str, code_verifier: str, state: str) -> Dict
# Exchanges code for access/refresh tokens

refresh_access_token() -> str
# Refreshes token (if refresh token available)
```

#### Profile Operations
```python
get_profile() -> Dict[str, Any]
# Requires: r_liteprofile scope

get_email_address() -> str
# Requires: r_emailaddress scope
```

#### Rate Limiting
```python
_check_rate_limit() -> None
# Enforces 100 requests/day limit via Redis

check_rate_limit() -> Dict[str, Any]
# Returns current usage and remaining quota
```

**LinkedIn-Specific Considerations:**

1. **No Refresh Tokens for Some APIs**
   - Compliance API tokens last 1 year, no refresh
   - Standard API provides refresh tokens (1 year validity)
   - Graceful handling when refresh not available

2. **Rate Limits**
   - Basic tier: 100 requests/day
   - Redis tracking with automatic reset at midnight UTC

3. **Token Validity**
   - Access tokens: 60 days (standard) or 1 year (compliance)
   - Refresh tokens: 1 year (when provided)

---

## API Endpoints

### Base Path: `/api/linkedin`

All endpoints are fully documented with OpenAPI schemas.

### 1. OAuth Flow Endpoints

#### `GET /api/linkedin/authorize`

Generate OAuth authorization URL to initiate the flow.

**Query Parameters:**
- `scopes` (string, optional): Space-separated scopes (default: `r_liteprofile r_emailaddress`)

**Response:**
```json
{
  "authorization_url": "https://www.linkedin.com/oauth/v2/authorization?...",
  "state": "abc123...",
  "expires_in": 600
}
```

**Usage:**
```bash
curl "http://localhost:8001/api/linkedin/authorize?scopes=r_liteprofile%20r_emailaddress"
```

**Flow:**
1. Call this endpoint
2. Redirect user to `authorization_url`
3. User grants consent on LinkedIn
4. LinkedIn redirects to callback with `code` and `state`

---

#### `GET /api/linkedin/callback`

Handle OAuth callback and exchange code for tokens.

**Query Parameters:**
- `code` (string, required): Authorization code from LinkedIn
- `state` (string, required): State for CSRF verification

**Response:**
```json
{
  "access_token": "AQX...",
  "token_type": "Bearer",
  "expires_in": 5184000,
  "expires_at": "2024-03-15T10:00:00Z",
  "refresh_token_available": true,
  "scope": "r_liteprofile r_emailaddress"
}
```

**Security:**
- PKCE code_verifier retrieved from Redis (stored during `/authorize`)
- State parameter verified against Redis
- Tokens encrypted before storage

**Error Responses:**
- `401 Unauthorized`: Code exchange failed or state verification failed
- `500 Internal Server Error`: Network or unexpected error

---

#### `POST /api/linkedin/refresh`

Refresh access token using refresh token.

**Important:** LinkedIn may not provide refresh tokens for all API types. If unavailable, returns error indicating re-authentication required.

**Response (Success):**
```json
{
  "access_token": "AQY...",
  "token_type": "Bearer",
  "expires_in": 5184000,
  "expires_at": "2024-05-15T10:00:00Z",
  "refresh_token_available": true
}
```

**Response (No Refresh Token):**
```json
{
  "detail": "No refresh token available - LinkedIn did not provide refresh capability. Please re-authenticate via OAuth flow."
}
```

---

### 2. Profile API Endpoints

#### `GET /api/linkedin/profile`

Get authenticated user's LinkedIn profile.

**Requires:**
- Valid access token
- Scope: `r_liteprofile`

**Response:**
```json
{
  "id": "abc123",
  "first_name": "John",
  "last_name": "Doe",
  "profile_url": "https://linkedin.com/in/abc123",
  "raw_data": {
    "id": "abc123",
    "localizedFirstName": "John",
    "localizedLastName": "Doe"
  }
}
```

**Rate Limit:** Counts toward 100/day limit

---

#### `GET /api/linkedin/email`

Get authenticated user's email address.

**Requires:**
- Valid access token
- Scope: `r_emailaddress`

**Response:**
```json
{
  "email": "john.doe@example.com"
}
```

**Rate Limit:** Counts toward 100/day limit

---

### 3. Utility Endpoints

#### `GET /api/linkedin/rate-limit`

Check current rate limit status.

**Response:**
```json
{
  "remaining": 85,
  "limit": 100,
  "reset_at": "2024-01-16T00:00:00Z",
  "retry_after": 0,
  "requests_today": 15
}
```

**Use Case:** Monitor API usage to avoid hitting daily limit

---

#### `GET /api/linkedin/token-status`

Check token expiration and refresh availability.

**Response:**
```json
{
  "has_access_token": true,
  "has_refresh_token": false,
  "expires_at": "2024-03-15T10:00:00Z",
  "is_expired": false,
  "days_until_expiry": 45.5,
  "requires_reauth": false
}
```

**Use Case:** Determine if token refresh is possible or re-authentication needed

---

## Setup Instructions

### 1. LinkedIn App Configuration

**Create LinkedIn App:**
1. Go to https://www.linkedin.com/developers/apps
2. Create a new app
3. Configure OAuth 2.0 settings:
   - **Redirect URLs**: `http://localhost:8001/api/linkedin/callback`
   - **Scopes**:
     - `r_liteprofile` (Sign In with LinkedIn)
     - `r_emailaddress` (Sign In with LinkedIn)
     - `w_member_social` (Share on LinkedIn - optional)

**Get Credentials:**
- Client ID: Found in app settings → Auth tab
- Client Secret: Found in app settings → Auth tab

### 2. Environment Configuration

Add to `.env` file:

```bash
# LinkedIn OAuth 2.0 Configuration
LINKEDIN_CLIENT_ID=your_linkedin_client_id_here
LINKEDIN_CLIENT_SECRET=your_linkedin_client_secret_here
LINKEDIN_REDIRECT_URI=http://localhost:8001/api/linkedin/callback

# CRM Encryption Key (for token storage)
CRM_ENCRYPTION_KEY=your_fernet_encryption_key_here
```

**Generate Encryption Key:**
```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

### 3. Redis Setup (Optional but Recommended)

Redis is used for:
- State parameter storage (CSRF protection)
- Code verifier storage (PKCE)
- Rate limiting (100 requests/day tracking)

**Start Redis:**
```bash
docker-compose up -d redis
```

**Configure Redis URL in `.env`:**
```bash
REDIS_URL=redis://localhost:6379/0
```

**Without Redis:**
- State/code_verifier storage disabled (less secure)
- Rate limiting disabled (no enforcement)

---

## OAuth Flow Example

### Complete Integration Flow

**Step 1: Initialize OAuth Flow**

```bash
# Frontend: Get authorization URL
curl "http://localhost:8001/api/linkedin/authorize?scopes=r_liteprofile%20r_emailaddress"

# Response:
{
  "authorization_url": "https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=...",
  "state": "abc123...",
  "expires_in": 600
}
```

**Step 2: User Consent**

```javascript
// Frontend: Redirect user to authorization URL
window.location.href = authResponse.authorization_url;

// User grants consent on LinkedIn
// LinkedIn redirects to: http://localhost:8001/api/linkedin/callback?code=AQT...&state=abc123
```

**Step 3: Exchange Code for Tokens**

```bash
# Backend automatically handles this when user redirects to callback
# Or manually:
curl "http://localhost:8001/api/linkedin/callback?code=AQT...&state=abc123"

# Response:
{
  "access_token": "AQX...",
  "token_type": "Bearer",
  "expires_in": 5184000,
  "expires_at": "2024-03-15T10:00:00Z",
  "refresh_token_available": true
}
```

**Step 4: Use Access Token**

```bash
# Get profile
curl -H "Authorization: Bearer AQX..." \
  "http://localhost:8001/api/linkedin/profile"

# Get email
curl -H "Authorization: Bearer AQX..." \
  "http://localhost:8001/api/linkedin/email"
```

**Step 5: Token Refresh (Before Expiry)**

```bash
# Check token status
curl "http://localhost:8001/api/linkedin/token-status"

# If expires_at approaching, refresh
curl -X POST "http://localhost:8001/api/linkedin/refresh"
```

---

## Security Features

### 1. PKCE (Proof Key for Code Exchange)

**Implementation:**
- SHA256 code challenge generated from random code verifier
- Code verifier stored in Redis (10 min TTL)
- Verified during token exchange
- Protects against authorization code interception

**Code:**
```python
# Generate
code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32))
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
)

# Store in Redis
redis.setex(f"linkedin:oauth:state:{state}", 600, code_verifier)
```

### 2. State Parameter (CSRF Protection)

**Implementation:**
- Random 32-byte state generated for each auth request
- Stored in Redis with 10-minute TTL
- Verified during callback
- Prevents cross-site request forgery attacks

**Code:**
```python
state = secrets.token_urlsafe(32)
redis.setex(f"linkedin:oauth:state:{state}", 600, code_verifier)

# Verify in callback
stored_verifier = redis.get(f"linkedin:oauth:state:{state}")
if not stored_verifier:
    raise CRMAuthenticationError("State verification failed")
```

### 3. Token Encryption

**Implementation:**
- Fernet symmetric encryption for stored tokens
- Encryption key from environment variable
- Tokens encrypted before database storage
- Decrypted only when needed

**Code:**
```python
from cryptography.fernet import Fernet

# Encrypt
encrypted_token = self.encrypt_credential(access_token)

# Store in database
credentials.access_token = encrypted_token

# Decrypt when needed
access_token = self.decrypt_credential(credentials.access_token)
```

---

## Rate Limiting

### Implementation

**Daily Limit:** 100 requests per day (LinkedIn basic tier)

**Redis Tracking:**
```python
# Increment counter
key = f"linkedin:ratelimit:daily:{user_id}"
count = redis.incr(key)

# Set 24-hour expiry on first request
if count == 1:
    redis.expire(key, 86400)

# Check limit
if count > 100:
    raise CRMRateLimitError("LinkedIn daily limit exceeded")
```

**Endpoints Counted:**
- `GET /profile`
- `GET /email`
- Any other LinkedIn API calls

**Endpoints NOT Counted:**
- `/authorize` (generates URL only)
- `/callback` (token exchange)
- `/refresh` (token refresh)
- `/rate-limit` (status check)
- `/token-status` (status check)

### Monitoring

**Check Usage:**
```bash
curl "http://localhost:8001/api/linkedin/rate-limit"

# Response:
{
  "remaining": 85,        # Requests left today
  "limit": 100,           # Daily limit
  "reset_at": "2024-01-16T00:00:00Z",  # When counter resets
  "retry_after": 0,       # Seconds to wait if throttled
  "requests_today": 15    # Requests made so far
}
```

**Best Practices:**
1. Check `/rate-limit` periodically
2. Cache profile/email data to reduce API calls
3. Implement exponential backoff if approaching limit
4. Monitor `requests_today` to stay under 80% threshold

---

## Error Handling

### Exception Hierarchy

All LinkedIn errors inherit from `CRMException`:

```
CRMException (base)
├── CRMAuthenticationError (401)
│   ├── Invalid/expired access token
│   ├── Missing OAuth scopes
│   └── State verification failed
├── CRMRateLimitError (429)
│   └── Daily limit exceeded (100 requests)
├── CRMNetworkError (502)
│   └── Connection to LinkedIn failed
└── CRMValidationError (422)
    └── Invalid request parameters
```

### Error Response Format

```json
{
  "error": {
    "code": "CRM_AUTHENTICATION_ERROR",
    "message": "LinkedIn authentication failed: Invalid or expired access token",
    "context": {
      "requires_reauth": true
    }
  }
}
```

### Common Errors

**1. No Refresh Token Available**
```json
{
  "detail": "No refresh token available - LinkedIn did not provide refresh capability. Please re-authenticate via OAuth flow."
}
```

**Solution:** Re-initiate OAuth flow via `/authorize` endpoint

**2. Rate Limit Exceeded**
```json
{
  "error": {
    "code": "CRM_RATE_LIMIT_ERROR",
    "message": "LinkedIn daily limit exceeded: 100 requests per day",
    "context": {
      "requests_made": 101,
      "limit": 100
    }
  }
}
```

**Solution:** Wait until `reset_at` timestamp (midnight UTC)

**3. Missing Scope**
```json
{
  "detail": "LinkedIn authentication failed or missing r_emailaddress scope"
}
```

**Solution:** Re-authorize with correct scopes

**4. State Verification Failed**
```json
{
  "error": {
    "code": "CRM_AUTHENTICATION_ERROR",
    "message": "State verification failed - possible CSRF attack",
    "context": {
      "state": "abc123"
    }
  }
}
```

**Solution:** Check Redis connectivity; Re-initiate OAuth flow

---

## Testing

### Manual Testing

**1. Test Authorization URL Generation**
```bash
curl "http://localhost:8001/api/linkedin/authorize"
```

Expected: Valid authorization URL with state parameter

**2. Test OAuth Flow (Interactive)**
```bash
# Get auth URL
AUTH_RESPONSE=$(curl -s "http://localhost:8001/api/linkedin/authorize")
AUTH_URL=$(echo $AUTH_RESPONSE | jq -r .authorization_url)

# Open in browser (requires manual interaction)
open "$AUTH_URL"

# After consent, LinkedIn redirects to callback
# Copy code and state from redirect URL
# http://localhost:8001/api/linkedin/callback?code=AQT...&state=abc123

# Exchange code for token
curl "http://localhost:8001/api/linkedin/callback?code=AQT...&state=abc123"
```

**3. Test Profile Access**
```bash
# Replace with actual access token from step 2
TOKEN="AQX..."

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8001/api/linkedin/profile"
```

**4. Test Rate Limit Tracking**
```bash
# Check initial status
curl "http://localhost:8001/api/linkedin/rate-limit"

# Make API calls
for i in {1..5}; do
  curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8001/api/linkedin/profile"
done

# Check updated status
curl "http://localhost:8001/api/linkedin/rate-limit"
# Should show requests_today: 5, remaining: 95
```

### Automated Tests (TODO)

Create `tests/test_linkedin_oauth.py`:

```python
import pytest
from app.services.linkedin_oauth import LinkedInProvider
from app.services.crm.base import CRMCredentials

@pytest.fixture
def linkedin_provider():
    credentials = CRMCredentials(platform="linkedin")
    return LinkedInProvider(
        credentials=credentials,
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost/callback"
    )

def test_generate_authorization_url(linkedin_provider):
    scopes = ["r_liteprofile", "r_emailaddress"]
    auth_url, code_verifier, state = linkedin_provider.generate_authorization_url(scopes)

    assert "linkedin.com/oauth/v2/authorization" in auth_url
    assert "code_challenge=" in auth_url
    assert "state=" in auth_url
    assert len(code_verifier) > 0
    assert len(state) > 0

# Add more tests...
```

---

## Database Integration (TODO)

The current implementation stores credentials in memory. For production:

### 1. Create Migration

```python
# alembic/versions/xxx_add_linkedin_credentials.py

def upgrade():
    op.create_table(
        'linkedin_credentials',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('access_token', sa.String(500)),  # Encrypted
        sa.Column('refresh_token', sa.String(500)),  # Encrypted
        sa.Column('token_expires_at', sa.DateTime),
        sa.Column('scopes', sa.JSON),
        sa.Column('created_at', sa.DateTime, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, onupdate=datetime.utcnow),
    )
```

### 2. Update Endpoints

```python
# app/api/linkedin.py

@router.get("/callback")
async def callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)  # Add authentication
):
    # ... exchange code for tokens ...

    # Store in database
    db_credentials = LinkedInCredentials(
        user_id=current_user.id,
        access_token=provider.credentials.access_token,  # Already encrypted
        refresh_token=provider.credentials.refresh_token,
        token_expires_at=provider.credentials.token_expires_at,
        scopes=['r_liteprofile', 'r_emailaddress']
    )
    db.add(db_credentials)
    db.commit()
```

---

## Production Considerations

### 1. Redis Configuration

**High Availability:**
```bash
# Use Redis Sentinel or Redis Cluster
REDIS_URL=redis-sentinel://sentinel1:26379,sentinel2:26379/mymaster
```

**Connection Pooling:**
```python
import redis
from redis.connection import ConnectionPool

pool = ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=50,
    decode_responses=True
)
redis_client = redis.Redis(connection_pool=pool)
```

### 2. Token Storage

**Encryption Key Rotation:**
```python
# Store multiple encryption keys for gradual migration
CRM_ENCRYPTION_KEY_CURRENT=new_key_here
CRM_ENCRYPTION_KEY_PREVIOUS=old_key_here

# Decrypt with fallback
def decrypt_credential(ciphertext: str) -> str:
    try:
        return fernet_current.decrypt(ciphertext)
    except:
        return fernet_previous.decrypt(ciphertext)
```

### 3. Rate Limit Monitoring

**Alert on High Usage:**
```python
async def _check_rate_limit():
    count = await redis.incr(key)

    # Alert at 80% threshold
    if count == 80:
        await send_alert("LinkedIn API usage at 80% (80/100)")

    if count > 100:
        raise CRMRateLimitError(...)
```

### 4. Logging

**Structured Logging:**
```python
logger.info(
    "LinkedIn OAuth token exchanged",
    extra={
        "user_id": user_id,
        "scopes": scopes,
        "expires_at": expires_at.isoformat(),
        "has_refresh_token": has_refresh
    }
)
```

### 5. HTTPS Redirect URI

**Production Configuration:**
```bash
LINKEDIN_REDIRECT_URI=https://api.yourdomain.com/api/linkedin/callback
```

---

## LinkedIn API Scopes

### Available Scopes

| Scope | Description | Use Case |
|-------|-------------|----------|
| `r_liteprofile` | Basic profile (name, photo) | User authentication |
| `r_emailaddress` | Email address | User identification |
| `w_member_social` | Share content | Post on user's behalf |
| `r_organization_social` | Read company posts | Company page analytics |
| `w_organization_social` | Manage company posts | Company content management |
| `r_compliance` | Compliance data (1 year tokens) | Regulatory compliance |

### Scope Configuration

**Development:**
```python
scopes = ["r_liteprofile", "r_emailaddress"]
```

**Production (with posting):**
```python
scopes = ["r_liteprofile", "r_emailaddress", "w_member_social"]
```

**Enterprise (compliance):**
```python
scopes = ["r_compliance"]  # Special access required
```

---

## Files Created/Modified

### New Files

1. **`backend/app/services/linkedin_oauth.py`** (481 lines)
   - `LinkedInProvider` class
   - OAuth 2.0 implementation with PKCE
   - Profile and email API methods
   - Rate limiting logic

2. **`backend/app/api/linkedin.py`** (688 lines)
   - 8 API endpoints with OpenAPI docs
   - Pydantic models for request/response
   - Complete error handling

3. **`LINKEDIN_OAUTH_IMPLEMENTATION.md`** (this file)
   - Comprehensive documentation
   - Setup instructions
   - Usage examples

### Modified Files

1. **`backend/app/main.py`**
   - Added `linkedin` router import
   - Registered LinkedIn endpoints

2. **`.env.example`**
   - Added LinkedIn OAuth credentials
   - Added redirect URI configuration

---

## Next Steps

### Immediate (Production-Ready)

- [ ] Add database persistence for credentials
- [ ] Implement user authentication middleware
- [ ] Add automated tests (pytest)
- [ ] Configure HTTPS redirect URI
- [ ] Set up Redis for production

### Future Enhancements

- [ ] Company page API integration (`w_organization_social`)
- [ ] Content posting (`w_member_social`)
- [ ] Connection requests API
- [ ] Messaging API
- [ ] Analytics and insights

### Monitoring

- [ ] Datadog/Sentry integration for errors
- [ ] Rate limit alerting (80% threshold)
- [ ] Token expiration monitoring
- [ ] Failed authentication tracking

---

## Support

### LinkedIn Developer Resources

- **OAuth Documentation**: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
- **API Reference**: https://learn.microsoft.com/en-us/linkedin/
- **Developer Portal**: https://www.linkedin.com/developers/
- **Support**: https://www.linkedin.com/help/linkedin

### Internal Documentation

- **CRM Base Class**: `backend/app/services/crm/base.py`
- **HubSpot Example**: `backend/app/services/crm/hubspot.py`
- **Exception Handling**: `backend/app/core/exceptions.py`

---

## License

Same as parent project (sales-agent).

---

**Implementation Date**: January 2025
**Last Updated**: January 2025
**Status**: ✅ Ready for Testing
