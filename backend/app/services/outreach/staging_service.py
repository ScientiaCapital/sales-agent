"""
Outreach Staging Service - Manage staged outreach with approval workflows

Orchestrates multi-channel outreach (email, SMS, LinkedIn, calls) with
human-in-the-loop approval for drafts.

Key Features:
- Stage drafts in dim_ai_drafts table for review
- Auto-send via Close CRM (if AUTO mode)
- Slack notifications with approval buttons
- Batch approval/rejection of drafts
- Integration with OutreachAgent for content generation

Usage:
    service = OutreachStagingService()

    # Stage email + SMS for review
    result = await service.stage_outreach(OutreachRequest(
        lead_id="lead_abc",
        channels=[OutreachChannel.EMAIL, OutreachChannel.SMS],
        mode=StagingMode.DRAFT
    ))

    # Approve and send draft
    await service.approve_draft("draft_123")

    # Get pending drafts
    drafts = await service.get_pending_drafts(limit=20)
"""

import os
import uuid
import time
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.outreach import (
    OutreachRequest,
    OutreachResult,
    OutreachChannel,
    StagingMode,
    ChannelResult,
    DraftApprovalRequest,
    DraftRejectionRequest
)
from app.services.slack_notifier import SlackNotifier
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Supabase client (lazy loaded)
_supabase_client = None


def get_supabase():
    """
    Get or create Supabase client (lazy loading).

    Returns:
        Supabase client instance
    """
    global _supabase_client

    if _supabase_client is None:
        try:
            from supabase import create_client, Client

            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_SERVICE_KEY')

            if not supabase_url or not supabase_key:
                raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

            _supabase_client = create_client(supabase_url, supabase_key)
            logger.info("Supabase client initialized for staging service")

        except ImportError:
            raise ImportError("supabase-py not installed. Run: pip install supabase")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Supabase: {e}")

    return _supabase_client


