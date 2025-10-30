"""
Metrics collection and aggregation service.

Provides business logic for querying and aggregating metrics from analytics tables.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_
from app.models.analytics_models import (
    AnalyticsSystemMetrics,
    AnalyticsLeadMetrics,
    AnalyticsCampaignMetrics
)
from app.models.agent_models import AgentExecution
from app.models.api_call import CerebrasAPICall
from app.core.cache import get_cache_manager
import logging

logger = logging.getLogger(__name__)


class MetricsService:
    """
    Service for collecting and querying metrics data.

    Provides methods for:
    - Agent execution metrics (latency, cost, success rate)
    - Cost tracking by AI provider
    - API endpoint performance
    - Business metrics (leads qualified, conversion rates)
    """

    def __init__(self, db: Session):
        """Initialize metrics service with database session."""
        self.db = db
        self.cache = get_cache_manager()

    def get_agent_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
        agent_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get agent execution metrics for date range.

        Args:
            start_date: Start of date range
            end_date: End of date range
            agent_type: Optional filter by specific agent type

        Returns:
            List of agent metrics grouped by agent_type and date
        """
        try:
            # Build query with optional agent_type filter
            query = (
                self.db.query(
                    AgentExecution.agent_type,
                    func.date(AgentExecution.created_at).label("date"),
                    func.count(AgentExecution.id).label("total_executions"),
                    func.sum(
                        case((AgentExecution.status == 'success', 1), else_=0)
                    ).label("successful_executions"),
                    func.sum(
                        case((AgentExecution.status == 'failed', 1), else_=0)
                    ).label("failed_executions"),
                    func.avg(AgentExecution.latency_ms).label("avg_latency_ms"),
                    func.min(AgentExecution.latency_ms).label("min_latency_ms"),
                    func.max(AgentExecution.latency_ms).label("max_latency_ms"),
                    func.sum(AgentExecution.cost_usd).label("total_cost_usd"),
                    func.avg(AgentExecution.cost_usd).label("avg_cost_usd")
                )
                .filter(
                    and_(
                        AgentExecution.created_at >= start_date,
                        AgentExecution.created_at <= end_date
                    )
                )
            )

            if agent_type:
                query = query.filter(AgentExecution.agent_type == agent_type)

            query = query.group_by(
                AgentExecution.agent_type,
                func.date(AgentExecution.created_at)
            ).order_by(
                func.date(AgentExecution.created_at).desc()
            )

            results = query.all()

            # Transform results to dict with success_rate calculation
            metrics = []
            for row in results:
                total = row.total_executions or 0
                successful = row.successful_executions or 0
                success_rate = successful / total if total > 0 else 0.0

                metrics.append({
                    "agent_type": row.agent_type,
                    "date": row.date,
                    "total_executions": total,
                    "successful_executions": successful,
                    "failed_executions": row.failed_executions or 0,
                    "avg_latency_ms": float(row.avg_latency_ms or 0),
                    "min_latency_ms": float(row.min_latency_ms) if row.min_latency_ms else None,
                    "max_latency_ms": float(row.max_latency_ms) if row.max_latency_ms else None,
                    "total_cost_usd": float(row.total_cost_usd or 0),
                    "avg_cost_usd": float(row.avg_cost_usd or 0),
                    "success_rate": success_rate
                })

            logger.info(f"Retrieved {len(metrics)} agent metric records")
            return metrics

        except Exception as e:
            logger.error(f"Error fetching agent metrics: {e}", exc_info=True)
            raise

    def get_cost_by_provider(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get cost metrics by AI provider.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of cost metrics by provider and date
        """
        try:
            # Query Cerebras API calls
            cerebras_query = (
                self.db.query(
                    func.date(CerebrasAPICall.created_at).label("date"),
                    func.count(CerebrasAPICall.id).label("total_calls"),
                    func.sum(CerebrasAPICall.total_tokens).label("total_tokens"),
                    func.sum(CerebrasAPICall.cost_usd).label("total_cost_usd"),
                    func.avg(CerebrasAPICall.latency_ms).label("avg_latency_ms")
                )
                .filter(
                    and_(
                        CerebrasAPICall.created_at >= start_date,
                        CerebrasAPICall.created_at <= end_date,
                        CerebrasAPICall.success == True
                    )
                )
                .group_by(func.date(CerebrasAPICall.created_at))
                .all()
            )

            # Transform results
            metrics = []
            for row in cerebras_query:
                metrics.append({
                    "provider": "cerebras",
                    "date": row.date,
                    "total_calls": row.total_calls or 0,
                    "total_tokens": row.total_tokens or 0,
                    "total_cost_usd": float(row.total_cost_usd or 0),
                    "avg_latency_ms": float(row.avg_latency_ms or 0)
                })

            # Query AgentExecution for other providers (Claude, DeepSeek, etc.)
            provider_query = (
                self.db.query(
                    AgentExecution.model_used,
                    func.date(AgentExecution.created_at).label("date"),
                    func.count(AgentExecution.id).label("total_calls"),
                    func.sum(
                        AgentExecution.prompt_tokens + AgentExecution.completion_tokens
                    ).label("total_tokens"),
                    func.sum(AgentExecution.cost_usd).label("total_cost_usd"),
                    func.avg(AgentExecution.latency_ms).label("avg_latency_ms")
                )
                .filter(
                    and_(
                        AgentExecution.created_at >= start_date,
                        AgentExecution.created_at <= end_date,
                        AgentExecution.model_used.isnot(None),
                        AgentExecution.status == 'success'
                    )
                )
                .group_by(AgentExecution.model_used, func.date(AgentExecution.created_at))
                .all()
            )

            # Map model names to providers
            for row in provider_query:
                model_name = row.model_used or ""
                provider = "unknown"

                if "claude" in model_name.lower():
                    provider = "claude"
                elif "deepseek" in model_name.lower():
                    provider = "deepseek"
                elif "llama" in model_name.lower() and "cerebras" not in model_name.lower():
                    provider = "ollama"
                elif "gpt" in model_name.lower():
                    provider = "openai"

                metrics.append({
                    "provider": provider,
                    "date": row.date,
                    "total_calls": row.total_calls or 0,
                    "total_tokens": row.total_tokens or 0,
                    "total_cost_usd": float(row.total_cost_usd or 0),
                    "avg_latency_ms": float(row.avg_latency_ms or 0)
                })

            logger.info(f"Retrieved {len(metrics)} provider cost metric records")
            return metrics

        except Exception as e:
            logger.error(f"Error fetching cost metrics by provider: {e}", exc_info=True)
            raise

    def get_metrics_summary(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get comprehensive metrics summary for dashboard.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Dict with summary metrics for all categories
        """
        try:
            # Check cache first
            cache_key = f"metrics_summary:{start_date.date()}:{end_date.date()}"
            cached_result = self.cache.get(cache_key)
            if cached_result:
                logger.debug("Returning cached metrics summary")
                return cached_result

            # Agent execution summary
            agent_stats = (
                self.db.query(
                    func.count(AgentExecution.id).label("total_executions"),
                    func.sum(
                        case((AgentExecution.status == 'success', 1), else_=0)
                    ).label("successful_executions"),
                    func.avg(AgentExecution.latency_ms).label("avg_latency_ms"),
                    func.sum(AgentExecution.cost_usd).label("total_cost_usd")
                )
                .filter(
                    and_(
                        AgentExecution.created_at >= start_date,
                        AgentExecution.created_at <= end_date
                    )
                )
                .first()
            )

            total_agent_executions = agent_stats.total_executions or 0
            successful_agent_executions = agent_stats.successful_executions or 0
            agent_success_rate = (
                successful_agent_executions / total_agent_executions
                if total_agent_executions > 0 else 0.0
            )

            # Cost by provider
            cost_by_provider = {}
            provider_costs = self.get_cost_by_provider(start_date, end_date)
            for cost_entry in provider_costs:
                provider = cost_entry["provider"]
                if provider not in cost_by_provider:
                    cost_by_provider[provider] = 0.0
                cost_by_provider[provider] += cost_entry["total_cost_usd"]

            # Lead metrics
            lead_stats = (
                self.db.query(
                    func.count(AnalyticsLeadMetrics.id).label("leads_processed"),
                    func.sum(
                        case((AnalyticsLeadMetrics.qualification_tier.in_(['A', 'B']), 1), else_=0)
                    ).label("leads_qualified")
                )
                .filter(
                    and_(
                        AnalyticsLeadMetrics.created_at >= start_date,
                        AnalyticsLeadMetrics.created_at <= end_date
                    )
                )
                .first()
            )

            leads_processed = lead_stats.leads_processed or 0
            leads_qualified = lead_stats.leads_qualified or 0
            qualification_rate = (
                leads_qualified / leads_processed
                if leads_processed > 0 else 0.0
            )

            # Build summary
            summary = {
                "period_start": start_date,
                "period_end": end_date,

                # API performance (placeholder - would need HTTP metrics)
                "total_api_requests": 0,
                "avg_response_time_ms": 0.0,
                "error_rate": 0.0,

                # Agent performance
                "total_agent_executions": total_agent_executions,
                "agent_success_rate": agent_success_rate,
                "avg_agent_latency_ms": float(agent_stats.avg_latency_ms or 0),

                # Cost tracking
                "total_cost_usd": float(agent_stats.total_cost_usd or 0),
                "cost_by_provider": cost_by_provider,

                # Business metrics
                "leads_processed": leads_processed,
                "leads_qualified": leads_qualified,
                "qualification_rate": qualification_rate
            }

            # Cache for 5 minutes
            self.cache.set(cache_key, summary, ttl=300)

            logger.info("Generated metrics summary")
            return summary

        except Exception as e:
            logger.error(f"Error generating metrics summary: {e}", exc_info=True)
            raise

    def track_system_metric(
        self,
        metric_name: str,
        metric_value: float,
        metric_unit: str,
        category: str,
        subcategory: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None,
        agent_type: Optional[str] = None,
        endpoint: Optional[str] = None
    ) -> AnalyticsSystemMetrics:
        """
        Track a system-level metric.

        Args:
            metric_name: Name of the metric (e.g., "response_time")
            metric_value: Numeric value of the metric
            metric_unit: Unit of measurement (ms, %, count, etc.)
            category: Category (performance, error, resource, business)
            subcategory: Optional subcategory (api, database, redis, etc.)
            tags: Optional additional context tags
            agent_type: Optional agent type if metric is agent-specific
            endpoint: Optional endpoint path if metric is endpoint-specific

        Returns:
            Created AnalyticsSystemMetrics record
        """
        try:
            metric = AnalyticsSystemMetrics(
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=metric_unit,
                category=category,
                subcategory=subcategory,
                tags=tags,
                agent_type=agent_type,
                endpoint=endpoint,
                recorded_at=datetime.utcnow()
            )

            self.db.add(metric)
            self.db.commit()
            self.db.refresh(metric)

            logger.debug(f"Tracked system metric: {metric_name}={metric_value}{metric_unit}")
            return metric

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error tracking system metric: {e}", exc_info=True)
            raise
