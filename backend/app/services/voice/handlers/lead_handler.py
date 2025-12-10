"""Lead Qualification Handler for voice calls.

Asks qualifying questions about company, role, needs, budget, and timeline.
Scores leads based on responses and recommends transfer for high-quality leads.
"""

import logging
import re
from typing import Dict, List, Optional

from .base import BaseHandler, HandlerResponse
from app.services.voice.intent_classifier import SalesIntent

logger = logging.getLogger(__name__)


# Qualification questions in priority order
QUALIFICATION_QUESTIONS = [
    {
        "key": "company",
        "question": "May I ask what company you're with?",
        "follow_up": "And what does your company do?"
    },
    {
        "key": "role",
        "question": "What's your role at the company?",
        "follow_up": "Are you involved in the decision-making process for tools like ours?"
    },
    {
        "key": "pain_points",
        "question": "What challenges are you hoping to solve?",
        "follow_up": "How is that impacting your business right now?"
    },
    {
        "key": "timeline",
        "question": "What's your timeline for making a decision?",
        "follow_up": "Is there a specific deadline driving this?"
    },
    {
        "key": "budget",
        "question": "Have you set aside a budget for this type of solution?",
        "follow_up": "Do you have a range in mind?"
    },
]


class LeadQualificationHandler(BaseHandler):
    """Handler for LEAD_QUALIFICATION intent.

    Qualifies leads through conversational questions and scores them
    based on company size, decision authority, budget, and timeline.

    Example:
        >>> handler = LeadQualificationHandler()
        >>> response = handler.handle(
        ...     transcript="Hi, I'm interested in your product",
        ...     conversation_history=[],
        ...     lead_context=None
        ... )
        >>> print(response.response_text)
        Thanks for your interest! May I ask what company you're with?
    """

    def __init__(self, cerebras_service=None):
        """Initialize lead qualification handler.

        Args:
            cerebras_service: Optional CerebrasService for enhanced responses
        """
        super().__init__(cerebras_service)
        logger.info("LeadQualificationHandler initialized")

    def handle(
        self,
        transcript: str,
        conversation_history: List[Dict],
        lead_context: Optional[Dict] = None
    ) -> HandlerResponse:
        """Process transcript and ask qualifying questions.

        Args:
            transcript: Current user speech transcript
            conversation_history: List of conversation turns
            lead_context: Optional lead data from CRM

        Returns:
            HandlerResponse with next question or qualification summary
        """
        logger.info(f"Processing lead qualification: '{transcript}'")

        # Extract qualification data from conversation
        qualification_data = self._extract_qualification_data(
            transcript, conversation_history, lead_context
        )

        # Determine what we still need to know
        missing_info = self._get_missing_info(qualification_data)

        if not missing_info:
            # All info gathered - calculate score and potentially transfer
            lead_score = self.calculate_lead_score(qualification_data)
            should_transfer = lead_score >= 7

            if should_transfer:
                response_text = (
                    f"This sounds like a great fit! "
                    f"Let me connect you with someone who can discuss next steps."
                )
            else:
                response_text = (
                    f"Thank you for sharing that information. "
                    f"Based on what you've told me, I think we could be a good match. "
                    f"Would you like to schedule a demo to learn more?"
                )

            return HandlerResponse(
                response_text=response_text,
                next_intent=SalesIntent.MEETING_SCHEDULE if not should_transfer else SalesIntent.WARM_TRANSFER,
                should_transfer=should_transfer,
                data=qualification_data,
                metadata={"lead_score": lead_score}
            )

        # Ask the next qualifying question
        next_question = missing_info[0]
        response_text = self._generate_question_response(
            next_question, transcript, qualification_data
        )

        return HandlerResponse(
            response_text=response_text,
            next_intent=SalesIntent.LEAD_QUALIFICATION,
            should_transfer=False,
            data=qualification_data,
            metadata={"questions_asked": len(QUALIFICATION_QUESTIONS) - len(missing_info)}
        )

    def _extract_qualification_data(
        self,
        transcript: str,
        conversation_history: List[Dict],
        lead_context: Optional[Dict]
    ) -> Dict:
        """Extract qualification data from conversation.

        Args:
            transcript: Current transcript
            conversation_history: Previous turns
            lead_context: CRM lead data

        Returns:
            Dict with extracted qualification data
        """
        data = {}

        # Start with lead context if available
        if lead_context:
            data["company"] = lead_context.get("company")
            data["contact_name"] = lead_context.get("contact_name")
            data["email"] = lead_context.get("email")

        # Combine all text for analysis
        all_text = transcript
        for turn in conversation_history:
            if turn.get("role") == "user":
                all_text += " " + turn.get("content", "")

        all_text_lower = all_text.lower()

        # Extract company name
        if not data.get("company"):
            company = self._extract_company(all_text)
            if company:
                data["company"] = company

        # Extract role
        role = self._extract_role(all_text_lower)
        if role:
            data["role"] = role

        # Check for decision-maker indicators
        if any(word in all_text_lower for word in [
            "ceo", "cto", "cfo", "vp", "director", "head of", "owner",
            "decision", "decide", "approve", "budget authority"
        ]):
            data["is_decision_maker"] = True
        elif any(word in all_text_lower for word in [
            "manager", "lead", "senior", "principal"
        ]):
            data["is_decision_maker"] = "maybe"

        # Extract timeline
        timeline = self._extract_timeline(all_text_lower)
        if timeline:
            data["timeline"] = timeline

        # Extract budget indicators
        budget = self._extract_budget(all_text_lower)
        if budget:
            data["budget"] = budget

        # Extract pain points
        pain_points = self._extract_pain_points(all_text_lower)
        if pain_points:
            data["pain_points"] = pain_points

        # Extract company size
        size = self._extract_company_size(all_text_lower)
        if size:
            data["company_size"] = size

        return data

    def _extract_company(self, text: str) -> Optional[str]:
        """Extract company name from text."""
        # Look for patterns like "I'm with X" or "from X" or "at X"
        patterns = [
            r"(?:i'm with|from|at|work for|working for|company is)\s+([A-Z][A-Za-z0-9\s&]+?)(?:\.|,|$|\s+and)",
            r"([A-Z][A-Za-z0-9\s&]+?)(?:\s+here|is\s+my\s+company)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                if len(company) > 2 and len(company) < 50:
                    return company

        return None

    def _extract_role(self, text: str) -> Optional[str]:
        """Extract job role/title from text."""
        role_patterns = [
            r"(?:i'm|i am)\s+(?:a|the|an)?\s*([a-z\s]+?)(?:\s+at|\s+for|\s+here|$|,)",
            r"(?:my role|my title|position)\s+(?:is|as)\s+(?:a|the|an)?\s*([a-z\s]+)",
        ]

        roles_keywords = [
            "ceo", "cto", "cfo", "coo", "vp", "director", "manager",
            "engineer", "developer", "analyst", "consultant", "founder",
            "owner", "president", "head", "lead", "chief", "executive"
        ]

        for pattern in role_patterns:
            match = re.search(pattern, text)
            if match:
                role = match.group(1).strip()
                if any(keyword in role for keyword in roles_keywords):
                    return role.title()

        # Check for standalone role mentions
        for keyword in roles_keywords:
            if keyword in text:
                return keyword.title()

        return None

    def _extract_timeline(self, text: str) -> Optional[str]:
        """Extract purchase timeline from text."""
        if any(word in text for word in ["asap", "immediately", "urgent", "right now", "this week"]):
            return "immediate"
        elif any(word in text for word in ["this month", "next month", "few weeks"]):
            return "1_month"
        elif any(word in text for word in ["quarter", "3 months", "90 days"]):
            return "3_months"
        elif any(word in text for word in ["6 months", "half year", "next year"]):
            return "6_months"
        elif any(word in text for word in ["just looking", "exploring", "researching", "not sure"]):
            return "exploring"
        return None

    def _extract_budget(self, text: str) -> Optional[str]:
        """Extract budget information from text."""
        if any(word in text for word in ["budget approved", "have budget", "budget set", "allocated"]):
            return "confirmed"
        elif any(word in text for word in ["exploring budget", "need approval", "checking budget"]):
            return "exploring"
        elif any(word in text for word in ["no budget", "tight budget", "limited"]):
            return "limited"

        # Look for dollar amounts
        dollar_match = re.search(r'\$\s*[\d,]+(?:k|K|m|M)?', text)
        if dollar_match:
            return f"mentioned: {dollar_match.group()}"

        return None

    def _extract_pain_points(self, text: str) -> Optional[List[str]]:
        """Extract pain points from text."""
        pain_keywords = {
            "efficiency": ["slow", "inefficient", "manual", "time-consuming"],
            "cost": ["expensive", "costs too much", "over budget", "spending"],
            "integration": ["doesn't integrate", "fragmented", "siloed"],
            "scalability": ["can't scale", "growing", "outgrown"],
            "support": ["poor support", "no help", "frustrated"]
        }

        found_pains = []
        for category, keywords in pain_keywords.items():
            if any(word in text for word in keywords):
                found_pains.append(category)

        return found_pains if found_pains else None

    def _extract_company_size(self, text: str) -> Optional[str]:
        """Extract company size from text."""
        # Look for employee count patterns
        size_match = re.search(r'(\d+)\s*(?:employees?|people|team members?)', text)
        if size_match:
            count = int(size_match.group(1))
            if count <= 10:
                return "1-10"
            elif count <= 50:
                return "11-50"
            elif count <= 100:
                return "51-100"
            elif count <= 500:
                return "101-500"
            else:
                return "500+"

        # Keyword-based size
        if any(word in text for word in ["startup", "small team", "just us"]):
            return "1-10"
        elif any(word in text for word in ["mid-size", "medium", "growing"]):
            return "51-100"
        elif any(word in text for word in ["enterprise", "large", "fortune"]):
            return "500+"

        return None

    def _get_missing_info(self, qualification_data: Dict) -> List[Dict]:
        """Get list of questions for missing info.

        Args:
            qualification_data: Currently gathered data

        Returns:
            List of question dicts for missing info
        """
        missing = []

        if not qualification_data.get("company"):
            missing.append(QUALIFICATION_QUESTIONS[0])

        if not qualification_data.get("role"):
            missing.append(QUALIFICATION_QUESTIONS[1])

        if not qualification_data.get("pain_points"):
            missing.append(QUALIFICATION_QUESTIONS[2])

        if not qualification_data.get("timeline"):
            missing.append(QUALIFICATION_QUESTIONS[3])

        # Only ask budget if we have most other info (sensitive topic)
        if len(missing) <= 1 and not qualification_data.get("budget"):
            missing.append(QUALIFICATION_QUESTIONS[4])

        return missing

    def _generate_question_response(
        self,
        question_info: Dict,
        transcript: str,
        qualification_data: Dict
    ) -> str:
        """Generate a natural response with the next question.

        Args:
            question_info: Dict with question key and text
            transcript: Current transcript for context
            qualification_data: Already gathered data

        Returns:
            TTS-friendly response text
        """
        question = question_info["question"]

        # Add acknowledgment if this isn't the first interaction
        if qualification_data:
            acknowledgments = [
                "Thanks for sharing that.",
                "Great, thank you.",
                "I appreciate that.",
                "Perfect.",
            ]
            import random
            return f"{random.choice(acknowledgments)} {question}"

        # First interaction
        return f"Thanks for your interest! {question}"

    def calculate_lead_score(self, qualification_data: Dict) -> int:
        """Calculate lead score (0-10) based on qualification data.

        Scoring criteria:
        - Company size: 1-10 employees = 1pt, 11-100 = 2pts, 100-500 = 3pts, 500+ = 3pts
        - Decision maker: Yes = 2pts, Maybe = 1pt, No = 0pts
        - Budget: Confirmed = 2pts, Exploring = 1pt, Limited = 0pts
        - Timeline: Immediate = 3pts, 1-3 months = 2pts, 6+ months = 1pt

        Args:
            qualification_data: Gathered qualification data

        Returns:
            Score from 0-10
        """
        score = 0

        # Company size scoring
        size = qualification_data.get("company_size", "")
        if "500+" in size:
            score += 3
        elif "101-500" in size:
            score += 3
        elif "51-100" in size:
            score += 2
        elif "11-50" in size:
            score += 1
        elif size:
            score += 1

        # Decision maker scoring
        is_dm = qualification_data.get("is_decision_maker")
        if is_dm is True:
            score += 2
        elif is_dm == "maybe":
            score += 1

        # Budget scoring
        budget = qualification_data.get("budget", "")
        if "confirmed" in budget:
            score += 2
        elif "exploring" in budget or "mentioned" in budget:
            score += 1

        # Timeline scoring
        timeline = qualification_data.get("timeline", "")
        if timeline == "immediate":
            score += 3
        elif timeline in ["1_month", "3_months"]:
            score += 2
        elif timeline == "6_months":
            score += 1

        logger.info(f"Lead score calculated: {score}/10")
        return min(score, 10)
