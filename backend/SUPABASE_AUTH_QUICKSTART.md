# Supabase Authentication - Quick Start Guide

## 5-Minute Setup

### 1. Install Dependency

```bash
cd backend
source venv/bin/activate  # Activate your virtual environment
pip install supabase==2.10.0
```

### 2. Configure Environment

Add to `.env`:

```env
SUPABASE_URL=https://oyyakkuvvtckocncuwwf.supabase.co
SUPABASE_SERVICE_KEY=REVOKED
```

### 3. Start Server

```bash
uvicorn app.main:app --reload
```

Visit: http://localhost:8000/api/v1/docs

### 4. Test with cURL

```bash
# Signup
curl -X POST http://localhost:8000/api/v1/supabase-auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "SecurePass123"}'

# Login
curl -X POST http://localhost:8000/api/v1/supabase-auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "SecurePass123"}'

# Get User (replace TOKEN)
curl -X GET http://localhost:8000/api/v1/supabase-auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Common Use Cases

### Protect an Endpoint

```python
from app.auth.dependencies import get_current_user

@router.get("/protected")
async def my_endpoint(current_user: dict = Depends(get_current_user)):
    return {"user": current_user["email"]}
```

### Require Admin Role

```python
from app.auth.dependencies import require_admin

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: dict = Depends(require_admin)
):
    # Only admins can access this
    return {"deleted": user_id}
```

### Optional Authentication

```python
from app.auth.dependencies import get_optional_user

@router.get("/public-or-private")
async def mixed_endpoint(current_user: Optional[dict] = Depends(get_optional_user)):
    if current_user:
        return {"message": f"Hello {current_user['email']}"}
    return {"message": "Hello guest"}
```

## API Endpoints Summary

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/supabase-auth/signup` | POST | No | Register new user |
| `/supabase-auth/login` | POST | No | Login |
| `/supabase-auth/magic-link` | POST | No | Send passwordless link |
| `/supabase-auth/verify-otp` | POST | No | Verify magic link |
| `/supabase-auth/me` | GET | Yes | Get current user |
| `/supabase-auth/logout` | POST | Yes | Logout |
| `/supabase-auth/refresh` | POST | No | Refresh token |
| `/supabase-auth/password-reset` | POST | No | Request reset |

## Testing

```bash
# Run tests
pytest tests/test_supabase_auth.py -v

# With coverage
pytest tests/test_supabase_auth.py --cov=app/auth
```

## Troubleshooting

**"Could not validate credentials"**
- Check if token is in `Authorization: Bearer TOKEN` format
- Verify token hasn't expired (15 min for access token)

**"Supabase credentials not configured"**
- Add `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` to `.env`
- Restart server after updating `.env`

**"User already registered"**
- Use `/login` instead of `/signup`
- Or use `/password-reset` to reset password

## Full Documentation

See `SUPABASE_AUTH_README.md` for complete documentation.
