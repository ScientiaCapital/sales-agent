/**
 * HVAC Trade Prompts
 *
 * Extraction prompts optimized for HVAC blueprints and field photos.
 * Based on audit results showing Qwen3-30B extracts tonnage, BTU, zone_count.
 *
 * Key fields to extract:
 * - tonnage (primary measurement)
 * - btu, zone_count, register_count
 * - duct_sizes
 *
 * @module @scientia/vlm-core/prompts
 * @version 1.0.0
 * @license Proprietary - Scientia Capital
 */

/**
 * HVAC blueprint extraction prompt
 *
 * Achieves 8/10 scores with Qwen3-30B on mechanical room drawings.
 */
export const HVAC_BLUEPRINT_PROMPT = `You are an expert HVAC technician analyzing a mechanical blueprint.

Extract ALL visible information and return JSON:
{
  "trade": "hvac",
  "tonnage": <number or null>,
  "btu": <number or null>,
  "seer_rating": <number or null>,
  "hspf_rating": <number or null>,
  "afue_rating": <number or null>,
  "zone_count": <number or null>,
  "thermostat_count": <number or null>,
  "register_count": <number or null>,
  "return_count": <number or null>,
  "duct_sizes": ["<list of duct dimensions like '12x8'>"],
  "main_trunk_size": "<string or null>",
  "system_type": "<string: 'split', 'package', 'mini_split', 'geothermal' or null>",
  "fuel_type": "<string: 'electric', 'gas', 'propane', 'oil' or null>",
  "refrigerant_type": "<string like 'R-410A' or null>",
  "air_handler_location": "<string or null>",
  "condenser_location": "<string or null>",
  "cfm_total": <number or null>,
  "static_pressure": <number or null>,
  "scale": "<string or null>",
  "project_name": "<string or null>",
  "sheet_number": "<string or null>",
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- Extract all duct sizes visible on the plan
- Note supply vs return registers
- Calculate zone counts from thermostat locations`;

/**
 * HVAC field photo prompt (equipment labels)
 */
export const HVAC_FIELD_PHOTO_PROMPT = `You are an expert HVAC technician analyzing a field photo of HVAC equipment.

Assess the condition and extract any visible information:
{
  "trade": "hvac",
  "equipment_type": "<string: 'condenser', 'air_handler', 'furnace', 'heat_pump', 'mini_split', 'thermostat' or null>",
  "manufacturer": "<string or null>",
  "model_number": "<string or null>",
  "serial_number": "<string or null>",
  "tonnage": <number or null>,
  "btu_input": <number or null>,
  "btu_output": <number or null>,
  "seer_rating": <number or null>,
  "hspf_rating": <number or null>,
  "afue_rating": <number or null>,
  "voltage": <number or null>,
  "refrigerant_type": "<string or null>",
  "refrigerant_charge_oz": <number or null>,
  "manufacture_date": "<string or null>",
  "estimated_age_years": <number or null>,
  "condition": "<string: 'good', 'fair', 'poor', 'damaged' or null>",
  "visible_damage": "<string or null>",
  "rust_corrosion": <boolean or null>,
  "refrigerant_leak_signs": <boolean or null>,
  "filter_access": "<string or null>",
  "replacement_recommended": <boolean or null>,
  "notes": "<string with additional observations or null>",
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- Extract model and serial numbers carefully
- Calculate age from serial number if possible
- Note any efficiency ratings visible`;

/**
 * HVAC symbol legend prompt
 */
export const HVAC_SYMBOL_PROMPT = `You are analyzing an HVAC symbol legend.

Extract the symbol definitions:
{
  "trade": "hvac",
  "chart_type": "symbol_legend",
  "symbols": [
    {"symbol": "<description>", "meaning": "<what it represents>"}
  ],
  "notes": "<any additional information>",
  "confidence": <0.0-1.0>
}

IMPORTANT: Return ONLY valid JSON, no markdown or explanation.`;

/**
 * Get the appropriate HVAC prompt based on image type
 */
export function getHvacPrompt(imageType: 'blueprint' | 'field_photo' | 'symbol_legend'): string {
  switch (imageType) {
    case 'blueprint':
      return HVAC_BLUEPRINT_PROMPT;
    case 'field_photo':
      return HVAC_FIELD_PHOTO_PROMPT;
    case 'symbol_legend':
      return HVAC_SYMBOL_PROMPT;
    default:
      return HVAC_BLUEPRINT_PROMPT;
  }
}

/**
 * Expected fields for HVAC blueprint extraction
 */
export const HVAC_BLUEPRINT_FIELDS = [
  'trade',
  'tonnage',
  'btu',
  'zone_count',
  'register_count',
  'return_count',
  'duct_sizes',
  'scale',
  'confidence',
] as const;

/**
 * Primary measurement field for HVAC
 */
export const HVAC_PRIMARY_FIELD = 'tonnage';

/**
 * Secondary measurement fields for HVAC
 */
export const HVAC_SECONDARY_FIELDS = [
  'btu',
  'zone_count',
  'register_count',
] as const;
