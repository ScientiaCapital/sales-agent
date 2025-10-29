# Performance Workflow

## Overview

The Performance Workflow identifies and resolves performance bottlenecks to meet SLA targets. It provides comprehensive analysis, benchmarking, optimization suggestions, and cost validation for the sales-agent project.

## Purpose & When to Use

**Use this workflow when:**
- Application is running slowly
- Response times exceed targets
- Memory or CPU usage is high
- Cost per request is too high
- You need to optimize specific components
- Preparing for production deployment
- Monitoring performance over time

**Don't use this workflow for:**
- Debugging errors (use Debug Workflow)
- Code review (use Review Workflow)
- Feature development (use Feature Workflow)
- Routine monitoring (use monitoring tools)

## Prerequisites

### Environment Setup
- `.env` file with required API keys
- PostgreSQL and Redis running
- Application running and accessible
- Monitoring data available (optional)

### Required Environment Variables
```bash
CEREBRAS_API_KEY=your_cerebras_key
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0
DEEPSEEK_API_KEY=your_deepseek_key
```

### Performance Targets
The workflow validates against these targets:
- **Cerebras Latency**: <1000ms
- **Database Queries**: <50ms
- **API Response**: <200ms
- **Agent Execution**: <5000ms
- **Cerebras Cost**: <$0.0001 per request
- **DeepSeek Cost**: <$0.001 per request
- **Memory Usage**: <80%
- **CPU Usage**: <80%

## Step-by-Step Guide

### 1. Start the Workflow

```bash
# Interactive mode
python commands/performance_workflow.py

# Quick performance check
python commands/performance_workflow.py --quick

# Analyze specific component
python commands/performance_workflow.py --component cerebras

# Comprehensive analysis
python commands/performance_workflow.py --type 2
```

### 2. Select Analysis Type

The workflow will prompt you for:

#### Analysis Type
```
What would you like to analyze?
1. Quick performance check
2. Comprehensive analysis
3. Specific component (Cerebras, Database, API, etc.)
4. Cost optimization
5. Memory and CPU usage
6. Custom benchmarks
```

#### Time Range (for analysis types 1, 2, 4, 5)
```
Time range for analysis:
1. Last hour
2. Last 24 hours
3. Last week
4. Real-time (current)
```

#### Component Selection (for specific analysis)
```
Select component:
1. Cerebras AI
2. Database
3. FastAPI
4. LangGraph agents
5. Redis
6. CRM sync
7. All components
```

#### Benchmark Options (for custom benchmarks)
```
Benchmark options:
1. Load test API endpoints
2. Stress test database
3. Agent execution benchmarks
4. Memory usage under load
5. All benchmarks
```

### 3. Performance Analysis

The workflow performs comprehensive analysis based on your selections:

#### Quick Performance Check
- **Cerebras Latency**: Current vs target (1000ms)
- **Database Performance**: Query time vs target (50ms)
- **API Response Time**: Current vs target (200ms)
- **Memory Usage**: Current vs target (80%)
- **Performance Score**: Overall score (0-100)

#### Comprehensive Analysis
- Combines all analysis types
- Cross-component correlation
- System-wide performance picture
- Resource utilization patterns

#### Component-Specific Analysis
- **Cerebras AI**: Latency, cost, error rates
- **Database**: Query performance, connection pool, slow queries
- **FastAPI**: Response times, request rates, error codes
- **LangGraph Agents**: Execution time, success rates, token usage
- **Redis**: Memory usage, connections, key expiration
- **CRM Sync**: Sync performance, error rates, data volume

#### Cost Optimization Analysis
- **Cerebras Cost**: Per-request cost vs target ($0.0001)
- **DeepSeek Cost**: Per-request cost vs target ($0.001)
- **Claude Cost**: Per-request cost for comparison
- **Cost Trends**: Historical cost analysis
- **Optimization Opportunities**: Model switching, caching, batching

#### Resource Usage Analysis
- **Memory Usage**: Current vs target (80%)
- **CPU Usage**: Current vs target (80%)
- **Disk Usage**: Storage utilization
- **Resource Trends**: Historical usage patterns
- **Scaling Recommendations**: Resource scaling needs

