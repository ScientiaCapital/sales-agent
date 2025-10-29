# Debug Workflow

## Overview

The Debug Workflow provides systematic troubleshooting and issue resolution for the sales-agent project. It analyzes logs, LangSmith traces, circuit breaker status, and system health to identify root causes and suggest fixes.

## Purpose & When to Use

**Use this workflow when:**
- Application errors or exceptions occur
- Performance issues are detected
- Services are not responding properly
- LangSmith traces show failures
- Circuit breakers are triggering
- System health is degraded
- You need to investigate recent issues

**Don't use this workflow for:**
- Feature development (use Feature Workflow)
- Code review (use Review Workflow)
- Performance optimization (use Performance Workflow)
- Routine monitoring (use monitoring tools)

## Prerequisites

### Environment Setup
- `.env` file with required API keys
- PostgreSQL and Redis running
- Log files accessible
- LangSmith API access (optional)

### Required Environment Variables
```bash
CEREBRAS_API_KEY=your_cerebras_key
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0
LANGCHAIN_API_KEY=your_langsmith_key  # Optional
```

### Log Files
The workflow analyzes these log sources:
- Application logs (`backend/logs/`)
- Error logs (`backend/logs/error.log`)
- System logs (Docker containers)
- LangSmith traces (via API)

## Step-by-Step Guide

### 1. Start the Workflow

```bash
# Interactive mode
python commands/debug_workflow.py

# Debug specific component
python commands/debug_workflow.py --component cerebras

# Debug recent errors
python commands/debug_workflow.py --type 1
```

### 2. Select Debug Scope

The workflow will prompt you for:

#### Debug Type
```
What would you like to debug?
1. Recent errors (last 24 hours)
2. Specific component (Cerebras, Redis, Database, etc.)
3. Performance issues
4. LangSmith traces
5. Circuit breaker status
6. Full system analysis
```

#### Time Range (for errors/performance)
```
Time range:
1. Last hour
2. Last 24 hours
3. Last week
4. Custom range
```

#### Component Selection (for specific debugging)
```
Select component:
1. Cerebras AI
2. Redis
3. Database
4. FastAPI
5. LangGraph agents
6. CRM sync
7. All components
```

#### Severity Filter
```
Severity filter:
1. All issues
2. Errors only
3. Warnings and errors
4. Critical only
```

### 3. Analysis Execution

The workflow performs comprehensive analysis based on your selections:

#### Recent Errors Analysis
- Scans application logs for error patterns
- Identifies error frequency and trends
- Categorizes errors by component and severity
- Tracks error resolution over time

#### Component-Specific Analysis
- **Cerebras AI**: Latency, error rates, API health
- **Redis**: Memory usage, connections, key expiration
- **Database**: Query performance, connection pool, slow queries
- **FastAPI**: Response times, request rates, error codes
- **LangGraph Agents**: Execution success, token usage, trace failures
- **CRM Sync**: Sync status, last sync time, error rates

#### Performance Analysis
- Endpoint response times
- Database query performance
- Memory and CPU usage
- Slow operation identification

#### LangSmith Trace Analysis
- Failed trace identification
- Slow trace detection
- Token usage analysis
- Agent execution patterns

#### Circuit Breaker Analysis
- Breaker state monitoring
- Failure count tracking
- Recovery time analysis
- Service dependency health

### 4. Issue Detection

The workflow identifies various issue types:

#### Error Issues
```json
{
  "type": "application",
  "severity": "error",
  "component": "api",
  "message": "Database connection timeout",
  "timestamp": "2025-01-01T12:00:00Z",
  "details": {"error": "Connection timeout after 30s"}
}
```

#### Performance Issues
```json
{
  "type": "performance",
  "severity": "warning",
  "component": "api",
  "message": "Slow endpoints detected: /api/leads/qualify",
  "details": {"response_time": 1650.0}
}
```

#### Circuit Breaker Issues
```json
{
  "type": "circuit_breaker",
  "severity": "error",
  "component": "cerebras",
  "message": "Circuit breaker OPEN for cerebras",
  "details": {"state": "OPEN", "failures": 5}
}
```

### 5. Fix Suggestions

The workflow provides specific fix recommendations:

#### Performance Fixes
- **Slow Endpoints**: "Optimize endpoint queries, add caching, or implement pagination"
- **Database Issues**: "Add database indexes, optimize queries, or increase connection pool"
- **Memory Issues**: "Implement memory optimization or increase available memory"

#### Circuit Breaker Fixes
- **Open Breakers**: "Check service health, review retry policies, or increase timeout values"
- **Half-Open Breakers**: "Monitor service recovery and adjust failure thresholds"

#### LangSmith Fixes
- **Failed Traces**: "Review agent prompts, check token limits, or optimize model usage"
- **Slow Traces**: "Optimize agent logic or reduce complexity"

### 6. Debug Report Generation

The workflow generates a comprehensive JSON report:

```json
{
  "scope": {
    "type": "2",
    "component": "1",
    "severity": "2"
  },
  "timestamp": "2025-01-01T12:00:00Z",
  "issues": [...],
  "components": ["Cerebras AI"],
  "metrics": {
    "cerebras_latency": 633.0,
    "cerebras_errors": 0,
    "total_errors": 0
  },
  "recommendations": [
    "Consider implementing comprehensive monitoring and alerting"
  ]
}
```

