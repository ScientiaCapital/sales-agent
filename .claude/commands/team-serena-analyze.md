---
description: "Deep code analysis and navigation with Serena"
---

# 🔍 Serena Code Intelligence & Analysis

Advanced codebase exploration using Serena's semantic code tools.

## Analysis Capabilities:

### 1. Symbol Discovery
Find any code symbol (class, function, variable):
- Search by name with substring matching
- Navigate symbol hierarchies
- Understand symbol relationships

Tool: `mcp__serena__find_symbol(name_path, relative_path, include_body)`

### 2. Reference Tracking
Find all references to a symbol:
- See where code is used
- Understand dependencies
- Track call chains

Tool: `mcp__serena__find_referencing_symbols(name_path, relative_path)`

### 3. Pattern Search
Search for code patterns across codebase:
- Regex-based content search
- Filter by file types
- Context-aware results

Tool: `mcp__serena__search_for_pattern(substring_pattern, relative_path)`

### 4. File Overview
Get high-level file structure:
- Top-level symbols
- Imports and exports
- File organization

Tool: `mcp__serena__get_symbols_overview(relative_path)`

## Analysis Workflows:

### Understanding New Code
1. **List Directory** - See file structure
2. **Get Overview** - Understand file organization
3. **Find Symbols** - Locate key components
4. **Trace References** - Understand relationships

### Refactoring Preparation
1. **Find Symbol** - Locate code to refactor
2. **Find References** - See all usage
3. **Analyze Impact** - Understand dependencies
4. **Plan Changes** - Create safe refactoring strategy

### Bug Investigation
1. **Search Pattern** - Find error-related code
2. **Find Symbol** - Locate problematic function
3. **Trace References** - See how it's called
4. **Identify Root Cause** - Understand bug origin

## Example Analysis:

```
Task: "Understand multi-tenant routing in middleware.ts"

1. Get file overview:
   mcp__serena__get_symbols_overview("middleware.ts")

2. Find routing function:
   mcp__serena__find_symbol("middleware", "middleware.ts", include_body: true)

3. Find tenant config:
   mcp__serena__find_symbol("getDomainConfig", include_body: true)

4. Find all references:
   mcp__serena__find_referencing_symbols("getDomainConfig", "src/config/domains.config.ts")
```

## Serena's Strengths:

✅ **Semantic Search** - Understands code structure, not just text
✅ **Fast Navigation** - Jump directly to symbols
✅ **Relationship Mapping** - See how code connects
✅ **Memory Integration** - Saves insights for future use

Perfect for: Code exploration, refactoring, bug investigation, architecture review
