"""
Campaign Orchestration Service

Manages campaign lifecycle, message generation, A/B testing, and analytics.
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.campaign import (
    Campaign, 
    CampaignMessage, 
    MessageVariantAnalytics,
    CampaignStatus, 
    CampaignChannel,
    MessageStatus,
    MessageTone
)
from app.models.lead import Lead
from app.services.outreach.message_generator import MessageGenerator
from app.core.logging import setup_logging
from app.core.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    ResourceConflictError
)

logger = setup_logging(__name__)


class CampaignService:
    """
    Service for managing outreach campaigns with A/B testing.
    
    Features:
    - Campaign creation with audience targeting
    - Bulk message generation with 3 variants per lead
    - A/B testing analytics and variant performance tracking
    - Campaign activation and status management
    """
    
    def __init__(self, db: Session):
        """
        Initialize campaign service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.message_generator = MessageGenerator()
    
    def create_campaign(
        self,
        name: str,
        channel: str,
        min_qualification_score: Optional[float] = None,
        target_industries: Optional[List[str]] = None,
        target_company_sizes: Optional[List[str]] = None,
        message_template: Optional[str] = None,
        custom_context: Optional[str] = None
    ) -> Campaign:
        """
        Create a new outreach campaign.
        
        Args:
            name: Campaign name
            channel: Communication channel (email, linkedin, sms)
            min_qualification_score: Minimum lead qualification score (0-100)
            target_industries: List of target industries
            target_company_sizes: List of target company size ranges
            message_template: Optional template with {{variable}} placeholders
            custom_context: Additional context for message generation
        
        Returns:
            Created Campaign object
        
        Raises:
            ValidationError: If parameters are invalid
        """
        # Validate channel
        if channel.lower() not in ['email', 'linkedin', 'sms']:
            raise ValidationError(
                f"Invalid channel: {channel}. Must be email, linkedin, or sms",
                context={"channel": channel}
            )
        
        # Create campaign
        campaign = Campaign(
            name=name,
            status=CampaignStatus.DRAFT,
            channel=CampaignChannel(channel.lower()),
            min_qualification_score=min_qualification_score,
            target_industries=target_industries or [],
            target_company_sizes=target_company_sizes or [],
            message_template=message_template,
            custom_context=custom_context
        )
        
        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)
        
        logger.info(f"Campaign created: {name} (ID: {campaign.id}, Channel: {channel})")
        
        return campaign
    
    def generate_messages(
        self,
        campaign_id: int,
        custom_context: Optional[str] = None,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate personalized messages for all qualified leads in campaign.
        
        Args:
            campaign_id: Campaign ID
            custom_context: Override campaign's custom_context for this generation
            force_regenerate: Regenerate messages even if they already exist
        
        Returns:
            Dictionary with generation statistics
        
        Raises:
            ResourceNotFoundError: If campaign not found
            ResourceConflictError: If messages already exist and force_regenerate=False
            ValidationError: If no qualified leads found
        """
        # Get campaign
        campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise ResourceNotFoundError(
                f"Campaign {campaign_id} not found",
                context={"campaign_id": campaign_id}
            )
        
        # Check if messages already exist
        existing_count = self.db.query(CampaignMessage).filter(
            CampaignMessage.campaign_id == campaign_id
        ).count()
        
        if existing_count > 0 and not force_regenerate:
            raise ResourceConflictError(
                f"Campaign already has {existing_count} messages. Use force_regenerate=true to regenerate",
                context={"campaign_id": campaign_id, "existing_messages": existing_count}
            )
        
        # Delete existing messages if force regenerating
        if force_regenerate and existing_count > 0:
            self.db.query(CampaignMessage).filter(
                CampaignMessage.campaign_id == campaign_id
            ).delete()
            logger.info(f"Deleted {existing_count} existing messages for campaign {campaign_id}")
        
        # Build lead query with targeting filters
        leads_query = self.db.query(Lead)
        
        if campaign.min_qualification_score is not None:
            leads_query = leads_query.filter(
                Lead.qualification_score >= campaign.min_qualification_score
            )
        
        if campaign.target_industries:
            leads_query = leads_query.filter(
                Lead.industry.in_(campaign.target_industries)
            )
        
        if campaign.target_company_sizes:
            leads_query = leads_query.filter(
                Lead.company_size.in_(campaign.target_company_sizes)
            )
        
        qualified_leads = leads_query.all()
        
        if not qualified_leads:
            raise ValidationError(
                "No qualified leads found matching campaign criteria",
                context={
                    "campaign_id": campaign_id,
                    "min_score": campaign.min_qualification_score,
                    "industries": campaign.target_industries,
                    "company_sizes": campaign.target_company_sizes
                }
            )
        
        # Generate messages for each lead
        stats = {
            "messages_generated": 0,
            "leads_processed": len(qualified_leads),
            "total_cost": 0.0,
            "failed": 0
        }
        
        context_to_use = custom_context if custom_context is not None else campaign.custom_context
        
        for lead in qualified_leads:
            try:
                # Build lead context
                lead_context = {
                    "company_name": lead.company_name,
                    "contact_name": lead.contact_name,
                    "contact_title": lead.contact_title,
                    "contact_email": lead.contact_email,
                    "qualification_score": lead.qualification_score,
                    "research_summary": lead.qualification_reasoning,
                    "industry": lead.industry,
                    "company_size": lead.company_size
                }
                
                # Generate 3 variants
                result = self.message_generator.generate_message_variants(
                    channel=campaign.channel.value,
                    lead_context=lead_context,
                    custom_context=context_to_use,
                    template=campaign.message_template
                )
                
                # Create message record
                message = CampaignMessage(
                    campaign_id=campaign_id,
                    lead_id=lead.id,
                    variants=result["variants"],
                    selected_variant=0,  # Default to first variant
                    status=MessageStatus.PENDING,
                    generation_cost=result["cost_usd"]
                )
                self.db.add(message)
                self.db.flush()  # Get message.id for analytics
                
                # Create analytics records for each variant
                for i, variant in enumerate(result["variants"]):
                    analytics = MessageVariantAnalytics(
                        message_id=message.id,
                        variant_number=i,
                        tone=MessageTone(variant["tone"]),
                        subject=variant.get("subject"),
                        body=variant["body"]
                    )
                    self.db.add(analytics)
                
                stats["messages_generated"] += 1
                stats["total_cost"] += result["cost_usd"]
                
            except Exception as e:
                logger.error(f"Failed to generate message for lead {lead.id}: {e}")
                stats["failed"] += 1
                continue
        
        # Update campaign totals
        campaign.total_messages = stats["messages_generated"]
        campaign.total_cost = stats["total_cost"]
        
        self.db.commit()
        
        logger.info(
            f"Generated {stats['messages_generated']} messages for campaign {campaign_id} "
            f"(Cost: ${stats['total_cost']:.4f})"
        )
        
        return stats
    
    def get_campaign_analytics(self, campaign_id: int) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a campaign including A/B test results.
        
        Args:
            campaign_id: Campaign ID
        
        Returns:
            Dictionary with campaign metrics, costs, and A/B testing results
        
        Raises:
            ResourceNotFoundError: If campaign not found
        """
        campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise ResourceNotFoundError(
                f"Campaign {campaign_id} not found",
                context={"campaign_id": campaign_id}
            )
        
        # Get variant performance grouped by tone
        variant_performance = []
        
        for tone in MessageTone:
            # Get all analytics for this tone across all campaign messages
            analytics = self.db.query(MessageVariantAnalytics).filter(
                MessageVariantAnalytics.message_id.in_(
                    self.db.query(CampaignMessage.id).filter(
                        CampaignMessage.campaign_id == campaign_id
                    )
                ),
                MessageVariantAnalytics.tone == tone
            ).all()
            
            if not analytics:
                continue
            
            total_selected = sum(a.times_selected for a in analytics)
            total_opened = sum(a.times_opened for a in analytics)
            total_clicked = sum(a.times_clicked for a in analytics)
            total_replied = sum(a.times_replied for a in analytics)
            
            variant_performance.append({
                "tone": tone.value,
                "times_selected": total_selected,
                "times_opened": total_opened,
                "times_clicked": total_clicked,
                "times_replied": total_replied,
                "open_rate": (total_opened / total_selected * 100) if total_selected > 0 else 0,
                "click_rate": (total_clicked / total_selected * 100) if total_selected > 0 else 0,
                "reply_rate": (total_replied / total_selected * 100) if total_selected > 0 else 0
            })
        
        # Determine winning variant based on reply rate
        winning_variant = max(
            variant_performance,
            key=lambda x: x["reply_rate"]
        ) if variant_performance else None
        
        # Get top performing messages
        top_messages = self.db.query(CampaignMessage).filter(
            CampaignMessage.campaign_id == campaign_id,
            CampaignMessage.status == MessageStatus.REPLIED
        ).order_by(CampaignMessage.replied_at.desc()).limit(5).all()
        
        top_performing = []
        for msg in top_messages:
            top_performing.append({
                "message_id": msg.id,
                "lead_id": msg.lead_id,
                "selected_variant": msg.selected_variant,
                "replied_at": msg.replied_at.isoformat() if msg.replied_at else None
            })
        
        return {
            "campaign": campaign,
            "metrics": {
                "open_rate": campaign.open_rate,
                "click_rate": campaign.click_rate,
                "reply_rate": campaign.reply_rate,
                "delivery_rate": campaign.delivery_rate
            },
            "cost": {
                "total_cost_usd": campaign.total_cost,
                "cost_per_message": campaign.total_cost / campaign.total_messages if campaign.total_messages > 0 else 0,
                "cost_per_reply": campaign.total_cost / campaign.total_replied if campaign.total_replied > 0 else 0
            },
            "ab_testing": {
                "variant_performance": variant_performance,
                "winning_variant": winning_variant
            },
            "top_performing_messages": top_performing
        }
    
    def update_message_status(
        self,
        message_id: int,
        status: str,
        variant_number: Optional[int] = None
    ) -> CampaignMessage:
        """
        Update message status and track variant performance.
        
        Args:
            message_id: Message ID
            status: New status (sent, delivered, opened, clicked, replied, bounced, failed)
            variant_number: Variant number (0-2) if tracking specific variant performance
        
        Returns:
            Updated CampaignMessage object
        
        Raises:
            ResourceNotFoundError: If message not found
            ValidationError: If status or variant_number invalid
        """
        message = self.db.query(CampaignMessage).filter(
            CampaignMessage.id == message_id
        ).first()
        
        if not message:
            raise ResourceNotFoundError(
                f"Message {message_id} not found",
                context={"message_id": message_id}
            )
        
        # Update message status
        try:
            message.status = MessageStatus(status.lower())
        except ValueError:
            raise ValidationError(
                f"Invalid status: {status}",
                context={"status": status}
            )
        
        # Set timestamp for status change
        status_field = f"{status.lower()}_at"
        if hasattr(message, status_field):
            setattr(message, status_field, datetime.utcnow())
        
        # Update variant analytics if variant specified
        if variant_number is not None:
            if variant_number not in [0, 1, 2]:
                raise ValidationError(
                    f"Invalid variant_number: {variant_number}. Must be 0, 1, or 2",
                    context={"variant_number": variant_number}
                )
            
            analytics = self.db.query(MessageVariantAnalytics).filter(
                MessageVariantAnalytics.message_id == message_id,
                MessageVariantAnalytics.variant_number == variant_number
            ).first()
            
            if analytics:
                analytics.times_selected += 1
                if status == "opened":
                    analytics.times_opened += 1
                elif status == "clicked":
                    analytics.times_clicked += 1
                elif status == "replied":
                    analytics.times_replied += 1
        
        # Update campaign metrics
        campaign = message.campaign
        if status == "sent":
            campaign.total_sent += 1
        elif status == "delivered":
            campaign.total_delivered += 1
        elif status == "opened":
            campaign.total_opened += 1
        elif status == "clicked":
            campaign.total_clicked += 1
        elif status == "replied":
            campaign.total_replied += 1
        
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    def activate_campaign(self, campaign_id: int) -> Campaign:
        """
        Activate a campaign and mark it ready for sending.
        
        Args:
            campaign_id: Campaign ID
        
        Returns:
            Updated Campaign object
        
        Raises:
            ResourceNotFoundError: If campaign not found
            ValidationError: If campaign cannot be activated
        """
        campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise ResourceNotFoundError(
                f"Campaign {campaign_id} not found",
                context={"campaign_id": campaign_id}
            )
        
        if campaign.total_messages == 0:
            raise ValidationError(
                "Cannot activate campaign with no messages",
                context={"campaign_id": campaign_id}
            )
        
        campaign.status = CampaignStatus.ACTIVE
        campaign.activated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(campaign)
        
        logger.info(f"Campaign {campaign_id} activated with {campaign.total_messages} messages")
        return campaign
    
    def get_campaign_messages(
        self,
        campaign_id: int,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[CampaignMessage]:
        """
        Get messages for a campaign with optional filtering.
        
        Args:
            campaign_id: Campaign ID
            status: Optional status filter
            skip: Number of records to skip (pagination)
            limit: Maximum records to return (pagination)
        
        Returns:
            List of CampaignMessage objects
        
        Raises:
            ResourceNotFoundError: If campaign not found
        """
        # Verify campaign exists
        campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise ResourceNotFoundError(
                f"Campaign {campaign_id} not found",
                context={"campaign_id": campaign_id}
            )
        
        # Build query
        query = self.db.query(CampaignMessage).filter(
            CampaignMessage.campaign_id == campaign_id
        )
        
        # Apply status filter if provided
        if status:
            try:
                query = query.filter(CampaignMessage.status == MessageStatus(status.lower()))
            except ValueError:
                raise ValidationError(
                    f"Invalid status: {status}",
                    context={"status": status}
                )
        
        # Apply pagination
        messages = query.offset(skip).limit(limit).all()
        
        return messages
    
    def get_message_variants(self, message_id: int) -> List[Dict[str, Any]]:
        """
        Get all variants for a message with their analytics.
        
        Args:
            message_id: Message ID
        
        Returns:
            List of variants with analytics data
        
        Raises:
            ResourceNotFoundError: If message not found
        """
        message = self.db.query(CampaignMessage).filter(
            CampaignMessage.id == message_id
        ).first()
        
        if not message:
            raise ResourceNotFoundError(
                f"Message {message_id} not found",
                context={"message_id": message_id}
            )
        
        # Get analytics for all variants
        analytics = self.db.query(MessageVariantAnalytics).filter(
            MessageVariantAnalytics.message_id == message_id
        ).order_by(MessageVariantAnalytics.variant_number).all()
        
        # Build variant response with analytics
        variants = []
        for i, variant_data in enumerate(message.variants):
            # Find matching analytics
            variant_analytics = next(
                (a for a in analytics if a.variant_number == i),
                None
            )
            
            variant_info = {
                "variant_number": i,
                "tone": variant_data["tone"],
                "subject": variant_data.get("subject"),
                "body": variant_data["body"],
                "is_selected": i == message.selected_variant,
                "analytics": {
                    "times_selected": variant_analytics.times_selected if variant_analytics else 0,
                    "times_opened": variant_analytics.times_opened if variant_analytics else 0,
                    "times_clicked": variant_analytics.times_clicked if variant_analytics else 0,
                    "times_replied": variant_analytics.times_replied if variant_analytics else 0
                } if variant_analytics else None
            }
            
            variants.append(variant_info)
        
        return variants
    
    def list_campaigns(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Campaign]:
        """
        List all campaigns with optional filtering.
        
        Args:
            status: Optional status filter
            skip: Number of records to skip (pagination)
            limit: Maximum records to return (pagination)
        
        Returns:
            List of Campaign objects
        """
        query = self.db.query(Campaign)
        
        # Apply status filter if provided
        if status:
            try:
                query = query.filter(Campaign.status == CampaignStatus(status.lower()))
            except ValueError:
                raise ValidationError(
                    f"Invalid status: {status}",
                    context={"status": status}
                )
        
        # Order by creation date (newest first)
        query = query.order_by(Campaign.created_at.desc())
        
        # Apply pagination
        campaigns = query.offset(skip).limit(limit).all()
        
        return campaigns