## MCP Workflow Integration

### When Manual Analysis is Needed

For complex debugging scenarios, the workflow can use the mandatory MCP pattern:

1. **Sequential Thinking**: Break down the debugging problem
2. **Serena**: Navigate codebase to find related code
3. **Context7**: Research debugging best practices
4. **Implementation**: Generate custom analysis scripts

### MCP Usage Example

```python
# For complex debugging scenarios
if scope['type'] == "6":  # Full system analysis
    # Use MCP for comprehensive analysis
    workflow_result = await self.mcp_manager.run_mandatory_workflow(
        f"Debug {scope['component']} issues"
    )
```

## Project-Specific Considerations

### Sales-Agent Architecture

#### LangGraph Agents
- **QualificationAgent**: Check Cerebras latency and success rates
- **EnrichmentAgent**: Monitor Apollo/LinkedIn API calls
- **GrowthAgent**: Analyze cyclic execution patterns
- **ConversationAgent**: Check voice integration health

#### CRM Integration
- **Close CRM**: Monitor bidirectional sync status
- **Apollo.io**: Check enrichment API health
- **LinkedIn**: Verify scraping operation status

#### Performance Targets
- **Cerebras**: <1000ms latency target
- **Database**: <50ms query time
- **API**: <200ms response time
- **Agent Execution**: <5000ms for complex agents

### Common Issues in Sales-Agent

#### 1. Cerebras API Issues
**Symptoms**: High latency, timeouts, errors
**Causes**: API rate limits, network issues, model overload
**Fixes**: Implement retry logic, circuit breakers, fallback models

#### 2. Redis Connection Issues
**Symptoms**: State persistence failures, agent state loss
**Causes**: Redis server down, connection pool exhaustion
**Fixes**: Check Redis health, increase connection limits

#### 3. Database Performance
**Symptoms**: Slow queries, connection timeouts
**Causes**: Missing indexes, inefficient queries, connection pool issues
**Fixes**: Add indexes, optimize queries, tune connection pool

#### 4. LangGraph Agent Failures
**Symptoms**: Agent execution errors, state corruption
**Causes**: Tool failures, prompt issues, state management problems
**Fixes**: Review tool implementations, optimize prompts, fix state schemas

## Examples

### Example 1: Debug Recent Errors

```bash
$ python commands/debug_workflow.py

What would you like to debug? 1
Time range: 2
Severity filter: 2

🔍 Analyzing recent errors...
✅ Found 3 errors in last 24 hours

📊 Metrics:
  - total_errors: 3
  - time_range: 24 hours
  - error_rate: 0.125

📁 Report generated:
  - debug_report_20250101_120000.json
```

### Example 2: Debug Cerebras Component

```bash
$ python commands/debug_workflow.py --component cerebras

🔍 Analyzing Cerebras AI...
✅ Component analysis completed

📊 Metrics:
  - cerebras_latency: 633.0
  - cerebras_errors: 0
  - api_health: healthy

📋 Recommendations:
  - Consider implementing comprehensive monitoring and alerting
```

### Example 3: Performance Analysis

```bash
$ python commands/debug_workflow.py --type 3

🔍 Analyzing performance issues...
⚠️  Found 2 performance issues

📊 Metrics:
  - response_times: {'/api/leads/qualify': 1650.0}
  - memory_usage: 65.2
  - cpu_usage: 45.8

📋 Fixes suggested:
  - Optimize endpoint queries, add caching, or implement pagination
  - Add database indexes, optimize queries, or increase connection pool
```

## Common Pitfalls

### 1. Insufficient Log Data
**Problem**: No recent logs or incomplete log coverage
**Solution**: Ensure proper logging configuration and log retention

### 2. Missing LangSmith Access
**Problem**: Cannot analyze LangSmith traces
**Solution**: Set `LANGCHAIN_API_KEY` environment variable

### 3. Component Not Available
**Problem**: Selected component is not running or accessible
**Solution**: Check service status and configuration

### 4. False Positives
**Problem**: Workflow reports issues that aren't actual problems
**Solution**: Review thresholds and adjust sensitivity settings

## Success Criteria

A successful debug workflow should:

✅ **Identify root causes** of issues clearly
✅ **Provide actionable fixes** with specific recommendations
✅ **Generate comprehensive reports** with all relevant data
✅ **Categorize issues** by severity and component
✅ **Suggest preventive measures** to avoid future issues

## Troubleshooting

### Check Prerequisites
```bash
python commands/common/checks.py
```

### Verify Log Access
```bash
ls -la backend/logs/
```

### Test Component Health
```bash
python commands/debug_workflow.py --component all
```

### Manual Override
```bash
python commands/debug_workflow.py --type 6  # Force full analysis
```

## Related Workflows

- **Feature Workflow**: For implementing fixes after debugging
- **Performance Workflow**: For detailed performance optimization
- **Review Workflow**: For validating fixes before deployment
- **Team Orchestrate**: For complex multi-component debugging