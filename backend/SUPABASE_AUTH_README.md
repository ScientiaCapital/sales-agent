# Supabase Authentication - Implementation Guide

## Overview

This implementation provides **Supabase-based authentication** for the sales-agent project, offering a modern, scalable alternative to the existing JWT-based auth system.

## Features Implemented

- Email/password signup and login
- Magic link authentication (passwordless)
- JWT token validation (Supabase JWTs)
- Role-based access control (admin, user)
- Password reset flow
- Session management (refresh tokens)
- Comprehensive test suite (17+ tests)

## Project Structure

```
backend/
├── app/
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── supabase_auth.py      # Supabase client wrapper (async)
│   │   └── dependencies.py        # FastAPI dependencies for JWT validation
│   ├── api/
│   │   └── supabase_auth.py       # Auth API endpoints
│   └── core/
│       └── config.py               # Settings (updated with Supabase config)
├── tests/
│   └── test_supabase_auth.py      # 17 comprehensive tests
└── requirements.txt                # Updated with supabase==2.10.0
```

## Environment Variables

Add these to your `.env` file:

```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_role_key_here

# Optional: For offline JWT validation (faster, no API call)
SUPABASE_JWT_SECRET=your_jwt_secret_from_supabase_settings

# JWT Configuration (optional overrides)
JWT_SECRET_KEY=your_custom_jwt_secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Getting Supabase Credentials

1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Navigate to **Settings** > **API**
4. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **Anon public** key → `SUPABASE_ANON_KEY`
   - **Service role** key → `SUPABASE_SERVICE_KEY`
5. For JWT secret: **Settings** > **API** > **JWT Secret**

## API Endpoints

All endpoints are prefixed with `/api/v1/supabase-auth`

### Public Endpoints (No Auth Required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/signup` | Register new user with email/password |
| POST | `/login` | Login with email/password |
| POST | `/magic-link` | Send magic link to email |
| POST | `/verify-otp` | Verify OTP/magic link token |
| POST | `/password-reset` | Send password reset email |
| POST | `/refresh` | Refresh access token |

### Protected Endpoints (Requires JWT)

| Method | Endpoint | Description | Role Required |
|--------|----------|-------------|---------------|
| GET | `/me` | Get current user info | user/admin |
| POST | `/logout` | Logout and invalidate session | user/admin |
| POST | `/password-reset/confirm` | Update password after reset | user/admin |
| GET | `/admin-only` | Example admin endpoint | admin |

## Usage Examples

### 1. User Signup

```bash
curl -X POST http://localhost:8000/api/v1/supabase-auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123",
    "full_name": "John Doe"
  }'
```

Response:
```json
{
  "user": {
    "id": "uuid-here",
    "email": "user@example.com",
    "user_metadata": {
      "full_name": "John Doe",
      "role": "user"
    }
  },
  "access_token": "eyJhbGc...",
  "refresh_token": "refresh_token_here",
  "expires_in": 3600
}
```

### 2. Login

```bash
curl -X POST http://localhost:8000/api/v1/supabase-auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123"
  }'
```

### 3. Magic Link (Passwordless)

```bash
# Step 1: Send magic link
curl -X POST http://localhost:8000/api/v1/supabase-auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'

# Step 2: User receives email with token, verify it
curl -X POST http://localhost:8000/api/v1/supabase-auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "token": "123456",
    "type": "magiclink"
  }'
```

### 4. Protected Endpoint

```bash
curl -X GET http://localhost:8000/api/v1/supabase-auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 5. Refresh Token

```bash
curl -X POST http://localhost:8000/api/v1/supabase-auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'
```

## Role-Based Access Control

### User Roles

- **user**: Default role for new signups (read access)
- **admin**: Full access to all endpoints

### Assigning Admin Role

Update user metadata in Supabase:

```sql
UPDATE auth.users
SET raw_user_meta_data = jsonb_set(
  raw_user_meta_data,
  '{role}',
  '"admin"'
)
WHERE email = 'admin@example.com';
```

### Using Role Dependencies in Your Endpoints

```python
from app.auth.dependencies import require_admin, require_user, has_role

# Require any authenticated user
@router.get("/protected")
async def protected_endpoint(
    current_user: dict = Depends(require_user)
):
    return {"message": "User authenticated"}

