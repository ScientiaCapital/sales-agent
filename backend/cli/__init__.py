"""
CLI Module for Drop-In Enrichment

Terminal-based enrichment command for the sales agent platform.
Supports multiple input types with automatic Close CRM deduplication.

Usage:
    python -m cli.enrich "https://acme-hvac.com"
    python -m cli.enrich "Acme HVAC" --type name
    python -m cli.enrich "lead_abc123" --type close_id
"""

__version__ = "1.0.0"