### 4. Benchmark Execution

When benchmarks are requested, the workflow runs:

#### API Load Test
- **Requests per Second**: Throughput capacity
- **Response Time Distribution**: P50, P95, P99 latencies
- **Error Rate**: Failure percentage under load
- **Concurrent Users**: Maximum supported users

#### Database Stress Test
- **Queries per Second**: Database throughput
- **Query Time Distribution**: Performance under load
- **Connection Pool Usage**: Pool utilization
- **Lock Contention**: Database locking issues

#### Agent Execution Benchmarks
- **Qualification Agent**: Latency and success rate
- **Enrichment Agent**: Latency and success rate
- **Growth Agent**: Latency and success rate
- **Conversation Agent**: Latency and success rate

#### Memory Load Test
- **Baseline Memory**: Idle memory usage
- **Load Memory**: Memory under load
- **Memory Growth**: Memory increase rate
- **GC Efficiency**: Garbage collection effectiveness

### 5. Bottleneck Identification

The workflow identifies performance bottlenecks:

#### High Latency Issues
```json
{
  "component": "cerebras",
  "issue": "High latency: 1650ms",
  "severity": "warning",
  "current": 1650,
  "target": 1000
}
```

#### Resource Exhaustion
```json
{
  "component": "system",
  "issue": "High memory usage: 85%",
  "severity": "critical",
  "current": 85,
  "target": 80
}
```

#### Cost Issues
```json
{
  "component": "cerebras",
  "issue": "High cost: $0.0002 per request",
  "severity": "warning",
  "current": 0.0002,
  "target": 0.0001
}
```

### 6. Optimization Suggestions

The workflow provides specific optimization recommendations:

#### Cerebras AI Optimizations
- **Request Batching**: Group multiple requests
- **Caching**: Cache frequent responses
- **Fallback Models**: Use cheaper models for simple tasks
- **Prompt Optimization**: Reduce token usage

#### Database Optimizations
- **Index Addition**: Add missing indexes
- **Query Optimization**: Rewrite slow queries
- **Connection Pool Tuning**: Adjust pool settings
- **Partitioning**: Partition large tables

#### API Optimizations
- **Response Caching**: Cache API responses
- **Pagination**: Implement pagination for large datasets
- **Compression**: Enable response compression
- **Load Balancing**: Distribute load across instances

#### System Resource Optimizations
- **Memory Optimization**: Reduce memory footprint
- **CPU Optimization**: Optimize CPU-intensive operations
- **Scaling**: Scale resources horizontally or vertically
- **Resource Limits**: Implement proper resource limits

### 7. Performance Report Generation

The workflow generates a comprehensive JSON report:

```json
{
  "scope": {
    "type": "2",
    "time_range": "2"
  },
  "timestamp": "2025-01-01T12:00:00Z",
  "metrics": {
    "cerebras_latency": 633.0,
    "database_query_time": 25.5,
    "api_response_time": 150.0,
    "memory_usage": 65.2,
    "cpu_usage": 45.8
  },
  "targets": {
    "cerebras_latency": {
      "current": 633.0,
      "target": 1000,
      "met": true
    }
  },
  "bottlenecks": [...],
  "optimizations": [...],
  "performance_score": 85.5
}
```

## MCP Workflow Integration

### When Manual Analysis is Needed

For complex performance scenarios, the workflow can use the mandatory MCP pattern:

1. **Sequential Thinking**: Break down performance problems
2. **Serena**: Navigate codebase to find performance bottlenecks
3. **Context7**: Research performance optimization best practices
4. **Implementation**: Generate custom optimization scripts

### MCP Usage Example

```python
# For complex performance scenarios
if scope['type'] == "2":  # Comprehensive analysis
    # Use MCP for deep analysis
    workflow_result = await self.mcp_manager.run_mandatory_workflow(
        f"Analyze {scope['component']} performance"
    )
```

## Project-Specific Considerations

### Sales-Agent Performance Targets

