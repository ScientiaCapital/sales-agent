/**
 * Plumbing Trade Prompts
 *
 * Extraction prompts optimized for plumbing blueprints and field photos.
 * Based on audit results for fixture schedules and equipment labels.
 *
 * Key fields to extract:
 * - fixture_count (primary measurement)
 * - pipe_sizes, water_heater_specs
 * - drain_sizes
 *
 * @module @scientia/vlm-core/prompts
 * @version 1.0.0
 * @license Proprietary - Scientia Capital
 */

/**
 * Plumbing blueprint extraction prompt
 */
export const PLUMBING_BLUEPRINT_PROMPT = `You are an expert plumber analyzing a plumbing blueprint.

Extract ALL visible information and return JSON:
{
  "trade": "plumbing",
  "fixture_count": <number or null>,
  "toilet_count": <number or null>,
  "sink_count": <number or null>,
  "shower_count": <number or null>,
  "tub_count": <number or null>,
  "dishwasher_count": <number or null>,
  "washing_machine_count": <number or null>,
  "water_heater_count": <number or null>,
  "water_heater_type": "<string: 'tank', 'tankless', 'heat_pump' or null>",
  "water_heater_gallons": <number or null>,
  "main_water_line_size": "<string like '1 inch' or null>",
  "main_drain_size": "<string like '4 inch' or null>",
  "supply_pipe_material": "<string: 'copper', 'pex', 'cpvc', 'galvanized' or null>",
  "drain_pipe_material": "<string: 'pvc', 'abs', 'cast_iron' or null>",
  "vent_pipe_sizes": ["<list of vent sizes>"],
  "cleanout_count": <number or null>,
  "shutoff_valve_count": <number or null>,
  "pressure_regulator": <boolean or null>,
  "water_softener": <boolean or null>,
  "recirculation_pump": <boolean or null>,
  "sump_pump": <boolean or null>,
  "scale": "<string or null>",
  "project_name": "<string or null>",
  "sheet_number": "<string or null>",
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- Count all fixtures visible on the plan
- Note pipe sizes at key locations
- Identify special equipment (softeners, pumps, etc.)`;

/**
 * Plumbing field photo prompt (water heater nameplate)
 */
export const PLUMBING_FIELD_PHOTO_PROMPT = `You are an expert plumber analyzing a field photo of plumbing equipment.

Assess the condition and extract any visible information:
{
  "trade": "plumbing",
  "equipment_type": "<string: 'water_heater', 'tankless', 'softener', 'pump', 'fixture' or null>",
  "manufacturer": "<string or null>",
  "model_number": "<string or null>",
  "serial_number": "<string or null>",
  "capacity_gallons": <number or null>,
  "btu_input": <number or null>,
  "first_hour_rating": <number or null>,
  "recovery_rate_gph": <number or null>,
  "energy_factor": <number or null>,
  "uef_rating": <number or null>,
  "fuel_type": "<string: 'electric', 'gas', 'propane' or null>",
  "voltage": <number or null>,
  "gpm_rating": <number or null>,
  "manufacture_date": "<string or null>",
  "estimated_age_years": <number or null>,
  "condition": "<string: 'good', 'fair', 'poor', 'damaged' or null>",
  "rust_corrosion": <boolean or null>,
  "leak_signs": <boolean or null>,
  "anode_rod_status": "<string or null>",
  "expansion_tank": <boolean or null>,
  "temperature_setting": <number or null>,
  "replacement_recommended": <boolean or null>,
  "notes": "<string with additional observations or null>",
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- Extract all rating plate information
- Calculate age from serial number if possible
- Note any visible leaks, rust, or damage`;

/**
 * Plumbing isometric drawing prompt
 */
export const PLUMBING_ISOMETRIC_PROMPT = `You are analyzing a plumbing isometric drawing.

Extract the system layout:
{
  "trade": "plumbing",
  "drawing_type": "isometric",
  "floors_shown": <number or null>,
  "main_stack_size": "<string or null>",
  "branch_sizes": ["<list of branch drain sizes>"],
  "vent_configuration": "<string: 'wet_vent', 'dry_vent', 'aav' or null>",
  "fixture_units_total": <number or null>,
  "cleanout_locations": ["<list of cleanout positions>"],
  "notes": "<string with additional observations or null>",
  "confidence": <0.0-1.0>
}

IMPORTANT: Return ONLY valid JSON, no markdown or explanation.`;

/**
 * Get the appropriate plumbing prompt based on image type
 */
export function getPlumbingPrompt(imageType: 'blueprint' | 'field_photo' | 'isometric'): string {
  switch (imageType) {
    case 'blueprint':
      return PLUMBING_BLUEPRINT_PROMPT;
    case 'field_photo':
      return PLUMBING_FIELD_PHOTO_PROMPT;
    case 'isometric':
      return PLUMBING_ISOMETRIC_PROMPT;
    default:
      return PLUMBING_BLUEPRINT_PROMPT;
  }
}

/**
 * Expected fields for plumbing blueprint extraction
 */
export const PLUMBING_BLUEPRINT_FIELDS = [
  'trade',
  'fixture_count',
  'water_heater_type',
  'main_water_line_size',
  'main_drain_size',
  'scale',
  'confidence',
] as const;

/**
 * Primary measurement field for plumbing
 */
export const PLUMBING_PRIMARY_FIELD = 'fixture_count';

/**
 * Secondary measurement fields for plumbing
 */
export const PLUMBING_SECONDARY_FIELDS = [
  'water_heater_gallons',
  'main_water_line_size',
  'main_drain_size',
] as const;
