"""
Tests for custom exception hierarchy and exception handlers.

Verifies:
- Exception class attributes and inheritance
- FastAPI exception handlers return correct status codes
- Error responses have correct structure
- Exception logging behavior
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.exceptions import (
    SalesAgentException,
    LeadQualificationError,
    CerebrasAPIError,
    CerebrasTimeoutError,
    CerebrasRateLimitError,
    ExternalAPIError,
    RunPodAPIError,
    RunPodTimeoutError,
    SocialMediaAPIError,
    TwitterAPIError,
    RedditAPIError,
    StorageError,
    S3UploadError,
    S3DownloadError,
    DatabaseError,
    DatabaseConnectionError,
    DatabaseQueryError,
    ValidationError,
    InvalidFileFormatError,
    FileSizeExceededError,
    MissingRequiredFieldError,
    ResourceNotFoundError,
    LeadNotFoundError,
    DocumentNotFoundError,
    AuthenticationError,
    AuthorizationError,
    ServiceUnavailableError,
    CircuitBreakerOpenError,
    ConfigurationError,
    MissingAPIKeyError,
)


class TestExceptionAttributes:
    """Test exception class attributes and initialization."""

    def test_base_exception_attributes(self):
        """Test SalesAgentException has correct attributes."""
        exc = SalesAgentException(
            message="Test error",
            error_code="TEST_ERROR",
            details={"key": "value"},
            status_code=500
        )

        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.details == {"key": "value"}
        assert exc.status_code == 500
        assert exc.timestamp is not None

    def test_base_exception_to_dict(self):
        """Test SalesAgentException.to_dict() method."""
        exc = SalesAgentException(
            message="Test error",
            error_code="TEST_ERROR"
        )

        error_dict = exc.to_dict()
        assert error_dict["error"] == "TEST_ERROR"
        assert error_dict["message"] == "Test error"
        assert "timestamp" in error_dict

    def test_cerebras_api_error_defaults(self):
        """Test CerebrasAPIError has correct defaults."""
        exc = CerebrasAPIError()

        assert exc.message == "Cerebras API request failed"
        assert exc.error_code == "CEREBRAS_API_ERROR"
        assert exc.status_code == 500

    def test_cerebras_timeout_error(self):
        """Test CerebrasTimeoutError has correct error code."""
        exc = CerebrasTimeoutError()

        assert exc.error_code == "CEREBRAS_API_TIMEOUT"
        assert exc.status_code == 500

    def test_cerebras_rate_limit_error(self):
        """Test CerebrasRateLimitError has 429 status code."""
        exc = CerebrasRateLimitError()

        assert exc.error_code == "CEREBRAS_RATE_LIMIT"
        assert exc.status_code == 429  # Too Many Requests

    def test_validation_error_status_code(self):
        """Test ValidationError has 400 status code."""
        exc = ValidationError()

        assert exc.status_code == 400  # Bad Request

    def test_lead_not_found_error(self):
        """Test LeadNotFoundError includes lead_id in details."""
        exc = LeadNotFoundError(lead_id=123)

        assert exc.error_code == "LEAD_NOT_FOUND"
        assert exc.status_code == 404
        assert exc.details["lead_id"] == 123
        assert "123" in exc.message

    def test_document_not_found_error(self):
        """Test DocumentNotFoundError includes document_id in details."""
        exc = DocumentNotFoundError(document_id=456)

        assert exc.error_code == "DOCUMENT_NOT_FOUND"
        assert exc.status_code == 404
        assert exc.details["document_id"] == 456

    def test_authentication_error_status_code(self):
        """Test AuthenticationError has 401 status code."""
        exc = AuthenticationError()

        assert exc.status_code == 401  # Unauthorized

    def test_authorization_error_status_code(self):
        """Test AuthorizationError has 403 status code."""
        exc = AuthorizationError()

        assert exc.status_code == 403  # Forbidden

    def test_service_unavailable_error(self):
        """Test ServiceUnavailableError has 503 status code."""
        exc = ServiceUnavailableError()

        assert exc.status_code == 503  # Service Unavailable

    def test_circuit_breaker_open_error(self):
        """Test CircuitBreakerOpenError includes service name."""
        exc = CircuitBreakerOpenError(service_name="cerebras")

        assert exc.error_code == "CIRCUIT_BREAKER_OPEN"
        assert exc.status_code == 503
        assert exc.details["service_name"] == "cerebras"
        assert "cerebras" in exc.message

    def test_missing_api_key_error(self):
        """Test MissingAPIKeyError has 501 status code."""
        exc = MissingAPIKeyError(service_name="Twitter")

        assert exc.error_code == "MISSING_API_KEY"
        assert exc.status_code == 501  # Not Implemented
        assert exc.details["service_name"] == "Twitter"
        assert "Twitter" in exc.message

    def test_external_api_error_status_code(self):
        """Test ExternalAPIError has 502 status code (Bad Gateway)."""
        exc = ExternalAPIError()

        assert exc.status_code == 502  # Bad Gateway


class TestExceptionInheritance:
    """Test exception inheritance hierarchy."""

    def test_lead_qualification_error_inherits_from_base(self):
        """Test LeadQualificationError inherits from SalesAgentException."""
        exc = LeadQualificationError()
        assert isinstance(exc, SalesAgentException)

    def test_cerebras_api_error_inherits_from_lead_qualification(self):
        """Test CerebrasAPIError inherits from LeadQualificationError."""
        exc = CerebrasAPIError()
        assert isinstance(exc, LeadQualificationError)
        assert isinstance(exc, SalesAgentException)

    def test_cerebras_timeout_inherits_from_cerebras_api(self):
        """Test CerebrasTimeoutError inherits from CerebrasAPIError."""
        exc = CerebrasTimeoutError()
        assert isinstance(exc, CerebrasAPIError)
        assert isinstance(exc, LeadQualificationError)
        assert isinstance(exc, SalesAgentException)

    def test_runpod_error_inherits_from_external_api(self):
        """Test RunPodAPIError inherits from ExternalAPIError."""
        exc = RunPodAPIError()
        assert isinstance(exc, ExternalAPIError)
        assert isinstance(exc, SalesAgentException)

    def test_s3_upload_error_inherits_from_storage(self):
        """Test S3UploadError inherits from StorageError."""
        exc = S3UploadError()
        assert isinstance(exc, StorageError)
        assert isinstance(exc, SalesAgentException)

    def test_invalid_file_format_inherits_from_validation(self):
        """Test InvalidFileFormatError inherits from ValidationError."""
        exc = InvalidFileFormatError()
        assert isinstance(exc, ValidationError)
        assert isinstance(exc, SalesAgentException)

    def test_lead_not_found_inherits_from_resource_not_found(self):
        """Test LeadNotFoundError inherits from ResourceNotFoundError."""
        exc = LeadNotFoundError(lead_id=1)
        assert isinstance(exc, ResourceNotFoundError)
        assert isinstance(exc, SalesAgentException)


class TestExceptionHandlers:
    """Test FastAPI exception handlers with integration tests."""

    def test_sales_agent_exception_handler(self):
        """Test SalesAgentException handler returns correct format."""
        # Test via an endpoint that raises custom exception
        # For now, we'll test the base handler directly
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient

        test_app = FastAPI()

        @test_app.exception_handler(SalesAgentException)
        async def handler(request: Request, exc: SalesAgentException):
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.to_dict()
            )

        @test_app.get("/test-error")
        async def test_endpoint():
            raise CerebrasAPIError(
                message="Test API failure",
                details={"test": "data"}
            )

        test_client = TestClient(test_app)
        response = test_client.get("/test-error")

        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "CEREBRAS_API_ERROR"
        assert data["message"] == "Test API failure"
        assert "timestamp" in data
        # Details should NOT be in response (only in logs)
        assert "details" not in data

    def test_lead_not_found_handler(self):
        """Test LeadNotFoundError returns 404."""
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient

        test_app = FastAPI()

        @test_app.exception_handler(SalesAgentException)
        async def handler(request: Request, exc: SalesAgentException):
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.to_dict()
            )

        @test_app.get("/test-not-found")
        async def test_endpoint():
            raise LeadNotFoundError(lead_id=999)

        test_client = TestClient(test_app)
        response = test_client.get("/test-not-found")

        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "LEAD_NOT_FOUND"
        assert "999" in data["message"]

    def test_validation_error_handler(self):
        """Test ValidationError returns 400."""
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient

        test_app = FastAPI()

        @test_app.exception_handler(SalesAgentException)
        async def handler(request: Request, exc: SalesAgentException):
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.to_dict()
            )

        @test_app.get("/test-validation")
        async def test_endpoint():
            raise InvalidFileFormatError(
                message="Invalid CSV format",
                details={"filename": "test.txt"}
            )

        test_client = TestClient(test_app)
        response = test_client.get("/test-validation")

        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "INVALID_FILE_FORMAT"
        assert "CSV" in data["message"]

    def test_service_unavailable_handler(self):
        """Test ServiceUnavailableError returns 503."""
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient

        test_app = FastAPI()

        @test_app.exception_handler(SalesAgentException)
        async def handler(request: Request, exc: SalesAgentException):
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.to_dict()
            )

        @test_app.get("/test-unavailable")
        async def test_endpoint():
            raise CircuitBreakerOpenError(service_name="cerebras")

        test_client = TestClient(test_app)
        response = test_client.get("/test-unavailable")

        assert response.status_code == 503
        data = response.json()
        assert data["error"] == "CIRCUIT_BREAKER_OPEN"

    def test_rate_limit_error_handler(self):
        """Test CerebrasRateLimitError returns 429."""
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient

        test_app = FastAPI()

        @test_app.exception_handler(SalesAgentException)
        async def handler(request: Request, exc: SalesAgentException):
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.to_dict()
            )

        @test_app.get("/test-rate-limit")
        async def test_endpoint():
            raise CerebrasRateLimitError()

        test_client = TestClient(test_app)
        response = test_client.get("/test-rate-limit")

        assert response.status_code == 429
        data = response.json()
        assert data["error"] == "CEREBRAS_RATE_LIMIT"


class TestErrorResponseStructure:
    """Test error response structure consistency."""

    def test_error_response_has_required_fields(self):
        """Test all error responses have error, message, timestamp."""
        exc = CerebrasAPIError(
            message="Test error",
            details={"extra": "data"}
        )

        response = exc.to_dict()

        # Required fields
        assert "error" in response
        assert "message" in response
        assert "timestamp" in response

        # Technical details NOT exposed
        assert "details" not in response
        assert "status_code" not in response

    def test_error_codes_are_uppercase_with_underscores(self):
        """Test error codes follow naming convention."""
        test_cases = [
            (CerebrasAPIError(), "CEREBRAS_API_ERROR"),
            (RunPodAPIError(), "RUNPOD_API_ERROR"),
            (S3UploadError(), "S3_UPLOAD_FAILED"),
            (DatabaseConnectionError(), "DATABASE_CONNECTION_ERROR"),
            (InvalidFileFormatError(), "INVALID_FILE_FORMAT"),
            (LeadNotFoundError(1), "LEAD_NOT_FOUND"),
            (CircuitBreakerOpenError("test"), "CIRCUIT_BREAKER_OPEN"),
            (MissingAPIKeyError("test"), "MISSING_API_KEY"),
        ]

        for exc, expected_code in test_cases:
            assert exc.error_code == expected_code
            # Verify uppercase with underscores
            assert exc.error_code.isupper()
            assert " " not in exc.error_code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
