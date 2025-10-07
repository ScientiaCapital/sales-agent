"""
Audit logging middleware for capturing all API requests and security events.
Uses FastAPI background tasks for non-blocking database writes.
"""
import time
import uuid
import json
from typing import Optional, Callable
from fastapi import Request, Response, BackgroundTasks
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.models.security import SecurityEvent, EventType
from app.models.database import SessionLocal
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to capture all API requests for audit logging.
    Logs are written asynchronously using background tasks to avoid blocking.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process each request and log audit information.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/endpoint in the chain

        Returns:
            The HTTP response
        """
        # Generate unique request ID for tracing
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Capture request start time
        start_time = time.time()

        # Extract client information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        # Process the request
        try:
            response = await call_next(request)

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Schedule background task for audit logging
            if hasattr(request.app.state, "background_tasks"):
                background_tasks = request.app.state.background_tasks
            else:
                background_tasks = BackgroundTasks()

            # Log the request
            background_tasks.add_task(
                self._log_audit_event,
                request_id=request_id,
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                latency_ms=latency_ms,
                ip_address=client_ip,
                user_agent=user_agent,
                user_id=getattr(request.state, "user_id", None),
            )

            # Add request ID to response headers for tracing
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Log the error
            latency_ms = int((time.time() - start_time) * 1000)

            # Log error event
            if hasattr(request.app.state, "background_tasks"):
                background_tasks = request.app.state.background_tasks
            else:
                background_tasks = BackgroundTasks()

            background_tasks.add_task(
                self._log_audit_event,
                request_id=request_id,
                method=request.method,
                path=str(request.url.path),
                status_code=500,
                latency_ms=latency_ms,
                ip_address=client_ip,
                user_agent=user_agent,
                user_id=getattr(request.state, "user_id", None),
                event_type=EventType.API_ERROR,
                metadata={"error": str(e)},
            )

            # Re-raise the exception
            raise

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract the client's real IP address, considering proxy headers.

        Args:
            request: The HTTP request

        Returns:
            The client's IP address
        """
        # Check for proxy headers
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take the first IP in the chain
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct connection
        if request.client:
            return request.client.host

        return ""

    def _log_audit_event(
        self,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        latency_ms: int,
        ip_address: str,
        user_agent: str,
        user_id: Optional[int] = None,
        event_type: Optional[EventType] = None,
        metadata: Optional[dict] = None,
    ):
        """
        Log an audit event to the database.
        This runs in a background task to avoid blocking the response.

        Args:
            request_id: Unique request identifier
            method: HTTP method
            path: Request path
            status_code: HTTP response status code
            latency_ms: Request processing time in milliseconds
            ip_address: Client IP address
            user_agent: Client user agent string
            user_id: ID of the authenticated user (if any)
            event_type: Type of security event
            metadata: Additional context data
        """
        db = SessionLocal()
        try:
            # Determine event type based on path and method
            if event_type is None:
                event_type = self._determine_event_type(method, path, status_code)

            # Determine resource and action from path
            resource, action = self._parse_resource_action(method, path)

            # Build metadata
            event_metadata = metadata or {}
            event_metadata.update({
                "method": method,
                "path": path,
                "status_code": status_code,
                "latency_ms": latency_ms,
            })

            # Create audit log entry
            audit_event = SecurityEvent(
                event_type=event_type,
                user_id=user_id,
                resource=resource,
                action=action,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                request_method=method,
                request_path=path,
                status_code=status_code,
                latency_ms=latency_ms,
                metadata=event_metadata,
            )

            db.add(audit_event)
            db.commit()

            logger.debug(
                f"Audit logged: {event_type.value} - {method} {path} "
                f"[{status_code}] {latency_ms}ms"
            )

        except Exception as e:
            logger.error(f"Failed to log audit event: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    def _determine_event_type(self, method: str, path: str, status_code: int) -> EventType:
        """
        Determine the appropriate event type based on request details.

        Args:
            method: HTTP method
            path: Request path
            status_code: Response status code

        Returns:
            The appropriate EventType
        """
        # Authentication endpoints
        if "/auth/login" in path:
            return EventType.LOGIN_SUCCESS if status_code == 200 else EventType.LOGIN_FAILED
        elif "/auth/logout" in path:
            return EventType.LOGOUT
        elif "/auth/refresh" in path:
            return EventType.TOKEN_REFRESH

        # CRM endpoints
        elif "/crm/" in path or "/sync/" in path:
            return EventType.CRM_SYNC
        elif "/apollo/" in path or "/hubspot/" in path:
            return EventType.CRM_AUTH

        # GDPR endpoints
        elif "/gdpr/export" in path:
            return EventType.DATA_EXPORT_REQUESTED
        elif "/gdpr/delete" in path:
            return EventType.DATA_DELETION_REQUESTED
        elif "/gdpr/consent" in path:
            return EventType.CONSENT_GRANTED if method == "POST" else EventType.DATA_READ

        # Generic CRUD operations
        elif method == "POST":
            return EventType.DATA_CREATED
        elif method == "GET":
            return EventType.DATA_READ
        elif method in ["PUT", "PATCH"]:
            return EventType.DATA_UPDATED
        elif method == "DELETE":
            return EventType.DATA_DELETED

        # Default
        return EventType.DATA_READ

    def _parse_resource_action(self, method: str, path: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse the resource and action from the request.

        Args:
            method: HTTP method
            path: Request path

        Returns:
            Tuple of (resource, action)
        """
        # Parse resource from path
        path_parts = path.strip("/").split("/")

        # Skip 'api' and version prefix
        if path_parts and path_parts[0] == "api":
            path_parts = path_parts[1:]
        if path_parts and path_parts[0].startswith("v"):
            path_parts = path_parts[1:]

        # Get resource name
        resource = None
        if path_parts:
            resource = path_parts[0]
            # Add ID if present
            if len(path_parts) > 1 and path_parts[1].isdigit():
                resource = f"{resource}:{path_parts[1]}"

        # Map HTTP method to action
        action_map = {
            "GET": "read",
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete",
        }
        action = action_map.get(method, method.lower())

        return resource, action


class AuditLoggingRoute(APIRoute):
    """
    Custom APIRoute that logs specific security events for sensitive endpoints.
    Can be used for more granular control over audit logging.
    """

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            # Add any pre-processing here
            response = await original_route_handler(request)
            # Add any post-processing here
            return response

        return custom_route_handler


def log_security_event(
    event_type: EventType,
    user_id: Optional[int] = None,
    resource: Optional[str] = None,
    action: Optional[str] = None,
    metadata: Optional[dict] = None,
    request: Optional[Request] = None,
):
    """
    Utility function to manually log security events.
    Can be called from anywhere in the application.

    Args:
        event_type: Type of security event
        user_id: ID of the user involved
        resource: Resource being accessed
        action: Action being performed
        metadata: Additional context data
        request: The HTTP request (for extracting IP, user agent, etc.)
    """
    db = SessionLocal()
    try:
        # Extract request context if available
        ip_address = None
        user_agent = None
        request_id = None

        if request:
            # Get IP address
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                ip_address = forwarded.split(",")[0].strip()
            elif request.client:
                ip_address = request.client.host

            # Get user agent
            user_agent = request.headers.get("user-agent", "")

            # Get request ID
            request_id = getattr(request.state, "request_id", None)

        # Create audit event
        audit_event = SecurityEvent(
            event_type=event_type,
            user_id=user_id,
            resource=resource,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            metadata=metadata,
        )

        db.add(audit_event)
        db.commit()

        logger.info(
            f"Security event logged: {event_type.value} - "
            f"User: {user_id}, Resource: {resource}, Action: {action}"
        )

    except Exception as e:
        logger.error(f"Failed to log security event: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()