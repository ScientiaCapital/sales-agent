# LangGraph create_react_agent() Complete Guide - 2025

Production-ready patterns for building ReAct agents with ChatAnthropic, tool binding, and async execution.

## Table of Contents

1. [Complete Working Example](#complete-working-example)
2. [Core Concepts](#core-concepts)
3. [Tool Selection & State Management](#tool-selection--state-management)
4. [Max Iterations & Loop Control](#max-iterations--loop-control)
5. [Processing Agent Output](#processing-agent-output)
6. [Async Patterns with ainvoke()](#async-patterns-with-ainvoke)
7. [Error Handling for ReAct Agents](#error-handling-for-react-agents)
8. [System Prompts & Tool Use Strategy](#system-prompts--tool-use-strategy)
9. [Performance Optimization](#performance-optimization)
10. [Common Pitfalls & Solutions](#common-pitfalls--solutions)

---

## Complete Working Example

Production-ready enrichment agent that calls Apollo and LinkedIn APIs.

### Basic Setup with 2-3 Tools

```python
# backend/app/services/langgraph_enrichment_agent.py

from typing import Annotated, TypedDict
import json
import logging
from datetime import datetime

from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage, HumanMessage
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent, ToolNode
from langgraph.graph import MessagesState
from langgraph.checkpoint.memory import InMemorySaver

logger = logging.getLogger(__name__)


# ============================================================================
# DEFINE TOOLS (these are called by the agent)
# ============================================================================

@tool
def search_apollo_contact(email: str) -> dict:
    """
    Search for contact details on Apollo.io by email address.

    Args:
        email: Email address to search for

    Returns:
        Dictionary containing contact details (name, title, company, etc.)
    """
    try:
        from app.services.apollo import ApolloService
        apollo = ApolloService()

        # Call Apollo API
        result = apollo.search_contact(email=email)

        if result:
            logger.info(f"Apollo search successful for {email}")
            return {
                "status": "success",
                "email": email,
                "data": {
                    "name": result.get("name"),
                    "title": result.get("title"),
                    "company": result.get("company"),
                    "phone": result.get("phone"),
                    "linkedin_url": result.get("linkedin_url"),
                    "location": result.get("location"),
                }
            }
        else:
            return {
                "status": "not_found",
                "email": email,
                "data": None
            }
    except Exception as e:
        logger.error(f"Apollo search failed for {email}: {str(e)}")
        return {
            "status": "error",
            "email": email,
            "error": str(e)
        }


@tool
def search_linkedin_profile(profile_url: str) -> dict:
    """
    Scrape LinkedIn profile data using Browserbase.

    Args:
        profile_url: LinkedIn profile URL (e.g., https://linkedin.com/in/johndoe)

    Returns:
        Dictionary containing profile details (headline, summary, experience, etc.)
    """
    try:
        from app.services.linkedin_scraper import LinkedInScraperService
        scraper = LinkedInScraperService()

        # Scrape LinkedIn profile
        result = scraper.scrape_profile(profile_url)

        if result:
            logger.info(f"LinkedIn scrape successful for {profile_url}")
            return {
                "status": "success",
                "profile_url": profile_url,
                "data": {
                    "name": result.get("name"),
                    "headline": result.get("headline"),
                    "about": result.get("about"),
                    "experience": result.get("experience", [])[:3],  # Top 3 positions
                    "skills": result.get("skills", [])[:5],  # Top 5 skills
                    "education": result.get("education"),
                }
            }
        else:
            return {
                "status": "not_found",
                "profile_url": profile_url,
                "data": None
            }
    except Exception as e:
        logger.error(f"LinkedIn scrape failed for {profile_url}: {str(e)}")
        return {
            "status": "error",
            "profile_url": profile_url,
            "error": str(e)
        }


@tool
def enrich_contact_summary(contact_data: dict) -> dict:
    """
    Synthesize enriched contact data into a structured summary for enrichment.

    Args:
        contact_data: Dictionary with keys 'email', 'apollo_data', 'linkedin_data'

    Returns:
        Dictionary with enriched contact profile
    """
    try:
        apollo_data = contact_data.get("apollo_data", {})
        linkedin_data = contact_data.get("linkedin_data", {})

        # Merge data intelligently
        enriched = {
            "email": contact_data.get("email"),
            "full_name": apollo_data.get("name") or linkedin_data.get("name"),
            "title": apollo_data.get("title") or linkedin_data.get("headline"),
            "company": apollo_data.get("company"),
            "phone": apollo_data.get("phone"),
            "location": apollo_data.get("location"),
            "linkedin_url": apollo_data.get("linkedin_url"),
            "skills": linkedin_data.get("skills", []),
            "experience_count": len(linkedin_data.get("experience", [])),
            "enrichment_score": calculate_enrichment_score(apollo_data, linkedin_data),
            "enriched_at": datetime.utcnow().isoformat()
        }

        return {
            "status": "success",
            "data": enriched
        }
    except Exception as e:
        logger.error(f"Enrichment synthesis failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


def calculate_enrichment_score(apollo_data: dict, linkedin_data: dict) -> float:
    """Calculate enrichment completeness score 0-100"""
    score = 0.0
    max_points = 100.0

    # Apollo data (40 points max)
    if apollo_data.get("name"): score += 10
    if apollo_data.get("title"): score += 10
    if apollo_data.get("company"): score += 10
    if apollo_data.get("phone"): score += 10

    # LinkedIn data (40 points max)
    if linkedin_data.get("headline"): score += 10
    if linkedin_data.get("about"): score += 10
    if linkedin_data.get("experience"): score += 10
    if linkedin_data.get("skills"): score += 10

    # Both sources (20 points max)
    if apollo_data and linkedin_data: score += 20

    return min(score, max_points)


# ============================================================================
# CREATE AGENT WITH create_react_agent
# ============================================================================

def create_enrichment_agent(temperature: float = 0.7, checkpointer=None):
    """
    Create a ReAct agent for contact enrichment.

    Args:
        temperature: LLM temperature (0.7 = balanced, 0.0 = deterministic)
        checkpointer: Optional checkpoint saver for persistence

    Returns:
        Compiled LangGraph agent
    """

    # Initialize ChatAnthropic model
    model = ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        temperature=temperature,
        max_tokens=2000,
    )

    # Define tools for the agent
    tools = [
        search_apollo_contact,
        search_linkedin_profile,
        enrich_contact_summary,
    ]

    # System prompt that guides tool use strategy
    system_prompt = """You are a contact enrichment specialist. Your job is to gather and synthesize information about a contact from multiple sources.

ENRICHMENT STRATEGY:
1. Start by searching Apollo for email-based contact information
2. Use LinkedIn to gather professional background and skills
3. Synthesize all data into a comprehensive contact profile
4. Always provide a final enrichment summary

IMPORTANT RULES:
- Only call tools with valid, complete information
- If a tool returns "error" or "not_found", try alternative approaches
- Don't make up data - only report what you found
- Always conclude with a final enrichment summary before completing
- Be concise but thorough in your findings

TOOL USAGE:
- Use search_apollo_contact first with the email address
- Then use search_linkedin_profile with LinkedIn URL if available
- Finally, use enrich_contact_summary to create the complete profile
"""

    # Create the agent using create_react_agent
    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=system_prompt,
        checkpointer=checkpointer or InMemorySaver(),
    )

    return agent


# ============================================================================
# AGENT INVOCATION PATTERNS
# ============================================================================

def enrich_contact(email: str, linkedin_url: str = None) -> dict:
    """
    Synchronous invocation - enrich a single contact.

    Args:
        email: Contact email address
        linkedin_url: Optional LinkedIn profile URL

    Returns:
        Enrichment result with agent output
    """
    agent = create_enrichment_agent()

    # Prepare the input
    user_message = f"""Please enrich the following contact:
- Email: {email}
- LinkedIn URL: {linkedin_url or "Not provided"}

Search for information and create a comprehensive enrichment profile."""

    # Invoke the agent
    input_state = {
        "messages": [HumanMessage(content=user_message)]
    }

    try:
        result = agent.invoke(
            input_state,
            config={"configurable": {"thread_id": f"enrichment_{email}_{datetime.utcnow().timestamp()}"}},
        )

        # Extract final response from agent output
        final_message = result["messages"][-1]

        return {
            "status": "success",
            "email": email,
            "enrichment_data": extract_enrichment_data(result["messages"]),
            "final_response": final_message.content if isinstance(final_message, AIMessage) else str(final_message),
            "message_count": len(result["messages"]),
        }

    except Exception as e:
        logger.error(f"Enrichment failed for {email}: {str(e)}")
        return {
            "status": "error",
            "email": email,
            "error": str(e),
        }


async def enrich_contact_async(email: str, linkedin_url: str = None) -> dict:
    """
    Asynchronous invocation with ainvoke() - for concurrent enrichment.

    Args:
        email: Contact email address
        linkedin_url: Optional LinkedIn profile URL

    Returns:
        Enrichment result with agent output
    """
    agent = create_enrichment_agent()

    user_message = f"""Please enrich the following contact:
- Email: {email}
- LinkedIn URL: {linkedin_url or "Not provided"}

Search for information and create a comprehensive enrichment profile."""

    input_state = {
        "messages": [HumanMessage(content=user_message)]
    }

    try:
        # Use ainvoke for async execution
        result = await agent.ainvoke(
            input_state,
            config={"configurable": {"thread_id": f"enrichment_{email}_{datetime.utcnow().timestamp()}"}},
        )

        final_message = result["messages"][-1]

        return {
            "status": "success",
            "email": email,
            "enrichment_data": extract_enrichment_data(result["messages"]),
            "final_response": final_message.content if isinstance(final_message, AIMessage) else str(final_message),
        }

    except Exception as e:
        logger.error(f"Async enrichment failed for {email}: {str(e)}")
        return {
            "status": "error",
            "email": email,
            "error": str(e),
        }


def extract_enrichment_data(messages: list) -> dict:
    """
    Extract structured enrichment data from agent message history.

    Args:
        messages: List of messages from agent execution

    Returns:
        Enriched contact data dictionary
    """
    enrichment_data = {
        "apollo_data": None,
        "linkedin_data": None,
        "enrichment_summary": None,
    }

    for message in messages:
        # Look for tool messages with enrichment data
        if isinstance(message, ToolMessage):
            try:
                content = json.loads(message.content) if isinstance(message.content, str) else message.content

                if message.name == "search_apollo_contact" and content.get("status") == "success":
                    enrichment_data["apollo_data"] = content.get("data")

                elif message.name == "search_linkedin_profile" and content.get("status") == "success":
                    enrichment_data["linkedin_data"] = content.get("data")

                elif message.name == "enrich_contact_summary" and content.get("status") == "success":
                    enrichment_data["enrichment_summary"] = content.get("data")

            except (json.JSONDecodeError, TypeError):
                pass

    return enrichment_data


# Streaming invocation
def enrich_contact_streaming(email: str, linkedin_url: str = None):
    """
    Stream agent progress in real-time.

    Yields:
        Dictionary with streaming updates from agent
    """
    agent = create_enrichment_agent()

    user_message = f"""Please enrich the following contact:
- Email: {email}
- LinkedIn URL: {linkedin_url or "Not provided"}

Search for information and create a comprehensive enrichment profile."""

    input_state = {
        "messages": [HumanMessage(content=user_message)]
    }

    # Stream with updates mode to see each step
    for step in agent.stream(
        input_state,
        config={"configurable": {"thread_id": f"enrichment_{email}_{datetime.utcnow().timestamp()}"}},
        stream_mode="updates"
    ):
        yield step
```

---

## Core Concepts

### What is create_react_agent()?

`create_react_agent()` is LangGraph's prebuilt function that creates a **ReAct (Reasoning + Acting)** agent. It:

1. Takes an LLM and a list of tools
2. Creates a graph with agent reasoning and tool execution nodes
3. Automatically handles the loop of: reason → act → observe → repeat
4. Returns a compiled runnable graph

```python
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(model="claude-3-5-sonnet-20241022")
tools = [search_apollo_contact, search_linkedin_profile]

agent = create_react_agent(model, tools, prompt="Your system prompt here")
```

### Why use create_react_agent() vs. building from scratch?

| Aspect | create_react_agent() | Custom StateGraph |
|--------|---------------------|-------------------|
| **Setup Time** | 5 minutes | 30+ minutes |
| **Maintenance** | Auto-updated by LangGraph | Manual updates required |
| **Tool Error Handling** | Built-in ToolNode handling | Must implement custom |
| **Streaming** | Full support out-of-box | Must configure manually |
| **Production Ready** | Yes, battle-tested | Only if carefully designed |

**Use `create_react_agent()` when you need:**
- Standard tool-calling agent patterns
- Tool-based reasoning and acting
- Production reliability

**Use custom StateGraph when you need:**
- Complex multi-agent coordination
- Custom state transitions
- Specialized error handling

---

## Tool Selection & State Management

### Best Practice: Semantic Tool Selection

For many tools (10+), use semantic selection instead of passing all tools:

```python
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

# Index your tools by description
tool_documents = [
    Document(
        page_content=tool.description,
        id=tool.name,
        metadata={"tool_name": tool.name},
    )
    for tool in [search_apollo_contact, search_linkedin_profile, enrich_contact_summary]
]

vector_store = InMemoryVectorStore(embedding=OpenAIEmbeddings())
vector_store.add_documents(tool_documents)

# Dynamic tool selection
def select_tools(state: MessagesState) -> dict:
    """Select relevant tools based on user query"""
    query = state["messages"][-1].content
    relevant_docs = vector_store.similarity_search(query, k=2)
    selected_tool_names = [doc.id for doc in relevant_docs]
    return {"selected_tools": selected_tool_names}
```

### Tool Binding Best Practices

```python
# Good: Bind tools with specific configuration
model_with_tools = model.bind_tools(
    tools,
    # Prevent infinite parallel tool calls
    parallel_tool_calls=False,
    # Force tool usage if needed
    tool_choice={"type": "tool", "name": "search_apollo_contact"}  # optional
)

agent = create_react_agent(
    model=model_with_tools,
    tools=tools,
)

# Bad: Don't rebind tools in each node
# This is inefficient and can cause issues
```

---

## Max Iterations & Loop Control

### Setting Max Iterations to Prevent Infinite Loops

```python
# Invocation with recursion_limit (max iterations)
result = agent.invoke(
    input_state,
    config={
        "recursion_limit": 25,  # Max 25 tool calls before stopping
        "configurable": {"thread_id": "enrichment_1"}
    }
)

# Handle recursion limit exceeded
from langgraph.errors import GraphRecursionError

try:
    result = agent.invoke(input_state, config={"recursion_limit": 5})
except GraphRecursionError as e:
    logger.error(f"Agent exceeded max iterations: {e}")
    # Gracefully handle - use partial results
    return extract_enrichment_data(e.state.get("messages", []))
```

### Calculating Appropriate Iteration Limits

For enrichment agent with 3 tools:
- **Optimal**: 10-15 iterations
- **Safe**: 20-25 iterations
- **Maximum**: 50 iterations

```python
# Estimate iterations needed:
# 1. Search Apollo (1 iteration)
# 2. Tool execution (1 iteration)
# 3. Observe result, decide next step (1 iteration)
# 4. Search LinkedIn (1 iteration)
# 5. Tool execution (1 iteration)
# 6. Observe result (1 iteration)
# 7. Synthesize summary (1 iteration)
# 8. Tool execution (1 iteration)
# 9. Final response (1 iteration)
# Total: ~9 iterations + 5 safety margin = 14

DEFAULT_RECURSION_LIMIT = 25  # Safe default
CRITICAL_ENRICHMENT_LIMIT = 50  # When you absolutely need to succeed
```

### Streaming to Monitor Iterations

```python
def enrich_contact_with_monitoring(email: str) -> dict:
    """Monitor iteration count during enrichment"""
    agent = create_enrichment_agent()

    input_state = {
        "messages": [HumanMessage(content=f"Enrich: {email}")]
    }

    iteration_count = 0
    final_state = None

    for step in agent.stream(input_state, stream_mode="updates"):
        iteration_count += 1
        logger.info(f"Iteration {iteration_count}: {list(step.keys())}")

        if iteration_count > 30:
            logger.warning(f"Enrichment taking too many iterations: {iteration_count}")

        final_state = step

    return {
        "status": "success",
        "iterations_used": iteration_count,
        "data": extract_enrichment_data(final_state["agent"]["messages"]),
    }
```

---

## Processing Agent Output

### Extracting Tool Results from Agent Output

The agent's final state contains a message history. Parse it like this:

```python
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
import json

def extract_agent_output(result: dict) -> dict:
    """Extract structured data from agent execution result"""
    messages = result["messages"]

    extracted = {
        "user_input": None,
        "tool_calls": [],
        "tool_results": [],
        "final_reasoning": None,
        "final_response": None,
    }

    for i, msg in enumerate(messages):
        # User input
        if isinstance(msg, HumanMessage):
            extracted["user_input"] = msg.content

        # Tool calls from AI
        elif isinstance(msg, AIMessage):
            if msg.tool_calls:
                extracted["tool_calls"].extend([
                    {
                        "name": tc["name"],
                        "args": tc["args"],
                        "id": tc["id"],
                    }
                    for tc in msg.tool_calls
                ])

            # Final reasoning/response
            if not (i + 1 < len(messages) and isinstance(messages[i + 1], ToolMessage)):
                extracted["final_response"] = msg.content

        # Tool execution results
        elif isinstance(msg, ToolMessage):
            try:
                content = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                extracted["tool_results"].append({
                    "tool_name": msg.name,
                    "tool_call_id": msg.tool_call_id,
                    "status": content.get("status") if isinstance(content, dict) else "unknown",
                    "result": content,
                })
            except json.JSONDecodeError:
                extracted["tool_results"].append({
                    "tool_name": msg.name,
                    "tool_call_id": msg.tool_call_id,
                    "result": msg.content,
                })

    return extracted


# Usage
result = agent.invoke(input_state)
output = extract_agent_output(result)

print(f"Tool calls made: {len(output['tool_calls'])}")
for call in output['tool_calls']:
    print(f"  - {call['name']}: {call['args']}")

print(f"Tool results: {len(output['tool_results'])}")
for result in output['tool_results']:
    print(f"  - {result['tool_name']}: {result['status']}")

print(f"Final response: {output['final_response']}")
```

### Extracting Specific Data by Tool

```python
def extract_enrichment_results(result: dict) -> dict:
    """Extract enrichment-specific data from agent output"""
    messages = result["messages"]

    enrichment = {
        "apollo_data": None,
        "linkedin_data": None,
        "enrichment_summary": None,
        "raw_messages": messages,
    }

    for msg in messages:
        if isinstance(msg, ToolMessage):
            try:
                content = json.loads(msg.content) if isinstance(msg.content, str) else msg.content

                if msg.name == "search_apollo_contact":
                    enrichment["apollo_data"] = content.get("data")

                elif msg.name == "search_linkedin_profile":
                    enrichment["linkedin_data"] = content.get("data")

                elif msg.name == "enrich_contact_summary":
                    enrichment["enrichment_summary"] = content.get("data")

            except json.JSONDecodeError:
                logger.warning(f"Failed to parse tool result: {msg.content}")

    return enrichment
```

---

## Async Patterns with ainvoke()

### Basic Async Invocation

```python
import asyncio

async def enrich_async(email: str) -> dict:
    """Single async enrichment"""
    agent = create_enrichment_agent()

    input_state = {
        "messages": [HumanMessage(content=f"Enrich: {email}")]
    }

    # Use ainvoke for async execution
    result = await agent.ainvoke(input_state)
    return extract_enrichment_results(result)


# Usage
result = asyncio.run(enrich_async("john@example.com"))
```

### Concurrent Enrichment (Multiple Contacts)

```python
async def enrich_contacts_concurrent(emails: list[str]) -> list[dict]:
    """Enrich multiple contacts concurrently"""
    tasks = [
        enrich_async(email)
        for email in emails
    ]

    # Run all concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    return [
        {
            "email": email,
            "result": result,
            "status": "success" if not isinstance(result, Exception) else "error",
            "error": str(result) if isinstance(result, Exception) else None,
        }
        for email, result in zip(emails, results)
    ]


# Usage in FastAPI
@app.post("/api/enrich/batch")
async def batch_enrich(request: BatchEnrichRequest):
    results = await enrich_contacts_concurrent(request.emails)
    return {"results": results, "total": len(results)}
```

### Streaming Async with astream()

```python
async def enrich_with_streaming(email: str):
    """Stream agent progress asynchronously"""
    agent = create_enrichment_agent()

    input_state = {
        "messages": [HumanMessage(content=f"Enrich: {email}")]
    }

    async for step in agent.astream(input_state, stream_mode="updates"):
        # Yield each step for real-time updates
        yield step


# Usage in FastAPI streaming endpoint
@app.post("/api/enrich/stream")
async def stream_enrich(email: str):
    async def generate():
        async for step in enrich_with_streaming(email):
            yield f"data: {json.dumps(step)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Important: Config Parameter for Async Invocation

```python
async def enrich_with_config(email: str):
    """Async invocation with proper config"""
    agent = create_enrichment_agent()

    input_state = {
        "messages": [HumanMessage(content=f"Enrich: {email}")]
    }

    # IMPORTANT: Pass config explicitly for reliable async
    result = await agent.ainvoke(
        input_state,
        config={
            "configurable": {"thread_id": f"enrichment_{email}"},
            "recursion_limit": 25,
        }
    )

    return extract_enrichment_results(result)
```

---

## Error Handling for ReAct Agents

### Tool Error Handling

```python
from langgraph.prebuilt import ToolNode

# Method 1: Default error handling (automatic ToolMessage with error)
tool_node = ToolNode(tools=[search_apollo_contact, search_linkedin_profile])

# Method 2: Custom error message
tool_node = ToolNode(
    tools=[search_apollo_contact, search_linkedin_profile],
    handle_tool_errors="That tool call failed. Please try a different approach."
)

# Then use in agent
agent = create_react_agent(
    model=model,
    tools=tool_node,  # Pass the node instead of list
)
```

### Comprehensive Error Handling Pattern

```python
def safe_enrich_contact(email: str, linkedin_url: str = None, timeout: int = 30) -> dict:
    """
    Production-grade enrichment with comprehensive error handling.

    Args:
        email: Contact email
        linkedin_url: Optional LinkedIn URL
        timeout: Timeout in seconds

    Returns:
        Result dict with status, data, and error handling
    """
    from concurrent.futures import TimeoutError as FutureTimeoutError
    from langgraph.errors import GraphRecursionError

    agent = create_enrichment_agent()

    input_state = {
        "messages": [
            HumanMessage(
                content=f"Enrich contact:\nEmail: {email}\nLinkedIn: {linkedin_url or 'N/A'}"
            )
        ]
    }

    result = {
        "status": "unknown",
        "email": email,
        "enrichment_data": None,
        "error": None,
        "error_type": None,
    }

    try:
        # Invoke with timeout and recursion limit
        agent_result = agent.invoke(
            input_state,
            config={
                "recursion_limit": 25,
                "configurable": {"thread_id": f"enrich_{email}_{datetime.utcnow().timestamp()}"},
            },
        )

        result["status"] = "success"
        result["enrichment_data"] = extract_enrichment_results(agent_result)

    except GraphRecursionError as e:
        # Agent exceeded max iterations
        logger.warning(f"Recursion limit exceeded for {email}")
        result["status"] = "partial"
        result["error"] = "Agent exceeded max iterations - partial enrichment"
        result["error_type"] = "recursion_limit"
        result["enrichment_data"] = extract_enrichment_results({"messages": e.state.get("messages", [])})

    except FutureTimeoutError:
        logger.error(f"Timeout enriching {email}")
        result["status"] = "timeout"
        result["error"] = f"Enrichment timed out after {timeout}s"
        result["error_type"] = "timeout"

    except ValueError as e:
        logger.error(f"Invalid input for {email}: {str(e)}")
        result["status"] = "error"
        result["error"] = str(e)
        result["error_type"] = "invalid_input"

    except Exception as e:
        logger.exception(f"Unexpected error enriching {email}")
        result["status"] = "error"
        result["error"] = str(e)
        result["error_type"] = type(e).__name__

    return result
```

### Tool-Level Error Handling

```python
@tool
def search_apollo_contact_with_fallback(email: str) -> dict:
    """
    Search Apollo with fallback handling.
    """
    try:
        from app.services.apollo import ApolloService
        apollo = ApolloService()
        result = apollo.search_contact(email=email)

        if result:
            return {
                "status": "success",
                "email": email,
                "data": result,
            }
        else:
            # Not found is not an error
            return {
                "status": "not_found",
                "email": email,
                "data": None,
            }

    except Exception as e:
        # Log but don't raise - let agent decide what to do
        logger.error(f"Apollo error for {email}: {str(e)}")

        return {
            "status": "error",
            "email": email,
            "error": str(e),
            "message": "Apollo service temporarily unavailable. Proceeding with LinkedIn search.",
        }
```

---

## System Prompts & Tool Use Strategy

### Crafting Effective System Prompts

```python
# ============================================================================
# EXCELLENT SYSTEM PROMPT - Clear tool strategy
# ============================================================================

ENRICHMENT_SYSTEM_PROMPT = """You are a contact enrichment specialist with expertise in data gathering and synthesis.

YOUR GOAL:
Gather comprehensive contact information from Apollo and LinkedIn, then synthesize it into a enrichment profile.

ENRICHMENT WORKFLOW (follow this exactly):
1. First, use search_apollo_contact with the email address
   - This provides: name, title, company, phone, LinkedIn URL
2. If LinkedIn URL is available or found:
   - Use search_linkedin_profile with the LinkedIn URL
   - This provides: headline, skills, experience, education
3. Finally, use enrich_contact_summary with all gathered data
   - This creates the final enrichment profile

IMPORTANT CONSTRAINTS:
- Only call tools with complete, valid information
- If email is invalid or missing, ask for clarification
- If a tool returns "error" or "not_found", don't retry the same tool
- Use alternative tools or report what you found
- Never hallucinate data - report only what was found
- Email format must be valid (user@domain.com)
- LinkedIn URLs must start with https://linkedin.com/

TOOL OUTPUT INTERPRETATION:
- status: "success" = tool worked, use the data
- status: "error" = tool failed, try alternative approach
- status: "not_found" = contact not in system, report as-is
- status: "timeout" = service slow, still might have partial data

RESPONSE FORMAT:
Always end with a concise summary:
"Enrichment complete. Found: [name], [title], [company]. Skills: [skills]. Score: [score]/100"
"""

agent = create_react_agent(
    model=model,
    tools=tools,
    prompt=ENRICHMENT_SYSTEM_PROMPT,
)


# ============================================================================
# POOR SYSTEM PROMPT - Vague, leads to mistakes
# ============================================================================

POOR_PROMPT = """Enrich the contact with information."""
# Problem: No clear workflow, agent guesses tool order and parameters
```

### Tool Use Guidance in Prompts

```python
# Include explicit tool decision trees
TOOL_SELECTION_PROMPT = """You have 3 tools available:

1. search_apollo_contact(email: str)
   - Use when: You have an email address
   - Returns: Professional profile info
   - Success rate: 60% (many people not in Apollo)

2. search_linkedin_profile(profile_url: str)
   - Use when: You have LinkedIn URL
   - Returns: Skills, experience, education
   - Success rate: 85% (most profiles public)

3. enrich_contact_summary(contact_data: dict)
   - Use when: You have data from both Apollo and LinkedIn
   - Returns: Merged, scored enrichment profile
   - Success rate: 100% (always works if inputs provided)

DECISION RULES:
- Start with Apollo IF you have email
- Switch to LinkedIn IF Apollo fails or returns no LinkedIn URL
- Use summary tool ONLY when you have data from step 1 and/or 2
- If both Apollo and LinkedIn fail, report findings and skip summary

CRITICAL: Never call summary tool without at least some data from Apollo/LinkedIn
"""
```

### Preventing Tool Misuse

```python
# Force sequential tool calling
model_with_constraints = model.bind_tools(
    tools,
    # Prevent parallel tool calls
    parallel_tool_calls=False,
    # Optional: force a specific tool first
    tool_choice={"type": "tool", "name": "search_apollo_contact"}  # for initial call only
)

agent = create_react_agent(
    model=model_with_constraints,
    tools=tools,
)
```

---

## Performance Optimization

### Optimization Checklist

```python
# 1. CACHING - Cache tool results
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def cached_apollo_search(email_hash: str) -> dict:
    """Cache Apollo results for 1 hour"""
    # Implementation
    pass


# 2. PARALLEL TOOL CALLS (when safe)
model_with_parallel = model.bind_tools(
    tools,
    parallel_tool_calls=True,  # If tools don't depend on each other
)


# 3. TIMEOUT ENFORCEMENT
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Enrichment timeout")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)  # 30 second timeout

try:
    result = agent.invoke(input_state)
finally:
    signal.alarm(0)  # Cancel alarm


# 4. BATCH PROCESSING
async def batch_enrich_optimized(emails: list[str], batch_size: int = 5):
    """Process in batches to avoid overwhelming services"""
    results = []

    for i in range(0, len(emails), batch_size):
        batch = emails[i:i+batch_size]
        batch_results = await enrich_contacts_concurrent(batch)
        results.extend(batch_results)

        # Brief pause between batches
        await asyncio.sleep(0.5)

    return results


# 5. MODEL SELECTION FOR PERFORMANCE
# Use cheaper models for simple tasks
def create_enrichment_agent_optimized():
    """Use Haiku for speed over Sonnet for accuracy"""
    model = ChatAnthropic(
        model="claude-3-5-haiku-20241022",  # 3x faster, good for enrichment
        temperature=0.7,
        max_tokens=1000,  # Reduce for faster generation
    )

    return create_react_agent(model, tools)
```

### Performance Metrics

```python
import time
from dataclasses import dataclass

@dataclass
class EnrichmentMetrics:
    email: str
    total_time_ms: float
    iterations: int
    tools_called: int
    apollo_success: bool
    linkedin_success: bool
    enrichment_score: float

def enrich_with_metrics(email: str) -> tuple[dict, EnrichmentMetrics]:
    """Track performance metrics during enrichment"""
    agent = create_enrichment_agent()

    start_time = time.time()
    iteration_count = 0
    tool_calls = 0
    apollo_found = False
    linkedin_found = False

    input_state = {
        "messages": [HumanMessage(content=f"Enrich: {email}")]
    }

    for step in agent.stream(input_state, stream_mode="updates"):
        iteration_count += 1

        # Count tools called
        if "agent" in step and step["agent"].get("messages"):
            for msg in step["agent"]["messages"]:
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    tool_calls += len(msg.tool_calls)

    result = agent.invoke(input_state)
    final_data = extract_enrichment_results(result)

    elapsed_ms = (time.time() - start_time) * 1000

    # Determine success
    apollo_found = final_data["apollo_data"] is not None
    linkedin_found = final_data["linkedin_data"] is not None
    enrichment_score = (
        final_data["enrichment_summary"].get("enrichment_score", 0)
        if final_data["enrichment_summary"] else 0
    )

    metrics = EnrichmentMetrics(
        email=email,
        total_time_ms=elapsed_ms,
        iterations=iteration_count,
        tools_called=tool_calls,
        apollo_success=apollo_found,
        linkedin_success=linkedin_found,
        enrichment_score=enrichment_score,
    )

    return final_data, metrics
```

---

## Common Pitfalls & Solutions

### Pitfall 1: Infinite Tool Loops

```python
# PROBLEM: Agent keeps calling same tool
# Solution: Set max_iterations and monitor

result = agent.invoke(
    input_state,
    config={"recursion_limit": 15}  # MUST set this
)

# MONITOR
def enrich_with_loop_detection(email: str) -> dict:
    """Detect and break infinite loops"""
    agent = create_enrichment_agent()

    input_state = {
        "messages": [HumanMessage(content=f"Enrich: {email}")]
    }

    tool_call_counts = {}

    for step in agent.stream(input_state, stream_mode="updates"):
        for msg in step.get("agent", {}).get("messages", []):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc["name"]
                    tool_call_counts[tool_name] = tool_call_counts.get(tool_name, 0) + 1

                    # Alert if tool called too many times
                    if tool_call_counts[tool_name] > 3:
                        logger.warning(f"Tool {tool_name} called {tool_call_counts[tool_name]} times!")

    return agent.invoke(input_state)
```

### Pitfall 2: Tool Returns Dict as String

```python
# PROBLEM: Tool returns JSON string but code expects dict
# Solution: Always handle both types

def safe_parse_tool_result(content) -> dict:
    """Handle both string and dict tool results"""
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"status": "error", "raw": content}
    elif isinstance(content, dict):
        return content
    else:
        return {"status": "error", "type": type(content).__name__}
```

### Pitfall 3: Missing Thread ID

```python
# PROBLEM: No thread ID in config causes state corruption in concurrent scenarios
# Solution: Always provide thread_id

# WRONG
result = agent.invoke(input_state)  # Will lose state if multiple calls running

# RIGHT
result = agent.invoke(
    input_state,
    config={
        "configurable": {"thread_id": f"enrichment_{email}_{uuid.uuid4()}"},
        "recursion_limit": 25,
    }
)
```

### Pitfall 4: Not Handling Tool Errors in Tools

```python
# BAD: Tool raises exception
@tool
def bad_search_apollo(email: str) -> dict:
    apollo = ApolloService()
    return apollo.search(email)  # Will raise if API fails

# GOOD: Tool catches and returns error status
@tool
def good_search_apollo(email: str) -> dict:
    try:
        apollo = ApolloService()
        result = apollo.search(email)
        return {"status": "success", "data": result}
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Try LinkedIn search as alternative"
        }
```

### Pitfall 5: Async Config Issues in Python < 3.11

```python
# ISSUE: Python < 3.11 doesn't propagate context automatically
# Solution: Pass config explicitly

async def enrich_async_py310(email: str, config: dict = None):
    """Async invocation with explicit config for Python 3.10"""
    agent = create_enrichment_agent()

    # MUST pass config explicitly
    if config is None:
        config = {"configurable": {"thread_id": f"enrich_{email}"}}

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=f"Enrich: {email}")]},
        config=config,
    )

    return result
```

### Pitfall 6: No Fallback for API Failures

```python
# BAD: Single point of failure
def enrich_apollo_only(email: str) -> dict:
    agent = create_react_agent(model, [search_apollo_contact])
    # If Apollo is down, enrichment fails completely

# GOOD: Multiple pathways
def enrich_with_fallbacks(email: str) -> dict:
    agent = create_react_agent(
        model,
        tools=[
            search_apollo_contact,
            search_linkedin_profile,
            enrich_contact_summary,
        ]
    )

    # System prompt guides fallback strategy
    return agent.invoke(input_state)
```

---

## Quick Reference: Production Checklist

```python
# Production Readiness Checklist

CHECKLIST = """
CONFIGURATION:
[ ] Set recursion_limit (recommended: 25)
[ ] Provide thread_id in config
[ ] Use ChatAnthropic (not Chat​OpenAI)
[ ] Set temperature appropriately (0.7 for enrichment)
[ ] Limit max_tokens (2000 is reasonable)

TOOLS:
[ ] All tools catch exceptions and return status dict
[ ] Tools return consistent JSON structure
[ ] Tool descriptions are clear and concise
[ ] Tools have proper type hints
[ ] Tools include examples in docstrings

SYSTEM PROMPT:
[ ] Includes clear tool workflow
[ ] Specifies decision rules
[ ] Handles "not found" cases
[ ] Prevents tool misuse

ERROR HANDLING:
[ ] Try/catch around agent.invoke()
[ ] Handle GraphRecursionError separately
[ ] Extract and log failed tool calls
[ ] Return partial results when possible
[ ] Implement fallback strategies

MONITORING:
[ ] Log each tool call
[ ] Track iteration counts
[ ] Monitor response times
[ ] Alert on >3 iterations per tool
[ ] Track enrichment success rates

TESTING:
[ ] Unit test each tool independently
[ ] Integration test agent with mocked tools
[ ] Load test concurrent invocations
[ ] Test timeout scenarios
[ ] Test with invalid inputs
"""

print(CHECKLIST)
```

---

## Summary

**Key Takeaways:**

1. **Use `create_react_agent()`** - It's production-ready and handles tool calling automatically
2. **Set `recursion_limit`** - Prevent infinite loops (recommended: 25)
3. **Always catch exceptions** - `GraphRecursionError`, timeouts, invalid inputs
4. **Design tools carefully** - Return status dicts, handle errors internally
5. **Write clear prompts** - Include tool workflow and decision rules
6. **Use async for concurrency** - `ainvoke()` for multiple enrichments
7. **Extract structured data** - Parse messages to get tool results
8. **Monitor performance** - Track iterations, times, success rates
9. **Provide fallbacks** - Multiple tools reduce single points of failure
10. **Thread IDs matter** - Always provide thread_id in config for reliability

---

## References

- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **ChatAnthropic**: https://docs.anthropic.com/
- **ReAct Paper**: https://arxiv.org/abs/2210.03629
- **Tool Calling Best Practices**: https://python.langchain.com/docs/concepts/tool_calling/