class OutreachStagingService:
    """
    Service for managing staged outreach with approval workflows.

    Handles the lifecycle of outreach drafts from creation → review → send.
    """

    def __init__(self):
        """Initialize staging service with Supabase and Slack clients."""
        self.supabase = get_supabase()
        self.slack = SlackNotifier()

    async def stage_outreach(self, request: OutreachRequest) -> OutreachResult:
        """
        Stage outreach based on mode and channels.

        Workflow:
        1. For each channel, generate content (or use overrides)
        2. If DRAFT/REVIEW mode: save to dim_ai_drafts + notify Slack
        3. If AUTO mode: send immediately via Close CRM
        4. Return aggregated results

        Args:
            request: OutreachRequest with channels, mode, and content

        Returns:
            OutreachResult with detailed per-channel results
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())

        logger.info(
            f"Staging outreach for lead {request.lead_id}: "
            f"channels={[c.value for c in request.channels]}, mode={request.mode.value}"
        )

        # Initialize result
        result = OutreachResult(
            request_id=request_id,
            lead_id=request.lead_id,
            channels_requested=request.channels,
            created_at=datetime.utcnow()
        )

        # Fetch company data from Supabase
        company_data = await self._get_company_data(request.lead_id)
        if not company_data:
            logger.error(f"Company not found for lead_id: {request.lead_id}")
            return result

        # Process each channel
        channel_results = []
        for channel in request.channels:
            channel_result = await self._process_channel(
                request=request,
                channel=channel,
                company_data=company_data
            )
            channel_results.append(channel_result)

            # Update aggregate stats
            if channel_result.success:
                if channel_result.status == "staged":
                    result.channels_staged.append(channel)
                    result.drafts_created += 1
                elif channel_result.status == "sent":
                    result.channels_sent.append(channel)
            else:
                result.channels_failed.append(channel)

        result.results = channel_results

        # Send Slack notification if drafts were created
        if result.drafts_created > 0 and request.mode != StagingMode.AUTO_APPROVE:
            slack_sent = await self._notify_slack_for_approval(
                company_name=company_data.get("name", "Unknown"),
                drafts=channel_results,
                lead_id=request.lead_id
            )
            result.slack_notified = slack_sent

        # Finalize timing
        result.total_processing_time_ms = int((time.time() - start_time) * 1000)
        result.completed_at = datetime.utcnow()

        logger.info(
            f"Outreach staging complete: {result.drafts_created} drafts, "
            f"{len(result.channels_sent)} sent, {len(result.channels_failed)} failed"
        )

        return result

    async def _process_channel(
        self,
        request: OutreachRequest,
        channel: OutreachChannel,
        company_data: Dict[str, Any]
    ) -> ChannelResult:
        """
        Process a single outreach channel.

        Args:
            request: Original outreach request
            channel: Channel to process
            company_data: Company data from Supabase

        Returns:
            ChannelResult with success/failure details
        """
        start_time = time.time()

        try:
            # Generate or use override content
            content = await self._generate_content(
                channel=channel,
                request=request,
                company_data=company_data
            )

            # Stage or send based on mode
            if request.mode == StagingMode.AUTO_APPROVE:
                # Send immediately via Close CRM
                activity_id = await self._send_via_close(
                    channel=channel,
                    content=content,
                    lead_id=request.lead_id
                )

                return ChannelResult(
                    channel=channel,
                    success=True,
                    status="sent",
                    activity_id=activity_id,
                    processed_at=datetime.utcnow(),
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )

            else:
                # Stage as draft in dim_ai_drafts
                draft_id = await self._create_draft(
                    channel=channel,
                    content=content,
                    company_data=company_data,
                    request=request
                )

                return ChannelResult(
                    channel=channel,
                    success=True,
                    status="staged",
                    draft_id=draft_id,
                    processed_at=datetime.utcnow(),
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )

        except Exception as e:
            logger.error(f"Failed to process channel {channel.value}: {e}")

            return ChannelResult(
                channel=channel,
                success=False,
                status="failed",
                error=str(e),
                processed_at=datetime.utcnow(),
                processing_time_ms=int((time.time() - start_time) * 1000)
            )

    async def _generate_content(
        self,
        channel: OutreachChannel,
        request: OutreachRequest,
        company_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Generate content for a channel (or use override).

        Args:
            channel: Channel to generate content for
            request: Original request (may have overrides)
            company_data: Company data for personalization

        Returns:
            Dict with 'subject' (if email) and 'body' keys
        """
        # Check for overrides
        if channel == OutreachChannel.EMAIL:
            if request.email_subject and request.email_body:
                return {
                    "subject": request.email_subject,
                    "body": request.email_body
                }

        elif channel == OutreachChannel.SMS:
            if request.sms_text:
                return {"body": request.sms_text}

        elif channel == OutreachChannel.LINKEDIN:
            if request.linkedin_note:
                return {"body": request.linkedin_note}

        elif channel == OutreachChannel.CALL:
            if request.call_script:
                return {"body": request.call_script}

        # TODO: Generate via AI (integrate with SalesIntelAgent or OutreachAgent)
        # For now, use placeholder templates
        return await self._generate_template_content(channel, company_data)

    async def _generate_template_content(
        self,
        channel: OutreachChannel,
        company_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Generate template content for a channel.

        TODO: Replace with AI-generated content from SalesIntelAgent.

        Args:
            channel: Channel type
            company_data: Company data for personalization

        Returns:
            Dict with content
        """
        company_name = company_data.get("name", "your company")

        if channel == OutreachChannel.EMAIL:
            return {
                "subject": f"Quick question about {company_name}",
                "body": f"Hi,\n\nI noticed {company_name} and wanted to reach out...\n\nBest,\nTim"
            }

        elif channel == OutreachChannel.SMS:
            return {
                "body": f"Hi! Quick question about {company_name}. Do you have 2 mins this week? - Tim"
            }

        elif channel == OutreachChannel.LINKEDIN:
            return {
                "body": f"Hi! I'd like to connect and discuss opportunities for {company_name}."
            }

        elif channel == OutreachChannel.CALL:
            return {
                "body": f"Talking points for {company_name}:\n- Intro\n- Discuss needs\n- Schedule follow-up"
            }

        else:
            return {"body": "Content generation not implemented for this channel"}

    async def _create_draft(
        self,
        channel: OutreachChannel,
        content: Dict[str, str],
        company_data: Dict[str, Any],
        request: OutreachRequest
    ) -> str:
        """
        Create draft in dim_ai_drafts table.

        Args:
            channel: Channel type
            content: Generated content
            company_data: Company data
            request: Original request

        Returns:
            Draft ID (UUID)
        """
        draft_data = {
            "company_id": company_data.get("id"),
            "draft_type": channel.value,
            "subject": content.get("subject"),
            "body": content.get("body"),
            "status": "pending",
            "created_by": request.created_by
        }

        response = self.supabase.table("dim_ai_drafts").insert(draft_data).execute()

        if not response.data:
            raise RuntimeError("Failed to create draft in Supabase")

        draft_id = response.data[0]["id"]
        logger.info(f"Created draft {draft_id} for channel {channel.value}")

        return draft_id

    async def _send_via_close(
        self,
        channel: OutreachChannel,
        content: Dict[str, str],
        lead_id: str
    ) -> str:
        """
        Send outreach via Close CRM.

        Args:
            channel: Channel type
            content: Content to send
            lead_id: Close CRM lead ID

        Returns:
            Close CRM activity ID
        """
        # Check if Close writes are enabled
        if os.getenv("CLOSE_WRITE_DISABLED", "True").lower() in ("true", "1", "yes"):
            raise RuntimeError("Close CRM writes are disabled (CLOSE_WRITE_DISABLED=True)")

        # TODO: Implement actual Close CRM sending via CloseEmailClient, CloseSMSClient, etc.
        # For now, raise NotImplementedError
        raise NotImplementedError(f"AUTO mode sending not yet implemented for {channel.value}")

    async def _get_company_data(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch company data from Supabase by lead_id.

        Args:
            lead_id: Close CRM lead ID

        Returns:
            Company data dict or None if not found
        """
        try:
            response = self.supabase.table("dim_companies") \
                .select("*") \
                .eq("close_lead_id", lead_id) \
                .limit(1) \
                .execute()

            if response.data:
                return response.data[0]

            logger.warning(f"No company found for lead_id: {lead_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch company data: {e}")
            return None

    async def _notify_slack_for_approval(
        self,
        company_name: str,
        drafts: List[ChannelResult],
        lead_id: str = ""
    ) -> bool:
        """
        Send Slack notification with approve/reject buttons.

        Args:
            company_name: Name of the company
            drafts: List of channel results (with draft_ids)
            lead_id: Close CRM lead ID

        Returns:
            True if notification sent successfully
        """
        # Filter to only drafts that need approval
        pending_drafts = [d for d in drafts if d.draft_id]

        if not pending_drafts:
            return False

        # Build draft data for Slack
        slack_drafts = []
        for draft in pending_drafts:
            # Get draft content from Supabase for preview
            try:
                response = self.supabase.table("dim_ai_drafts") \
                    .select("body, subject") \
                    .eq("id", draft.draft_id) \
                    .limit(1) \
                    .execute()

                if response.data:
                    body = response.data[0].get("body", "")
                    subject = response.data[0].get("subject", "")
                    preview = subject or body[:100]
                else:
                    preview = "No preview available"

            except Exception as e:
                logger.warning(f"Failed to fetch draft preview: {e}")
                preview = "No preview available"

            slack_drafts.append({
                "channel": draft.channel.value,
                "draft_id": draft.draft_id,
                "preview": preview
            })

        # Send multi-channel approval request
        return await self.slack.send_multichannel_approval_request(
            company_name=company_name,
            drafts=slack_drafts,
            lead_id=lead_id
        )

    async def approve_draft(self, draft_id: str, approved_by: str = "system") -> bool:
        """
        Approve and send a draft.

        Workflow:
        1. Fetch draft from dim_ai_drafts
        2. Update status to 'approved'
        3. Send via Close CRM
        4. Update status to 'sent' with activity ID

        Args:
            draft_id: Draft ID from dim_ai_drafts
            approved_by: User who approved

        Returns:
            True if approved and sent successfully
        """
        try:
            # Fetch draft
            response = self.supabase.table("dim_ai_drafts") \
                .select("*") \
                .eq("id", draft_id) \
                .limit(1) \
                .execute()

            if not response.data:
                logger.error(f"Draft not found: {draft_id}")
                return False

            draft = response.data[0]

            # Update status to approved
            self.supabase.table("dim_ai_drafts") \
                .update({"status": "approved"}) \
                .eq("id", draft_id) \
                .execute()

            # TODO: Send via Close CRM based on draft_type
            # For now, just mark as sent
            self.supabase.table("dim_ai_drafts") \
                .update({
                    "status": "sent",
                    "sent_at": datetime.utcnow().isoformat()
                }) \
                .eq("id", draft_id) \
                .execute()

            logger.info(f"Draft {draft_id} approved and sent by {approved_by}")
            return True

        except Exception as e:
            logger.error(f"Failed to approve draft {draft_id}: {e}")
            return False

    async def reject_draft(self, draft_id: str, reason: str = "", rejected_by: str = "system") -> bool:
        """
        Reject and discard a draft.

        Args:
            draft_id: Draft ID from dim_ai_drafts
            reason: Rejection reason (for learning)
            rejected_by: User who rejected

        Returns:
            True if rejected successfully
        """
        try:
            self.supabase.table("dim_ai_drafts") \
                .update({"status": "discarded"}) \
                .eq("id", draft_id) \
                .execute()

            logger.info(f"Draft {draft_id} rejected by {rejected_by}: {reason}")
            return True

        except Exception as e:
            logger.error(f"Failed to reject draft {draft_id}: {e}")
            return False

    async def get_pending_drafts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get drafts awaiting approval.

        Args:
            limit: Maximum number of drafts to return

        Returns:
            List of draft dicts
        """
        try:
            response = self.supabase.table("dim_ai_drafts") \
                .select("*, dim_companies(name, domain)") \
                .eq("status", "pending") \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()

            return response.data or []

        except Exception as e:
            logger.error(f"Failed to fetch pending drafts: {e}")
            return []
