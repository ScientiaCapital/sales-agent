"""
Message Generator Service

Generates personalized outreach messages with 3 variants for A/B testing using Cerebras ultra-fast inference.
"""

import os
import time
from typing import Dict, List, Optional, Any
from openai import OpenAI
import re

from app.core.logging import setup_logging
from app.core.exceptions import CerebrasAPIError, CerebrasTimeoutError, MissingAPIKeyError, ValidationError
from app.models.campaign import MessageTone

logger = setup_logging(__name__)


class MessageGenerator:
    """
    Service for generating personalized outreach messages with variants.
    
    Features:
    - Ultra-fast generation using Cerebras (<1s for 3 variants)
    - Template support with {{variable}} substitution
    - Channel-specific formatting (email, LinkedIn, SMS)
    - Context integration (lead data, research, scoring)
    - 3 variants per message (professional, friendly, direct)
    """
    
    # Cerebras pricing
    COST_PER_1M_TOKENS = 0.016  # $0.016 per 1M tokens
    
    def __init__(self):
        self.api_key = os.getenv("CEREBRAS_API_KEY")
        self.api_base = os.getenv("CEREBRAS_API_BASE", "https://api.cerebras.ai/v1")
        
        if not self.api_key:
            raise MissingAPIKeyError(
                "CEREBRAS_API_KEY environment variable not set",
                context={"api_key": "CEREBRAS_API_KEY"}
            )
        
        # Initialize OpenAI client with Cerebras endpoint
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_base
        )
        
        # Default model (llama3.1-8b for sub-1s inference)
        self.default_model = os.getenv("CEREBRAS_DEFAULT_MODEL", "llama3.1-8b")
    
    def generate_message_variants(
        self,
        channel: str,
        lead_context: Dict[str, Any],
        custom_context: Optional[str] = None,
        template: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate 3 message variants (professional, friendly, direct) for A/B testing.
        
        Args:
            channel: Communication channel (email, linkedin, sms)
            lead_context: Lead data including name, company, qualification score, research
            custom_context: Additional context for personalization
            template: Optional template with {{variables}}
        
        Returns:
            Dict with variants, generation_time_ms, and cost
        """
        start_time = time.time()
        
        # Build prompt for variant generation
        prompt = self._build_variant_prompt(channel, lead_context, custom_context, template)
        
        try:
            # Single API call generates all 3 variants
            response = self.client.chat.completions.create(
                model=self.default_model,
                messages=[
                    {"role": "system", "content": "You are an expert sales copywriter specializing in personalized outreach."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,  # ~200 tokens per variant
                temperature=0.7
            )
            
            # Extract variants from response
            content = response.choices[0].message.content
            variants = self._parse_variants(content, channel)
            
            # Calculate metrics
            latency_ms = int((time.time() - start_time) * 1000)
            tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 600
            cost_usd = (tokens_used / 1_000_000) * self.COST_PER_1M_TOKENS
            
            logger.info(
                f"Generated {len(variants)} variants in {latency_ms}ms "
                f"({tokens_used} tokens, ${cost_usd:.6f})"
            )
            
            return {
                "variants": variants,
                "generation_time_ms": latency_ms,
                "cost_usd": cost_usd,
                "tokens_used": tokens_used
            }
        
        except Exception as e:
            logger.error(f"Message generation failed: {e}", exc_info=True)
            raise CerebrasAPIError(
                f"Failed to generate message variants: {str(e)}",
                details={"channel": channel, "lead": lead_context.get("company_name")}
            )
    
    def _build_variant_prompt(
        self,
        channel: str,
        lead_context: Dict[str, Any],
        custom_context: Optional[str],
        template: Optional[str]
    ) -> str:
        """Build prompt for generating 3 message variants"""
        
        # Extract lead details
        company_name = lead_context.get("company_name", "the company")
        contact_name = lead_context.get("contact_name", "there")
        contact_title = lead_context.get("contact_title", "")
        qualification_score = lead_context.get("qualification_score", 0)
        research_summary = lead_context.get("research_summary", "")
        
        # Channel-specific instructions
        channel_instructions = {
            "email": "Email format with subject line and body. Keep professional but engaging.",
            "linkedin": "LinkedIn InMail format (1500 char max). Direct and value-focused.",
            "sms": "SMS format (160 char max). Ultra-concise and actionable."
        }
        
        prompt = f"""Generate 3 personalized outreach message variants for {channel}.

**Lead Context:**
- Company: {company_name}
- Contact: {contact_name} {f'({contact_title})' if contact_title else ''}
- Qualification Score: {qualification_score}/100
{f'- Research Insights: {research_summary}' if research_summary else ''}
{f'- Additional Context: {custom_context}' if custom_context else ''}

**Channel:** {channel_instructions.get(channel, 'Standard format')}

{f'**Template to follow:** {template}' if template else ''}

**Generate 3 variants with different tones:**

VARIANT 1 (PROFESSIONAL):
- Formal, executive-level tone
- Focus on ROI and business value
- Data-driven messaging

VARIANT 2 (FRIENDLY):
- Warm, conversational tone
- Build rapport and connection
- Problem-solution approach

VARIANT 3 (DIRECT):
- Concise, action-oriented tone
- Clear value proposition
- Strong call-to-action

Format each variant clearly with:
"""
        
        if channel == "email":
            prompt += """
Subject: [subject line]
Body: [email body]
---
"""
        else:
            prompt += """
Message: [message text]
---
"""
        
        return prompt
    
    def _parse_variants(self, content: str, channel: str) -> List[Dict[str, str]]:
        """Parse AI response into structured variants"""
        
        variants = []
        tones = [MessageTone.PROFESSIONAL, MessageTone.FRIENDLY, MessageTone.DIRECT]
        
        # Split by variant markers
        sections = content.split("VARIANT")
        
        for i, section in enumerate(sections[1:], start=0):  # Skip first split
            if i >= 3:
                break
            
            variant = {"tone": tones[i].value}
            
            if channel == "email":
                # Extract subject and body
                subject_match = re.search(r'Subject:\s*(.+?)(?:\n|Body:)', section, re.IGNORECASE)
                body_match = re.search(r'Body:\s*(.+?)(?:---|$)', section, re.DOTALL | re.IGNORECASE)
                
                variant["subject"] = subject_match.group(1).strip() if subject_match else f"Message for {i+1}"
                variant["body"] = body_match.group(1).strip() if body_match else section.strip()
            else:
                # Extract message text
                message_match = re.search(r'Message:\s*(.+?)(?:---|$)', section, re.DOTALL | re.IGNORECASE)
                variant["body"] = message_match.group(1).strip() if message_match else section.strip()
                variant["subject"] = None
            
            # Clean up the body
            variant["body"] = variant["body"].strip().replace("---", "")
            
            variants.append(variant)
        
        # Ensure we have exactly 3 variants
        while len(variants) < 3:
            variants.append({
                "tone": tones[len(variants)].value,
                "subject": f"Variant {len(variants) + 1}" if channel == "email" else None,
                "body": "Fallback message - please customize"
            })
        
        return variants[:3]
    
    def apply_template(self, template: str, variables: Dict[str, str]) -> str:
        """
        Apply variable substitution to template.
        
        Supports {{variable}} syntax.
        """
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result
    
    def format_for_channel(self, message: str, channel: str) -> str:
        """Apply channel-specific formatting"""
        
        if channel == "email":
            # Add HTML formatting for email
            return message.replace("\n", "<br>")
        
        elif channel == "linkedin":
            # Enforce LinkedIn character limit
            return message[:1500]
        
        elif channel == "sms":
            # Enforce SMS character limit
            return message[:160]
        
        return message
