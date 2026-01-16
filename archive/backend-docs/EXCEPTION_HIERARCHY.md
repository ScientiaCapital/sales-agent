# Exception Hierarchy Documentation

## Overview

The Sales Agent platform uses a custom exception hierarchy to provide structured error handling across the entire application. All custom exceptions inherit from `SalesAgentException` and include:

- **Error codes**: Machine-readable error identifiers
- **HTTP status codes**: Automatic mapping for API responses
- **Context data**: Additional debugging information
- **JSON serialization**: Direct conversion for API error responses

## Exception Hierarchy

```
SalesAgentException (base)
├── LeadException
│   ├── LeadValidationError (400)
│   ├── LeadNotFoundError (404)
│   └── LeadQualificationError (500)
├── CRMException (from app.services.crm.base)
│   ├── CRMAuthenticationError (401)
│   ├── CRMRateLimitError (429)
│   ├── CRMNotFoundError (404)
│   ├── CRMValidationError (422)
│   ├── CRMNetworkError (502)
│   └── CRMWebhookError (400)
├── VoiceException
│   ├── CartesiaAPIError (502)
│   ├── VoiceGenerationError (500)
│   ├── AudioProcessingError (500)
│   └── VoiceSessionNotFoundError (404)
├── DocumentException
│   ├── PDFProcessingError (500)
│   ├── DocumentParsingError (422)
│   ├── DocumentNotFoundError (404)
│   ├── UnsupportedDocumentTypeError (400)
│   └── DocumentTooLargeError (413)
├── ExternalAPIException
│   ├── APIConnectionError (502)
│   ├── APIRateLimitError (429)
│   ├── APIAuthenticationError (401)
│   └── APITimeoutError (504)
├── ConfigurationError (500)
│   └── MissingAPIKeyError (500)
├── ValidationError (400)
│   └── InvalidInputError (400)
├── ResourceNotFoundError (404)
└── ResourceConflictError (409)
```

## Usage Examples

### Basic Exception Usage

```python
from app.core.exceptions import LeadNotFoundError

# Raise exception with context
raise LeadNotFoundError(
    f"Lead {lead_id} not found",
    context={"lead_id": lead_id}
)
```

### Exception with Retry Information

```python
from app.core.exceptions import APIRateLimitError

raise APIRateLimitError(
    "Rate limit exceeded",
    context={"api": "OpenAI"},
    retry_after=60  # Seconds until rate limit resets
)
```

### Exception Handling in Routes

```python
from fastapi import APIRouter
from app.core.exceptions import LeadNotFoundError

@router.get("/leads/{lead_id}")
async def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise LeadNotFoundError(
            f"Lead {lead_id} not found",
            context={"lead_id": lead_id}
        )
    return lead
```

### Catching Specific Exceptions

```python
from app.core.exceptions import VoiceSessionNotFoundError, VoiceException

try:
    session = await voice_agent.get_session(session_id)
except VoiceSessionNotFoundError as e:
    logger.warning(f"Session not found: {e.context}")
    # Handle missing session
except VoiceException as e:
    logger.error(f"Voice error: {e}")
    # Handle general voice errors
```

## Exception Attributes

### All Exceptions Include

- **message** (str): Human-readable error message
- **error_code** (str): Machine-readable error code (e.g., "LEAD_NOT_FOUND")
- **status_code** (int): HTTP status code for API responses
- **context** (Dict[str, Any]): Additional context data

### Special Attributes

- **APIRateLimitError.retry_after** (int): Seconds until rate limit resets
- **CRMRateLimitError.retry_after** (int): Seconds until CRM rate limit resets

## Exception Methods

### to_dict()

Convert exception to dictionary for JSON serialization:

```python
exc = LeadNotFoundError("Lead not found", context={"lead_id": 123})
result = exc.to_dict()
# Returns:
# {
#     "error": {
#         "code": "LEAD_NOT_FOUND",
#         "message": "Lead not found",
#         "context": {"lead_id": 123}
#     }
# }
```

### __str__()

String representation for logging:

```python
exc = LeadNotFoundError("Lead not found", context={"lead_id": 123})
print(str(exc))
# Output: "LEAD_NOT_FOUND: Lead not found (context: {'lead_id': 123})"
```

## FastAPI Integration

The application automatically handles all `SalesAgentException` instances via the exception handler in `app/main.py`:

```python
@app.exception_handler(SalesAgentException)
async def sales_agent_exception_handler(request: Request, exc: SalesAgentException):
    """Handle all custom Sales Agent exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )
```

### API Error Response Format

When a custom exception is raised in an API route, clients receive:

```json
{
  "error": {
    "code": "LEAD_NOT_FOUND",
    "message": "Lead 123 not found",
    "context": {
      "lead_id": 123
    }
  }
}
```

## Error Code Reference

### Lead Exceptions
- `LEAD_ERROR`: Generic lead error (500)
- `LEAD_VALIDATION_ERROR`: Lead data validation failed (400)
- `LEAD_NOT_FOUND`: Lead not found in database (404)
- `LEAD_QUALIFICATION_ERROR`: Lead qualification failed (500)

### Voice Exceptions
- `VOICE_ERROR`: Generic voice error (500)
- `CARTESIA_API_ERROR`: Cartesia API call failed (502)
- `VOICE_GENERATION_ERROR`: Voice generation failed (500)
- `AUDIO_PROCESSING_ERROR`: Audio processing failed (500)
- `VOICE_SESSION_NOT_FOUND`: Voice session not found (404)

