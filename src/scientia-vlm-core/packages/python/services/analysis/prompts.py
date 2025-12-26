"""
Default prompts for blueprint analysis.

Contains trade-specific prompts for VLM analysis.
"""

from __future__ import annotations

SYSTEM_PROMPT = """You are an expert construction blueprint analyzer.

Analyze the provided image and extract structured data in JSON format.

Your response MUST be valid JSON with these fields:
- image_type: "blueprint" | "field_photo" | "document" | "other"
- trade: primary trade (solar, electrical, hvac, plumbing, roofing, etc.)
- confidence: float 0.0-1.0 indicating extraction confidence
- details: dict with trade-specific extracted fields

Always respond with properly formatted JSON. No additional text."""

TRADE_PROMPTS: dict[str, str] = {
    "solar": """Focus on solar installation details:
- Panel layout and count
- Inverter specifications
- Wiring diagrams
- Mounting system type
- Array orientation and tilt
- String configurations""",
    "electrical": """Focus on electrical system details:
- Panel schedules and load calculations
- Circuit layouts
- Wire sizing and types
- Conduit runs
- Grounding specifications
- Voltage and amperage ratings""",
    "hvac": """Focus on HVAC system details:
- Equipment schedules (tonnage, SEER)
- Duct layouts and sizing
- Refrigerant line sets
- Thermostat locations
- Ventilation requirements
- Zoning configurations""",
    "plumbing": """Focus on plumbing system details:
- Fixture schedules
- Pipe sizing and materials
- Water heater specifications
- Drainage layouts
- Vent stack locations
- Gas line configurations""",
    "roofing": """Focus on roofing details:
- Roof pitch and area
- Material specifications
- Flashing details
- Drainage patterns
- Penetration locations
- Underlayment requirements""",
    "structural": """Focus on structural details:
- Load paths and bearing walls
- Foundation specifications
- Beam and header sizes
- Connection details
- Seismic/wind bracing
- Material specifications""",
    "fire_protection": """Focus on fire protection details:
- Sprinkler layouts
- Pipe sizing and materials
- Head types and coverage
- Riser locations
- Alarm system components
- Fire-rated assemblies""",
}

GENERIC_PROMPT = """Analyze this construction document:
- Identify the primary trade or discipline
- Extract key specifications and dimensions
- Note any callouts or annotations
- Identify equipment and materials specified"""


def get_analysis_prompt() -> str:
    """Get the default analysis prompt for blueprint analysis.

    Returns:
        Prompt string instructing the model to analyze and extract JSON.
    """
    return f"""{SYSTEM_PROMPT}

Analyze the image and respond with JSON containing:
- image_type: type of document/image
- trade: primary construction trade
- confidence: extraction confidence (0.0-1.0)
- details: trade-specific extracted information"""


def get_trade_specific_prompt(trade: str | None) -> str:
    """Get trade-specific analysis prompt.

    Args:
        trade: Trade name (case-insensitive) or None for generic.

    Returns:
        Trade-specific prompt string, or generic if trade unknown.
    """
    if trade is None:
        return GENERIC_PROMPT

    trade_lower = trade.lower()
    return TRADE_PROMPTS.get(trade_lower, GENERIC_PROMPT)
