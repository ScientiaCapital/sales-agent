/**
 * Solar Trade Prompts
 *
 * Extraction prompts optimized for solar blueprints and field photos.
 * Based on audit results showing 10/10 scores on solar electrical diagrams.
 *
 * Key fields to extract:
 * - system_kw (primary measurement)
 * - panel_count, inverter_specs
 * - string_configuration
 *
 * @module @scientia/vlm-core/prompts
 * @version 1.0.0
 * @license Proprietary - Scientia Capital
 */

/**
 * Solar blueprint extraction prompt
 *
 * Achieves 10/10 scores with Qwen3-30B and GLM-4.6V on electrical diagrams.
 */
export const SOLAR_BLUEPRINT_PROMPT = `You are an expert solar installer analyzing a solar system blueprint.

Extract ALL visible information and return JSON:
{
  "trade": "solar",
  "system_kw": <number or null>,
  "panel_count": <number or null>,
  "panel_wattage": <number or null>,
  "panel_manufacturer": "<string or null>",
  "panel_model": "<string or null>",
  "inverter_type": "<string: 'string', 'micro', 'hybrid' or null>",
  "inverter_manufacturer": "<string or null>",
  "inverter_model": "<string or null>",
  "inverter_count": <number or null>,
  "inverter_kw": <number or null>,
  "string_count": <number or null>,
  "panels_per_string": <number or null>,
  "dc_voltage": <number or null>,
  "ac_voltage": <number or null>,
  "battery_included": <boolean or null>,
  "battery_kwh": <number or null>,
  "interconnection_type": "<string: 'grid_tied', 'hybrid', 'off_grid' or null>",
  "main_panel_upgrade_required": <boolean or null>,
  "new_service_size": <number or null>,
  "roof_area_sqft": <number or null>,
  "azimuth": <number or null>,
  "tilt": <number or null>,
  "annual_production_kwh": <number or null>,
  "scale": "<string or null>",
  "project_name": "<string or null>",
  "sheet_number": "<string or null>",
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- Extract string configuration details
- Note any electrical upgrade requirements
- Calculate system size from panel count × wattage if needed`;

/**
 * Solar field photo prompt (installation/defect assessment)
 *
 * UPDATED 2025-12-13: Enhanced for field photo visual assessment.
 * Focus on installation quality, defects, and conditions VLMs can observe.
 */
export const SOLAR_FIELD_PHOTO_PROMPT = `You are an expert solar installer analyzing a field photo for installation quality and defects.

Focus on VISUAL CONDITIONS you can observe. Return JSON:
{
  "trade": "solar",
  "photo_type": "<string: 'array_overview', 'panel_closeup', 'equipment_closeup', 'site_overview', 'aerial' or null>",
  "installation_progress": "<string: 'not_started', 'layout_marked', 'racking_installed', 'panels_mounted', 'wiring_in_progress', 'complete' or null>",
  "panel_visible_count": <number or null>,
  "panel_manufacturer": "<string or null>",
  "panel_model": "<string or null>",
  "panel_defects": ["<list: 'hot_spots', 'micro_cracks', 'discoloration', 'broken_glass', 'junction_box_damage', 'frame_damage', 'none'>"],
  "soiling_severity": "<string: 'clean', 'light_dust', 'moderate_soiling', 'heavy_soiling', 'debris_covered' or null>",
  "shading_severity": "<string: 'none', 'minor', 'moderate', 'severe' or null>",
  "shading_sources": ["<list: 'trees', 'chimney', 'vent_pipe', 'neighboring_building', 'parapet', 'antenna', 'other'>"],
  "mounting_type": "<string: 'roof_flush', 'roof_tilted', 'ground_fixed', 'ground_tracker', 'carport', 'awning' or null>",
  "mounting_quality": "<string: 'professional', 'acceptable', 'concerning', 'unsafe' or null>",
  "racking_condition": "<string: 'good', 'fair', 'rusted', 'damaged', 'missing_parts' or null>",
  "electrical_issues_visible": <boolean or null>,
  "electrical_concerns": ["<list: 'exposed_wiring', 'loose_connections', 'conduit_damage', 'improper_grounding', 'missing_labels', 'none'>"],
  "inverter_visible": <boolean or null>,
  "inverter_type": "<string: 'string', 'micro', 'hybrid' or null>",
  "inverter_condition": "<string: 'good', 'weathered', 'damaged', 'error_lights' or null>",
  "safety_hazard": <boolean or null>,
  "code_violations_visible": ["<list: 'setback_violation', 'fire_pathway_blocked', 'improper_mounting', 'electrical_violation', 'none'>"],
  "roof_condition_under_array": "<string: 'good', 'fair', 'damaged', 'not_visible' or null>",
  "estimated_system_age_years": <number or null>,
  "maintenance_needed": <boolean or null>,
  "maintenance_type": ["<list: 'cleaning', 'electrical_repair', 'mounting_repair', 'panel_replacement', 'inverter_service'>"],
  "photo_quality": "<string: 'good', 'acceptable', 'poor' or null>",
  "additional_photos_needed": <boolean or null>,
  "notes": "<string with detailed observations>",
  "confidence": <0.0-1.0>
}

IMPORTANT:
- Return ONLY valid JSON, no markdown or explanation
- Focus on what you can VISUALLY OBSERVE
- List ALL visible defects in panel_defects array
- Note ALL shading sources visible in the photo
- Set safety_hazard=true for any immediate dangers
- Be specific about electrical_concerns if wiring is visible`;

/**
 * Solar site assessment prompt
 */
export const SOLAR_SITE_PROMPT = `You are analyzing a solar site assessment photo (typically a satellite or drone view).

Extract site characteristics:
{
  "trade": "solar",
  "photo_type": "site_assessment",
  "roof_area_sqft_estimate": <number or null>,
  "usable_area_pct": <number or null>,
  "roof_sections": <number or null>,
  "primary_azimuth": "<string: 'N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW' or null>",
  "estimated_tilt": <number or null>,
  "obstacles_visible": ["<list: 'chimney', 'vent', 'skylight', 'hvac', 'tree', etc.>"],
  "shading_risk": "<string: 'low', 'medium', 'high' or null>",
  "ground_mount_possible": <boolean or null>,
  "estimated_panel_capacity": <number or null>,
  "notes": "<string with additional observations or null>",
  "confidence": <0.0-1.0>
}

IMPORTANT: Return ONLY valid JSON, no markdown or explanation.`;

/**
 * Get the appropriate solar prompt based on image type
 */
export function getSolarPrompt(imageType: 'blueprint' | 'field_photo' | 'site_assessment'): string {
  switch (imageType) {
    case 'blueprint':
      return SOLAR_BLUEPRINT_PROMPT;
    case 'field_photo':
      return SOLAR_FIELD_PHOTO_PROMPT;
    case 'site_assessment':
      return SOLAR_SITE_PROMPT;
    default:
      return SOLAR_BLUEPRINT_PROMPT;
  }
}

/**
 * Expected fields for solar blueprint extraction
 */
export const SOLAR_BLUEPRINT_FIELDS = [
  'trade',
  'system_kw',
  'panel_count',
  'panel_wattage',
  'inverter_type',
  'string_count',
  'scale',
  'confidence',
] as const;

/**
 * Primary measurement field for solar
 */
export const SOLAR_PRIMARY_FIELD = 'system_kw';

/**
 * Secondary measurement fields for solar
 */
export const SOLAR_SECONDARY_FIELDS = [
  'panel_count',
  'inverter_kw',
  'annual_production_kwh',
] as const;
