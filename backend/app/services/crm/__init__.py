"""
CRM Integration Package

Provides abstract CRM provider interface and platform-specific implementations
for HubSpot, Apollo, and LinkedIn integrations.

Usage:
    from app.services.crm import CRMProvider, Contact, HubSpotProvider

    # Initialize provider
    provider = HubSpotProvider(credentials)

    # Create contact
    contact = await provider.create_contact(Contact(...))
"""

from app.services.crm.base import (
    # Abstract Base Class
    CRMProvider,

    # Pydantic Models
    Contact,
    CRMCredentials,
    SyncResult,
    WebhookEvent,

    # Exceptions
    CRMException,
    CRMAuthenticationError,
    CRMRateLimitError,
    CRMNotFoundError,
    CRMValidationError,
    CRMNetworkError,
    CRMWebhookError,

    # Encryption Utilities
    CredentialEncryption,
)

from app.services.crm.hubspot import HubSpotProvider
from app.services.crm.apollo import ApolloProvider

__all__ = [
    # Abstract Base Class
    "CRMProvider",

    # Pydantic Models
    "Contact",
    "CRMCredentials",
    "SyncResult",
    "WebhookEvent",

    # Exceptions
    "CRMException",
    "CRMAuthenticationError",
    "CRMRateLimitError",
    "CRMNotFoundError",
    "CRMValidationError",
    "CRMNetworkError",
    "CRMWebhookError",

    # Encryption
    "CredentialEncryption",

    # Platform Implementations
    "HubSpotProvider",
    "ApolloProvider",
]
