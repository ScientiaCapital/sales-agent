"""
LangChain tools for Close CRM integration

Provides LangChain-compatible tools for lead/contact management operations
in Close CRM. Integrates with existing CloseProvider for API operations.

Tools:
- create_lead_tool: Create new lead with contact in Close CRM
- update_contact_tool: Update existing contact details
- search_leads_tool: Search for leads by query
- get_lead_tool: Get detailed lead information

Integration:
- Uses existing CloseProvider from app.services.crm.close
- Database: SessionLocal() for database access
- Redis: Singleton pattern for Redis client
- Error handling: ToolException for LangChain compatibility
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
import redis.asyncio as redis

from langchain_core.tools import tool, ToolException

from app.models.database import SessionLocal
from app.services.crm.close import CloseProvider
from app.services.crm.base import (
    Contact,
    CRMAuthenticationError,
    CRMRateLimitError,
    CRMNotFoundError,
    CRMValidationError,
    CRMNetworkError,
)
from app.services.crm.deduplication import get_deduplication_engine

logger = logging.getLogger(__name__)

# ========== Redis Client Singleton ==========

_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """
    Get or create global Redis client for rate limiting.

    Returns:
        Redis client instance
    """
    global _redis_client

    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        logger.info(f"Initialized Redis client: {redis_url}")

    return _redis_client


# ========== Pydantic Input Schemas ==========

class CreateLeadInput(BaseModel):
    """Input schema for creating a lead in Close CRM."""

    company_name: str = Field(
        ...,
        description="Company name for the lead (required)"
    )
    contact_name: Optional[str] = Field(
        default=None,
        description="Full name of primary contact"
    )
    contact_email: str = Field(
        ...,
        description="Email address of primary contact (required)"
    )
    contact_title: Optional[str] = Field(
        default=None,
        description="Job title of contact"
    )
    contact_phone: Optional[str] = Field(
        default=None,
        description="Phone number of contact"
    )
    industry: Optional[str] = Field(
        default=None,
        description="Industry or business sector"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes about the lead"
    )


class UpdateContactInput(BaseModel):
    """Input schema for updating a contact in Close CRM."""

    external_id: str = Field(
        ...,
        description="Close CRM contact ID (external_id from Contact)"
    )
    first_name: Optional[str] = Field(
        default=None,
        description="Updated first name"
    )
    last_name: Optional[str] = Field(
        default=None,
        description="Updated last name"
    )
    email: Optional[str] = Field(
        default=None,
        description="Updated email address"
    )
    title: Optional[str] = Field(
        default=None,
        description="Updated job title"
    )
    phone: Optional[str] = Field(
        default=None,
        description="Updated phone number"
    )
    company: Optional[str] = Field(
        default=None,
        description="Updated company name"
    )


class SearchLeadsInput(BaseModel):
    """Input schema for searching leads in Close CRM."""

    query: str = Field(
        ...,
        description="Search query (company name, contact email, etc.)"
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results to return (default: 10)"
    )


class GetLeadInput(BaseModel):
    """Input schema for getting a specific lead from Close CRM."""

    lead_id: str = Field(
        ...,
        description="Close CRM lead ID"
    )


# ========== LangChain Tools ==========

@tool(
    args_schema=CreateLeadInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def create_lead_tool(
    company_name: str,
    contact_email: str,
    contact_name: Optional[str] = None,
    contact_title: Optional[str] = None,
    contact_phone: Optional[str] = None,
    industry: Optional[str] = None,
    notes: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """Create a new lead with primary contact in Close CRM.

    This tool creates a lead (company record) in Close CRM with an associated
    primary contact. Close CRM requires an email address for the contact.
    The lead name defaults to the company name.

    Use this tool when you need to:
    - Add a new prospect/lead to the CRM
    - Create a company record with contact details
    - Initiate a sales pipeline for a new opportunity

    Args:
        company_name: Company name for the lead (required)
        contact_email: Email address of primary contact (required)
        contact_name: Full name of primary contact
        contact_title: Job title of contact
        contact_phone: Phone number of contact
        industry: Industry or business sector
        notes: Additional notes about the lead

    Returns:
        Tuple of:
        - Success message with lead details (for LLM)
        - Artifact dict with full contact data (for downstream processing)

    Raises:
        ToolException: If lead creation fails (API error, validation, rate limit)

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [create_lead_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(content="Create lead for Acme Corp, contact: john@acme.com")]
        })
        ```
    """
    db = SessionLocal()

    try:
        # Validate required fields
        if not contact_email or "@" not in contact_email:
            raise ToolException("Valid email address is required to create a lead")

        if not company_name or not company_name.strip():
            raise ToolException("Company name is required to create a lead")

        # Get API credentials
        api_key = os.getenv("CLOSE_API_KEY")
        if not api_key:
            raise ToolException(
                "CLOSE_API_KEY not found in environment. "
                "Please configure Close CRM credentials."
            )

        # ========== DEDUPLICATION CHECK ==========
        # Check for duplicates BEFORE creating lead
        dedup_engine = get_deduplication_engine(db, threshold=85.0)
        dedup_result = await dedup_engine.find_duplicates(
            email=contact_email,
            company=company_name,
            phone=contact_phone
        )

        if dedup_result.is_duplicate:
            best_match = dedup_result.get_best_match()
            if best_match:
                # Found duplicate - return warning instead of creating
                duplicate_info = (
                    f"⚠️  DUPLICATE DETECTED (confidence: {best_match.confidence:.1f}%)\n\n"
                    f"Cannot create lead for '{company_name}' ({contact_email}) - "
                    f"a similar contact already exists:\n\n"
                    f"  • Email: {best_match.contact.email}\n"
                    f"  • Company: {best_match.contact.company}\n"
                    f"  • Phone: {best_match.contact.phone or 'N/A'}\n"
                    f"  • LinkedIn: {best_match.contact.linkedin_url or 'N/A'}\n\n"
                    f"Match reasons:\n"
                )
                for detail in best_match.match_details:
                    duplicate_info += f"  • {detail.reason} ({detail.confidence:.0f}%)\n"

                duplicate_info += (
                    f"\n💡 Suggestion: Use update_contact_tool to update the existing contact instead.\n"
                    f"   Contact ID: {best_match.contact.external_ids.get('close', 'N/A')}"
                )

                logger.warning(
                    f"Duplicate lead prevented: {contact_email} matches existing contact "
                    f"with {best_match.confidence:.1f}% confidence"
                )

                # Return as artifact for downstream processing
                artifact = {
                    "duplicate_detected": True,
                    "confidence": best_match.confidence,
                    "existing_contact_id": best_match.contact.id,
                    "existing_contact": {
                        "email": best_match.contact.email,
                        "company": best_match.contact.company,
                        "external_ids": best_match.contact.external_ids
                    },
                    "match_details": [
                        {
                            "field": d.field_name,
                            "confidence": d.confidence,
                            "reason": d.reason
                        }
                        for d in best_match.match_details
                    ]
                }

                return duplicate_info, artifact

        # No duplicates found - proceed with creation
        logger.info(f"No duplicates found for {contact_email}, proceeding with lead creation")

        # Initialize Redis and Close provider
        redis_client = await get_redis_client()
        close_provider = CloseProvider(
            db=db,
            redis_client=redis_client,
            api_key=api_key
        )

        # Parse contact name into first/last
        first_name, last_name = None, None
        if contact_name:
            parts = contact_name.strip().split(maxsplit=1)
            first_name = parts[0] if parts else None
            last_name = parts[1] if len(parts) > 1 else None

        # Create Contact object
        contact = Contact(
            email=contact_email,
            first_name=first_name,
            last_name=last_name,
            company=company_name,
            title=contact_title,
            phone=contact_phone,
            enrichment_data={
                "industry": industry,
                "notes": notes
            } if (industry or notes) else None
        )

        # Call Close CRM API via provider
        created_contact = await close_provider.create_contact(contact)

        # Build success message
        contact_display = created_contact.first_name or created_contact.email
        content = (
            f"Successfully created lead '{company_name}' in Close CRM with "
            f"primary contact {contact_display}. "
            f"Lead ID: {created_contact.external_ids.get('close', 'N/A')}"
        )

        # Build artifact with full contact data
        artifact = {
            "lead_id": created_contact.external_ids.get("close"),
            "contact": created_contact.dict(),
            "company": company_name,
            "created_at": created_contact.created_at.isoformat() if created_contact.created_at else None
        }

        logger.info(f"Created lead in Close CRM: {company_name} ({contact_email})")

        return content, artifact

    except CRMValidationError as e:
        raise ToolException(f"Validation error: {str(e)}")

    except CRMRateLimitError as e:
        raise ToolException(
            f"Rate limit exceeded: {str(e)}. "
            f"Please retry after 60 seconds."
        )

    except CRMAuthenticationError as e:
        raise ToolException(
            f"Authentication failed: {str(e)}. "
            f"Check CLOSE_API_KEY in environment."
        )

    except CRMNetworkError as e:
        raise ToolException(f"Network error connecting to Close CRM: {str(e)}")

    except ToolException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error creating lead: {e}", exc_info=True)
        raise ToolException(
            f"Failed to create lead in Close CRM: {str(e)}. "
            f"This may be an API issue or network problem."
        )

    finally:
        db.close()


@tool(
    args_schema=UpdateContactInput,
    parse_docstring=True
)
async def update_contact_tool(
    external_id: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    title: Optional[str] = None,
    phone: Optional[str] = None,
    company: Optional[str] = None
) -> str:
    """Update an existing contact's details in Close CRM.

    This tool updates a contact's information in Close CRM. At least one
    field to update must be provided. The contact is identified by its
    Close CRM ID (external_id from Contact object).

    Use this tool when you need to:
    - Update contact information after enrichment
    - Correct outdated contact details
    - Add missing information to existing contacts

    Args:
        external_id: Close CRM contact ID (external_id from Contact)
        first_name: Updated first name
        last_name: Updated last name
        email: Updated email address
        title: Updated job title
        phone: Updated phone number
        company: Updated company name

    Returns:
        Success message with updated contact details

    Raises:
        ToolException: If update fails (not found, validation error, API error)

    Example:
        ```python
        # Update contact title after enrichment
        result = await update_contact_tool.ainvoke({
            "external_id": "contact_abc123",
            "title": "VP of Engineering",
            "phone": "+1-555-1234"
        })
        ```
    """
    db = SessionLocal()

    try:
        # Validate at least one field is provided
        updates = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "title": title,
            "phone": phone,
            "company": company
        }

        # Filter out None values
        updates = {k: v for k, v in updates.items() if v is not None}

        if not updates:
            raise ToolException(
                "At least one field must be provided to update the contact"
            )

        if not external_id:
            raise ToolException("Contact external_id is required")

        # Get API credentials
        api_key = os.getenv("CLOSE_API_KEY")
        if not api_key:
            raise ToolException(
                "CLOSE_API_KEY not found in environment. "
                "Please configure Close CRM credentials."
            )

        # Initialize Redis and Close provider
        redis_client = await get_redis_client()
        close_provider = CloseProvider(
            db=db,
            redis_client=redis_client,
            api_key=api_key
        )

        # Create Contact object with updates
        contact = Contact(
            email=email or "placeholder@example.com",  # Email required by Contact model
            external_ids={"close": external_id},
            **{k: v for k, v in updates.items() if k != "email"}
        )

        # Update via Close provider
        updated_contact = await close_provider.update_contact(contact)

        # Build success message
        updated_fields = ", ".join(updates.keys())
        contact_display = updated_contact.first_name or updated_contact.email

        message = (
            f"Successfully updated contact {contact_display} in Close CRM. "
            f"Updated fields: {updated_fields}"
        )

        logger.info(f"Updated contact in Close CRM: {external_id}")

        return message

    except CRMNotFoundError as e:
        raise ToolException(f"Contact not found: {str(e)}")

    except CRMValidationError as e:
        raise ToolException(f"Validation error: {str(e)}")

    except CRMRateLimitError as e:
        raise ToolException(
            f"Rate limit exceeded: {str(e)}. Please retry after 60 seconds."
        )

    except CRMAuthenticationError as e:
        raise ToolException(
            f"Authentication failed: {str(e)}. Check CLOSE_API_KEY."
        )

    except CRMNetworkError as e:
        raise ToolException(f"Network error: {str(e)}")

    except ToolException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error updating contact: {e}", exc_info=True)
        raise ToolException(f"Failed to update contact: {str(e)}")

    finally:
        db.close()


@tool(
    args_schema=SearchLeadsInput,
    parse_docstring=True
)
async def search_leads_tool(
    query: str,
    limit: int = 10
) -> str:
    """Search for leads in Close CRM by company name, email, or other criteria.

    This tool searches Close CRM leads using the provided query string.
    The query can match company names, contact emails, or other lead fields.
    Results are returned as a formatted list with key details.

    Use this tool when you need to:
    - Find leads by company name
    - Look up contacts by email address
    - Search for existing leads before creating duplicates

    Args:
        query: Search query (company name, contact email, etc.)
        limit: Maximum number of results to return (default: 10)

    Returns:
        Formatted string with search results

    Raises:
        ToolException: If search fails (API error, rate limit)

    Example:
        ```python
        # Search for leads at Acme Corp
        results = await search_leads_tool.ainvoke({
            "query": "Acme Corp",
            "limit": 5
        })
        ```
    """
    db = SessionLocal()

    try:
        if not query or not query.strip():
            raise ToolException("Search query cannot be empty")

        if limit < 1 or limit > 100:
            raise ToolException("Limit must be between 1 and 100")

        # Get API credentials
        api_key = os.getenv("CLOSE_API_KEY")
        if not api_key:
            raise ToolException(
                "CLOSE_API_KEY not found in environment. "
                "Please configure Close CRM credentials."
            )

        # Initialize Redis and Close provider
        redis_client = await get_redis_client()
        close_provider = CloseProvider(
            db=db,
            redis_client=redis_client,
            api_key=api_key
        )

        # Perform search via sync_contacts with query filter
        # Note: This uses the sync method with filters, which internally searches
        sync_result = await close_provider.sync_contacts(
            direction="import",
            filters={"query": query, "_limit": limit}
        )

        contacts = sync_result.contacts_processed

        if not contacts:
            return f"No leads found matching query: '{query}'"

        # Format results for LLM
        results = [f"Found {len(contacts)} lead(s) matching '{query}':\n"]

        for i, contact in enumerate(contacts[:limit], 1):
            contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.email
            company = contact.company or "No company"
            title = contact.title or "No title"
            lead_id = contact.external_ids.get("close", "N/A")

            results.append(
                f"{i}. {contact_name} - {title} at {company}\n"
                f"   Email: {contact.email}\n"
                f"   Lead ID: {lead_id}\n"
            )

        logger.info(f"Searched Close CRM: '{query}' ({len(contacts)} results)")

        return "\n".join(results)

    except CRMRateLimitError as e:
        raise ToolException(
            f"Rate limit exceeded: {str(e)}. Please retry after 60 seconds."
        )

    except CRMAuthenticationError as e:
        raise ToolException(
            f"Authentication failed: {str(e)}. Check CLOSE_API_KEY."
        )

    except CRMNetworkError as e:
        raise ToolException(f"Network error: {str(e)}")

    except ToolException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error searching leads: {e}", exc_info=True)
        raise ToolException(f"Failed to search leads: {str(e)}")

    finally:
        db.close()


@tool(
    args_schema=GetLeadInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def get_lead_tool(
    lead_id: str
) -> Tuple[str, Dict[str, Any]]:
    """Get detailed information about a specific lead from Close CRM.

    This tool retrieves full details for a lead by its Close CRM ID.
    Returns both a human-readable summary and structured lead data.

    Use this tool when you need to:
    - Get complete lead information
    - Review lead details before updating
    - Access enrichment data for a lead

    Args:
        lead_id: Close CRM lead ID

    Returns:
        Tuple of:
        - Human-readable lead summary (for LLM)
        - Artifact dict with complete lead data (for downstream processing)

    Raises:
        ToolException: If lead not found or API error occurs

    Example:
        ```python
        # Get lead details
        result = await get_lead_tool.ainvoke({
            "lead_id": "lead_abc123"
        })

        content, artifact = result
        print(content)  # Human-readable summary
        print(artifact["contact"])  # Full contact data
        ```
    """
    db = SessionLocal()

    try:
        if not lead_id:
            raise ToolException("Lead ID is required")

        # Get API credentials
        api_key = os.getenv("CLOSE_API_KEY")
        if not api_key:
            raise ToolException(
                "CLOSE_API_KEY not found in environment. "
                "Please configure Close CRM credentials."
            )

        # Initialize Redis and Close provider
        redis_client = await get_redis_client()
        close_provider = CloseProvider(
            db=db,
            redis_client=redis_client,
            api_key=api_key
        )

        # Get contact by external_id
        contact = await close_provider.get_contact(lead_id)

        if not contact:
            raise ToolException(f"Lead not found: {lead_id}")

        # Build human-readable summary
        contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.email
        company = contact.company or "No company"
        title = contact.title or "No title"

        content = (
            f"Lead Details:\n"
            f"- Contact: {contact_name}\n"
            f"- Title: {title}\n"
            f"- Company: {company}\n"
            f"- Email: {contact.email}\n"
            f"- Phone: {contact.phone or 'Not provided'}\n"
            f"- LinkedIn: {contact.linkedin_url or 'Not provided'}\n"
            f"- Last Synced: {contact.last_synced_at.isoformat() if contact.last_synced_at else 'Never'}"
        )

        # Build artifact with full data
        artifact = {
            "lead_id": lead_id,
            "contact": contact.dict(),
            "enrichment_data": contact.enrichment_data or {}
        }

        logger.info(f"Retrieved lead from Close CRM: {lead_id}")

        return content, artifact

    except CRMNotFoundError as e:
        raise ToolException(f"Lead not found: {str(e)}")

    except CRMRateLimitError as e:
        raise ToolException(
            f"Rate limit exceeded: {str(e)}. Please retry after 60 seconds."
        )

    except CRMAuthenticationError as e:
        raise ToolException(
            f"Authentication failed: {str(e)}. Check CLOSE_API_KEY."
        )

    except CRMNetworkError as e:
        raise ToolException(f"Network error: {str(e)}")

    except ToolException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error getting lead: {e}", exc_info=True)
        raise ToolException(f"Failed to get lead details: {str(e)}")

    finally:
        db.close()


class CheckDuplicateLeadsInput(BaseModel):
    """Input schema for checking duplicate leads"""

    email: Optional[str] = Field(
        default=None,
        description="Email address to check for duplicates"
    )
    company: Optional[str] = Field(
        default=None,
        description="Company name to check for duplicates"
    )
    phone: Optional[str] = Field(
        default=None,
        description="Phone number to check for duplicates"
    )
    linkedin_url: Optional[str] = Field(
        default=None,
        description="LinkedIn URL to check for duplicates"
    )
    threshold: float = Field(
        default=85.0,
        description="Confidence threshold for duplicate detection (0-100, default: 85)"
    )


@tool(
    args_schema=CheckDuplicateLeadsInput,
    parse_docstring=True
)
async def check_duplicate_leads_tool(
    email: Optional[str] = None,
    company: Optional[str] = None,
    phone: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    threshold: float = 85.0
) -> str:
    """Check if a lead already exists in the database (deduplication check).

    This tool searches for potential duplicate leads across multiple fields
    using multi-field matching (email, domain, company name, phone, LinkedIn).
    Returns duplicate matches with confidence scores.

    Use this tool when you need to:
    - Check for duplicates before creating a new lead
    - Verify if a contact already exists in the system
    - Find similar contacts based on partial information

    Args:
        email: Email address to check for duplicates
        company: Company name to check for duplicates
        phone: Phone number to check for duplicates
        linkedin_url: LinkedIn URL to check for duplicates
        threshold: Confidence threshold for duplicate detection (0-100, default: 85)

    Returns:
        Formatted string with duplicate check results

    Raises:
        ToolException: If duplicate check fails

    Example:
        ```python
        # Check for duplicates before creating lead
        result = await check_duplicate_leads_tool.ainvoke({
            "email": "john@acme.com",
            "company": "Acme Corporation",
            "threshold": 85
        })
        ```
    """
    db = SessionLocal()

    try:
        if not any([email, company, phone, linkedin_url]):
            raise ToolException(
                "At least one field (email, company, phone, or linkedin_url) must be provided"
            )

        # Run deduplication check
        dedup_engine = get_deduplication_engine(db, threshold=threshold)
        dedup_result = await dedup_engine.find_duplicates(
            email=email,
            company=company,
            phone=phone,
            linkedin_url=linkedin_url
        )

        if not dedup_result.matches:
            return (
                f"✅ No duplicates found!\n\n"
                f"Checked fields: {', '.join(dedup_result.checked_fields)}\n"
                f"Threshold: {threshold}%\n\n"
                f"Safe to create new lead."
            )

        # Found potential duplicates
        result_text = f"⚠️  Found {len(dedup_result.matches)} potential duplicate(s):\n\n"

        for i, match in enumerate(dedup_result.matches[:5], 1):  # Show top 5
            result_text += f"{i}. {match.contact.email} @ {match.contact.company}\n"
            result_text += f"   Confidence: {match.confidence:.1f}%\n"
            result_text += f"   Phone: {match.contact.phone or 'N/A'}\n"
            result_text += f"   LinkedIn: {match.contact.linkedin_url or 'N/A'}\n"
            result_text += f"   Match reasons:\n"

            for detail in match.match_details:
                result_text += f"     • {detail.reason} ({detail.confidence:.0f}%)\n"

            result_text += "\n"

        if dedup_result.is_duplicate:
            best_match = dedup_result.get_best_match()
            result_text += (
                f"🚫 DUPLICATE DETECTED (confidence >= {threshold}%)\n"
                f"Cannot create lead - update existing contact instead.\n"
                f"Contact ID: {best_match.contact.external_ids.get('close', 'N/A')}"
            )
        else:
            result_text += (
                f"ℹ️  Potential matches found but confidence < {threshold}%.\n"
                f"Safe to create new lead, but review matches first."
            )

        logger.info(
            f"Duplicate check complete: {len(dedup_result.matches)} matches, "
            f"highest confidence: {dedup_result.confidence:.1f}%"
        )

        return result_text

    except ToolException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error checking duplicates: {e}", exc_info=True)
        raise ToolException(f"Failed to check for duplicates: {str(e)}")

    finally:
        db.close()


# ========== Exports ==========

__all__ = [
    "create_lead_tool",
    "update_contact_tool",
    "search_leads_tool",
    "get_lead_tool",
    "check_duplicate_leads_tool",
]
