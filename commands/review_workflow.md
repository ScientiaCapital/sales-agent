# Review Workflow

## Overview

The Review Workflow ensures code quality before merging with comprehensive checks including linting, testing, security validation, and architecture review. It provides automated quality gates and detailed reports for the sales-agent project.

## Purpose & When to Use

**Use this workflow when:**
- Before merging code to main branch
- Before deploying to production
- After implementing new features
- During code review process
- Before creating pull requests
- When code quality issues are detected

**Don't use this workflow for:**
- Feature development (use Feature Workflow)
- Debugging issues (use Debug Workflow)
- Performance optimization (use Performance Workflow)
- Routine monitoring (use CI/CD tools)

## Prerequisites

### Environment Setup
- `.env` file with required API keys
- PostgreSQL and Redis running
- All dependencies installed
- Test database configured

### Required Environment Variables
```bash
CEREBRAS_API_KEY=your_cerebras_key
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0
LANGCHAIN_API_KEY=your_langsmith_key  # Optional
```

### Required Tools
- **Python**: Black, mypy, flake8, pytest
- **TypeScript**: ESLint, Prettier (if frontend exists)
- **Security**: bandit (optional)
- **Coverage**: pytest-cov

### Quality Thresholds
- **Test Coverage**: ≥80% (configurable)
- **Lint Errors**: 0 critical errors
- **Security Issues**: 0 critical vulnerabilities
- **Code Complexity**: ≤10 per function
- **Code Duplication**: ≤5%

## Step-by-Step Guide

### 1. Start the Workflow

```bash
# Interactive mode
python commands/review_workflow.py

# Quick review
python commands/review_workflow.py --quick

# Strict review
python commands/review_workflow.py --strict

# Pre-commit review
python commands/review_workflow.py --type 3
```

### 2. Select Review Scope

The workflow will prompt you for:

#### Review Type
```
What would you like to review?
1. Quick review (linting + basic tests)
2. Full review (all checks)
3. Pre-commit review
4. Pre-merge review
5. Security-focused review
6. Performance-focused review
7. Custom review
```

#### File Scope
```
File scope:
1. All files
2. Modified files only
3. Specific directory
4. Specific files
```

#### Check Types
```
Check types:
1. All checks
2. Linting only
3. Testing only
4. Security only
5. Custom selection
```

#### Quality Thresholds
```
Quality thresholds:
1. Default thresholds
2. Strict thresholds
3. Relaxed thresholds
4. Custom thresholds
```

### 3. Review Execution

The workflow performs comprehensive checks based on your selections:

#### Linting Checks
- **Python Linting**:
  - Black formatting check
  - mypy type checking
  - flake8 style checking
- **TypeScript Linting** (if frontend exists):
  - ESLint code quality
  - Prettier formatting

#### Testing Checks
- **Unit Tests**: pytest execution with coverage
- **Integration Tests**: API endpoint testing
- **Coverage Analysis**: Test coverage validation
- **Test Quality**: Test completeness and effectiveness

#### Security Checks
- **Hardcoded Secrets**: API keys, passwords, tokens
- **Vulnerability Scanning**: Known security issues
- **Dependency Security**: Outdated or vulnerable packages
- **Input Validation**: SQL injection, XSS prevention

#### Architecture Checks
- **Code Organization**: Proper separation of concerns
- **Design Patterns**: LangGraph, FastAPI patterns
- **Dependency Management**: Circular dependencies
- **Error Handling**: Proper exception management

#### Performance Checks
- **Performance Anti-patterns**: N+1 queries, inefficient loops
- **Memory Leaks**: Unclosed connections, large objects
- **Blocking Operations**: Synchronous calls in async code
- **Resource Usage**: CPU and memory efficiency

#### Documentation Checks
- **Docstrings**: Function and class documentation
- **README Updates**: Documentation completeness
- **API Documentation**: OpenAPI schema validation
- **Code Comments**: Complex logic explanation

### 4. Issue Detection

The workflow identifies various quality issues:

