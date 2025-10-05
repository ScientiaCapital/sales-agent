"""
Database models for the sales agent application
"""
from .database import Base, get_db, engine, SessionLocal
from .lead import Lead
from .report import Report
from .api_call import CerebrasAPICall
from .agent_models import (
    AgentExecution,
    AgentWorkflow,
    EnrichedLead,
    MarketingCampaign,
    BookedMeeting
)
from .customer_models import (
    Customer,
    KnowledgeDocument,
    CustomerAgent,
    CustomerQuota
)
from .social_media import (
    SocialMediaActivity,
    ContactSocialProfile,
    OrganizationChart
)
from .voice_models import (
    VoiceSessionLog,
    CartesiaAPICall,
    VoiceTurn,
    VoiceConfiguration,
    VoiceSessionStatus
)
from .crm import (
    CRMCredential,
    CRMContact,
    CRMSyncLog,
    CRMWebhook
)
from .campaign import (
    Campaign,
    CampaignMessage,
    MessageVariantAnalytics,
    CampaignStatus,
    CampaignChannel,
    MessageStatus,
    MessageTone
)

__all__ = [
    "Base",
    "get_db",
    "engine",
    "SessionLocal",
    "Lead",
    "Report",
    "CerebrasAPICall",
    "AgentExecution",
    "AgentWorkflow",
    "EnrichedLead",
    "MarketingCampaign",
    "BookedMeeting",
    "Customer",
    "KnowledgeDocument",
    "CustomerAgent",
    "CustomerQuota",
    "SocialMediaActivity",
    "ContactSocialProfile",
    "OrganizationChart",
    "VoiceSessionLog",
    "CartesiaAPICall",
    "VoiceTurn",
    "VoiceConfiguration",
    "VoiceSessionStatus",
    "CRMCredential",
    "CRMContact",
    "CRMSyncLog",
    "CRMWebhook",
    "Campaign",
    "CampaignMessage",
    "MessageVariantAnalytics",
    "CampaignStatus",
    "CampaignChannel",
    "MessageStatus",
    "MessageTone"
]
