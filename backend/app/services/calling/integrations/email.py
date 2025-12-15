"""
Email Sender for AI Calling System.

Send follow-up emails after calls for:
- Video link when they asked for it
- Meeting confirmation
- Resources/info they requested
- Post-call summary

Uses SendGrid for transactional email.
"""
import logging
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SendGridAPIClient = None
    Mail = None
    SENDGRID_AVAILABLE = False


class EmailTemplate(str, Enum):
    """Pre-built email templates."""
    VIDEO_LINK = "video_link"
    CALENDLY_LINK = "calendly_link"
    MEETING_CONFIRMATION = "meeting_confirmation"
    FOLLOW_UP = "follow_up"
    NOT_INTERESTED = "not_interested"


@dataclass
class EmailMessage:
    """Email message configuration."""
    to_email: str
    to_name: str
    subject: str
    body_html: str
    body_text: Optional[str] = None
    from_email: str = "tim@coperniq.ai"
    from_name: str = "Tim Kipper"
    # Result fields
    message_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


# Email templates (HTML)
EMAIL_TEMPLATES = {
    EmailTemplate.VIDEO_LINK: {
        "subject": "The Coperniq video you asked for",
        "body_html": """
<p>Hey {name},</p>

<p>Great chatting with you! As promised, here's that quick video showing what Coperniq does:</p>

<p><a href="{video_url}" style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 16px 0;">Watch the 2-Minute Video</a></p>

<p>No pressure at all. If it clicks and you want to dig deeper, you can <a href="{calendly_url}">grab 15 minutes on my calendar here</a>.</p>

<p>If not, no worries - you've got my info if anything changes.</p>

<p>- Tim</p>

<p style="color: #666; font-size: 12px; margin-top: 32px;">
Tim Kipper | Coperniq<br>
415-430-9465<br>
<a href="https://coperniq.ai">coperniq.ai</a>
</p>
""",
        "body_text": """Hey {name},

Great chatting with you! As promised, here's that quick video showing what Coperniq does:

{video_url}

No pressure at all. If it clicks and you want to dig deeper, grab 15 minutes on my calendar: {calendly_url}

If not, no worries - you've got my info if anything changes.

- Tim

Tim Kipper | Coperniq
415-430-9465
coperniq.ai
""",
    },

    EmailTemplate.CALENDLY_LINK: {
        "subject": "Let's find 15 minutes - Coperniq demo",
        "body_html": """
<p>Hey {name},</p>

<p>Thanks for your time on the call! Here's my calendar to grab those 15 minutes:</p>

<p><a href="{calendly_url}" style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 16px 0;">Book a Time</a></p>

<p>I'll show you {demo_focus} - nothing else. If it doesn't fit, I'll tell you.</p>

<p>Pick whatever works for you!</p>

<p>- Tim</p>

<p style="color: #666; font-size: 12px; margin-top: 32px;">
Tim Kipper | Coperniq<br>
415-430-9465<br>
<a href="https://coperniq.ai">coperniq.ai</a>
</p>
""",
        "body_text": """Hey {name},

Thanks for your time on the call! Here's my calendar to grab those 15 minutes:

{calendly_url}

I'll show you {demo_focus} - nothing else. If it doesn't fit, I'll tell you.

Pick whatever works for you!

- Tim

Tim Kipper | Coperniq
415-430-9465
coperniq.ai
""",
    },

    EmailTemplate.MEETING_CONFIRMATION: {
        "subject": "Confirmed: Coperniq Demo - {meeting_time}",
        "body_html": """
<p>Hey {name},</p>

<p>We're all set for <strong>{meeting_time}</strong>!</p>

<p>Here's what we'll cover:</p>
<ul>
<li>{demo_focus}</li>
<li>Your specific questions</li>
<li>Next steps if it's a fit</li>
</ul>

<p>You'll get a calendar invite shortly with the meeting link.</p>

<p>See you then!</p>

<p>- Tim</p>

<p style="color: #666; font-size: 12px; margin-top: 32px;">
Tim Kipper | Coperniq<br>
415-430-9465<br>
<a href="https://coperniq.ai">coperniq.ai</a>
</p>
""",
        "body_text": """Hey {name},

We're all set for {meeting_time}!

Here's what we'll cover:
- {demo_focus}
- Your specific questions
- Next steps if it's a fit

You'll get a calendar invite shortly with the meeting link.

See you then!

- Tim

Tim Kipper | Coperniq
415-430-9465
coperniq.ai
""",
    },

    EmailTemplate.FOLLOW_UP: {
        "subject": "Following up - {company_name}",
        "body_html": """
<p>Hey {name},</p>

<p>Good chatting earlier! Here are the resources I mentioned:</p>

<ul>
{resources_list}
</ul>

<p>If you want to dig deeper, <a href="{calendly_url}">here's my calendar</a> for a quick 15-minute walkthrough.</p>

<p>No pressure - just wanted to make sure you had everything.</p>

<p>- Tim</p>

<p style="color: #666; font-size: 12px; margin-top: 32px;">
Tim Kipper | Coperniq<br>
415-430-9465<br>
<a href="https://coperniq.ai">coperniq.ai</a>
</p>
""",
        "body_text": """Hey {name},

Good chatting earlier! Here are the resources I mentioned:

{resources_text}

If you want to dig deeper, here's my calendar for a quick 15-minute walkthrough: {calendly_url}

No pressure - just wanted to make sure you had everything.

- Tim

Tim Kipper | Coperniq
415-430-9465
coperniq.ai
""",
    },

    EmailTemplate.NOT_INTERESTED: {
        "subject": "Thanks for your time",
        "body_html": """
<p>Hey {name},</p>

<p>Thanks for taking my call earlier - I appreciate your time even if it's not a fit right now.</p>

<p>If your stack ever starts breaking or you want a second opinion, you've got my info.</p>

<p>Best of luck!</p>

<p>- Tim</p>

<p style="color: #666; font-size: 12px; margin-top: 32px;">
Tim Kipper | Coperniq<br>
415-430-9465<br>
<a href="https://coperniq.ai">coperniq.ai</a>
</p>
""",
        "body_text": """Hey {name},

Thanks for taking my call earlier - I appreciate your time even if it's not a fit right now.

If your stack ever starts breaking or you want a second opinion, you've got my info.

Best of luck!

- Tim

Tim Kipper | Coperniq
415-430-9465
coperniq.ai
""",
    },
}


