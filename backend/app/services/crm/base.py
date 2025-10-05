"""
Abstract CRM Provider Interface

Defines the base interface for all CRM integrations (HubSpot, Apollo, LinkedIn).
All CRM providers must implement these methods to ensure consistent behavior.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from cryptography.fernet import Fernet
import os
import json


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class Contact(BaseModel):
    """Unified contact model across all CRM platforms"""
    
    id: Optional[int] = None  # Internal database ID
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    
    # Platform-specific IDs (e.g., {"hubspot": "12345", "apollo": "67890"})
    external_ids: Dict[str, str] = Field(default_factory=dict)
    
    # Enrichment data from Apollo
    enrichment_data: Optional[Dict[str, Any]] = None
    
    # Metadata
    source_platform: Optional[str] = None  # Which CRM this contact came from
    last_synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "company": "Tech Corp",
                "title": "CTO",
                "phone": "+1234567890",
                "linkedin_url": "https://linkedin.com/in/johndoe",
                "external_ids": {
                    "hubspot": "12345",
                    "apollo": "67890"
                },
                "source_platform": "hubspot"
            }
        }


class CRMCredentials(BaseModel):
    """Encrypted credentials for CRM authentication"""
    
    platform: str  # "hubspot", "apollo", "linkedin"
    user_id: Optional[int] = None  # Associated user (if applicable)
    
    # OAuth tokens (encrypted in database)
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    
    # API keys (encrypted in database)
    api_key: Optional[str] = None
    
    # OAuth metadata
    scopes: Optional[List[str]] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SyncResult(BaseModel):
    """Result of a CRM sync operation"""
    
    platform: str
    operation: str  # "import", "export", "bidirectional"
    
    contacts_processed: int = 0
    contacts_created: int = 0
    contacts_updated: int = 0
    contacts_failed: int = 0
    
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "platform": "hubspot",
                "operation": "import",
                "contacts_processed": 150,
                "contacts_created": 45,
                "contacts_updated": 105,
                "contacts_failed": 0,
                "errors": [],
                "started_at": "2024-01-15T10:00:00Z",
                "completed_at": "2024-01-15T10:02:30Z",
                "duration_seconds": 150.5
            }
        }


class WebhookEvent(BaseModel):
    """Webhook event from CRM platform"""
    
    platform: str
    event_type: str  # "contact.created", "contact.updated", etc.
    event_id: str  # Platform-specific event ID
    
    contact_id: Optional[str] = None  # External contact ID
    payload: Dict[str, Any]
    
    signature: Optional[str] = None  # Webhook signature for verification
    timestamp: datetime


# ============================================================================
# EXCEPTIONS
# ============================================================================


class CRMException(Exception):
    """Base exception for all CRM operations"""
    pass


class CRMAuthenticationError(CRMException):
    """Authentication failed (invalid credentials, expired tokens)"""
    pass


class CRMRateLimitError(CRMException):
    """Rate limit exceeded"""
    
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after  # Seconds until rate limit resets


class CRMNotFoundError(CRMException):
    """Resource not found (contact, organization, etc.)"""
    pass


class CRMValidationError(CRMException):
    """Invalid data provided to CRM"""
    pass


class CRMNetworkError(CRMException):
    """Network connectivity issues"""
    pass


class CRMWebhookError(CRMException):
    """Webhook signature verification failed"""
    pass


# ============================================================================
# ENCRYPTION MIXIN
# ============================================================================


class CredentialEncryption:
    """Mixin for encrypting/decrypting CRM credentials"""
    
    @staticmethod
    def _get_encryption_key() -> bytes:
        """Get encryption key from environment variable"""
        key = os.getenv("CRM_ENCRYPTION_KEY")
        if not key:
            raise ValueError(
                "CRM_ENCRYPTION_KEY not set in environment. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        return key.encode()
    
    @staticmethod
    def encrypt_credential(plaintext: str) -> str:
        """Encrypt a credential (token, API key) for database storage"""
        fernet = Fernet(CredentialEncryption._get_encryption_key())
        return fernet.encrypt(plaintext.encode()).decode()
    
    @staticmethod
    def decrypt_credential(ciphertext: str) -> str:
        """Decrypt a credential from database"""
        fernet = Fernet(CredentialEncryption._get_encryption_key())
        return fernet.decrypt(ciphertext.encode()).decode()


# ============================================================================
# ABSTRACT CRM PROVIDER
# ============================================================================


class CRMProvider(ABC, CredentialEncryption):
    """
    Abstract base class for all CRM integrations.
    
    All CRM providers (HubSpot, Apollo, LinkedIn) must implement these methods.
    """
    
    def __init__(self, credentials: CRMCredentials):
        """
        Initialize CRM provider with credentials.
        
        Args:
            credentials: Encrypted credentials for authentication
        """
        self.credentials = credentials
        self.platform = credentials.platform
    
    # ========================================================================
    # AUTHENTICATION
    # ========================================================================
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the CRM platform.
        
        Returns:
            True if authentication successful
            
        Raises:
            CRMAuthenticationError: If authentication fails
        """
        pass
    
    @abstractmethod
    async def refresh_access_token(self) -> str:
        """
        Refresh OAuth access token (if applicable).
        
        Returns:
            New access token
            
        Raises:
            CRMAuthenticationError: If refresh fails
        """
        pass
    
    # ========================================================================
    # CONTACT OPERATIONS
    # ========================================================================
    
    @abstractmethod
    async def get_contact(self, contact_id: str) -> Contact:
        """
        Retrieve a contact by platform-specific ID.
        
        Args:
            contact_id: Platform-specific contact ID
            
        Returns:
            Contact object
            
        Raises:
            CRMNotFoundError: If contact doesn't exist
            CRMAuthenticationError: If not authenticated
        """
        pass
    
    @abstractmethod
    async def create_contact(self, contact: Contact) -> Contact:
        """
        Create a new contact in the CRM.
        
        Args:
            contact: Contact data to create
            
        Returns:
            Created contact with platform ID
            
        Raises:
            CRMValidationError: If contact data is invalid
            CRMAuthenticationError: If not authenticated
        """
        pass
    
    @abstractmethod
    async def update_contact(self, contact_id: str, contact: Contact) -> Contact:
        """
        Update an existing contact.
        
        Args:
            contact_id: Platform-specific contact ID
            contact: Updated contact data
            
        Returns:
            Updated contact
            
        Raises:
            CRMNotFoundError: If contact doesn't exist
            CRMValidationError: If update data is invalid
        """
        pass
    
    @abstractmethod
    async def enrich_contact(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Enrich contact data from platform (Apollo only).
        
        Args:
            email: Contact email address
            
        Returns:
            Enrichment data or None if not found
            
        Raises:
            CRMRateLimitError: If rate limit exceeded
        """
        pass
    
    # ========================================================================
    # SYNC OPERATIONS
    # ========================================================================
    
    @abstractmethod
    async def sync_contacts(
        self,
        direction: str = "import",  # "import", "export", "bidirectional"
        filters: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Sync contacts between local database and CRM platform.
        
        Args:
            direction: Sync direction ("import", "export", "bidirectional")
            filters: Optional filters for contacts to sync
            
        Returns:
            Sync operation result
            
        Raises:
            CRMAuthenticationError: If not authenticated
            CRMRateLimitError: If rate limit exceeded
        """
        pass
    
    @abstractmethod
    async def get_updated_contacts(self, since: datetime) -> List[Contact]:
        """
        Get contacts updated since a specific timestamp.
        
        Args:
            since: Timestamp to filter updates
            
        Returns:
            List of updated contacts
            
        Raises:
            CRMAuthenticationError: If not authenticated
        """
        pass
    
    # ========================================================================
    # WEBHOOK HANDLING
    # ========================================================================
    
    @abstractmethod
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify webhook signature from CRM platform.
        
        Args:
            payload: Raw webhook payload
            signature: Signature from webhook headers
            
        Returns:
            True if signature is valid
            
        Raises:
            CRMWebhookError: If signature verification fails
        """
        pass
    
    @abstractmethod
    async def handle_webhook(self, event: WebhookEvent) -> None:
        """
        Process a webhook event from the CRM platform.
        
        Args:
            event: Webhook event data
            
        Raises:
            CRMWebhookError: If event processing fails
        """
        pass
    
    # ========================================================================
    # RATE LIMITING
    # ========================================================================
    
    @abstractmethod
    async def check_rate_limit(self) -> Dict[str, Any]:
        """
        Check current rate limit status.
        
        Returns:
            Dict with rate limit info:
            {
                "remaining": 95,
                "limit": 100,
                "reset_at": datetime,
                "retry_after": 10  # seconds (if throttled)
            }
        """
        pass
