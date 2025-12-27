"""Prompting utilities: LCEL chain building and JSON response parsing."""
import re
import json
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel

from app.core.logging import setup_logging
from .schemas import LeadQualificationResult

logger = setup_logging(__name__)


# System prompt for qualification criteria with JSON output
QUALIFICATION_SYSTEM_PROMPT = """You are an AI sales assistant specializing in B2B lead qualification.

Analyze the provided lead information and assign a qualification score from 0-100 based on:

1. **Company Fit** (40 points)
   - Company size matches ICP (Ideal Customer Profile)
   - Industry alignment with product offerings
   - Market presence and growth indicators

2. **Contact Quality** (30 points)
   - Decision-maker level (C-suite, VP, Director)
   - Relevant title for the purchase decision
   - Accessibility and responsiveness signals

3. **Sales Potential** (30 points)
   - Buying signals (recent funding, expansion, hiring)
   - Urgency indicators (pain points, deadlines)
   - Budget/readiness signals

Scoring Tiers:
- Hot (80-100): High fit, decision-maker, strong buying signals → immediate outreach
- Warm (60-79): Good fit, relevant contact, some signals → nurture campaign
- Cold (40-59): Moderate fit, lower contact quality → long-term nurture
- Unqualified (0-39): Poor fit or missing critical info → deprioritize

**IMPORTANT**: Respond ONLY with valid JSON in this exact format:
{{
  "qualification_score": <number 0-100>,
  "qualification_reasoning": "<2-3 sentence explanation>",
  "tier": "<hot|warm|cold|unqualified>",
  "fit_assessment": "<company fit evaluation>",
  "contact_quality": "<contact level assessment>",
  "sales_potential": "<buying signals and readiness>",
  "recommendations": ["<action 1>", "<action 2>", "<action 3>"]
}}

Do not include any text before or after the JSON object."""


USER_PROMPT_TEMPLATE = """Qualify this lead:

Company: {company_name}
{optional_fields}

Respond with JSON only."""


def build_qualification_chain(llm: BaseChatModel):
    """
    Build LCEL chain: prompt | llm (free-form JSON generation)

    Args:
        llm: Initialized LLM instance

    Returns:
        Compiled LCEL chain ready for invocation
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", QUALIFICATION_SYSTEM_PROMPT),
        ("user", USER_PROMPT_TEMPLATE)
    ])

    # Build LCEL chain with free-form output
    # Pattern: prompt | llm (returns raw text to be parsed)
    return prompt | llm


def parse_json_response(response_text: str) -> LeadQualificationResult:
    """
    Parse free-form JSON response from LLM.

    Args:
        response_text: Raw text response from LLM

    Returns:
        Parsed LeadQualificationResult

    Raises:
        ValueError: If JSON parsing fails
    """
    try:
        # Try to extract JSON from response (handles cases where LLM adds text)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON object found in response: {response_text[:200]}")

        json_str = json_match.group(0)
        data = json.loads(json_str)

        # Validate and create Pydantic model
        return LeadQualificationResult(**data)

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing failed: {e}\nResponse: {response_text[:500]}")
        raise ValueError(f"Invalid JSON response from LLM: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to parse qualification response: {e}")
        raise ValueError(f"Failed to parse qualification response: {str(e)}")


def format_optional_fields(
    company_website: Optional[str] = None,
    company_size: Optional[str] = None,
    industry: Optional[str] = None,
    contact_name: Optional[str] = None,
    contact_title: Optional[str] = None,
    notes: Optional[str] = None
) -> str:
    """Format optional fields for prompt."""
    fields = []

    if company_website:
        fields.append(f"Website: {company_website}")
    if company_size:
        fields.append(f"Size: {company_size}")
    if industry:
        fields.append(f"Industry: {industry}")
    if contact_name:
        fields.append(f"Contact: {contact_name}")
    if contact_title:
        fields.append(f"Title: {contact_title}")
    if notes:
        fields.append(f"Notes: {notes}")

    return "\n".join(fields) if fields else "No additional information provided."


def build_full_prompt(
    company_name: str,
    optional_fields: str
) -> str:
    """Build complete prompt for cost-optimized provider path."""
    return f"""{QUALIFICATION_SYSTEM_PROMPT}

Qualify this lead:

Company: {company_name}
{optional_fields}

Respond with JSON only."""


__all__ = [
    "build_qualification_chain", "parse_json_response",
    "format_optional_fields", "build_full_prompt",
    "QUALIFICATION_SYSTEM_PROMPT", "USER_PROMPT_TEMPLATE"
]
