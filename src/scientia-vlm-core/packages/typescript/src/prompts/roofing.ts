/**
 * Roofing Trade Prompts
 *
 * Extraction prompts optimized for roofing blueprints and field photos.
 * Based on audit results showing Qwen3-30B achieves 10/10 on roof_framing_plan.jpg.
 *
 * Key fields to extract:
 * - total_squares (primary measurement)
 * - roof_pitch (e.g., "6/12")
 * - ridge_length_ft, valley_length_ft, eave_length_ft
 * - overhang_inches
 * - vent_count, chimney_count
 *
 * @module @scientia/vlm-core/prompts
 * @version 1.0.0
 * @license Proprietary - Scientia Capital
 */

/**
 * Roofing blueprint extraction prompt
 *
 * Achieves 10/10 scores with Qwen3-30B on complex roof framing plans.
 */
export const ROOFING_BLUEPRINT_PROMPT = `You are an expert roofing estimator analyzing a construction blueprint.

Extract ALL visible measurements and return JSON:
{
  "trade": "roofing",
  "total_squares": <number or null>,
  "roof_pitch": "<string like '6/12' or null>",
  "ridge_length_ft": <number or null>,
  "valley_length_ft": <number or null>,
  "eave_length_ft": <number or null>,
  "hip_length_ft": <number or null>,
  "rake_length_ft": <number or null>,
  "overhang_inches": <number or null>,
  "fascia_length_ft": <number or null>,
  "drip_edge_ft": <number or null>,
  "chimney_count": <number or null>,
  "vent_count": <number or null>,
  "skylight_count": <number or null>,
  "roof_type": "<string: 'gable', 'hip', 'flat', 'mansard', 'gambrel', 'shed' or null>",
  "decking_type": "<string or null>",
  "underlayment_type": "<string or null>",
  "scale": "<string like '1/4\" = 1'-0\"' or null>",
  "project_name": "<string or null>",
  "sheet_number": "<string or null>",
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- Extract every measurement visible on the blueprint
- If a measurement is partially visible or unclear, include it with lower confidence
- For roof pitch, use the format "rise/run" (e.g., "6/12")`;

/**
 * Roofing field photo prompt (damage assessment)
 *
 * UPDATED 2025-12-13: Enhanced for field photo damage assessment.
 * Previous version scored 3-5/10 because it asked for blueprint measurements.
 * This version focuses on visual assessment fields that VLMs can actually extract.
 */
export const ROOFING_FIELD_PHOTO_PROMPT = `You are an expert roofing inspector analyzing a field photo for damage assessment.

Focus on VISUAL CONDITIONS you can observe. Return JSON:
{
  "trade": "roofing",
  "damage_detected": <boolean>,
  "damage_type": "<string: 'hail', 'wind', 'age', 'water', 'impact', 'none' or null>",
  "damage_severity": "<string: 'minor', 'moderate', 'severe' or null>",
  "affected_area_pct": <number 0-100 or null>,
  "structural_damage": <boolean or null>,
  "safety_hazard": <boolean or null>,
  "immediate_action_required": <boolean or null>,
  "repair_vs_replace": "<string: 'repair', 'replace', 'both', 'none_needed' or null>",
  "roofing_material": "<string: 'asphalt_3tab', 'asphalt_architectural', 'metal', 'tile_clay', 'tile_concrete', 'slate', 'wood_shake', 'flat_membrane' or null>",
  "material_condition": "<string: 'intact', 'curling', 'cracked', 'missing', 'granule_loss', 'rusted', 'faded' or null>",
  "visible_issues": ["<list: 'missing_shingles', 'lifted_shingles', 'exposed_nails', 'moss_growth', 'debris', 'ponding_water', 'sagging', 'flashing_damage', 'gutter_damage', 'vent_damage'>"],
  "flashing_condition": "<string: 'good', 'fair', 'damaged', 'missing', 'not_visible' or null>",
  "gutter_condition": "<string: 'good', 'fair', 'damaged', 'clogged', 'not_visible' or null>",
  "estimated_roof_age_years": <number or null>,
  "photo_quality": "<string: 'good', 'acceptable', 'poor' or null>",
  "photo_coverage": "<string: 'full_roof', 'partial', 'detail_shot', 'ground_level' or null>",
  "weather_conditions": "<string: 'clear', 'overcast', 'wet', 'snow' or null>",
  "additional_photos_needed": <boolean or null>,
  "notes": "<string with detailed observations>",
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- Focus on what you can VISUALLY OBSERVE, not measurements
- Set structural_damage=true only if you see sagging, broken decking, or compromised framing
- Set safety_hazard=true if there are holes, unstable areas, or electrical hazards
- Be specific about visible_issues - list everything you can identify
- Note photo quality issues that affect assessment accuracy`;

/**
 * Roofing pitch chart prompt (reference)
 *
 * GLM-4.6V scores better on reference charts (6/10 vs 3/10 for other models).
 */
export const ROOFING_PITCH_CHART_PROMPT = `You are analyzing a roof pitch reference chart.

Extract the pitch information shown:
{
  "trade": "roofing",
  "chart_type": "pitch_reference",
  "pitches_shown": ["<pitch values like '4/12', '6/12', etc.>"],
  "angles_shown": ["<angle values in degrees if shown>"],
  "multipliers_shown": {"<pitch>": <multiplier>},
  "notes": "<any additional information from the chart>",
  "confidence": <0.0-1.0>
}

IMPORTANT: Return ONLY valid JSON, no markdown or explanation.`;

/**
 * Get the appropriate roofing prompt based on image type
 */
export function getRoofingPrompt(imageType: 'blueprint' | 'field_photo' | 'reference_chart'): string {
  switch (imageType) {
    case 'blueprint':
      return ROOFING_BLUEPRINT_PROMPT;
    case 'field_photo':
      return ROOFING_FIELD_PHOTO_PROMPT;
    case 'reference_chart':
      return ROOFING_PITCH_CHART_PROMPT;
    default:
      return ROOFING_BLUEPRINT_PROMPT;
  }
}

/**
 * Expected fields for roofing blueprint extraction (for validation)
 */
export const ROOFING_BLUEPRINT_FIELDS = [
  'trade',
  'total_squares',
  'roof_pitch',
  'ridge_length_ft',
  'valley_length_ft',
  'eave_length_ft',
  'overhang_inches',
  'chimney_count',
  'vent_count',
  'scale',
  'confidence',
] as const;

/**
 * Primary measurement field for roofing
 */
export const ROOFING_PRIMARY_FIELD = 'total_squares';

/**
 * Secondary measurement fields for roofing
 */
export const ROOFING_SECONDARY_FIELDS = [
  'roof_pitch',
  'ridge_length_ft',
  'valley_length_ft',
  'eave_length_ft',
] as const;
