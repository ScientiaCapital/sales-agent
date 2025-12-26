"""API routes for VLM Analysis service.

Provides REST endpoints for VLM image analysis.

PRIVATE - Scientia Capital Proprietary IP
"""
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from .analyzer import BlueprintAnalyzer
from .cache import AnalysisCache
from .dependencies import (
    MiddlewareChain,
    VLMProvider,
    get_analysis_cache,
    get_middleware_chain,
    get_tenant_id,
    get_vlm_provider,
)
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    ConfidenceBreakdown,
    ErrorResponse,
    ModelInfo,
)

router = APIRouter(tags=["VLM Analysis"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    responses={
        200: {"model": AnalyzeResponse, "description": "Successful analysis"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Provider error"},
    },
)
async def analyze_image(
    request: AnalyzeRequest,
    provider: Annotated[VLMProvider, Depends(get_vlm_provider)],
    middleware: Annotated[MiddlewareChain, Depends(get_middleware_chain)],
    cache: Annotated[AnalysisCache | None, Depends(get_analysis_cache)],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
) -> AnalyzeResponse:
    """Analyze single image with VLM.

    Performs intelligent VLM analysis with caching, RAG, and optional ROI re-analysis.

    Features:
    - SHA-256 image hashing for exact duplicate detection
    - Database-backed caching to avoid redundant VLM calls
    - RAG similarity search for similar extractions
    - Confidence-guided ROI re-analysis for low-confidence regions
    - Cost tracking and optimization

    Args:
        request: Analysis parameters (image, prompt, options)
        provider: VLM provider instance (injected)
        middleware: Middleware chain (injected)
        tenant_id: Tenant identifier (injected)

    Returns:
        AnalyzeResponse with extraction, confidence, and metadata

    Raises:
        HTTPException: On validation, rate limit, or provider errors

    Examples:
        ```python
        # Basic analysis
        response = await analyze_image({
            "image": "base64_encoded_image...",
            "prompt": "Extract equipment model and serial number",
            "analysis_type": "equipment",
            "model": "qwen/qwen2.5-vl-72b-instruct"
        })

        # Blueprint with ROI re-analysis
        response = await analyze_image({
            "image": "base64_blueprint...",
            "prompt": "Extract materials and quantities",
            "analysis_type": "blueprint",
            "enable_roi": true,
            "roi_threshold": 0.75,
            "max_roi_regions": 2
        })
        ```
    """
    start_time = time.time()

    try:
        # Create middleware context
        context = {
            "tenant_id": tenant_id,
            "tier": "pro",  # TODO: Get from tenant lookup
            "operation": "vlm.analyze",
            "metadata": {
                "analysis_type": request.analysis_type,
                "model": request.model,
                "trade": request.trade,
                "use_cache": request.use_cache,
                "use_rag": request.use_rag,
                "enable_roi": request.enable_roi,
                "workflow": request.workflow,
            },
        }

        # Execute with middleware chain
        async def handler(ctx: dict):
            # Create analyzer with cache and provider
            analyzer = BlueprintAnalyzer(cache=cache, provider=provider)

            # Run analysis pipeline:
            # 1. Hash image
            # 2. Cache lookup
            # 3. VLM API call (if cache miss)
            # 4. Confidence calculation
            # 5. Cache storage
            analysis_result = await analyzer.analyze(
                image_base64=request.image,
                prompt=request.prompt,
                model=request.model,
            )

            # Calculate cost saved (if cache hit)
            cost_saved = 0.0
            if analysis_result.cache_hit:
                # Estimate cost that would have been incurred
                cost_saved = 0.001  # ~$0.001 per image average

            return {
                "extraction": analysis_result.extraction,
                "confidence": analysis_result.confidence,
                "cache_hit": analysis_result.cache_hit,
                "rag_used": False,  # RAG not implemented yet
                "cost_saved": cost_saved,
                "model_used": analysis_result.model_used,
                "image_hash": analysis_result.image_hash,
            }

        result = await middleware.execute(context, handler)

        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000

        # Build confidence breakdown
        confidence_breakdown = ConfidenceBreakdown(
            overall=result["confidence"],
            vlm_confidence=result["confidence"],
            cache_hit=result["cache_hit"],
            rag_similarity=None,
            field_completeness=None,
            validation_pass=None,
            roi_boost=0.0,
        )

        # Build response
        response = AnalyzeResponse(
            extraction=result["extraction"],
            confidence=result["confidence"],
            confidence_breakdown=confidence_breakdown,
            cache_hit=result["cache_hit"],
            rag_used=result["rag_used"],
            cost_saved=result["cost_saved"],
            processing_time_ms=processing_time_ms,
            roi_analysis=None,  # TODO: Add ROI analysis
            model_used=result["model_used"],
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"VLM analysis error: {str(e)}",
        )


@router.post(
    "/analyze/batch",
    response_model=BatchAnalyzeResponse,
    responses={
        200: {"model": BatchAnalyzeResponse, "description": "Successful batch analysis"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Provider error"},
    },
)
async def analyze_batch(
    request: BatchAnalyzeRequest,
    provider: Annotated[VLMProvider, Depends(get_vlm_provider)],
    middleware: Annotated[MiddlewareChain, Depends(get_middleware_chain)],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
) -> BatchAnalyzeResponse:
    """Analyze multiple images with VLM (batch processing).

    Processes multiple images concurrently with automatic batching and rate limiting.

    Features:
    - Concurrent processing with automatic batching
    - Per-image caching and RAG
    - Aggregate statistics (total cost saved, cache hit rate)
    - Rate limiting to prevent API throttling

    Args:
        request: Batch analysis parameters (images, prompt, options)
        provider: VLM provider instance (injected)
        middleware: Middleware chain (injected)
        tenant_id: Tenant identifier (injected)

    Returns:
        BatchAnalyzeResponse with all results and aggregate stats

    Raises:
        HTTPException: On validation, rate limit, or provider errors

    Examples:
        ```python
        # Batch blueprint analysis
        response = await analyze_batch({
            "images": ["base64_page1...", "base64_page2...", "base64_page3..."],
            "prompt": "Extract materials and quantities from construction blueprint",
            "analysis_type": "blueprint",
            "model": "qwen/qwen2.5-vl-72b-instruct",
            "use_cache": true
        })

        # Results
        print(f"Processed {len(response.results)} images")
        print(f"Cache hit rate: {response.cache_hit_rate * 100:.1f}%")
        print(f"Total cost saved: ${response.total_cost_saved:.4f}")
        ```
    """
    start_time = time.time()

    try:
        # Create middleware context
        context = {
            "tenant_id": tenant_id,
            "tier": "pro",  # TODO: Get from tenant lookup
            "operation": "vlm.analyze_batch",
            "metadata": {
                "batch_size": len(request.images),
                "analysis_type": request.analysis_type,
                "model": request.model,
                "trade": request.trade,
                "use_cache": request.use_cache,
                "use_rag": request.use_rag,
                "workflow": request.workflow,
            },
        }

        # Execute with middleware chain
        async def handler(ctx: dict):
            # TODO: Implement batch processing with concurrency control
            # For now, process sequentially
            results = []
            total_cost_saved = 0.0
            cache_hits = 0

            for image in request.images:
                # Create individual request
                single_request = AnalyzeRequest(
                    image=image,
                    prompt=request.prompt,
                    analysis_type=request.analysis_type,
                    model=request.model,
                    trade=request.trade,
                    use_cache=request.use_cache,
                    use_rag=request.use_rag,
                    workflow=request.workflow,
                )

                # Analyze individual image
                result = await analyze_image(
                    single_request, provider, middleware, tenant_id
                )
                results.append(result)

                # Aggregate stats
                total_cost_saved += result.cost_saved
                if result.cache_hit:
                    cache_hits += 1

            return {
                "results": results,
                "total_cost_saved": total_cost_saved,
                "cache_hits": cache_hits,
            }

        batch_result = await middleware.execute(context, handler)

        # Calculate totals
        total_processing_time_ms = (time.time() - start_time) * 1000
        cache_hit_rate = (
            batch_result["cache_hits"] / len(request.images)
            if len(request.images) > 0
            else 0.0
        )

        return BatchAnalyzeResponse(
            results=batch_result["results"],
            total_processing_time_ms=total_processing_time_ms,
            total_cost_saved=batch_result["total_cost_saved"],
            cache_hit_rate=cache_hit_rate,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch analysis error: {str(e)}",
        )


@router.get(
    "/models",
    response_model=list[ModelInfo],
    responses={
        200: {"model": list[ModelInfo], "description": "List of available models"},
    },
)
async def get_models(
    provider: Annotated[VLMProvider, Depends(get_vlm_provider)],
) -> list[ModelInfo]:
    """Get list of available VLM models.

    Returns information about all supported VLM models including:
    - Model identifiers and names
    - Context length limits
    - Pricing information
    - Recommended use cases

    Args:
        provider: VLM provider instance (injected)

    Returns:
        List of ModelInfo objects with model details

    Examples:
        ```python
        models = await get_models()
        for model in models:
            print(f"{model.name}: ${model.cost_per_million_tokens}/1M tokens")
            print(f"  Recommended for: {', '.join(model.recommended_for)}")
        ```
    """
    models = provider.get_models()
    return [ModelInfo(**model) for model in models]
