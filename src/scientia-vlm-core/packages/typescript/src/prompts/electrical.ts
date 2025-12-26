/**
 * Electrical Trade Prompts
 *
 * Extraction prompts optimized for electrical blueprints and field photos.
 * Based on audit results showing Qwen3-30B achieves 10/10 on panel schedules.
 *
 * Key fields to extract:
 * - panel_amperage (primary measurement)
 * - circuit_count, gfci_count
 * - breaker_sizes, wire_gauges
 *
 * @module @scientia/vlm-core/prompts
 * @version 1.0.0
 * @license Proprietary - Scientia Capital
 */

/**
 * Electrical blueprint extraction prompt
 *
 * Achieves 10/10 scores with Qwen3-30B on panel schedules and floor plans.
 */
export const ELECTRICAL_BLUEPRINT_PROMPT = `You are an expert electrician analyzing an electrical blueprint or panel schedule.

Extract ALL visible information and return JSON:
{
  "trade": "electrical",
  "panel_amperage": <number or null>,
  "main_breaker_size": <number or null>,
  "circuit_count": <number or null>,
  "gfci_count": <number or null>,
  "afci_count": <number or null>,
  "subpanel_count": <number or null>,
  "outlets_per_circuit": <number or null>,
  "wire_gauge": "<string like '12 AWG' or null>",
  "breaker_sizes": [<list of breaker amperages>],
  "dedicated_circuits": ["<list of dedicated circuit names>"],
  "voltage": <number like 120 or 240 or null>,
  "phase": "<string: 'single', 'three' or null>",
  "total_load_amps": <number or null>,
  "available_capacity_amps": <number or null>,
  "scale": "<string or null>",
  "project_name": "<string or null>",
  "sheet_number": "<string or null>",
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- Extract every circuit from panel schedules
- Note GFCI and AFCI protected circuits
- Calculate total load if individual circuit loads are shown`;

/**
 * Electrical field photo prompt (panel/equipment)
 */
export const ELECTRICAL_FIELD_PHOTO_PROMPT = `You are an expert electrician analyzing a field photo of electrical equipment.

Assess the condition and extract any visible information:
{
  "trade": "electrical",
  "equipment_type": "<string: 'main_panel', 'subpanel', 'meter', 'disconnect', 'breaker' or null>",
  "manufacturer": "<string or null>",
  "model_number": "<string or null>",
  "panel_amperage": <number or null>,
  "main_breaker_size": <number or null>,
  "bus_rating": <number or null>,
  "available_spaces": <number or null>,
  "used_spaces": <number or null>,
  "tandem_breakers_allowed": <boolean or null>,
  "condition": "<string: 'good', 'fair', 'poor', 'damaged' or null>",
  "corrosion_visible": <boolean or null>,
  "wire_condition": "<string or null>",
  "grounding_visible": <boolean or null>,
  "neutral_bar_full": <boolean or null>,
  "code_violations_visible": ["<list any visible issues>"],
  "upgrade_recommended": <boolean or null>,
  "notes": "<string with additional observations or null>",
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- Note any safety concerns or code violations
- Check for double-tapped breakers, improper wiring, etc.`;

/**
 * Electrical symbol legend prompt
 */
export const ELECTRICAL_SYMBOL_PROMPT = `You are analyzing an electrical symbol legend.

Extract the symbol definitions:
{
  "trade": "electrical",
  "chart_type": "symbol_legend",
  "symbols": [
    {"symbol": "<description>", "meaning": "<what it represents>"}
  ],
  "notes": "<any additional information>",
  "confidence": <0.0-1.0>
}

IMPORTANT: Return ONLY valid JSON, no markdown or explanation.`;

/**
 * Get the appropriate electrical prompt based on image type
 */
export function getElectricalPrompt(imageType: 'blueprint' | 'field_photo' | 'symbol_legend'): string {
  switch (imageType) {
    case 'blueprint':
      return ELECTRICAL_BLUEPRINT_PROMPT;
    case 'field_photo':
      return ELECTRICAL_FIELD_PHOTO_PROMPT;
    case 'symbol_legend':
      return ELECTRICAL_SYMBOL_PROMPT;
    default:
      return ELECTRICAL_BLUEPRINT_PROMPT;
  }
}

/**
 * Expected fields for electrical blueprint extraction
 */
export const ELECTRICAL_BLUEPRINT_FIELDS = [
  'trade',
  'panel_amperage',
  'circuit_count',
  'gfci_count',
  'breaker_sizes',
  'voltage',
  'scale',
  'confidence',
] as const;

/**
 * Primary measurement field for electrical
 */
export const ELECTRICAL_PRIMARY_FIELD = 'panel_amperage';

/**
 * Secondary measurement fields for electrical
 */
export const ELECTRICAL_SECONDARY_FIELDS = [
  'circuit_count',
  'gfci_count',
  'main_breaker_size',
] as const;
