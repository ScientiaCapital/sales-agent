"""
Sync Security Middleware
========================

Enterprise security middleware for sync operations with:
- Authentication validation
- Authorization checks
- Rate limiting
- Input sanitization
- Audit logging
- Encryption for sensitive data
"""

from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
import asyncio
import hashlib
import hmac
import logging
import os
import re

logger = logging.getLogger(__name__)


@dataclass
class SecurityContext:
    """Security context for a sync operation"""
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    api_key_id: Optional[str] = None
    permissions: Set[str] = field(default_factory=set)
    rate_limit_key: Optional[str] = None
    request_id: Optional[str] = None


class SyncSecurityMiddleware:
    """
    Enterprise security middleware for sync operations.
    
    Features:
    - API key validation
    - Webhook signature verification
    - Rate limiting with Redis
    - Input sanitization
    - PII detection and masking
    - IP allowlisting
    - Audit trail
    """
    
    # Default rate limits
    DEFAULT_RATE_LIMIT = 1000  # requests per hour
    BURST_LIMIT = 100         # requests per minute
    
    # Sensitive field patterns
    SENSITIVE_PATTERNS = [
        r'\b\d{3}[-.]?\d{2}[-.]?\d{4}\b',  # SSN
        r'\b\d{16}\b',                       # Credit card
        r'\bpassword\s*[=:]\s*\S+',          # Passwords
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
    ]
    
    # Fields that should be encrypted at rest
    ENCRYPTED_FIELDS = [
        "api_key", "access_token", "refresh_token",
        "password", "secret", "credential"
    ]
    
    # IP allowlist for webhooks (Close CRM IP ranges)
    CLOSE_WEBHOOK_IPS = [
        "52.8.77.144/28",
        "52.9.145.112/28", 
        "54.183.227.80/28",
        "54.215.242.0/28"
    ]
    
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        supabase_client: Optional[Any] = None,
        encryption_key: Optional[str] = None,
        enable_rate_limiting: bool = True,
        enable_ip_allowlist: bool = True,
        enable_pii_detection: bool = True
    ):
        self.redis = redis_client
        self.supabase = supabase_client
        self.encryption_key = encryption_key or os.getenv("SYNC_ENCRYPTION_KEY")
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_ip_allowlist = enable_ip_allowlist
        self.enable_pii_detection = enable_pii_detection
        
        # Rate limit state (in-memory fallback if no Redis)
        self._rate_limit_cache: Dict[str, List[datetime]] = {}
        self._rate_limit_lock = asyncio.Lock()
    
    # =========================================================================
    # API KEY VALIDATION
    # =========================================================================
    
    async def validate_api_key(
        self,
        api_key: str,
        required_permissions: Optional[Set[str]] = None
    ) -> SecurityContext:
        """
        Validate API key and return security context.
        
        Args:
            api_key: API key to validate
            required_permissions: Required permissions for this operation
            
        Returns:
            SecurityContext with user/org details
            
        Raises:
            ValueError: If API key is invalid
            PermissionError: If lacking required permissions
        """
        if not api_key:
            raise ValueError("API key is required")
        
        # Hash the key for lookup
        key_hash = self._hash_api_key(api_key)
        
        # Look up in database
        if self.supabase:
            response = await (
                self.supabase.table("api_keys")
                .select("*")
                .eq("key_hash", key_hash)
                .eq("is_active", True)
                .maybe_single()
                .execute()
            )
            
            if not response.data:
                await self._log_security_event(
                    "invalid_api_key",
                    f"Invalid API key attempt: {api_key[:8]}...",
                    severity="warning"
                )
                raise ValueError("Invalid API key")
            
            key_data = response.data
            
            # Check expiration
            if key_data.get("expires_at"):
                expires = datetime.fromisoformat(key_data["expires_at"])
                if expires < datetime.utcnow():
                    raise ValueError("API key has expired")
            
            # Build security context
            context = SecurityContext(
                user_id=key_data.get("user_id"),
                organization_id=key_data.get("organization_id"),
                api_key_id=key_data.get("id"),
                permissions=set(key_data.get("permissions", [])),
                rate_limit_key=f"api:{key_data.get('id')}"
            )
            
            # Check required permissions
            if required_permissions:
                missing = required_permissions - context.permissions
                if missing:
                    raise PermissionError(f"Missing permissions: {missing}")
            
            return context
        
        # Fallback: basic validation for Close API key format
        if not api_key.startswith("api_"):
            raise ValueError("Invalid API key format")
        
        return SecurityContext(
            api_key_id=key_hash[:8],
            permissions={"read", "write"},
            rate_limit_key=f"api:{key_hash[:8]}"
        )
    
    # =========================================================================
    # WEBHOOK SIGNATURE VERIFICATION
    # =========================================================================
    
    async def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
        timestamp: Optional[str] = None
    ) -> bool:
        """
        Verify webhook signature (HMAC-SHA256).
        
        Args:
            payload: Raw request body
            signature: Signature from header
            secret: Webhook secret
            timestamp: Optional timestamp for replay protection
            
        Returns:
            True if signature is valid
        """
        if not all([payload, signature, secret]):
            return False
        
        # Check timestamp for replay protection (5 minute window)
        if timestamp:
            try:
                ts = datetime.fromisoformat(timestamp)
                if abs((datetime.utcnow() - ts).total_seconds()) > 300:
                    await self._log_security_event(
                        "webhook_replay_attempt",
                        f"Webhook timestamp too old: {timestamp}",
                        severity="warning"
                    )
                    return False
            except ValueError:
                pass
        
        # Compute expected signature
        if timestamp:
            message = f"{timestamp}.{payload.decode()}"
        else:
            message = payload.decode()
        
        expected = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison
        is_valid = hmac.compare_digest(expected, signature)
        
        if not is_valid:
            await self._log_security_event(
                "invalid_webhook_signature",
                "Webhook signature verification failed",
                severity="warning"
            )
        
        return is_valid
    
    # =========================================================================
    # RATE LIMITING
    # =========================================================================
    
    async def check_rate_limit(
        self,
        context: SecurityContext,
        limit: Optional[int] = None,
        window_seconds: int = 3600
    ) -> bool:
        """
        Check if request is within rate limits.
        
        Args:
            context: Security context with rate_limit_key
            limit: Custom limit (default: DEFAULT_RATE_LIMIT)
            window_seconds: Time window in seconds
            
        Returns:
            True if within limits, False if exceeded
        """
        if not self.enable_rate_limiting:
            return True
        
        limit = limit or self.DEFAULT_RATE_LIMIT
        key = context.rate_limit_key or context.ip_address or "default"
        
        if self.redis:
            # Use Redis for distributed rate limiting
            redis_key = f"rate_limit:{key}"
            now = datetime.utcnow().timestamp()
            
            # Remove old entries and add new one
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
            pipe.zadd(redis_key, {str(now): now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, window_seconds)
            
            results = await pipe.execute()
            count = results[2]
            
            if count > limit:
                await self._log_security_event(
                    "rate_limit_exceeded",
                    f"Rate limit exceeded for {key}: {count}/{limit}",
                    severity="warning"
                )
                return False
            
            return True
        
        # Fallback: in-memory rate limiting
        async with self._rate_limit_lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(seconds=window_seconds)
            
            if key not in self._rate_limit_cache:
                self._rate_limit_cache[key] = []
            
            # Remove old entries
            self._rate_limit_cache[key] = [
                ts for ts in self._rate_limit_cache[key]
                if ts > cutoff
            ]
            
            # Check limit
            if len(self._rate_limit_cache[key]) >= limit:
                await self._log_security_event(
                    "rate_limit_exceeded",
                    f"Rate limit exceeded for {key}",
                    severity="warning"
                )
                return False
            
            # Add new entry
            self._rate_limit_cache[key].append(now)
            return True
    
    # =========================================================================
    # IP ALLOWLISTING
    # =========================================================================
    
    def verify_ip_allowlist(
        self,
        ip_address: str,
        allowlist: Optional[List[str]] = None
    ) -> bool:
        """
        Verify IP address is in allowlist.
        
        Args:
            ip_address: Client IP address
            allowlist: Custom allowlist (default: CLOSE_WEBHOOK_IPS)
            
        Returns:
            True if IP is allowed
        """
        if not self.enable_ip_allowlist:
            return True
        
        if not ip_address:
            return False
        
        allowlist = allowlist or self.CLOSE_WEBHOOK_IPS
        
        import ipaddress
        try:
            client_ip = ipaddress.ip_address(ip_address)
            
            for cidr in allowlist:
                if "/" in cidr:
                    network = ipaddress.ip_network(cidr, strict=False)
                    if client_ip in network:
                        return True
                else:
                    if str(client_ip) == cidr:
                        return True
            
            return False
            
        except ValueError:
            return False
    
    # =========================================================================
    # INPUT SANITIZATION
    # =========================================================================
    
    def sanitize_input(
        self,
        data: Dict[str, Any],
        allowed_fields: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """
        Sanitize input data.
        
        Args:
            data: Input data to sanitize
            allowed_fields: Optional whitelist of allowed fields
            
        Returns:
            Sanitized data
        """
        result = {}
        
        for key, value in data.items():
            # Filter to allowed fields if specified
            if allowed_fields and key not in allowed_fields:
                continue
            
            # Recursively sanitize nested dicts
            if isinstance(value, dict):
                result[key] = self.sanitize_input(value, allowed_fields)
            elif isinstance(value, list):
                result[key] = [
                    self.sanitize_input(v, allowed_fields) if isinstance(v, dict) else self._sanitize_value(v)
                    for v in value
                ]
            else:
                result[key] = self._sanitize_value(value)
        
        return result
    
    def _sanitize_value(self, value: Any) -> Any:
        """Sanitize a single value"""
        if not isinstance(value, str):
            return value
        
        # Remove potential XSS
        value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)
        value = re.sub(r'javascript:', '', value, flags=re.IGNORECASE)
        value = re.sub(r'on\w+\s*=', '', value, flags=re.IGNORECASE)
        
        # Remove SQL injection attempts
        value = re.sub(r"';\s*--", '', value)
        value = re.sub(r";\s*DROP\s+TABLE", '', value, flags=re.IGNORECASE)
        
        return value.strip()
    
    # =========================================================================
    # PII DETECTION
    # =========================================================================
    
    def detect_pii(
        self,
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect PII in data.
        
        Args:
            data: Data to scan
            
        Returns:
            List of detected PII with field paths
        """
        if not self.enable_pii_detection:
            return []
        
        detections = []
        
        def scan_value(value: Any, path: str):
            if isinstance(value, str):
                for pattern in self.SENSITIVE_PATTERNS:
                    matches = re.findall(pattern, value)
                    for match in matches:
                        detections.append({
                            "field": path,
                            "type": self._classify_pii(pattern),
                            "sample": match[:4] + "..." if len(match) > 4 else "***"
                        })
            elif isinstance(value, dict):
                for k, v in value.items():
                    scan_value(v, f"{path}.{k}" if path else k)
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    scan_value(v, f"{path}[{i}]")
        
        scan_value(data, "")
        return detections
    
    @staticmethod
    def _classify_pii(pattern: str) -> str:
        """Classify PII type based on pattern"""
        if "\\d{3}" in pattern and "\\d{4}" in pattern:
            return "ssn"
        elif "\\d{16}" in pattern:
            return "credit_card"
        elif "password" in pattern.lower():
            return "password"
        elif "@" in pattern:
            return "email"
        return "unknown"
    
    def mask_pii(
        self,
        data: Dict[str, Any],
        detections: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Mask detected PII in data.
        
        Args:
            data: Data to mask
            detections: Optional pre-computed detections
            
        Returns:
            Data with PII masked
        """
        if detections is None:
            detections = self.detect_pii(data)
        
        import copy
        result = copy.deepcopy(data)
        
        for detection in detections:
            path_parts = detection["field"].replace("[", ".").replace("]", "").split(".")
            self._mask_at_path(result, path_parts, detection["type"])
        
        return result
    
    def _mask_at_path(
        self,
        data: Any,
        path_parts: List[str],
        pii_type: str
    ):
        """Mask value at given path"""
        if not path_parts or not data:
            return
        
        key = path_parts[0]
        
        # Handle empty key from root
        if key == "":
            if len(path_parts) > 1:
                self._mask_at_path(data, path_parts[1:], pii_type)
            return
        
        # Handle array index
        if key.isdigit():
            key = int(key)
        
        if len(path_parts) == 1:
            # Mask this value
            if isinstance(data, dict) and key in data:
                data[key] = f"[MASKED_{pii_type.upper()}]"
            elif isinstance(data, list) and isinstance(key, int) and key < len(data):
                data[key] = f"[MASKED_{pii_type.upper()}]"
        else:
            # Recurse
            if isinstance(data, dict) and key in data:
                self._mask_at_path(data[key], path_parts[1:], pii_type)
            elif isinstance(data, list) and isinstance(key, int) and key < len(data):
                self._mask_at_path(data[key], path_parts[1:], pii_type)
    
    # =========================================================================
    # ENCRYPTION
    # =========================================================================
    
    def encrypt_sensitive_fields(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Encrypt sensitive fields before storage"""
        if not self.encryption_key:
            return data
        
        import copy
        result = copy.deepcopy(data)
        
        def encrypt_if_sensitive(obj: Any, key: str = "") -> Any:
            if isinstance(obj, dict):
                return {
                    k: encrypt_if_sensitive(v, k)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [encrypt_if_sensitive(v, key) for v in obj]
            elif isinstance(obj, str) and any(
                s in key.lower() for s in self.ENCRYPTED_FIELDS
            ):
                return self._encrypt(obj)
            return obj
        
        return encrypt_if_sensitive(result)
    
    def decrypt_sensitive_fields(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Decrypt sensitive fields after retrieval"""
        if not self.encryption_key:
            return data
        
        import copy
        result = copy.deepcopy(data)
        
        def decrypt_if_encrypted(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: decrypt_if_encrypted(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [decrypt_if_encrypted(v) for v in obj]
            elif isinstance(obj, str) and obj.startswith("ENC:"):
                return self._decrypt(obj)
            return obj
        
        return decrypt_if_encrypted(result)
    
    def _encrypt(self, value: str) -> str:
        """Encrypt a value using Fernet"""
        try:
            from cryptography.fernet import Fernet
            f = Fernet(self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key)
            encrypted = f.encrypt(value.encode())
            return f"ENC:{encrypted.decode()}"
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return value
    
    def _decrypt(self, value: str) -> str:
        """Decrypt a value"""
        try:
            from cryptography.fernet import Fernet
            f = Fernet(self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key)
            encrypted = value[4:]  # Remove "ENC:" prefix
            return f.decrypt(encrypted.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return value
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    @staticmethod
    def _hash_api_key(api_key: str) -> str:
        """Hash API key for storage/lookup"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    async def _log_security_event(
        self,
        event_type: str,
        description: str,
        severity: str = "info",
        **kwargs
    ):
        """Log a security event"""
        logger.log(
            logging.WARNING if severity in ["warning", "error"] else logging.INFO,
            f"Security: {event_type} - {description}"
        )
        
        if self.supabase:
            try:
                await (
                    self.supabase.table("sync_audit_log")
                    .insert({
                        "operation": "security_event",
                        "entity_type": "security",
                        "direction": "internal",
                        "metadata": {
                            "event_type": event_type,
                            "description": description,
                            "severity": severity,
                            **kwargs
                        },
                        "status": severity,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    .execute()
                )
            except Exception as e:
                logger.error(f"Failed to log security event: {e}")


# =========================================================================
# DECORATOR FOR SECURING SYNC OPERATIONS
# =========================================================================

def secure_sync_operation(
    required_permissions: Optional[Set[str]] = None,
    rate_limit: Optional[int] = None
):
    """
    Decorator to secure sync operations.
    
    Usage:
        @secure_sync_operation(required_permissions={"sync:read", "sync:write"})
        async def sync_leads(context: SecurityContext, ...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get security middleware instance
            middleware = kwargs.get("security_middleware")
            if not middleware:
                logger.warning("No security middleware provided")
                return await func(*args, **kwargs)
            
            # Get security context
            context = kwargs.get("security_context")
            if not context:
                api_key = kwargs.get("api_key")
                if api_key:
                    context = await middleware.validate_api_key(
                        api_key, required_permissions
                    )
                    kwargs["security_context"] = context
            
            # Check rate limit
            if context and rate_limit:
                if not await middleware.check_rate_limit(context, rate_limit):
                    raise Exception("Rate limit exceeded")
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
