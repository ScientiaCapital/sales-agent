"""
Email Sender - SMTP handling with test mode support.

Provides:
- Test mode: Log emails to database (no actual sending)
- Production mode: Send via SMTP with threading support
- Reply simulation for testing
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mailbox import Mailbox
from app.models.signal import Signal

logger = logging.getLogger(__name__)


class EmailLog:
    """Email log entry for test mode."""

    def __init__(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: str,
        status: str = "logged",
        message_id: Optional[str] = None,
    ):
        self.to = to
        self.subject = subject
        self.body = body
        self.from_email = from_email
        self.status = status
        self.message_id = message_id or f"TEST_{uuid4().hex[:12]}"
        self.timestamp = datetime.utcnow()


class EmailSender:
    """
    Handles email sending with test mode support.

    In TEST MODE:
    - Logs all emails to database
    - No actual SMTP connections
    - Provides simulate_reply() for testing reply flows

    In PRODUCTION MODE:
    - Connects to SMTP server
    - Sends actual emails
    - Supports threading (In-Reply-To headers)
    """

    def __init__(self, session: AsyncSession, test_mode: bool = True):
        """
        Initialize sender.

        Args:
            session: Database session for logging
            test_mode: If True, log emails instead of sending
        """
        self.session = session
        self.test_mode = test_mode
        self._email_logs: list[EmailLog] = []

    async def send_email(
        self,
        mailbox: Mailbox,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        entry_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send an email or log it in test mode.

        Args:
            mailbox: Mailbox to send from
            to_email: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            in_reply_to: Message-ID for threading
            entry_id: Sequence entry ID for tracking

        Returns:
            Dict with status and message_id
        """
        if self.test_mode:
            return await self._log_test_email(
                mailbox, to_email, subject, body, entry_id
            )
        else:
            return await self._send_smtp_email(
                mailbox, to_email, subject, body, html_body, in_reply_to
            )

    async def _log_test_email(
        self,
        mailbox: Mailbox,
        to_email: str,
        subject: str,
        body: str,
        entry_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Log email to database in test mode."""
        message_id = f"TEST_{uuid4().hex[:12]}@{mailbox.email.split('@')[1]}"

        log_entry = EmailLog(
            to=to_email,
            subject=subject,
            body=body,
            from_email=mailbox.email,
            status="test_logged",
            message_id=message_id,
        )
        self._email_logs.append(log_entry)

        # Create signal record for tracking
        signal = Signal(
            lead_id=None,
            signal_type="email_sent_test",
            mailbox_email=mailbox.email,
            subject=subject,
            content=f"TO: {to_email}\n\n{body[:1000]}",
            intent="outbound",
            priority=5,
            processed=True,
            processed_at=datetime.utcnow(),
            received_at=datetime.utcnow(),
            message_id=message_id,
        )
        self.session.add(signal)
        await self.session.flush()

        logger.info(
            f"[TEST MODE] Email logged: "
            f"from={mailbox.email}, to={to_email}, "
            f"subject='{subject[:40]}...', message_id={message_id}"
        )

        return {
            "success": True,
            "message_id": message_id,
            "status": "test_logged",
            "test_mode": True,
        }

    async def _send_smtp_email(
        self,
        mailbox: Mailbox,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        in_reply_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send email via SMTP (production mode)."""
        try:
            # Build message
            if html_body:
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(body, "plain"))
                msg.attach(MIMEText(html_body, "html"))
            else:
                msg = MIMEText(body, "plain")

            # Generate message ID
            domain = mailbox.email.split("@")[1]
            message_id = f"<{uuid4().hex}@{domain}>"

            msg["From"] = mailbox.email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg["Message-ID"] = message_id

            # Threading support
            if in_reply_to:
                msg["In-Reply-To"] = in_reply_to
                msg["References"] = in_reply_to

            # Decrypt password for SMTP authentication
            try:
                password = mailbox.get_password()
            except ValueError as e:
                logger.error(f"Failed to decrypt password for {mailbox.email}: {e}")
                return {
                    "success": False,
                    "error": "Password decryption failed. Ensure MAILBOX_ENCRYPTION_KEY is set.",
                    "test_mode": False,
                }

            # Send via SMTP
            with smtplib.SMTP(mailbox.smtp_host, mailbox.smtp_port) as server:
                server.starttls()
                server.login(mailbox.email, password)
                server.send_message(msg)

            # Update mailbox stats
            mailbox.total_sent += 1

            logger.info(
                f"Email sent: from={mailbox.email}, to={to_email}, "
                f"subject='{subject[:40]}...', message_id={message_id}"
            )

            return {
                "success": True,
                "message_id": message_id,
                "status": "sent",
                "test_mode": False,
            }

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP auth failed for {mailbox.email}: {e}")
            return {
                "success": False,
                "error": "Authentication failed",
                "test_mode": False,
            }
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return {
                "success": False,
                "error": str(e),
                "test_mode": False,
            }
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "test_mode": False,
            }

    async def simulate_reply(
        self,
        entry_id: int,
        intent: str,
        reply_content: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Simulate a reply for testing.

        This triggers the reply handling flow as if a real email was received.

        Args:
            entry_id: Sequence entry to simulate reply for
            intent: Reply intent ('interested', 'not_interested', 'question', 'unsubscribe', 'ooo')
            reply_content: Optional reply text
            from_email: Email address to simulate reply from

        Returns:
            Dict with simulation result
        """
        from app.services.sequences.engine import SequenceEngine

        # Default reply content based on intent
        default_content = {
            "interested": "Yes, I'd love to learn more about your solution. When can we schedule a call?",
            "not_interested": "Thanks, but we're not interested at this time.",
            "question": "Can you tell me more about pricing?",
            "unsubscribe": "Please remove me from your mailing list.",
            "ooo": "I'm out of the office until next week. I'll respond when I return.",
        }

        content = reply_content or default_content.get(intent, "Reply content")

        logger.info(
            f"[TEST MODE] Simulating reply: entry_id={entry_id}, "
            f"intent={intent}"
        )

        # Create signal for the simulated reply
        signal = Signal(
            lead_id=None,
            signal_type="email_reply_simulated",
            mailbox_email=from_email,
            content=content,
            intent=intent,
            priority=1 if intent == "interested" else 3,
            received_at=datetime.utcnow(),
        )
        self.session.add(signal)
        await self.session.flush()

        # Trigger reply handling via engine
        engine = SequenceEngine(self.session)
        result = await engine.handle_reply(
            entry_id=entry_id,
            intent=intent,
            reply_content=content,
            from_email=from_email,
        )

        return {
            "success": True,
            "simulated": True,
            "intent": intent,
            "signal_id": signal.id,
            "engine_result": result,
        }

    def get_test_logs(self) -> list[Dict[str, Any]]:
        """Get all test email logs (test mode only)."""
        return [
            {
                "to": log.to,
                "from": log.from_email,
                "subject": log.subject,
                "body": log.body[:200] + "..." if len(log.body) > 200 else log.body,
                "message_id": log.message_id,
                "status": log.status,
                "timestamp": log.timestamp.isoformat(),
            }
            for log in self._email_logs
        ]

    def clear_test_logs(self):
        """Clear test email logs."""
        self._email_logs = []
        logger.info("Test email logs cleared")


class ReplyClassifier:
    """
    Classify reply intent using keyword matching.

    For MVP, uses keyword-based classification.
    TODO: Upgrade to LLM-based classification (use Claude, NOT OpenAI)
    """

    # Keywords for each intent category
    INTENT_KEYWORDS = {
        "interested": [
            "interested",
            "tell me more",
            "schedule",
            "call",
            "meeting",
            "demo",
            "learn more",
            "sounds good",
            "yes",
            "let's talk",
            "available",
            "when can we",
            "send me",
            "information",
        ],
        "not_interested": [
            "not interested",
            "no thanks",
            "no thank you",
            "not a good fit",
            "don't contact",
            "stop",
            "remove",
            "not for us",
            "pass",
            "decline",
        ],
        "unsubscribe": [
            "unsubscribe",
            "remove me",
            "opt out",
            "stop emailing",
            "take me off",
            "mailing list",
        ],
        "ooo": [
            "out of office",
            "ooo",
            "vacation",
            "away",
            "returning",
            "back on",
            "limited access",
            "auto-reply",
        ],
        "question": [
            "how much",
            "pricing",
            "cost",
            "what is",
            "can you explain",
            "tell me about",
            "?",  # Questions often have question marks
        ],
    }

    def classify(self, subject: str, body: str) -> str:
        """
        Classify reply intent from subject and body.

        Args:
            subject: Email subject line
            body: Email body text

        Returns:
            Intent string: 'interested', 'not_interested', 'unsubscribe', 'ooo', 'question', 'unknown'
        """
        text = f"{subject} {body}".lower()

        # Check each intent category
        intent_scores = {}
        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                intent_scores[intent] = score

        if not intent_scores:
            return "unknown"

        # Return highest scoring intent
        # Priority order for ties: unsubscribe > not_interested > interested > ooo > question
        priority_order = ["unsubscribe", "not_interested", "interested", "ooo", "question"]

        max_score = max(intent_scores.values())
        top_intents = [i for i, s in intent_scores.items() if s == max_score]

        for intent in priority_order:
            if intent in top_intents:
                return intent

        return top_intents[0] if top_intents else "unknown"