#### LangGraph Agents
- **QualificationAgent**: <1000ms (Cerebras)
- **EnrichmentAgent**: <3000ms (Apollo + LinkedIn)
- **GrowthAgent**: <5000ms (DeepSeek research)
- **MarketingAgent**: <4000ms (Parallel execution)
- **BDRAgent**: <2000ms per node
- **ConversationAgent**: <1000ms per turn

#### CRM Integration
- **Close CRM Sync**: <5000ms bidirectional
- **Apollo Enrichment**: <2000ms per contact
- **LinkedIn Scraping**: <3000ms per profile

#### Cost Targets
- **Cerebras**: <$0.0001 per qualification
- **DeepSeek**: <$0.001 per research operation
- **Claude**: <$0.002 per complex reasoning

### Common Performance Issues

#### 1. Cerebras Latency Spikes
**Symptoms**: Response times >1000ms
**Causes**: API rate limits, model overload, network issues
**Fixes**: Implement caching, request batching, fallback models

#### 2. Database Query Performance
**Symptoms**: Query times >50ms
**Causes**: Missing indexes, inefficient queries, connection pool issues
**Fixes**: Add indexes, optimize queries, tune connection pool

#### 3. Memory Leaks
**Symptoms**: Memory usage >80%
**Causes**: Unclosed connections, large objects, circular references
**Fixes**: Fix memory leaks, implement proper cleanup, add monitoring

#### 4. Agent Execution Delays
**Symptoms**: Agent execution >5000ms
**Causes**: Tool failures, complex prompts, state management issues
**Fixes**: Optimize prompts, fix tool implementations, improve state handling

## Examples

### Example 1: Quick Performance Check

```bash
$ python commands/performance_workflow.py --quick

⚡ Running quick performance check...
✅ Performance check completed

📊 Metrics:
  - targets_met: 4
  - targets_total: 4
  - performance_score: 100.0

📁 Report generated:
  - performance_report_20250101_120000.json
```

### Example 2: Cerebras Component Analysis

```bash
$ python commands/performance_workflow.py --component cerebras

⚡ Analyzing Cerebras AI performance...
✅ Component analysis completed

📊 Metrics:
  - cerebras_latency: 633.0
  - cerebras_cost: 0.000006
  - targets_met: 2
  - targets_total: 2

📋 Optimizations suggested:
  - Implement request batching, add caching, or use fallback models
```

### Example 3: Comprehensive Analysis with Benchmarks

```bash
$ python commands/performance_workflow.py --type 2

⚡ Running comprehensive performance analysis...
⚡ Running performance benchmarks...
✅ Analysis completed

📊 Metrics:
  - targets_met: 6
  - targets_total: 8
  - performance_score: 75.0
  - optimizations_suggested: 3

📁 Report generated:
  - performance_report_20250101_120000.json
```

## Common Pitfalls

### 1. Insufficient Baseline Data
**Problem**: No historical data for comparison
**Solution**: Run analysis regularly to build baseline

### 2. Misleading Metrics
**Problem**: Metrics don't reflect real user experience
**Solution**: Use realistic test data and user scenarios

### 3. Ignoring Cost Impact
**Problem**: Optimizing performance without considering cost
**Solution**: Balance performance and cost in optimization decisions

### 4. Over-Optimization
**Problem**: Optimizing components that don't need it
**Solution**: Focus on actual bottlenecks identified by analysis

## Success Criteria

A successful performance workflow should:

✅ **Meet SLA targets** for all critical components
✅ **Identify bottlenecks** with specific metrics
✅ **Provide actionable optimizations** with clear priorities
✅ **Generate comprehensive reports** with all relevant data
✅ **Validate cost targets** and suggest cost optimizations

## Troubleshooting

### Check Prerequisites
```bash
python commands/common/checks.py
```

### Verify Performance Targets
```bash
python commands/performance_workflow.py --type 1
```

### Run Specific Component Analysis
```bash
python commands/performance_workflow.py --component all
```

### Force Benchmark Execution
```bash
python commands/performance_workflow.py --type 6
```

## Related Workflows

- **Debug Workflow**: For fixing performance issues
- **Feature Workflow**: For implementing performance optimizations
- **Review Workflow**: For validating performance improvements
- **Team Orchestrate**: For complex performance optimization projects