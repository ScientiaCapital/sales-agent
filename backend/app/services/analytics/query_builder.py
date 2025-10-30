"""
Query Builder Service

Provides safe, parameterized query construction for custom reports.
Uses SQLAlchemy Core to prevent SQL injection while enabling flexible reporting.

Security Features:
- Whitelist validation for tables, columns, operators, and aggregations
- Parameterized queries via SQLAlchemy Core (automatic escaping)
- Type checking and value validation
- No raw SQL execution
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from sqlalchemy import select, func, and_, or_, desc, asc, cast, String, Integer, Float, Date
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.models.lead import Lead
from app.models.campaign import Campaign, MessageTemplate, MessageVariantAnalytics
from app.models.analytics_models import (
    AnalyticsLeadMetrics,
    AnalyticsCampaignMetrics,
    AnalyticsCostTracking,
    AnalyticsABTest
)


logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Query execution result with metadata"""
    data: List[Dict[str, Any]]
    total_count: int
    execution_time_ms: float
    columns: List[str]


class QueryBuilderError(Exception):
    """Base exception for query builder errors"""
    pass


class QueryValidationError(QueryBuilderError):
    """Raised when query configuration is invalid"""
    pass


class QueryBuilder:
    """
    Safe query builder for custom analytics reports.

    Prevents SQL injection by:
    1. Whitelisting allowed tables and models
    2. Validating columns against model attributes
    3. Using SQLAlchemy Core for parameterized queries
    4. Type checking all user inputs
    """

    # Whitelist of allowed tables (maps logical name to SQLAlchemy model)
    ALLOWED_TABLES = {
        'leads': Lead,
        'campaigns': Campaign,
        'message_templates': MessageTemplate,
        'message_variant_analytics': MessageVariantAnalytics,
        'analytics_lead_metrics': AnalyticsLeadMetrics,
        'analytics_campaign_metrics': AnalyticsCampaignMetrics,
        'analytics_cost_tracking': AnalyticsCostTracking,
        'analytics_ab_tests': AnalyticsABTest,
    }

    # Whitelist of allowed SQL operators
    ALLOWED_OPERATORS = {
        '=': lambda col, val: col == val,
        '!=': lambda col, val: col != val,
        '>': lambda col, val: col > val,
        '>=': lambda col, val: col >= val,
        '<': lambda col, val: col < val,
        '<=': lambda col, val: col <= val,
        'in': lambda col, val: col.in_(val if isinstance(val, list) else [val]),
        'not_in': lambda col, val: ~col.in_(val if isinstance(val, list) else [val]),
        'like': lambda col, val: col.like(f"%{val}%"),
        'ilike': lambda col, val: col.ilike(f"%{val}%"),
        'is_null': lambda col, val: col.is_(None),
        'is_not_null': lambda col, val: col.isnot(None),
    }

    # Whitelist of allowed aggregation functions
    ALLOWED_AGGREGATIONS = {
        'count': func.count,
        'sum': func.sum,
        'avg': func.avg,
        'min': func.min,
        'max': func.max,
        'count_distinct': lambda col: func.count(func.distinct(col)),
    }

    def __init__(self, db: Session):
        """Initialize query builder with database session"""
        self.db = db

    def build_and_execute(self, query_config: Dict[str, Any]) -> QueryResult:
        """
        Build and execute a query from configuration.

        Args:
            query_config: Query configuration dictionary with:
                - table: Table name (required)
                - columns: List of column names (required)
                - filters: List of filter clauses (optional)
                - aggregations: List of aggregation specs (optional)
                - group_by: List of column names (optional)
                - order_by: List of order specs (optional)
                - limit: Max rows to return (optional)

        Returns:
            QueryResult with data and metadata

        Raises:
            QueryValidationError: If configuration is invalid
        """
        start_time = datetime.now()

        try:
            # Validate and build query
            query = self._build_query(query_config)

            # Execute query
            result = self.db.execute(query)
            rows = result.fetchall()

            # Convert to dictionaries
            columns = list(result.keys())
            data = [dict(zip(columns, row)) for row in rows]

            # Calculate execution time
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(f"Query executed successfully: {len(data)} rows in {execution_time_ms:.2f}ms")

            return QueryResult(
                data=data,
                total_count=len(data),
                execution_time_ms=execution_time_ms,
                columns=columns
            )

        except QueryValidationError:
            raise
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise QueryBuilderError(f"Query execution failed: {str(e)}")

    def _build_query(self, config: Dict[str, Any]) -> Select:
        """Build SQLAlchemy Core SELECT query from configuration"""

        # Validate required fields
        if 'table' not in config:
            raise QueryValidationError("Missing required field: table")
        if 'columns' not in config or not config['columns']:
            raise QueryValidationError("Missing required field: columns")

        # Get and validate table
        table_name = config['table']
        model = self._validate_table(table_name)

        # Build SELECT clause
        query = self._build_select_clause(model, config['columns'], config.get('aggregations', []))

        # Add WHERE filters
        if config.get('filters'):
            query = self._add_filters(query, model, config['filters'])

        # Add GROUP BY
        if config.get('group_by'):
            query = self._add_group_by(query, model, config['group_by'])

        # Add ORDER BY
        if config.get('order_by'):
            query = self._add_order_by(query, model, config['order_by'])

        # Add LIMIT
        if config.get('limit'):
            limit = config['limit']
            if not isinstance(limit, int) or limit < 1 or limit > 10000:
                raise QueryValidationError("Limit must be an integer between 1 and 10000")
            query = query.limit(limit)

        return query

    def _validate_table(self, table_name: str):
        """Validate table name against whitelist"""
        if table_name not in self.ALLOWED_TABLES:
            raise QueryValidationError(
                f"Invalid table: {table_name}. Allowed tables: {', '.join(self.ALLOWED_TABLES.keys())}"
            )
        return self.ALLOWED_TABLES[table_name]

    def _validate_column(self, model, column_name: str):
        """Validate column exists on model"""
        if not hasattr(model, column_name):
            raise QueryValidationError(
                f"Invalid column: {column_name} for table {model.__tablename__}"
            )
        return getattr(model, column_name)

    def _build_select_clause(self, model, columns: List[str], aggregations: List[Dict[str, str]]) -> Select:
        """Build SELECT clause with columns and aggregations"""
        select_items = []

        # Add regular columns
        for col_name in columns:
            col = self._validate_column(model, col_name)
            select_items.append(col.label(col_name))

        # Add aggregations
        for agg_spec in aggregations:
            agg_func_name = agg_spec.get('function')
            agg_column_name = agg_spec.get('column')
            agg_alias = agg_spec.get('alias', f"{agg_func_name}_{agg_column_name}")

            if agg_func_name not in self.ALLOWED_AGGREGATIONS:
                raise QueryValidationError(
                    f"Invalid aggregation: {agg_func_name}. "
                    f"Allowed: {', '.join(self.ALLOWED_AGGREGATIONS.keys())}"
                )

            # Special case: COUNT(*) doesn't need a column
            if agg_func_name == 'count' and agg_column_name == '*':
                select_items.append(func.count().label(agg_alias))
            else:
                agg_col = self._validate_column(model, agg_column_name)
                agg_func = self.ALLOWED_AGGREGATIONS[agg_func_name]
                select_items.append(agg_func(agg_col).label(agg_alias))

        return select(*select_items)

    def _add_filters(self, query: Select, model, filters: List[Dict[str, Any]]) -> Select:
        """Add WHERE clause with filters"""
        conditions = []

        for filter_spec in filters:
            column_name = filter_spec.get('column')
            operator = filter_spec.get('operator')
            value = filter_spec.get('value')

            # Validate operator
            if operator not in self.ALLOWED_OPERATORS:
                raise QueryValidationError(
                    f"Invalid operator: {operator}. "
                    f"Allowed: {', '.join(self.ALLOWED_OPERATORS.keys())}"
                )

            # Validate column
            col = self._validate_column(model, column_name)

            # Build condition using operator function
            op_func = self.ALLOWED_OPERATORS[operator]
            condition = op_func(col, value)
            conditions.append(condition)

        if conditions:
            query = query.where(and_(*conditions))

        return query

    def _add_group_by(self, query: Select, model, group_by_columns: List[str]) -> Select:
        """Add GROUP BY clause"""
        group_cols = []
        for col_name in group_by_columns:
            col = self._validate_column(model, col_name)
            group_cols.append(col)

        if group_cols:
            query = query.group_by(*group_cols)

        return query

    def _add_order_by(self, query: Select, model, order_specs: List[Dict[str, str]]) -> Select:
        """Add ORDER BY clause"""
        for order_spec in order_specs:
            column_name = order_spec.get('column')
            direction = order_spec.get('direction', 'asc').lower()

            if direction not in ['asc', 'desc']:
                raise QueryValidationError(f"Invalid sort direction: {direction}. Must be 'asc' or 'desc'")

            col = self._validate_column(model, column_name)

            if direction == 'desc':
                query = query.order_by(desc(col))
            else:
                query = query.order_by(asc(col))

        return query

    def validate_query_config(self, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate query configuration without executing.

        Returns:
            (is_valid, error_message)
        """
        try:
            self._build_query(config)
            return (True, None)
        except QueryValidationError as e:
            return (False, str(e))
        except Exception as e:
            return (False, f"Validation failed: {str(e)}")


# Example query configurations for testing
EXAMPLE_QUERIES = {
    'lead_qualification_summary': {
        'table': 'leads',
        'columns': ['status'],
        'aggregations': [
            {'function': 'count', 'column': '*', 'alias': 'total_leads'},
            {'function': 'avg', 'column': 'qualification_score', 'alias': 'avg_score'}
        ],
        'group_by': ['status'],
        'order_by': [{'column': 'status', 'direction': 'asc'}],
        'limit': 100
    },
    'campaign_performance': {
        'table': 'analytics_campaign_metrics',
        'columns': ['campaign_id', 'metric_date'],
        'aggregations': [
            {'function': 'sum', 'column': 'messages_sent', 'alias': 'total_sent'},
            {'function': 'sum', 'column': 'responses_received', 'alias': 'total_responses'},
            {'function': 'avg', 'column': 'response_rate', 'alias': 'avg_response_rate'}
        ],
        'filters': [
            {'column': 'metric_date', 'operator': '>=', 'value': '2025-01-01'}
        ],
        'group_by': ['campaign_id', 'metric_date'],
        'order_by': [{'column': 'metric_date', 'direction': 'desc'}],
        'limit': 500
    },
    'high_value_leads': {
        'table': 'leads',
        'columns': ['id', 'company_name', 'email', 'qualification_score', 'status'],
        'filters': [
            {'column': 'qualification_score', 'operator': '>=', 'value': 75},
            {'column': 'status', 'operator': 'in', 'value': ['qualified', 'contacted']}
        ],
        'order_by': [{'column': 'qualification_score', 'direction': 'desc'}],
        'limit': 50
    }
}
