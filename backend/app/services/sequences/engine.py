"""
Sequence Engine - Core orchestration for multi-step email campaigns.

This is the CRITICAL component that:
1. Enrolls prospects from Qualifier (sales-agent) into email sequences
2. Executes sequence steps on schedule
3. Processes replies and triggers signals to VozLux for calls

Flow: Qualifier → SequenceEngine → EmailSender → SignalProcessor → VozLux
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.sequence import Sequence
from app.models.sequence_entry import SequenceEntry
from app.models.mailbox import Mailbox
from app.models.signal import Signal

logger = logging.getLogger(__name__)


class SequenceEngine:
    """
    Orchestrates multi-step email sequences for outbound campaigns.

    Responsibilities:
    - Enroll prospects into sequences
    - Execute scheduled email steps
    - Track sequence progress
    - Process replies and trigger signals
    - Coordinate with VozLux for call triggers
    """

    def __init__(self, session: AsyncSession):
        """Initialize engine with database session."""
        self.session = session
        self._test_mode = True  # Start in test mode - no actual emails

    # =========================================================================
    # ENROLLMENT
    # =========================================================================

    async def enroll_prospect(
        self,
        prospect_email: str,
        sequence_id: str,
        mailbox_id: int,
        custom_fields: Optional[Dict[str, Any]] = None,
        company_name: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        tier: Optional[str] = None,
        icp_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Enroll a prospect into an email sequence.

        Called by Qualifier (sales-agent) when a lead qualifies as Tier A or B.

        Args:
            prospect_email: Prospect's email address
            sequence_id: Unique sequence ID (e.g., 'solar_installer_intro')
            mailbox_id: ID of the mailbox to send from
            custom_fields: Additional data for personalization (coperniq_score, oems, etc.)
            company_name: Company name for the prospect
            first_name: Contact first name
            last_name: Contact last name
            tier: Qualification tier (A/B/C/D)
            icp_score: ICP score from Prospector (0-100)

        Returns:
            Dict with enrollment status and entry_id
        """
        try:
            # Check if prospect already exists
            prospect = await self._get_or_create_prospect(
                email=prospect_email,
                company=company_name,
                first_name=first_name,
                last_name=last_name,
                tier=tier,
                icp_score=icp_score,
                custom_fields=custom_fields or {},
            )

            # Get sequence
            sequence = await self._get_sequence_by_id(sequence_id)
            if not sequence:
                return {
                    "success": False,
                    "error": f"Sequence '{sequence_id}' not found",
                    "entry_id": None,
                }

            # Get mailbox
            mailbox = await self.session.get(Mailbox, mailbox_id)
            if not mailbox:
                return {
                    "success": False,
                    "error": f"Mailbox {mailbox_id} not found",
                    "entry_id": None,
                }

            # Check for existing enrollment
            existing_entry = await self._get_existing_entry(
                prospect.id, sequence.id
            )
            if existing_entry:
                if existing_entry.status in ["completed", "replied"]:
                    # Can re-enroll completed sequences
                    pass
                else:
                    return {
                        "success": False,
                        "error": "Prospect already enrolled in this sequence",
                        "entry_id": existing_entry.id,
                        "status": existing_entry.status,
                    }

            # Create sequence entry
            entry = SequenceEntry(
                lead_id=prospect.id,
                sequence_id=sequence.id,
                mailbox_id=mailbox.id,
                status="pending",
                current_step=0,
                started_at=datetime.utcnow(),
                emails_sent=0,
                opens=0,
                clicks=0,
            )

            self.session.add(entry)
            await self.session.commit()
            await self.session.refresh(entry)

            logger.info(
                f"Enrolled prospect {prospect_email} in sequence '{sequence_id}' "
                f"(entry_id={entry.id}, tier={tier})"
            )

            return {
                "success": True,
                "entry_id": entry.id,
                "prospect_id": prospect.id,
                "sequence_id": sequence.id,
                "status": "pending",
                "first_step_due": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to enroll prospect {prospect_email}: {e}")
            await self.session.rollback()
            return {
                "success": False,
                "error": str(e),
                "entry_id": None,
            }

    # =========================================================================
    # EXECUTION
    # =========================================================================

    async def execute_step(self, entry_id: int) -> Dict[str, Any]:
        """
        Execute the current step for a sequence entry.

        Args:
            entry_id: Sequence entry ID

        Returns:
            Dict with execution result and next step info
        """
        try:
            # Get entry with related data
            entry = await self.session.get(SequenceEntry, entry_id)
            if not entry:
                return {"success": False, "error": "Entry not found"}

            if entry.status not in ["pending", "active"]:
                return {
                    "success": False,
                    "error": f"Entry status is '{entry.status}', cannot execute",
                }

            # Get sequence with steps
            sequence = await self.session.get(Sequence, entry.sequence_id)
            if not sequence:
                return {"success": False, "error": "Sequence not found"}

            steps = sequence.steps or []
            if entry.current_step >= len(steps):
                entry.status = "completed"
                entry.completed_at = datetime.utcnow()
                await self.session.commit()
                return {
                    "success": True,
                    "action": "completed",
                    "message": "Sequence completed - no more steps",
                }

            # Get current step
            step = steps[entry.current_step]

            # Get prospect and mailbox
            prospect = await self.session.get(Lead, entry.lead_id)
            mailbox = await self.session.get(Mailbox, entry.mailbox_id)

            # Render email content with personalization
            subject = self._render_template(step.get("subject", ""), prospect)
            body = self._render_template(step.get("body", ""), prospect)

            # Send email (or log in test mode)
            send_result = await self._send_email(
                mailbox=mailbox,
                to_email=prospect.contact_email,
                subject=subject,
                body=body,
                entry_id=entry_id,
            )

            if send_result["success"]:
                # Update entry
                entry.status = "active"
                entry.current_step += 1
                entry.last_email_sent = datetime.utcnow()
                entry.emails_sent += 1

                # Store message ID for threading
                if entry.message_ids is None:
                    entry.message_ids = []
                entry.message_ids.append(send_result.get("message_id", ""))

                await self.session.commit()

                # Calculate next step timing
                next_step_delay = step.get("delay_days", 3)
                next_due = datetime.utcnow() + timedelta(days=next_step_delay)

                return {
                    "success": True,
                    "action": "sent",
                    "message_id": send_result.get("message_id"),
                    "test_mode": send_result.get("test_mode", False),
                    "current_step": entry.current_step,
                    "total_steps": len(steps),
                    "next_step_due": next_due.isoformat() if entry.current_step < len(steps) else None,
                }
            else:
                return {
                    "success": False,
                    "error": send_result.get("error", "Send failed"),
                }

        except Exception as e:
            logger.error(f"Failed to execute step for entry {entry_id}: {e}")
            await self.session.rollback()
            return {"success": False, "error": str(e)}

    async def process_due_emails(self, limit: int = 50) -> Dict[str, Any]:
        """
        Process all due emails (cron job entry point).

        Finds entries that are due for their next step and executes them.
        Respects sequence step delays (delay_days) to avoid sending emails too early.

        Args:
            limit: Maximum number of entries to process in one batch (max 1000)

        Returns:
            Dict with processing statistics
        """
        try:
            # Validate limit parameter
            if not isinstance(limit, int) or limit <= 0:
                logger.warning(f"Invalid limit parameter: {limit}, using default 50")
                limit = 50
            elif limit > 1000:
                logger.warning(f"Limit {limit} exceeds maximum 1000, capping at 1000")
                limit = 1000

            # Find entries that are pending or active
            # We'll filter by delay in Python since we need to check sequence steps
            query = select(SequenceEntry).where(
                SequenceEntry.status.in_(["pending", "active"])
            ).limit(limit * 2)  # Fetch more to account for filtering

            result = await self.session.execute(query)
            all_entries = result.scalars().all()

            # Filter entries that are actually due based on sequence delay_days
            due_entries = []
            filtered_count = 0

            for entry in all_entries:
                if len(due_entries) >= limit:
                    break

                # If no email sent yet, it's due immediately (first email)
                if entry.last_email_sent is None:
                    due_entries.append(entry)
                    continue

                # Get sequence to check step delay
                sequence = await self.session.get(Sequence, entry.sequence_id)
                if not sequence or not sequence.steps:
                    logger.warning(f"Entry {entry.id} has invalid sequence, skipping")
                    filtered_count += 1
                    continue

                # Check if we've completed all steps
                if entry.current_step >= len(sequence.steps):
                    logger.debug(f"Entry {entry.id} has completed all steps, skipping")
                    filtered_count += 1
                    continue

                # Get the current step's delay requirement
                current_step_index = entry.current_step
                if current_step_index > 0 and current_step_index < len(sequence.steps):
                    step = sequence.steps[current_step_index]
                    delay_days = step.get("delay_days", 0)

                    # Calculate if enough time has passed
                    time_since_last = datetime.utcnow() - entry.last_email_sent
                    required_delay = timedelta(days=delay_days)

                    if time_since_last >= required_delay:
                        due_entries.append(entry)
                    else:
                        # Not due yet
                        remaining = required_delay - time_since_last
                        logger.debug(
                            f"Entry {entry.id} not due yet, "
                            f"{remaining.total_seconds() / 3600:.1f}h remaining"
                        )
                        filtered_count += 1
                else:
                    # Shouldn't happen, but handle gracefully
                    due_entries.append(entry)

            logger.info(
                f"Found {len(all_entries)} pending/active entries, "
                f"{len(due_entries)} are due, {filtered_count} filtered by delay"
            )

            processed = 0
            sent = 0
            errors = 0

            for entry in due_entries:
                try:
                    exec_result = await self.execute_step(entry.id)
                    processed += 1
                    if exec_result.get("success"):
                        sent += 1
                    else:
                        errors += 1
                        logger.warning(
                            f"Failed to execute step for entry {entry.id}: "
                            f"{exec_result.get('error', 'Unknown error')}"
                        )
                except Exception as e:
                    logger.error(f"Error processing entry {entry.id}: {e}")
                    errors += 1

            logger.info(
                f"Processed {processed} due emails: {sent} sent, {errors} errors"
            )

            return {
                "processed": processed,
                "sent": sent,
                "errors": errors,
                "filtered": filtered_count,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to process due emails: {e}")
            return {"processed": 0, "sent": 0, "errors": 1, "error": str(e)}

    # =========================================================================
    # REPLY HANDLING
    # =========================================================================

    async def handle_reply(
        self,
        entry_id: int,
        intent: str,
        reply_content: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle a reply to a sequence email.

        Args:
            entry_id: Sequence entry that received the reply
            intent: Classified intent ('interested', 'not_interested', 'unsubscribe', 'question', 'ooo')
            reply_content: Optional reply text for context
            from_email: Email address that replied

        Returns:
            Dict with handling result and next action
        """
        try:
            entry = await self.session.get(SequenceEntry, entry_id)
            if not entry:
                return {"success": False, "error": "Entry not found"}

            prospect = await self.session.get(Lead, entry.lead_id)
            sequence = await self.session.get(Sequence, entry.sequence_id)

            # Update entry
            entry.reply_received = datetime.utcnow()
            entry.reply_intent = intent

            # Create signal record
            signal = Signal(
                lead_id=prospect.id,
                signal_type="email_reply",
                mailbox_email=from_email,
                content=reply_content,
                intent=intent,
                priority=self._get_intent_priority(intent),
                received_at=datetime.utcnow(),
            )
            self.session.add(signal)

            # Determine action based on intent
            next_action = None

            if intent == "interested":
                # Stop sequence and trigger call
                entry.status = "replied"
                if sequence and sequence.stop_on_reply:
                    entry.completed_at = datetime.utcnow()

                next_action = {
                    "action": "trigger_call",
                    "reason": "Interested reply - schedule sales call",
                    "priority": 1,
                }

                logger.info(
                    f"Interested reply from {prospect.contact_email} - triggering call"
                )

            elif intent == "not_interested":
                entry.status = "replied"
                entry.completed_at = datetime.utcnow()
                next_action = {
                    "action": "archive",
                    "reason": "Not interested - remove from sequence",
                    "priority": 5,
                }

            elif intent == "unsubscribe":
                entry.status = "unsubscribed"
                entry.completed_at = datetime.utcnow()
                # TODO: Add to global unsubscribe list
                next_action = {
                    "action": "unsubscribe",
                    "reason": "Unsubscribe request",
                    "priority": 1,
                }

            elif intent == "question":
                # Pause sequence, needs human review
                entry.status = "paused"
                next_action = {
                    "action": "human_review",
                    "reason": "Question received - needs response",
                    "priority": 2,
                }

            elif intent == "ooo":
                # Out of office - reschedule
                entry.status = "paused"
                next_action = {
                    "action": "reschedule",
                    "reason": "Out of office detected",
                    "priority": 4,
                }

            await self.session.commit()

            return {
                "success": True,
                "entry_id": entry_id,
                "intent": intent,
                "entry_status": entry.status,
                "signal_id": signal.id,
                "next_action": next_action,
            }

        except Exception as e:
            logger.error(f"Failed to handle reply for entry {entry_id}: {e}")
            await self.session.rollback()
            return {"success": False, "error": str(e)}

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    async def _get_or_create_prospect(
        self,
        email: str,
        company: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        tier: Optional[str] = None,
        icp_score: Optional[float] = None,
        custom_fields: Optional[Dict] = None,
    ) -> Lead:
        """Get existing prospect or create new one."""
        query = select(Lead).where(Lead.contact_email == email)
        result = await self.session.execute(query)
        prospect = result.scalar_one_or_none()

        if prospect:
            # Update with new data if provided
            if company and not prospect.company_name:
                prospect.company_name = company
            if tier:
                prospect.tier = tier
            if icp_score:
                prospect.qualification_score = icp_score
            if custom_fields:
                existing = prospect.additional_data or {}
                existing.update(custom_fields)
                prospect.additional_data = existing
            return prospect

        # Create new prospect
        prospect = Lead(
            contact_email=email,
            company_name=company or "Unknown",
            contact_name=f"{first_name or ''} {last_name or ''}".strip() or None,
            tier=tier,
            qualification_score=icp_score,
            additional_data=custom_fields or {},
        )
        self.session.add(prospect)
        await self.session.flush()
        return prospect

    async def _get_sequence_by_id(self, sequence_id: str) -> Optional[Sequence]:
        """Get sequence by its unique string ID."""
        query = select(Sequence).where(
            Sequence.sequence_id == sequence_id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _get_existing_entry(
        self, prospect_id: int, sequence_id: int
    ) -> Optional[SequenceEntry]:
        """Check for existing sequence enrollment."""
        query = select(SequenceEntry).where(
            and_(
                SequenceEntry.lead_id == prospect_id,
                SequenceEntry.sequence_id == sequence_id,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _send_email(
        self,
        mailbox: Mailbox,
        to_email: str,
        subject: str,
        body: str,
        entry_id: int,
    ) -> Dict[str, Any]:
        """
        Send email via SMTP or log in test mode.

        In production, this would connect to the actual SMTP server.
        In test mode, it logs to the database for review.
        """
        if self._test_mode:
            # TEST MODE: Log to database instead of sending
            message_id = f"TEST_{uuid4().hex[:12]}"
            logger.info(
                f"[TEST MODE] Email logged: to={to_email}, subject={subject[:50]}..."
            )

            # Create a signal entry for the test email
            signal = Signal(
                lead_id=None,  # Will be linked via entry
                signal_type="email_sent_test",
                mailbox_email=mailbox.email,
                subject=subject,
                content=body[:500],  # Truncate for storage
                intent="outbound",
                priority=5,
                processed=True,
                processed_at=datetime.utcnow(),
                received_at=datetime.utcnow(),
            )
            self.session.add(signal)

            return {
                "success": True,
                "message_id": message_id,
                "status": "test_logged",
                "test_mode": True,
            }

        # PRODUCTION MODE: Actual SMTP sending would go here
        # from app.services.sequences.sender import EmailSender
        # sender = EmailSender()
        # return await sender.send_email(mailbox, to_email, subject, body)

        return {
            "success": False,
            "error": "Production mode not yet implemented",
            "test_mode": False,
        }

    def _render_template(
        self, template: str, prospect: Lead
    ) -> str:
        """Render email template with prospect data."""
        replacements = {
            "{{first_name}}": prospect.contact_name.split()[0] if prospect.contact_name else "there",
            "{{last_name}}": prospect.contact_name.split()[-1] if prospect.contact_name and len(prospect.contact_name.split()) > 1 else "",
            "{{company}}": prospect.company_name or "your company",
            "{{email}}": prospect.contact_email,
        }

        # Add custom fields
        if prospect.additional_data:
            for key, value in prospect.additional_data.items():
                replacements[f"{{{{{key}}}}}"] = str(value)

        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)

        return result

    def _get_intent_priority(self, intent: str) -> int:
        """Map intent to priority (1=highest, 5=lowest)."""
        priorities = {
            "interested": 1,
            "question": 2,
            "unsubscribe": 1,  # Legal compliance
            "not_interested": 4,
            "ooo": 5,
        }
        return priorities.get(intent, 3)

    # =========================================================================
    # CONFIGURATION
    # =========================================================================

    def set_test_mode(self, enabled: bool):
        """Enable or disable test mode."""
        self._test_mode = enabled
        logger.info(f"Sequence engine test mode: {'enabled' if enabled else 'disabled'}")

    async def create_sequence(
        self,
        sequence_id: str,
        name: str,
        steps: List[Dict[str, Any]],
        stop_on_reply: bool = True,
        stop_on_bounce: bool = True,
        daily_limit_per_mailbox: int = 50,
    ) -> Sequence:
        """
        Create a new email sequence.

        Args:
            sequence_id: Unique identifier (e.g., 'solar_installer_intro')
            name: Human-readable name
            steps: List of step definitions, each with:
                - step_number: Step index (0, 1, 2, ...)
                - subject: Email subject template
                - body: Email body template
                - delay_days: Days to wait before this step (0 for immediate)
            stop_on_reply: Stop sequence when reply received
            stop_on_bounce: Stop sequence on bounce
            daily_limit_per_mailbox: Max emails per day from one mailbox

        Returns:
            Created Sequence
        """
        sequence = Sequence(
            sequence_id=sequence_id,
            name=name,
            steps=steps,
            stop_on_reply=stop_on_reply,
            stop_on_bounce=stop_on_bounce,
            daily_limit_per_mailbox=daily_limit_per_mailbox,
            is_active=True,
        )
        self.session.add(sequence)
        await self.session.commit()
        await self.session.refresh(sequence)

        logger.info(f"Created sequence '{sequence_id}' with {len(steps)} steps")
        return sequence

    # =========================================================================
    # STATISTICS
    # =========================================================================

    async def get_sequence_stats(self, sequence_id: str) -> Dict[str, Any]:
        """Get statistics for a sequence."""
        sequence = await self._get_sequence_by_id(sequence_id)
        if not sequence:
            return {"error": "Sequence not found"}

        # Count entries by status
        query = select(SequenceEntry).where(
            SequenceEntry.sequence_id == sequence.id
        )
        result = await self.session.execute(query)
        entries = result.scalars().all()

        status_counts = {}
        total_emails = 0
        total_opens = 0
        total_clicks = 0
        reply_count = 0

        for entry in entries:
            status = entry.status
            status_counts[status] = status_counts.get(status, 0) + 1
            total_emails += entry.emails_sent or 0
            total_opens += entry.opens or 0
            total_clicks += entry.clicks or 0
            if entry.reply_received:
                reply_count += 1

        return {
            "sequence_id": sequence_id,
            "name": sequence.name,
            "total_enrolled": len(entries),
            "status_breakdown": status_counts,
            "total_emails_sent": total_emails,
            "total_opens": total_opens,
            "total_clicks": total_clicks,
            "total_replies": reply_count,
            "open_rate": (total_opens / total_emails * 100) if total_emails > 0 else 0,
            "reply_rate": (reply_count / len(entries) * 100) if entries else 0,
        }
