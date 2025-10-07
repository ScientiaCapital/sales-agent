"""
Authentication API endpoints for user registration, login, and token management.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, validator

from app.models.database import get_db
from app.models.security import User, EventType
from app.services.auth import AuthService
from app.middleware.audit import log_security_event
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Security scheme for JWT Bearer authentication
security = HTTPBearer()


# Pydantic schemas
class UserRegisterRequest(BaseModel):
    """Request schema for user registration."""
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)

    @validator("password")
    def validate_password_strength(cls, v):
        """Ensure password meets minimum security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLoginRequest(BaseModel):
    """Request schema for user login."""
    username: str = Field(..., description="Username or email")
    password: str


class TokenResponse(BaseModel):
    """Response schema for token endpoints."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiration in seconds")


class UserResponse(BaseModel):
    """Response schema for user information."""
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    roles: list[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    """Request schema for token refresh."""
    refresh_token: str


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: UserRegisterRequest,
    req: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Register a new user account.

    Creates a new user with the default 'user' role.
    Password is securely hashed using bcrypt.

    Args:
        request: User registration data
        req: HTTP request (for audit logging)
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Created user information

    Raises:
        HTTPException: If username or email already exists
    """
    auth_service = AuthService(db)

    try:
        # Create user with default 'user' role
        user = auth_service.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role_names=["user"],  # Default role
        )

        # Log security event
        background_tasks.add_task(
            log_security_event,
            event_type=EventType.DATA_CREATED,
            user_id=user.id,
            resource=f"user:{user.id}",
            action="create",
            metadata={"username": user.username, "email": user.email},
            request=req,
        )

        # Return user info
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            roles=[role.name for role in user.roles],
            created_at=user.created_at,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Registration failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: UserLoginRequest,
    req: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Authenticate user and issue JWT tokens.

    Returns both access and refresh tokens on successful authentication.
    Access tokens expire in 15 minutes, refresh tokens in 7 days.

    Args:
        request: Login credentials
        req: HTTP request (for audit logging)
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        JWT tokens and expiration info

    Raises:
        HTTPException: If authentication fails
    """
    auth_service = AuthService(db)

    # Authenticate user
    user = auth_service.authenticate_user(request.username, request.password)

    if not user:
        # Log failed login attempt
        background_tasks.add_task(
            log_security_event,
            event_type=EventType.LOGIN_FAILED,
            resource="auth",
            action="login",
            metadata={"username": request.username},
            request=req,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Update login IP
    if req.client:
        user.last_login_ip = req.client.host
        db.commit()

    # Generate tokens
    access_token = auth_service.create_access_token(user)
    refresh_token = auth_service.create_refresh_token(user)

    # Log successful login
    background_tasks.add_task(
        log_security_event,
        event_type=EventType.LOGIN_SUCCESS,
        user_id=user.id,
        resource="auth",
        action="login",
        metadata={"username": user.username},
        request=req,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=15 * 60,  # 15 minutes in seconds
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    req: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Refresh access token using a valid refresh token.

    Implements token rotation - returns new access and refresh tokens.
    Old refresh token becomes invalid after successful refresh.

    Args:
        request: Refresh token
        req: HTTP request (for audit logging)
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        New JWT tokens and expiration info

    Raises:
        HTTPException: If refresh token is invalid or expired
    """
    auth_service = AuthService(db)

    # Refresh tokens
    result = auth_service.refresh_access_token(request.refresh_token)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_access_token, new_refresh_token = result

    # Get user from token for logging
    payload = auth_service.verify_token(request.refresh_token, token_type="refresh")
    if payload:
        user_id = int(payload.get("sub"))
        background_tasks.add_task(
            log_security_event,
            event_type=EventType.TOKEN_REFRESH,
            user_id=user_id,
            resource="auth",
            action="refresh",
            request=req,
        )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=15 * 60,  # 15 minutes in seconds
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    req: Request,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Logout user by revoking all their tokens.

    Increments the user's refresh token version, invalidating all existing tokens.

    Args:
        req: HTTP request (for audit logging)
        background_tasks: FastAPI background tasks
        credentials: JWT Bearer token
        db: Database session

    Returns:
        204 No Content on success

    Raises:
        HTTPException: If token is invalid
    """
    auth_service = AuthService(db)

    # Get current user from token
    user = auth_service.get_current_user(credentials.credentials)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Revoke all tokens for user
    auth_service.revoke_all_tokens(user)

    # Log logout event
    background_tasks.add_task(
        log_security_event,
        event_type=EventType.LOGOUT,
        user_id=user.id,
        resource="auth",
        action="logout",
        request=req,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Get current user information from JWT token.

    Args:
        credentials: JWT Bearer token
        db: Database session

    Returns:
        Current user information

    Raises:
        HTTPException: If token is invalid
    """
    auth_service = AuthService(db)

    # Get user from token
    user = auth_service.get_current_user(credentials.credentials)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        roles=[role.name for role in user.roles],
        created_at=user.created_at,
    )