#### Linting Issues
```json
{
  "type": "formatting",
  "severity": "warning",
  "file": "backend/app/services/cerebras.py",
  "line": "15",
  "message": "Black formatting issues found"
}
```

#### Test Issues
```json
{
  "type": "coverage",
  "severity": "warning",
  "file": "tests",
  "message": "Test coverage 75% below threshold 80%",
  "details": "Current: 75%, Required: 80%"
}
```

#### Security Issues
```json
{
  "type": "security",
  "severity": "critical",
  "file": "backend/app/config.py",
  "message": "Potential hardcoded secret found",
  "details": "Pattern: api_key = 'sk-...'"
}
```

#### Architecture Issues
```json
{
  "type": "architecture",
  "severity": "warning",
  "file": "structure",
  "message": "Services directory not found - consider proper separation of concerns"
}
```

### 5. Quality Scoring

The workflow calculates a quality score (0-100):

#### Score Calculation
- **Base Score**: 100 points
- **Critical Issues**: -20 points each
- **Warning Issues**: -5 points each
- **Coverage Below Threshold**: -10 points
- **Security Issues**: -15 points each

#### Quality Levels
- **90-100**: Excellent quality
- **80-89**: Good quality
- **70-79**: Acceptable quality
- **60-69**: Needs improvement
- **<60**: Poor quality

### 6. Review Decision

The workflow determines if the review passes:

#### Pass Criteria
- **No Critical Issues**: 0 critical errors
- **Quality Score**: ≥70 (configurable)
- **Test Coverage**: ≥80% (configurable)
- **Security Issues**: 0 critical vulnerabilities

#### Fail Criteria
- **Critical Issues**: Any critical errors
- **Low Quality Score**: <70
- **Low Coverage**: <80%
- **Security Vulnerabilities**: Any critical security issues

### 7. Review Report Generation

The workflow generates a comprehensive JSON report:

```json
{
  "scope": {
    "type": "2",
    "file_scope": "1",
    "check_types": "1",
    "thresholds": "1"
  },
  "timestamp": "2025-01-01T12:00:00Z",
  "checks": {
    "linting": {
      "status": "completed",
      "error_count": 0,
      "warning_count": 2,
      "total_issues": 2
    },
    "testing": {
      "status": "completed",
      "coverage": 85.5,
      "threshold": 80,
      "issues": []
    }
  },
  "quality_score": 90.0,
  "total_issues": 2,
  "critical_issues": 0,
  "warning_issues": 2,
  "checks_passed": 6,
  "checks_total": 6
}
```

## MCP Workflow Integration

### When Manual Analysis is Needed

For complex review scenarios, the workflow can use the mandatory MCP pattern:

1. **Sequential Thinking**: Break down review requirements
2. **Serena**: Navigate codebase to find patterns
3. **Context7**: Research best practices for code quality
4. **Implementation**: Generate custom review scripts

### MCP Usage Example

```python
# For complex review scenarios
if scope['type'] == "7":  # Custom review
    # Use MCP for deep analysis
    workflow_result = await self.mcp_manager.run_mandatory_workflow(
        f"Review {scope['component']} code quality"
    )
```

## Project-Specific Considerations

### Sales-Agent Quality Standards

#### LangGraph Agents
- **Proper State Management**: TypedDict definitions
- **Error Handling**: Circuit breakers and retries
- **Tool Integration**: Proper @tool decorators
- **Streaming Support**: Real-time token delivery

#### FastAPI Endpoints
- **Async/Await**: Proper async patterns
- **Pydantic Models**: Request/response validation
- **Error Handling**: HTTPException usage
- **Documentation**: OpenAPI schema completeness

#### Database Operations
- **SQLAlchemy Patterns**: Proper ORM usage
- **Migration Management**: Alembic migrations
- **Connection Pooling**: Efficient connection usage
- **Query Optimization**: Index usage and query patterns