class EmailSender:
    """
    Send follow-up emails via SendGrid.

    Usage:
        sender = EmailSender(api_key="your_sendgrid_key")

        # Send video link email
        result = await sender.send_video_link(
            to_email="lead@company.com",
            to_name="John Smith"
        )

        # Send meeting confirmation
        result = await sender.send_meeting_confirmation(
            to_email="lead@company.com",
            to_name="John",
            meeting_time="Tuesday at 2pm",
            demo_focus="how we handle dispatch for multi-trade shops"
        )
    """

    DEFAULT_VIDEO_URL = "https://www.loom.com/share/coperniq-demo"
    DEFAULT_CALENDLY_URL = "https://calendly.com/coperniq-sales/disco"

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: str = "tim@coperniq.ai",
        from_name: str = "Tim Kipper",
    ):
        self.api_key = api_key or os.getenv("SENDGRID_API_KEY")
        self.from_email = from_email
        self.from_name = from_name

        self.available = SENDGRID_AVAILABLE and self.api_key

        if self.available:
            self.client = SendGridAPIClient(self.api_key)
            logger.info("EmailSender initialized with SendGrid")
        else:
            self.client = None
            if not SENDGRID_AVAILABLE:
                logger.warning("SendGrid SDK not installed: pip install sendgrid")
            else:
                logger.warning("SENDGRID_API_KEY not configured")

    async def send(self, message: EmailMessage) -> EmailMessage:
        """
        Send an email message.

        Args:
            message: EmailMessage configuration

        Returns:
            EmailMessage with status populated
        """
        if not self.available:
            message.error = "SendGrid not available"
            message.status = "failed"
            logger.error("Cannot send email: SendGrid not configured")
            return message

        try:
            mail = Mail(
                from_email=Email(message.from_email, message.from_name),
                to_emails=To(message.to_email, message.to_name),
                subject=message.subject,
                html_content=Content("text/html", message.body_html),
            )

            if message.body_text:
                mail.add_content(Content("text/plain", message.body_text))

            response = self.client.send(mail)

            message.status = "sent" if response.status_code in [200, 202] else "failed"
            message.message_id = response.headers.get("X-Message-Id")
            logger.info(f"Email sent to {message.to_email}: {message.message_id}")

        except Exception as e:
            message.error = str(e)
            message.status = "failed"
            logger.error(f"Failed to send email to {message.to_email}: {e}")

        return message

    async def send_video_link(
        self,
        to_email: str,
        to_name: str,
        video_url: Optional[str] = None,
        calendly_url: Optional[str] = None,
    ) -> EmailMessage:
        """Send video link email."""
        template = EMAIL_TEMPLATES[EmailTemplate.VIDEO_LINK]

        message = EmailMessage(
            to_email=to_email,
            to_name=to_name,
            subject=template["subject"],
            body_html=template["body_html"].format(
                name=to_name.split()[0] if to_name else "there",
                video_url=video_url or self.DEFAULT_VIDEO_URL,
                calendly_url=calendly_url or self.DEFAULT_CALENDLY_URL,
            ),
            body_text=template["body_text"].format(
                name=to_name.split()[0] if to_name else "there",
                video_url=video_url or self.DEFAULT_VIDEO_URL,
                calendly_url=calendly_url or self.DEFAULT_CALENDLY_URL,
            ),
            from_email=self.from_email,
            from_name=self.from_name,
        )

        return await self.send(message)

    async def send_calendly_link(
        self,
        to_email: str,
        to_name: str,
        demo_focus: str = "how Coperniq can help your shop",
        calendly_url: Optional[str] = None,
    ) -> EmailMessage:
        """Send Calendly booking link email."""
        template = EMAIL_TEMPLATES[EmailTemplate.CALENDLY_LINK]

        # Pre-fill Calendly link
        url = calendly_url or self.DEFAULT_CALENDLY_URL
        url += f"?email={to_email}&name={to_name.replace(' ', '%20')}"

        message = EmailMessage(
            to_email=to_email,
            to_name=to_name,
            subject=template["subject"],
            body_html=template["body_html"].format(
                name=to_name.split()[0] if to_name else "there",
                calendly_url=url,
                demo_focus=demo_focus,
            ),
            body_text=template["body_text"].format(
                name=to_name.split()[0] if to_name else "there",
                calendly_url=url,
                demo_focus=demo_focus,
            ),
            from_email=self.from_email,
            from_name=self.from_name,
        )

        return await self.send(message)

    async def send_meeting_confirmation(
        self,
        to_email: str,
        to_name: str,
        meeting_time: str,
        demo_focus: str = "how Coperniq fits your workflow",
    ) -> EmailMessage:
        """Send meeting confirmation email."""
        template = EMAIL_TEMPLATES[EmailTemplate.MEETING_CONFIRMATION]

        message = EmailMessage(
            to_email=to_email,
            to_name=to_name,
            subject=template["subject"].format(meeting_time=meeting_time),
            body_html=template["body_html"].format(
                name=to_name.split()[0] if to_name else "there",
                meeting_time=meeting_time,
                demo_focus=demo_focus,
            ),
            body_text=template["body_text"].format(
                name=to_name.split()[0] if to_name else "there",
                meeting_time=meeting_time,
                demo_focus=demo_focus,
            ),
            from_email=self.from_email,
            from_name=self.from_name,
        )

        return await self.send(message)

    async def send_follow_up(
        self,
        to_email: str,
        to_name: str,
        company_name: str,
        resources: List[Dict[str, str]],
        calendly_url: Optional[str] = None,
    ) -> EmailMessage:
        """
        Send follow-up email with resources.

        Args:
            to_email: Recipient email
            to_name: Recipient name
            company_name: Lead's company name
            resources: List of {"title": "...", "url": "..."}
            calendly_url: Optional Calendly link
        """
        template = EMAIL_TEMPLATES[EmailTemplate.FOLLOW_UP]

        # Build resources list
        resources_html = "\n".join([
            f'<li><a href="{r["url"]}">{r["title"]}</a></li>'
            for r in resources
        ])
        resources_text = "\n".join([
            f'- {r["title"]}: {r["url"]}'
            for r in resources
        ])

        message = EmailMessage(
            to_email=to_email,
            to_name=to_name,
            subject=template["subject"].format(company_name=company_name),
            body_html=template["body_html"].format(
                name=to_name.split()[0] if to_name else "there",
                resources_list=resources_html,
                calendly_url=calendly_url or self.DEFAULT_CALENDLY_URL,
            ),
            body_text=template["body_text"].format(
                name=to_name.split()[0] if to_name else "there",
                resources_text=resources_text,
                calendly_url=calendly_url or self.DEFAULT_CALENDLY_URL,
            ),
            from_email=self.from_email,
            from_name=self.from_name,
        )

        return await self.send(message)

    async def send_not_interested(
        self,
        to_email: str,
        to_name: str,
    ) -> EmailMessage:
        """Send graceful exit email when they're not interested."""
        template = EMAIL_TEMPLATES[EmailTemplate.NOT_INTERESTED]

        message = EmailMessage(
            to_email=to_email,
            to_name=to_name,
            subject=template["subject"],
            body_html=template["body_html"].format(
                name=to_name.split()[0] if to_name else "there",
            ),
            body_text=template["body_text"].format(
                name=to_name.split()[0] if to_name else "there",
            ),
            from_email=self.from_email,
            from_name=self.from_name,
        )

        return await self.send(message)


# Quick helpers
async def send_video_email(to_email: str, to_name: str) -> EmailMessage:
    """Quick helper to send video link email."""
    sender = EmailSender()
    return await sender.send_video_link(to_email, to_name)


async def send_calendly_email(to_email: str, to_name: str) -> EmailMessage:
    """Quick helper to send Calendly link email."""
    sender = EmailSender()
    return await sender.send_calendly_link(to_email, to_name)
