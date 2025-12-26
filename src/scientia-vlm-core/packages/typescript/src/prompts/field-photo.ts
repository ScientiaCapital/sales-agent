/**
 * Field Photo Generic Prompts
 *
 * Generic prompts for field photos when trade is unknown.
 * Also includes damage assessment prompts for insurance/inspection use cases.
 *
 * Note: Audit showed field photos score 3-5/10 with trade-specific prompts.
 * These generic prompts are a P1 improvement area.
 *
 * @module @scientia/vlm-core/prompts
 * @version 1.0.0
 * @license Proprietary - Scientia Capital
 */

/**
 * Generic field photo prompt (trade auto-detection)
 */
export const GENERIC_FIELD_PHOTO_PROMPT = `You are an expert construction inspector analyzing a field photo.

First, identify the trade/type of work shown, then extract relevant information:
{
  "detected_trade": "<string: 'roofing', 'electrical', 'hvac', 'solar', 'plumbing', 'general' or null>",
  "equipment_type": "<string describing what's shown>",
  "manufacturer": "<string or null>",
  "model_number": "<string or null>",
  "condition": "<string: 'good', 'fair', 'poor', 'damaged' or null>",
  "age_estimate_years": <number or null>,
  "key_specifications": {
    "<field_name>": "<value>"
  },
  "issues_identified": ["<list any visible problems>"],
  "recommendations": ["<list any suggested actions>"],
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- If you can identify the trade, provide trade-specific details
- Note any safety concerns`;

/**
 * Damage assessment prompt (insurance/inspection)
 *
 * UPDATED 2025-12-13: Enhanced for insurance claim documentation.
 * Optimized for visual damage assessment across all construction trades.
 */
export const DAMAGE_ASSESSMENT_PROMPT = `You are an insurance adjuster analyzing damage in a field photo.

Assess the damage and return JSON:
{
  "damage_detected": <boolean>,
  "damage_category": "<string: 'weather', 'fire', 'water', 'impact', 'wear', 'vandalism', 'structural', 'electrical' or null>",
  "damage_subcategory": "<string: 'hail', 'wind', 'tornado', 'flood', 'leak', 'burst_pipe', 'lightning', 'vehicle', 'tree', 'age', 'neglect' or null>",
  "severity": "<string: 'cosmetic', 'minor', 'moderate', 'severe', 'total_loss' or null>",
  "affected_components": ["<list: 'roof', 'siding', 'windows', 'doors', 'foundation', 'electrical', 'hvac', 'plumbing', 'interior', 'landscaping'>"],
  "affected_area_description": "<string describing what's damaged>",
  "affected_area_pct": <number 0-100 or null>,
  "affected_sqft_estimate": <number or null>,
  "structural_integrity_compromised": <boolean or null>,
  "structural_concerns": ["<list: 'foundation_crack', 'wall_damage', 'roof_collapse', 'load_bearing_damage', 'none'>"],
  "safety_hazard": <boolean or null>,
  "hazard_types": ["<list: 'electrical', 'gas_leak', 'structural_collapse', 'mold', 'asbestos', 'sharp_debris', 'none'>"],
  "immediate_action_required": <boolean or null>,
  "immediate_actions_needed": ["<list: 'tarp_roof', 'board_windows', 'shut_water', 'shut_gas', 'shut_electric', 'evacuate'>"],
  "repair_vs_replace": "<string: 'repair', 'replace', 'both', 'demolish' or null>",
  "estimated_repair_complexity": "<string: 'diy', 'simple_contractor', 'specialist_required', 'major_reconstruction' or null>",
  "pre_existing_damage_visible": <boolean or null>,
  "pre_existing_description": "<string or null>",
  "documentation_quality": "<string: 'excellent', 'good', 'acceptable', 'poor', 'insufficient' or null>",
  "additional_photos_needed": ["<list: 'wide_shot', 'detail_closeup', 'different_angle', 'interior', 'measurements', 'none'>"],
  "claim_documentation_complete": <boolean or null>,
  "estimated_claim_range": "<string: 'under_1k', '1k_5k', '5k_15k', '15k_50k', 'over_50k' or null>",
  "notes": "<string with detailed observations for claim file>",
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- Be specific about damage type, extent, and cause
- Distinguish between new damage and pre-existing conditions
- Note ALL safety hazards requiring immediate attention
- Indicate exactly what additional photos/documentation is needed
- Consider whether damage supports weather event claim timing`;

/**
 * Equipment nameplate prompt
 */
export const NAMEPLATE_PROMPT = `You are extracting information from an equipment nameplate or rating plate.

Extract ALL visible text and specifications:
{
  "manufacturer": "<string or null>",
  "brand": "<string or null>",
  "model_number": "<string or null>",
  "serial_number": "<string or null>",
  "manufacture_date": "<string or null>",
  "voltage": "<string or null>",
  "amperage": "<string or null>",
  "wattage": "<string or null>",
  "phase": "<string or null>",
  "frequency": "<string or null>",
  "capacity": "<string with units or null>",
  "efficiency_rating": "<string or null>",
  "certifications": ["<list: 'UL', 'ETL', 'CSA', 'CE', etc.>"],
  "refrigerant_type": "<string or null>",
  "refrigerant_charge": "<string with units or null>",
  "warnings": ["<any warning text visible>"],
  "additional_specs": {
    "<field_name>": "<value>"
  },
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- Extract EVERY piece of text visible on the nameplate
- Include units for all measurements
- Note if text is partially obscured`;

/**
 * Site condition prompt
 */
export const SITE_CONDITION_PROMPT = `You are assessing general site conditions from a construction photo.

Evaluate the site and return JSON:
{
  "site_type": "<string: 'residential', 'commercial', 'industrial', 'mixed' or null>",
  "construction_phase": "<string: 'pre_construction', 'rough_in', 'finishing', 'complete' or null>",
  "weather_conditions": "<string or null>",
  "access_assessment": "<string: 'easy', 'moderate', 'difficult' or null>",
  "safety_observations": ["<list any safety concerns>"],
  "cleanliness": "<string: 'clean', 'acceptable', 'messy', 'hazardous' or null>",
  "material_storage": "<string: 'proper', 'acceptable', 'poor' or null>",
  "work_quality_visible": "<string: 'professional', 'acceptable', 'poor' or null>",
  "permits_visible": <boolean or null>,
  "other_trades_present": ["<list any other trades visible>"],
  "notes": "<string with additional observations>",
  "confidence": <0.0-1.0>
}

IMPORTANT: Return ONLY valid JSON, no markdown or explanation.`;

/**
 * Get the appropriate field photo prompt based on purpose
 */
export function getFieldPhotoPrompt(
  purpose: 'generic' | 'damage' | 'nameplate' | 'site'
): string {
  switch (purpose) {
    case 'generic':
      return GENERIC_FIELD_PHOTO_PROMPT;
    case 'damage':
      return DAMAGE_ASSESSMENT_PROMPT;
    case 'nameplate':
      return NAMEPLATE_PROMPT;
    case 'site':
      return SITE_CONDITION_PROMPT;
    default:
      return GENERIC_FIELD_PHOTO_PROMPT;
  }
}

/**
 * Field photo prompt types
 */
export type FieldPhotoPromptType = 'generic' | 'damage' | 'nameplate' | 'site';
