"""
System Report Templates

Pre-built report templates for common analytics use cases.
These templates can be loaded into the database on startup or via CLI command.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
import uuid

from app.models.report_template import ReportTemplate


# ============================================================================
# System Template Definitions
# ============================================================================

SYSTEM_TEMPLATES = [
    {
        "template_id": "system_lead_qualification_summary",
        "name": "Lead Qualification Summary",
        "description": "Summary of leads grouped by qualification status with average scores and counts. "
                       "Useful for understanding the distribution of leads across qualification stages.",
        "report_type": "lead_analysis",
        "query_config": {
            "table": "leads",
            "columns": ["status"],
            "aggregations": [
                {"function": "count", "column": "*", "alias": "total_leads"},
                {"function": "avg", "column": "qualification_score", "alias": "avg_score"},
                {"function": "min", "column": "qualification_score", "alias": "min_score"},
                {"function": "max", "column": "qualification_score", "alias": "max_score"}
            ],
            "filters": [],
            "group_by": ["status"],
            "order_by": [{"column": "status", "direction": "asc"}],
            "limit": 100
        },
        "visualization_config": {
            "chart_type": "bar",
            "x_axis": "status",
            "y_axis": "total_leads",
            "series": ["total_leads", "avg_score"]
        },
        "filter_config": {
            "available_filters": [
                {
                    "column": "status",
                    "label": "Status",
                    "type": "select",
                    "options": ["new", "contacted", "qualified", "unqualified", "converted"]
                },
                {
                    "column": "qualification_score",
                    "label": "Min Score",
                    "type": "number",
                    "operator": ">="
                }
            ]
        }
    },
    {
        "template_id": "system_campaign_performance",
        "name": "Campaign Performance Over Time",
        "description": "Time-series analysis of campaign metrics including messages sent, responses received, "
                       "and response rates. Track campaign effectiveness over time with daily granularity.",
        "report_type": "campaign_performance",
        "query_config": {
            "table": "analytics_campaign_metrics",
            "columns": ["campaign_id", "metric_date"],
            "aggregations": [
                {"function": "sum", "column": "messages_sent", "alias": "total_sent"},
                {"function": "sum", "column": "responses_received", "alias": "total_responses"},
                {"function": "avg", "column": "response_rate", "alias": "avg_response_rate"},
                {"function": "sum", "column": "conversions", "alias": "total_conversions"}
            ],
            "filters": [],
            "group_by": ["campaign_id", "metric_date"],
            "order_by": [
                {"column": "metric_date", "direction": "desc"},
                {"column": "campaign_id", "direction": "asc"}
            ],
            "limit": 500
        },
        "visualization_config": {
            "chart_type": "line",
            "x_axis": "metric_date",
            "y_axis": "total_sent",
            "series": ["total_sent", "total_responses", "total_conversions"]
        },
        "filter_config": {
            "available_filters": [
                {
                    "column": "campaign_id",
                    "label": "Campaign ID",
                    "type": "number",
                    "operator": "="
                },
                {
                    "column": "metric_date",
                    "label": "Start Date",
                    "type": "date",
                    "operator": ">="
                },
                {
                    "column": "metric_date",
                    "label": "End Date",
                    "type": "date",
                    "operator": "<="
                }
            ]
        }
    },
    {
        "template_id": "system_high_value_leads",
        "name": "High-Value Lead List",
        "description": "Detailed list of high-scoring leads (75+) that are qualified or contacted. "
                       "Sorted by qualification score descending for prioritized outreach.",
        "report_type": "lead_analysis",
        "query_config": {
            "table": "leads",
            "columns": ["id", "company_name", "email", "qualification_score", "status", "created_at"],
            "aggregations": [],
            "filters": [
                {"column": "qualification_score", "operator": ">=", "value": 75},
                {"column": "status", "operator": "in", "value": ["qualified", "contacted"]}
            ],
            "group_by": [],
            "order_by": [{"column": "qualification_score", "direction": "desc"}],
            "limit": 50
        },
        "visualization_config": {
            "chart_type": "table",
            "x_axis": None,
            "y_axis": None,
            "series": ["company_name", "email", "qualification_score", "status"]
        },
        "filter_config": {
            "available_filters": [
                {
                    "column": "qualification_score",
                    "label": "Min Score",
                    "type": "number",
                    "operator": ">=",
                    "default": 75
                },
                {
                    "column": "status",
                    "label": "Status",
                    "type": "multi-select",
                    "options": ["new", "contacted", "qualified", "unqualified", "converted"]
                },
                {
                    "column": "created_at",
                    "label": "Created After",
                    "type": "date",
                    "operator": ">="
                }
            ]
        }
    },
    {
        "template_id": "system_cost_breakdown",
        "name": "Cost Breakdown by Provider",
        "description": "Summary of API costs grouped by provider (Cerebras, DeepSeek, OpenAI, etc.) "
                       "with total spend, request counts, and average cost per request.",
        "report_type": "cost_summary",
        "query_config": {
            "table": "analytics_cost_tracking",
            "columns": ["provider"],
            "aggregations": [
                {"function": "sum", "column": "cost_usd", "alias": "total_cost"},
                {"function": "count", "column": "*", "alias": "total_requests"},
                {"function": "avg", "column": "cost_usd", "alias": "avg_cost_per_request"},
                {"function": "sum", "column": "tokens_used", "alias": "total_tokens"}
            ],
            "filters": [],
            "group_by": ["provider"],
            "order_by": [{"column": "total_cost", "direction": "desc"}],
            "limit": 50
        },
        "visualization_config": {
            "chart_type": "pie",
            "x_axis": "provider",
            "y_axis": "total_cost",
            "series": ["total_cost"]
        },
        "filter_config": {
            "available_filters": [
                {
                    "column": "provider",
                    "label": "Provider",
                    "type": "select",
                    "options": ["cerebras", "deepseek", "openai", "anthropic", "perplexity", "ollama"]
                },
                {
                    "column": "operation_type",
                    "label": "Operation Type",
                    "type": "select",
                    "options": ["qualification", "enrichment", "outreach", "research", "conversation"]
                },
                {
                    "column": "cost_usd",
                    "label": "Min Cost",
                    "type": "number",
                    "operator": ">="
                }
            ]
        }
    },
    {
        "template_id": "system_ab_test_summary",
        "name": "A/B Test Results Summary",
        "description": "Summary of all A/B tests with conversion rates, statistical significance, "
                       "and winner determination. Filter by status to see active or completed tests.",
        "report_type": "ab_test_results",
        "query_config": {
            "table": "analytics_ab_tests",
            "columns": [
                "test_id",
                "test_name",
                "status",
                "variant_a_name",
                "variant_b_name",
                "conversion_rate_a",
                "conversion_rate_b",
                "statistical_significance",
                "winner"
            ],
            "aggregations": [],
            "filters": [],
            "group_by": [],
            "order_by": [
                {"column": "start_date", "direction": "desc"}
            ],
            "limit": 100
        },
        "visualization_config": {
            "chart_type": "table",
            "x_axis": None,
            "y_axis": None,
            "series": ["test_name", "status", "conversion_rate_a", "conversion_rate_b", "winner"]
        },
        "filter_config": {
            "available_filters": [
                {
                    "column": "status",
                    "label": "Status",
                    "type": "select",
                    "options": ["draft", "running", "completed", "paused"]
                },
                {
                    "column": "test_type",
                    "label": "Test Type",
                    "type": "select",
                    "options": ["campaign", "agent_performance", "ui_element"]
                },
                {
                    "column": "statistical_significance",
                    "label": "Max P-Value",
                    "type": "number",
                    "operator": "<=",
                    "default": 0.05
                }
            ]
        }
    }
]


# ============================================================================
# System Template Management Functions
# ============================================================================

def load_system_templates(db: Session, overwrite: bool = False) -> Dict[str, Any]:
    """
    Load system templates into the database.

    Args:
        db: Database session
        overwrite: If True, update existing system templates. If False, skip existing.

    Returns:
        Dictionary with counts of created/updated/skipped templates
    """
    created = 0
    updated = 0
    skipped = 0

    for template_data in SYSTEM_TEMPLATES:
        # Check if template already exists
        existing = db.query(ReportTemplate).filter(
            ReportTemplate.template_id == template_data['template_id']
        ).first()

        if existing:
            if overwrite:
                # Update existing template
                existing.name = template_data['name']
                existing.description = template_data['description']
                existing.report_type = template_data['report_type']
                existing.query_config = template_data['query_config']
                existing.visualization_config = template_data['visualization_config']
                existing.filter_config = template_data['filter_config']
                updated += 1
            else:
                skipped += 1
                continue
        else:
            # Create new template
            new_template = ReportTemplate(
                template_id=template_data['template_id'],
                name=template_data['name'],
                description=template_data['description'],
                report_type=template_data['report_type'],
                query_config=template_data['query_config'],
                visualization_config=template_data['visualization_config'],
                filter_config=template_data['filter_config'],
                is_system_template=True,
                created_by="system"
            )
            db.add(new_template)
            created += 1

    db.commit()

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": len(SYSTEM_TEMPLATES)
    }


def get_system_template_by_id(template_id: str) -> Dict[str, Any] | None:
    """
    Get a system template definition by ID.

    Args:
        template_id: System template ID

    Returns:
        Template definition dictionary or None if not found
    """
    for template in SYSTEM_TEMPLATES:
        if template['template_id'] == template_id:
            return template
    return None


def list_system_template_ids() -> List[str]:
    """
    Get a list of all system template IDs.

    Returns:
        List of template IDs
    """
    return [t['template_id'] for t in SYSTEM_TEMPLATES]


# ============================================================================
# CLI Command (for manual seeding)
# ============================================================================

if __name__ == "__main__":
    """
    Standalone script to seed system templates.

    Usage:
        python -m app.services.analytics.system_templates
    """
    import sys
    from app.models.database import SessionLocal

    db = SessionLocal()
    try:
        print("Loading system report templates...")
        result = load_system_templates(db, overwrite=False)
        print(f"✅ Created: {result['created']}")
        print(f"⚠️  Updated: {result['updated']}")
        print(f"⏭️  Skipped: {result['skipped']}")
        print(f"📊 Total: {result['total']}")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        db.close()
