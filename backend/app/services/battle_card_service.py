"""
Battle Card service for real-time conversation intelligence

Manages battle card templates and triggers them based on conversation context.
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.conversation_models import (
    BattleCardTemplate,
    ConversationBattleCard,
    BattleCardType,
)

logger = logging.getLogger(__name__)


class BattleCardService:
    """
    Service for managing and triggering battle cards during sales conversations.

    Battle cards provide quick-reference information for handling common situations
    like pricing questions, competitor comparisons, objections, etc.
    """

    def __init__(self, db: Session):
        """
        Initialize battle card service.

        Args:
            db: Database session
        """
        self.db = db

    def get_templates(
        self,
        card_type: Optional[str] = None,
        is_active: bool = True,
    ) -> List[BattleCardTemplate]:
        """
        Get battle card templates.

        Args:
            card_type: Optional filter by card type
            is_active: Filter by active status

        Returns:
            List of battle card templates
        """
        query = self.db.query(BattleCardTemplate).filter(
            BattleCardTemplate.is_active == is_active
        )

        if card_type:
            query = query.filter(BattleCardTemplate.card_type == card_type)

        templates = query.order_by(BattleCardTemplate.priority.desc()).all()

        return templates

    def find_matching_templates(
        self,
        text: str,
        detected_topics: List[str],
        trigger_keywords: List[str],
    ) -> List[BattleCardTemplate]:
        """
        Find battle card templates matching the conversation context.

        Args:
            text: Current conversation text
            detected_topics: Topics detected in conversation
            trigger_keywords: Keywords that should trigger cards

        Returns:
            List of matching battle card templates ordered by relevance
        """
        text_lower = text.lower()
        matching_templates = []

        # Get all active templates
        templates = self.get_templates(is_active=True)

        for template in templates:
            match_score = 0

            # Check trigger keywords
            template_keywords = template.trigger_keywords or []
            for keyword in template_keywords:
                if keyword.lower() in text_lower:
                    match_score += 3  # High weight for keyword match

                if keyword in trigger_keywords:
                    match_score += 2  # Match from suggestion engine

            # Check trigger phrases
            template_phrases = template.trigger_phrases or []
            for phrase in template_phrases:
                if phrase.lower() in text_lower:
                    match_score += 4  # Higher weight for phrase match

            # Check topics
            template_topics = template.trigger_topics or []
            for topic in template_topics:
                if topic in detected_topics:
                    match_score += 1

            if match_score > 0:
                matching_templates.append((template, match_score))

        # Sort by match score and priority
        matching_templates.sort(
            key=lambda x: (x[1], x[0].priority),
            reverse=True
        )

        # Return top 3 matches
        return [template for template, score in matching_templates[:3]]

    def create_conversation_battle_card(
        self,
        conversation_id: str,
        template: BattleCardTemplate,
        trigger_keyword: Optional[str] = None,
        trigger_turn_id: Optional[str] = None,
        relevance_score: Optional[float] = None,
    ) -> ConversationBattleCard:
        """
        Create a battle card instance for a specific conversation.

        Args:
            conversation_id: Conversation ID
            template: Battle card template
            trigger_keyword: Keyword that triggered the card
            trigger_turn_id: Turn ID that triggered the card
            relevance_score: Relevance score (0.0 to 1.0)

        Returns:
            Created ConversationBattleCard instance
        """
        battle_card = ConversationBattleCard(
            conversation_id=conversation_id,
            card_type=template.card_type,
            trigger_keyword=trigger_keyword,
            trigger_turn_id=trigger_turn_id,
            title=template.title,
            content=template.content,
            talking_points=template.talking_points,
            response_template=template.response_template,
            relevance_score=relevance_score,
        )

        self.db.add(battle_card)
        self.db.flush()

        # Update template usage stats
        template.times_triggered += 1
        self.db.commit()

        logger.info(f"Created battle card '{template.name}' for conversation {conversation_id}")

        return battle_card

    def mark_battle_card_viewed(self, battle_card_id: str):
        """Mark a battle card as viewed by the agent."""
        from datetime import datetime

        battle_card = self.db.query(ConversationBattleCard).filter(
            ConversationBattleCard.id == battle_card_id
        ).first()

        if battle_card and not battle_card.viewed_at:
            battle_card.viewed_at = datetime.utcnow()

            # Calculate time to view
            time_diff = (battle_card.viewed_at - battle_card.suggested_at).total_seconds()
            battle_card.time_to_view_seconds = int(time_diff)

            self.db.commit()

            logger.info(f"Battle card {battle_card_id} viewed after {time_diff:.1f}s")

    def mark_battle_card_used(self, battle_card_id: str, was_helpful: bool = True):
        """Mark a battle card as used by the agent."""
        from datetime import datetime

        battle_card = self.db.query(ConversationBattleCard).filter(
            ConversationBattleCard.id == battle_card_id
        ).first()

        if battle_card and not battle_card.used_at:
            battle_card.used_at = datetime.utcnow()
            battle_card.was_helpful = was_helpful

            # Calculate time to use
            time_diff = (battle_card.used_at - battle_card.suggested_at).total_seconds()
            battle_card.time_to_use_seconds = int(time_diff)

            self.db.commit()

            # Update template usage stats
            template = self.db.query(BattleCardTemplate).filter(
                and_(
                    BattleCardTemplate.card_type == battle_card.card_type,
                    BattleCardTemplate.title == battle_card.title
                )
            ).first()

            if template:
                template.times_used += 1

                # Update usage rate
                if template.times_triggered > 0:
                    template.usage_rate = template.times_used / template.times_triggered

                self.db.commit()

            logger.info(f"Battle card {battle_card_id} used after {time_diff:.1f}s (helpful: {was_helpful})")

    def get_conversation_battle_cards(
        self,
        conversation_id: str,
    ) -> List[ConversationBattleCard]:
        """
        Get all battle cards for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            List of battle cards
        """
        battle_cards = self.db.query(ConversationBattleCard).filter(
            ConversationBattleCard.conversation_id == conversation_id
        ).order_by(ConversationBattleCard.suggested_at.desc()).all()

        return battle_cards

    def get_battle_card_stats(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get battle card usage statistics for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Dictionary with usage statistics
        """
        battle_cards = self.get_conversation_battle_cards(conversation_id)

        if not battle_cards:
            return {
                "total_shown": 0,
                "total_viewed": 0,
                "total_used": 0,
                "view_rate": 0.0,
                "usage_rate": 0.0,
            }

        total_shown = len(battle_cards)
        total_viewed = sum(1 for bc in battle_cards if bc.viewed_at)
        total_used = sum(1 for bc in battle_cards if bc.used_at)

        view_rate = total_viewed / total_shown if total_shown > 0 else 0.0
        usage_rate = total_used / total_shown if total_shown > 0 else 0.0

        return {
            "total_shown": total_shown,
            "total_viewed": total_viewed,
            "total_used": total_used,
            "view_rate": round(view_rate, 2),
            "usage_rate": round(usage_rate, 2),
            "cards_by_type": self._get_cards_by_type(battle_cards),
        }

    def _get_cards_by_type(self, battle_cards: List[ConversationBattleCard]) -> Dict[str, int]:
        """Group battle cards by type."""
        by_type = {}
        for card in battle_cards:
            card_type = card.card_type.value if hasattr(card.card_type, 'value') else str(card.card_type)
            by_type[card_type] = by_type.get(card_type, 0) + 1
        return by_type