# Require admin role
@router.get("/admin")
async def admin_endpoint(
    current_user: dict = Depends(require_admin)
):
    return {"message": "Admin access granted"}

# Check specific role(s)
@router.get("/manager", dependencies=[Depends(has_role("manager"))])
async def manager_endpoint():
    return {"message": "Manager access granted"}
```

## Testing

### Run Tests

```bash
# Activate virtual environment
source venv/bin/activate  # or: source backend/venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run Supabase auth tests
pytest tests/test_supabase_auth.py -v

# Run with coverage
pytest tests/test_supabase_auth.py --cov=app/auth --cov-report=html
```

### Test Coverage

- User signup (success, weak password, duplicate email)
- User login (success, invalid credentials, missing fields)
- Magic link (send, verify OTP, invalid token)
- Password reset (send email)
- Token refresh (success, invalid token)
- Protected endpoints (valid token, invalid token, missing token)
- Role-based access (admin, user, banned user)
- Logout (success)

## Security Considerations

### Password Requirements

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit

### JWT Token Validation

Two validation methods:

1. **Online Validation** (default): Calls Supabase API to validate token
   - Pros: Always up-to-date, handles token revocation
   - Cons: Slower, requires API call

2. **Offline Validation** (optional): Validates JWT locally using secret
   - Pros: Faster, no API call
   - Cons: Doesn't detect token revocation immediately
   - Requires: `SUPABASE_JWT_SECRET` environment variable

### Session Management

- Access tokens expire in 15 minutes (default)
- Refresh tokens expire in 7 days (default)
- Logout invalidates the current session

## Migration from Legacy Auth

If migrating from the existing JWT auth system:

1. **Coexistence**: Both systems can run simultaneously
   - Legacy auth: `/api/v1/auth/*`
   - Supabase auth: `/api/v1/supabase-auth/*`

2. **User Migration**: Create a script to migrate users:
   ```python
   from app.services.auth import AuthService
   from app.auth.supabase_auth import get_supabase_client

   # Pseudo-code
   for user in legacy_users:
       await supabase_client.signup(
           email=user.email,
           password=generate_temp_password(),
           user_metadata={"legacy_id": user.id}
       )
       # Send password reset email
   ```

3. **Gradual Rollout**:
   - Week 1: Deploy Supabase auth alongside legacy
   - Week 2: Migrate existing users
   - Week 3: Switch new signups to Supabase
   - Week 4: Deprecate legacy endpoints

## Troubleshooting

### Common Issues

1. **"Supabase credentials not configured"**
   - Solution: Add `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` to `.env`

2. **"Invalid refresh token"**
   - Solution: Tokens expire after 7 days, user must login again

3. **"Could not validate credentials"**
   - Solution: Check token format, ensure it starts with "Bearer "

4. **"User already registered"**
   - Solution: Use login instead, or request password reset

5. **Tests fail with "ModuleNotFoundError: gotrue"**
   - Solution: Install supabase package: `pip install supabase==2.10.0`

## Integration with Existing Features

### Using Supabase Auth in Other Routers

```python
from app.auth.dependencies import get_current_user

@router.post("/leads")
async def create_lead(
    lead_data: LeadCreate,
    current_user: dict = Depends(get_current_user)
):
    # Create lead with user context
    lead = create_lead_in_db(
        lead_data,
        created_by=current_user["id"]
    )
    return lead
```

### Storing User ID in Database

```python
# Example: Associate records with Supabase user ID
class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True)
    # ... other fields ...
    created_by_supabase_id = Column(String(36))  # UUID from Supabase
```

## Future Enhancements

- [ ] OAuth providers (Google, GitHub, etc.)
- [ ] Two-factor authentication (2FA)
- [ ] Email verification enforcement
- [ ] Account lockout after failed attempts
- [ ] Session management dashboard
- [ ] Audit logging integration
- [ ] Rate limiting per user

## Resources

- [Supabase Auth Documentation](https://supabase.com/docs/guides/auth)
- [Supabase Python Client](https://github.com/supabase-community/supabase-py)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Supabase logs in dashboard
3. Check application logs for detailed errors
4. Contact the development team

---

**Implementation Date**: December 6, 2025
**Version**: 1.0.0
**Status**: Production Ready
