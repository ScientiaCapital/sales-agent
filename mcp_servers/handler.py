"""RunPod Serverless Handler for Context7 MCP Server.

This handler wraps the FastAPI application for deployment to RunPod serverless.
It translates RunPod event format to FastAPI request format and routes accordingly.

Deployment:
    runpod deploy --endpoint-id <your-endpoint-id> --handler handler.py

Environment Variables:
    RUNPOD_API_KEY: RunPod API key for vLLM backend
    RUNPOD_VLLM_ENDPOINT_ID: RunPod vLLM endpoint ID
"""

import runpod
import json
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import FastAPI app
try:
    from context7_load_balancer import app, vllm_client
    from context7_load_balancer import ResearchRequest, ResearchResponse
except ImportError as e:
    logger.error(f"Failed to import FastAPI app: {e}")
    raise


def handler(event: Dict[str, Any]) -> Dict[str, Any]:
    """RunPod serverless handler for Context7 MCP server.
    
    Routes incoming RunPod events to appropriate FastAPI endpoints.
    
    Args:
        event: RunPod event dictionary with 'input' key containing request data
            Expected format:
            {
                "input": {
                    "path": "/ping" or "/v1/research",
                    "method": "GET" or "POST",
                    "body": {...}  # For POST requests
                }
            }
    
    Returns:
        Dictionary with response data
            {
                "status_code": 200,
                "body": {...}
            }
    """
    try:
        # Extract request data
        request_data = event.get('input', {})
        path = request_data.get('path', '/ping')
        method = request_data.get('method', 'GET')
        body = request_data.get('body', {})
        
        logger.info(f"Received {method} request for {path}")
        
        # Route to health check
        if path == '/ping' and method == 'GET':
            from datetime import datetime
            return {
                "status_code": 200,
                "body": {
                    "status": "healthy",
                    "service": "context7-mcp",
                    "timestamp": datetime.utcnow().isoformat(),
                    "vllm_configured": vllm_client is not None
                }
            }
        
        # Route to research endpoint
        elif path == '/v1/research' and method == 'POST':
            # Validate vLLM client
            if not vllm_client:
                return {
                    "status_code": 500,
                    "body": {
                        "detail": "RunPod vLLM backend not configured. Set RUNPOD_API_KEY and RUNPOD_VLLM_ENDPOINT_ID."
                    }
                }
            
            # Parse request body
            try:
                research_request = ResearchRequest(**body)
            except Exception as e:
                logger.error(f"Invalid request body: {e}")
                return {
                    "status_code": 400,
                    "body": {"detail": f"Invalid request: {str(e)}"}
                }
            
            # Process research query (synchronous wrapper for async call)
            import asyncio
            from datetime import datetime
            
            start_time = datetime.utcnow()
            
            try:
                # Run async vLLM call
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                response = loop.run_until_complete(
                    vllm_client.chat.completions.create(
                        model="meta-llama/Llama-3.1-8B",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a research assistant. Provide comprehensive, accurate answers based on the query."
                            },
                            {
                                "role": "user",
                                "content": f"Research query: {research_request.query}"
                            }
                        ],
                        max_tokens=research_request.max_tokens,
                        temperature=research_request.temperature,
                    )
                )
                
                loop.close()
                
                # Calculate latency
                end_time = datetime.utcnow()
                latency_ms = int((end_time - start_time).total_seconds() * 1000)
                
                # Extract result
                result_text = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else None
                
                logger.info(f"Research completed in {latency_ms}ms, tokens: {tokens_used}")
                
                return {
                    "status_code": 200,
                    "body": {
                        "result": result_text,
                        "model": response.model,
                        "tokens_used": tokens_used,
                        "latency_ms": latency_ms,
                        "timestamp": end_time.isoformat()
                    }
                }
                
            except Exception as e:
                logger.error(f"vLLM processing error: {e}")
                return {
                    "status_code": 503,
                    "body": {"detail": f"vLLM backend error: {str(e)}"}
                }
        
        # Route to root endpoint
        elif path == '/' and method == 'GET':
            return {
                "status_code": 200,
                "body": {
                    "service": "Context7 MCP Load Balancer",
                    "version": "1.0.0",
                    "status": "running",
                    "endpoints": {
                        "health": "/ping",
                        "research": "/v1/research",
                        "docs": "/docs"
                    }
                }
            }
        
        # Unknown endpoint
        else:
            return {
                "status_code": 404,
                "body": {"detail": f"Endpoint not found: {method} {path}"}
            }
    
    except Exception as e:
        logger.error(f"Handler error: {e}", exc_info=True)
        return {
            "status_code": 500,
            "body": {"detail": f"Internal server error: {str(e)}"}
        }


# Start RunPod serverless
if __name__ == "__main__":
    logger.info("Starting RunPod serverless handler...")
    runpod.serverless.start({"handler": handler})