def seed_default_battle_cards(db: Session):
    """
    Seed database with default battle card templates.

    Call this during initialization to populate common battle cards.
    """
    default_cards = [
        {
            "name": "Pricing Objection",
            "card_type": BattleCardType.PRICING,
            "title": "Addressing Pricing Concerns",
            "content": "Focus on value, not cost. Emphasize ROI and long-term benefits.",
            "talking_points": [
                "Average customer sees 3x ROI within 6 months",
                "Cost of doing nothing is higher than investment",
                "Flexible payment options available"
            ],
            "response_template": "I understand budget is important. Let me show you how our solution typically pays for itself within [X] months through [specific benefits].",
            "trigger_keywords": ["expensive", "price", "cost", "budget", "afford"],
            "priority": 10,
        },
        {
            "name": "Competitor Comparison",
            "card_type": BattleCardType.COMPETITOR,
            "title": "Competitive Differentiation",
            "content": "Focus on unique value propositions and customer success stories.",
            "talking_points": [
                "Only solution with [unique feature]",
                "Better customer support (avg response time: 2 hours)",
                "Higher customer satisfaction scores"
            ],
            "response_template": "While [competitor] is a good option, our customers choose us for [key differentiators]. Let me share a case study...",
            "trigger_keywords": ["competitor", "alternative", "versus", "vs", "comparison"],
            "priority": 9,
        },
        {
            "name": "Security and Compliance",
            "card_type": BattleCardType.TECHNICAL,
            "title": "Security & Compliance Overview",
            "content": "Enterprise-grade security with SOC 2 Type II, GDPR, and HIPAA compliance.",
            "talking_points": [
                "SOC 2 Type II certified",
                "GDPR and HIPAA compliant",
                "End-to-end encryption",
                "Regular security audits"
            ],
            "response_template": "Security is a top priority. We maintain [certifications] and implement [security measures].",
            "trigger_keywords": ["security", "secure", "compliance", "gdpr", "hipaa", "soc2"],
            "priority": 8,
        },
        {
            "name": "Integration Capabilities",
            "card_type": BattleCardType.FEATURE,
            "title": "Integration Ecosystem",
            "content": "Seamless integrations with 100+ popular tools and platforms.",
            "talking_points": [
                "Pre-built integrations with CRM, marketing automation, etc.",
                "RESTful API for custom integrations",
                "Zapier support for no-code integrations",
                "Dedicated integration support team"
            ],
            "response_template": "We integrate with all major platforms including [relevant tools for their industry]. Our API makes custom integrations straightforward.",
            "trigger_keywords": ["integrate", "integration", "api", "connect", "sync"],
            "priority": 7,
        },
    ]

    for card_data in default_cards:
        # Check if card already exists
        existing = db.query(BattleCardTemplate).filter(
            BattleCardTemplate.name == card_data["name"]
        ).first()

        if not existing:
            template = BattleCardTemplate(**card_data)
            db.add(template)
            logger.info(f"Created default battle card: {card_data['name']}")

    db.commit()
    logger.info("Default battle cards seeded")