#### CRM Integration
- **API Key Security**: Environment variable usage
- **Error Handling**: Circuit breakers and retries
- **Data Validation**: Input/output validation
- **Sync Patterns**: Bidirectional sync logic

### Common Quality Issues

#### 1. Missing Type Hints
**Symptoms**: mypy errors, unclear function signatures
**Fixes**: Add type hints to all functions and variables

#### 2. Incomplete Error Handling
**Symptoms**: Unhandled exceptions, poor error messages
**Fixes**: Add try/catch blocks, proper exception types

#### 3. Hardcoded Values
**Symptoms**: API keys in code, magic numbers
**Fixes**: Move to environment variables, use constants

#### 4. Missing Tests
**Symptoms**: Low test coverage, untested edge cases
**Fixes**: Add unit tests, integration tests, edge case tests

#### 5. Performance Issues
**Symptoms**: Slow queries, memory leaks, blocking operations
**Fixes**: Optimize queries, fix memory leaks, use async patterns

## Examples

### Example 1: Quick Review

```bash
$ python commands/review_workflow.py --quick

🔍 Running quick review...
✅ Quick review completed

📊 Metrics:
  - test_coverage: 85.5
  - lint_errors: 0
  - security_issues: 0
  - quality_score: 90.0
  - checks_passed: 2
  - checks_total: 2

✅ Review PASSED
```

### Example 2: Full Review

```bash
$ python commands/review_workflow.py --type 2

🔍 Running full review...
✅ Full review completed

📊 Metrics:
  - test_coverage: 85.5
  - lint_errors: 2
  - security_issues: 0
  - quality_score: 85.0
  - checks_passed: 6
  - checks_total: 6

📁 Report generated:
  - review_report_20250101_120000.json

✅ Review PASSED
```

### Example 3: Review with Issues

```bash
$ python commands/review_workflow.py --type 2

🔍 Running full review...
❌ Full review completed

📊 Metrics:
  - test_coverage: 65.0
  - lint_errors: 5
  - security_issues: 1
  - quality_score: 45.0
  - checks_passed: 4
  - checks_total: 6

📁 Report generated:
  - review_report_20250101_120000.json

❌ Review FAILED
```

## Common Pitfalls

### 1. Insufficient Test Coverage
**Problem**: Tests don't cover all code paths
**Solution**: Add more test cases, especially edge cases

### 2. Ignoring Security Issues
**Problem**: Security vulnerabilities not addressed
**Solution**: Fix security issues before merging

### 3. Poor Error Handling
**Problem**: Unhandled exceptions cause crashes
**Solution**: Add proper try/catch blocks and error messages

### 4. Code Duplication
**Problem**: Repeated code patterns
**Solution**: Extract common functionality into reusable functions

### 5. Missing Documentation
**Problem**: Code is hard to understand
**Solution**: Add docstrings and comments for complex logic

## Success Criteria

A successful review workflow should:

✅ **Pass all quality checks** with no critical issues
✅ **Meet coverage thresholds** (≥80% test coverage)
✅ **Identify security issues** and provide fixes
✅ **Validate architecture patterns** and suggest improvements
✅ **Generate comprehensive reports** with actionable recommendations

## Troubleshooting

### Check Prerequisites
```bash
python commands/common/checks.py
```

### Install Required Tools
```bash
# Python tools
pip install black mypy flake8 pytest pytest-cov bandit

# TypeScript tools (if frontend exists)
cd frontend && npm install
```

### Run Specific Checks
```bash
# Linting only
python commands/review_workflow.py --type 2 --check-types 2

# Testing only
python commands/review_workflow.py --type 2 --check-types 3
```

### Fix Common Issues
```bash
# Fix Black formatting
black backend/app/

# Fix mypy type issues
mypy backend/app/

# Fix flake8 style issues
flake8 backend/app/
```

## Related Workflows

- **Feature Workflow**: For implementing fixes after review
- **Debug Workflow**: For fixing issues found in review
- **Performance Workflow**: For optimizing performance issues
- **Team Orchestrate**: For complex review coordination