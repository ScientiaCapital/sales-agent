"""
Integration module for adding CostOptimizer to UnifiedRouter.

This module provides the patch to integrate budget enforcement into the
UnifiedRouter's route() method without modifying the core UnifiedRouter class.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException

from app.services.unified_router import UnifiedRouter, RoutingStrategy, ModelResponse
from app.services.cost_optimizer import CostOptimizer, BudgetStatus
from app.services.usage_tracker import UsageTracker
from app.models.database import Session

logger = logging.getLogger(__name__)


class CostOptimizedUnifiedRouter(UnifiedRouter):
    """
    Extended UnifiedRouter with integrated cost optimization and budget enforcement.

    This subclass adds budget checking and automatic strategy downgrade
    to the base UnifiedRouter functionality.
    """

    def __init__(
        self,
        cost_optimizer: Optional[CostOptimizer] = None,
        usage_tracker: Optional[UsageTracker] = None,
        db: Optional[Session] = None,
        redis_client: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize cost-optimized router.

        Args:
            cost_optimizer: CostOptimizer instance for budget enforcement
            usage_tracker: UsageTracker for cost tracking
            db: Database session for usage tracking
            redis_client: Redis client for caching
            **kwargs: Additional arguments for UnifiedRouter
        """
        super().__init__(**kwargs)

        # Initialize cost management components
        if cost_optimizer:
            self.cost_optimizer = cost_optimizer
        elif usage_tracker and redis_client:
            # Create CostOptimizer if not provided
            self.cost_optimizer = CostOptimizer(
                usage_tracker=usage_tracker,
                unified_router=self,
                redis_client=redis_client
            )
        else:
            self.cost_optimizer = None
            logger.warning("CostOptimizer not initialized - budget enforcement disabled")

        self.usage_tracker = usage_tracker
        self.db = db

        # Track current routing strategy
        self.strategy = RoutingStrategy.BALANCED  # Default strategy

    async def route(
        self,
        task_type,
        prompt: str,
        system_prompt: Optional[str] = None,
        strategy_override: Optional[RoutingStrategy] = None,
        max_latency_ms: Optional[int] = None,
        max_cost_usd: Optional[float] = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        user_id: Optional[str] = None
    ) -> ModelResponse:
        """
        Route request with budget enforcement and auto-downgrade.

        This method extends the base route() with:
        1. Budget status check before routing
        2. Automatic strategy downgrade at 90% utilization
        3. Request blocking at 100% budget
        4. Cost tracking and budget updates

        Args:
            task_type: Type of task
            prompt: User prompt
            system_prompt: Optional system prompt
            strategy_override: Override strategy selection
            max_latency_ms: Max latency constraint
            max_cost_usd: Max cost constraint
            temperature: Model temperature
            max_tokens: Max response tokens
            user_id: Optional user ID for user-specific budgets

        Returns:
            ModelResponse with result and metadata

        Raises:
            HTTPException: 429 if budget exceeded
        """
        # Use override strategy if provided, otherwise use current strategy
        effective_strategy = strategy_override or self.strategy

        # Check budget if CostOptimizer is available
        if self.cost_optimizer:
            try:
                # Check daily budget status
                budget_status = await self.cost_optimizer.check_budget_status(
                    user_id=user_id,
                    period="daily"
                )

                # Enforce budget rules
                new_strategy, allowed = await self.cost_optimizer.enforce_budget(
                    current_strategy=effective_strategy,
                    budget_status=budget_status
                )

                # Block if budget exceeded
                if not allowed:
                    logger.error(
                        f"Budget exceeded: {budget_status.utilization_percent}% utilization. "
                        f"Blocking request."
                    )
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "Daily budget exceeded",
                            "message": budget_status.recommended_action,
                            "budget_status": {
                                "current_spend_usd": budget_status.current_spend_usd,
                                "budget_limit_usd": budget_status.budget_limit_usd,
                                "utilization_percent": budget_status.utilization_percent
                            }
                        }
                    )

                # Update strategy if downgraded
                if new_strategy != effective_strategy:
                    logger.info(
                        f"Budget enforcement: Auto-downgraded routing strategy from "
                        f"{effective_strategy.value} to {new_strategy.value} "
                        f"(utilization: {budget_status.utilization_percent}%)"
                    )
                    effective_strategy = new_strategy
                    self.strategy = new_strategy  # Update current strategy

            except HTTPException:
                raise  # Re-raise HTTP exceptions
            except Exception as e:
                logger.error(f"Budget check failed: {e}. Proceeding with caution.")
                # Continue without budget enforcement on error

        # Call parent route method with effective strategy
        try:
            response = await super().route(
                task_type=task_type,
                prompt=prompt,
                system_prompt=system_prompt,
                strategy_override=effective_strategy,
                max_latency_ms=max_latency_ms,
                max_cost_usd=max_cost_usd,
                temperature=temperature,
                max_tokens=max_tokens
            )

            # Update budget spend if tracking is available
            if self.cost_optimizer and response.cost_usd > 0:
                try:
                    await self.cost_optimizer.update_spend(
                        cost_usd=response.cost_usd,
                        user_id=user_id,
                        provider=response.provider
                    )
                except Exception as e:
                    logger.error(f"Failed to update budget spend: {e}")

            return response

        except Exception as e:
            logger.error(f"Routing failed: {e}")
            raise

    async def get_budget_status(
        self,
        user_id: Optional[str] = None,
        period: str = "daily"
    ) -> Optional[BudgetStatus]:
        """
        Get current budget status.

        Args:
            user_id: Optional user ID
            period: Budget period ("daily" or "monthly")

        Returns:
            BudgetStatus or None if not available
        """
        if self.cost_optimizer:
            return await self.cost_optimizer.check_budget_status(
                user_id=user_id,
                period=period
            )
        return None

    def get_optimization_rules(self) -> Dict[str, Any]:
        """
        Get current optimization rules and settings.

        Returns:
            Dictionary of optimization rules
        """
        rules = {
            "current_strategy": self.strategy.value,
            "budget_enforcement": self.cost_optimizer is not None
        }

        if self.cost_optimizer:
            rules.update(self.cost_optimizer.get_optimization_rules())

        return rules


# Factory function for creating cost-optimized router
def create_cost_optimized_router(
    db: Session,
    redis_client: Any,
    enable_circuit_breakers: bool = True,
    enable_retry: bool = True
) -> CostOptimizedUnifiedRouter:
    """
    Create a UnifiedRouter with integrated cost optimization.

    Args:
        db: Database session
        redis_client: Redis client
        enable_circuit_breakers: Enable circuit breakers
        enable_retry: Enable retry logic

    Returns:
        CostOptimizedUnifiedRouter instance
    """
    # Create usage tracker
    usage_tracker = UsageTracker(db=db, redis_client=redis_client)

    # Create cost-optimized router
    router = CostOptimizedUnifiedRouter(
        usage_tracker=usage_tracker,
        db=db,
        redis_client=redis_client,
        enable_circuit_breakers=enable_circuit_breakers,
        enable_retry=enable_retry
    )

    logger.info("Created cost-optimized UnifiedRouter with budget enforcement")

    return router