"""
Content module - bridges GTME playbooks to agent systems.

Two modes of operation:
1. File-based: Load directly from coperniq-forge markdown files (local dev)
2. Supabase-backed: Query from dim_gtme_* tables (production)

Workflow:
1. Edit content in coperniq-forge/05-gtme-motions/ (human-readable markdown)
2. Run sync: python -m app.content.gtme_supabase_sync
3. Agents query Supabase for latest content

Tables (Dimensions):
- dim_gtme_sequences: Email/SMS sequences
- dim_gtme_campaigns: Campaign strategies
- dim_gtme_scripts: Phone scripts
- dim_gtme_resources: Value-add content
- dim_gtme_prospects: Flagship prospect research

Tables (Facts):
- fact_gtme_touches: Outreach telemetry (which content converted)

Features:
- Telemetry: Track touches, update outcomes, analyze performance
- Routing: Route prospects to sequences based on pain patterns
- Discovery: Pull discovery questions to power enrichment workflows
"""

# File-based loader (local dev, fallback)
from .gtme_loader import (
    GTMEContentLoader,
    EmailSequence,
    SequenceStep,
    get_sequence_for_engine as get_sequence_from_file,
    list_available_sequences as list_sequences_from_files,
    get_personalization_context,
)

# Supabase sync (content deployment)
from .gtme_supabase_sync import GTMESupabaseSync

# Supabase queries (production - agents use these)
from .gtme_queries import (
    GTMEQueries,
    get_sequence,
    get_sequence_for_engine,
    get_phone_script,
    get_cold_opener,
    get_campaign,
    get_objection_handling,
    get_resource_content,
    get_call_context,
)

# Telemetry (track outreach, analyze performance)
from .gtme_telemetry import (
    GTMETelemetry,
    record_touch,
    update_outcome,
    get_sequence_performance,
    get_meeting_attribution,
)

# Routing (route prospects based on pain patterns)
from .gtme_routing import (
    GTMERouter,
    get_discovery_questions,
    recommend_sequence,
    get_personalized_opener,
    route_batch,
)

__all__ = [
    # File-based
    "GTMEContentLoader",
    "EmailSequence",
    "SequenceStep",
    "get_sequence_from_file",
    "list_sequences_from_files",
    "get_personalization_context",
    # Supabase sync
    "GTMESupabaseSync",
    # Supabase queries (primary for agents)
    "GTMEQueries",
    "get_sequence",
    "get_sequence_for_engine",
    "get_phone_script",
    "get_cold_opener",
    "get_campaign",
    "get_objection_handling",
    "get_resource_content",
    "get_call_context",
    # Telemetry (track outreach)
    "GTMETelemetry",
    "record_touch",
    "update_outcome",
    "get_sequence_performance",
    "get_meeting_attribution",
    # Routing (pain-based sequence selection)
    "GTMERouter",
    "get_discovery_questions",
    "recommend_sequence",
    "get_personalized_opener",
    "route_batch",
]