### Document Exceptions
- `DOCUMENT_ERROR`: Generic document error (500)
- `PDF_PROCESSING_ERROR`: PDF processing failed (500)
- `DOCUMENT_PARSING_ERROR`: Document parsing failed (422)
- `DOCUMENT_NOT_FOUND`: Document not found (404)
- `UNSUPPORTED_DOCUMENT_TYPE`: Unsupported document type (400)
- `DOCUMENT_TOO_LARGE`: Document exceeds size limit (413)

### External API Exceptions
- `EXTERNAL_API_ERROR`: Generic external API error (502)
- `API_CONNECTION_ERROR`: Failed to connect to API (502)
- `API_RATE_LIMIT_ERROR`: API rate limit exceeded (429)
- `API_AUTHENTICATION_ERROR`: API authentication failed (401)
- `API_TIMEOUT_ERROR`: API request timed out (504)

### CRM Exceptions
- `CRM_ERROR`: Generic CRM error (500)
- `CRM_AUTHENTICATION_ERROR`: CRM authentication failed (401)
- `CRM_RATE_LIMIT_ERROR`: CRM rate limit exceeded (429)
- `CRM_NOT_FOUND`: CRM resource not found (404)
- `CRM_VALIDATION_ERROR`: Invalid CRM data (422)
- `CRM_NETWORK_ERROR`: CRM network error (502)
- `CRM_WEBHOOK_ERROR`: Webhook verification failed (400)

### Configuration Exceptions
- `CONFIGURATION_ERROR`: Application configuration error (500)
- `MISSING_API_KEY`: Required API key not found (500)

### Validation Exceptions
- `VALIDATION_ERROR`: Data validation error (400)
- `INVALID_INPUT`: Invalid input data (400)

### Resource Exceptions
- `RESOURCE_NOT_FOUND`: Generic resource not found (404)
- `RESOURCE_CONFLICT`: Resource conflict (409)

## Best Practices

### 1. Use Specific Exceptions

✅ **Do**: Use specific exceptions for specific scenarios
```python
raise LeadNotFoundError(f"Lead {lead_id} not found", context={"lead_id": lead_id})
```

❌ **Don't**: Use generic HTTPException
```python
raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
```

### 2. Include Context Data

✅ **Do**: Include relevant context for debugging
```python
raise DocumentTooLargeError(
    "File exceeds size limit",
    context={"file_size_mb": 15.5, "max_size_mb": 10, "filename": "resume.pdf"}
)
```

❌ **Don't**: Omit helpful context
```python
raise DocumentTooLargeError("File too large")
```

### 3. Use Appropriate Error Codes

Each exception automatically includes the correct error code and HTTP status code. Just instantiate the right exception class.

### 4. Handle Exceptions at the Right Level

- **Service layer**: Raise domain-specific exceptions (LeadException, VoiceException, etc.)
- **API routes**: Catch and re-raise as needed, or let FastAPI handler process them
- **FastAPI handler**: Automatically converts to JSON responses

### 5. Log Before Raising

```python
logger.error(f"Failed to qualify lead {lead_id}: {error}", exc_info=True)
raise LeadQualificationError(
    f"Qualification failed for lead {lead_id}",
    context={"lead_id": lead_id, "error": str(error)}
)
```

## Migration from Generic Exceptions

### Replace ValueError for Missing API Keys

```python
# Old
if not api_key:
    raise ValueError("CEREBRAS_API_KEY not set")

# New
if not api_key:
    raise MissingAPIKeyError(
        "CEREBRAS_API_KEY environment variable not set",
        context={"api_key": "CEREBRAS_API_KEY"}
    )
```

### Replace HTTPException

```python
# Old
raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")

# New
raise LeadNotFoundError(f"Lead {lead_id} not found", context={"lead_id": lead_id})
```

### Replace Generic Exception

```python
# Old
raise Exception("Voice session not found")

# New
raise VoiceSessionNotFoundError(
    f"Session {session_id} not found",
    context={"session_id": session_id}
)
```

## Testing Exceptions

All exceptions are thoroughly tested in `tests/test_exceptions.py`:

```bash
pytest tests/test_exceptions.py -v
```

Test coverage includes:
- Exception creation and attributes
- Error codes and status codes
- JSON serialization (to_dict)
- String representations (__str__, __repr__)
- Inheritance hierarchy
- Exception raising and catching
- Error code mapping catalog

## Implementation Files

- **Exception definitions**: `app/core/exceptions.py`
- **CRM exceptions**: `app/services/crm/base.py` (extends SalesAgentException)
- **Exception handler**: `app/main.py` (FastAPI exception handler)
- **Tests**: `tests/test_exceptions.py`

## Error Code Mapping

The `ERROR_CODE_MAPPING` dictionary in `app/core/exceptions.py` provides reverse lookup from error codes to exception classes:

```python
from app.core.exceptions import ERROR_CODE_MAPPING

# Get exception class by error code
exception_class = ERROR_CODE_MAPPING["LEAD_NOT_FOUND"]
# Returns: LeadNotFoundError
```

This is useful for:
- Programmatic exception handling
- Error code validation
- Documentation generation
- API client libraries

---

**Last Updated**: Task 22 - Wave 1 Implementation
