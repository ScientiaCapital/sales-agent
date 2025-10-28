# 🎭 MCP Team Workflows - Complete Guide

## Understanding MCP Orchestration

The MCP (Model Context Protocol) team provides specialized agents that work together to handle different aspects of development. Success comes from knowing which agent handles what.

## Agent Specializations

### 🧠 Serena - Code Intelligence Expert
**Best For:**
- Finding code symbols and references
- Understanding codebase structure
- Navigating complex code relationships
- Mapping dependencies

**Use When:**
- "Where is this function used?"
- "Show me all references to this class"
- "Find similar code patterns"
- "What does this file contain?"

### 📋 Task Master AI - Project Coordinator
**Best For:**
- Project-level task tracking
- Priority management
- Dependency coordination
- Progress monitoring

**Use When:**
- "What should I work on next?"
- "Show me all pending tasks"
- "Update task status"
- "What's blocking progress?"

### 🦐 Shrimp - Execution Specialist
**Best For:**
- Detailed task breakdown
- Implementation guidance
- Quality verification
- Completion scoring

**Use When:**
- "How do I implement this?"
- "Break this task into steps"
- "Verify this is complete"
- "Score this implementation"

### 🤔 Sequential Thinking - Problem Solver
**Best For:**
- Complex decision making
- Step-by-step analysis
- Architecture design
- Trade-off evaluation

**Use When:**
- "Help me design this system"
- "What's the best approach?"
- "Analyze this problem"
- "Evaluate these options"

### 💾 Memory - Knowledge Keeper
**Best For:**
- Saving decisions
- Storing patterns
- Recalling context
- Team knowledge base

**Use When:**
- "Save this decision"
- "Remember this pattern"
- "What did we decide about X?"
- "Store this for later"

## Complete Workflows

### 1. Feature Development (Full Cycle)

#### Phase 1: Planning
```
Command: /team-architect-mcp

Agent Flow:
1. Sequential Thinking: Define requirements
2. Serena: Analyze existing code
3. Sequential Thinking: Design solution
4. Memory: Save architecture decision

Output: Feature architecture document
```

#### Phase 2: Task Breakdown
```
Command: /team-shrimp-plan

Agent Flow:
1. Shrimp: Analyze complexity
2. Shrimp: Split into subtasks
3. Shrimp: Create implementation guides
4. Task Master: Import tasks

Output: Detailed task list with guides
```

#### Phase 3: Implementation
```
Command: /team-orchestrate

Agent Flow:
1. Task Master: Get next task
2. Serena: Navigate to code location
3. Execute: Make changes
4. Task Master: Update status

Repeat for each subtask
```

#### Phase 4: Verification
```
Command: /team-shrimp-verify

Agent Flow:
1. Shrimp: Check completion criteria
2. Sequential Thinking: Assess quality
3. Shrimp: Score implementation (0-100)
4. Memory: Save learnings

Threshold: 80+ for completion
```

#### Phase 5: Documentation
```
Command: /team-memory-save

Agent Flow:
1. Memory: Create feature entity
2. Memory: Add implementation details
3. Memory: Link related concepts
4. Memory: Store for future reference

Output: Persistent knowledge
```

### 2. Bug Investigation & Fix

#### Phase 1: Problem Analysis
```
Command: /team-think-sequential

Agent Flow:
1. Sequential Thinking: Define bug symptoms
2. Sequential Thinking: Form hypotheses
3. Sequential Thinking: Plan investigation
4. Output: Investigation strategy
```

#### Phase 2: Code Investigation
```
Command: /team-serena-analyze

Agent Flow:
1. Serena: Find suspected code
2. Serena: Search for error patterns
3. Serena: Trace execution flow
4. Serena: Map dependencies

Output: Bug location candidates
```

#### Phase 3: Research
```
Command: /team-research

Agent Flow:
1. Web Search: Similar issues
2. Context7: Library documentation
3. Serena: Related code patterns
4. Sequential Thinking: Synthesize

Output: Solution approaches
```

#### Phase 4: Root Cause
```
Command: /team-think-sequential

Agent Flow:
1. Sequential Thinking: Analyze evidence
2. Sequential Thinking: Test hypotheses
3. Sequential Thinking: Confirm cause
4. Output: Root cause identified
```

#### Phase 5: Fix Implementation
```
Command: /team-orchestrate

Agent Flow:
1. Task Master: Create fix task
2. Serena: Navigate to bug
3. Execute: Implement fix
4. Execute: Add regression test
5. Verify: Fix works

Output: Bug fixed
```

#### Phase 6: Documentation
```
Command: /team-memory-save

Agent Flow:
1. Memory: Save bug solution
2. Memory: Document prevention
3. Memory: Link related issues
4. Output: Knowledge saved
```

### 3. Code Review & Refactoring

#### Phase 1: Analysis
```
Command: /team-serena-analyze

Agent Flow:
1. Serena: Get code overview
2. Serena: Find all references
3. Serena: Check dependencies
4. Serena: Identify patterns

Output: Code analysis report
```

#### Phase 2: Quality Assessment
```
Command: /team-think-sequential

Agent Flow:
1. Sequential Thinking: Evaluate structure
2. Sequential Thinking: Check patterns
3. Sequential Thinking: Assess performance
4. Sequential Thinking: Review security

Output: Quality assessment
```

#### Phase 3: Improvement Planning
```
Command: /team-shrimp-plan

Agent Flow:
1. Shrimp: Identify improvements
2. Shrimp: Break into subtasks
3. Shrimp: Define success criteria
4. Task Master: Create tasks

Output: Refactoring plan
```

#### Phase 4: Implementation
```
Command: /team-orchestrate

Agent Flow:
1. Task Master: Get refactoring task
2. Serena: Navigate code
3. Execute: Apply changes
4. Execute: Run tests
5. Verify: No regressions

Output: Improved code
```

#### Phase 5: Pattern Capture
```
Command: /team-memory-save

Agent Flow:
1. Memory: Save refactoring pattern
2. Memory: Document improvements
3. Memory: Create guidelines
4. Output: Team knowledge updated
```

### 4. Performance Optimization

#### Phase 1: Bottleneck Identification
```
Command: /team-think-sequential

Agent Flow:
1. Sequential Thinking: Define goals
2. Sequential Thinking: Measure current
3. Sequential Thinking: Prioritize issues
4. Output: Optimization targets
```

#### Phase 2: Research
```
Command: /team-research

Agent Flow:
1. Web Search: Optimization techniques
2. Context7: Framework docs
3. Serena: Current implementation
4. Sequential Thinking: Evaluate options

Output: Optimization strategies
```

#### Phase 3: Code Analysis
```
Command: /team-serena-analyze

Agent Flow:
1. Serena: Find slow code
2. Serena: Analyze queries
3. Serena: Check render patterns
4. Output: Performance issues
```

#### Phase 4: Implementation
```
Command: /team-orchestrate

Agent Flow:
1. Shrimp: Plan optimizations
2. Task Master: Track changes
3. Execute: Apply optimizations
4. Execute: Measure improvements

Output: Performance gains
```

#### Phase 5: Documentation
```
Command: /team-memory-save

Agent Flow:
1. Memory: Save optimization patterns
2. Memory: Document benchmarks
3. Memory: Record techniques
4. Output: Performance playbook
```

## Daily Workflow Patterns

### 🌅 Morning Routine (15 minutes)
```bash
# 1. Initialize team
/team-start-advanced
# Output: All 8 MCP servers active, 6 memories loaded

# 2. Daily standup
/daily-standup-mcp
# Output: Yesterday's wins, today's priorities, blockers

# 3. Get first task
/team-task-master next
# Output: Next priority task with context

# 4. Ready to code!
```

### 💻 Development Session
```bash
# Feature work
/team-architect-mcp → /team-shrimp-plan → /team-orchestrate

# Bug fixing
/team-think-sequential → /team-serena-analyze → Fix

# Code review
/team-serena-analyze → /workflow/review-workflow
```

### 🌙 Evening Wrap-up (10 minutes)
```bash
# 1. Update task status
/team-task-master status
# Mark completed tasks

# 2. Sync systems
/team-sync-tasks
# Synchronize Task Master ↔ Shrimp

# 3. Save learnings
/team-memory-save
# Document important insights

# 4. Check health
/team-health-check
# Verify all systems for tomorrow
```

## Advanced Patterns

### Parallel Development
Run multiple workflows simultaneously:

**Terminal 1: Implementation**
```bash
/team-orchestrate
# Main feature development
```

**Terminal 2: Quality**
```bash
/team-serena-analyze
# Continuous code review
```

**Terminal 3: Research**
```bash
/team-research
# Investigate related topics
```

### Cross-Agent Intelligence
Combine agents for powerful workflows:

```bash
# Complex Architecture
Sequential Thinking → Serena → Research → Memory
# Design → Validate → Research → Document

# Systematic Debugging  
Sequential Thinking → Serena → Research → Fix → Memory
# Analyze → Locate → Research → Fix → Document

# Quality Review
Serena → Sequential Thinking → Shrimp → Memory
# Analyze → Assess → Verify → Document
```

### Context Persistence
Use Memory for team knowledge:

```bash
# After important decisions
/team-memory-save "Multi-tenant auth architecture"

# Before similar work
Memory: Recall auth patterns

# During onboarding
Memory: Share team knowledge

# Continuous learning
Memory: Build pattern library
```

## Troubleshooting Workflows

### MCP Server Issues
```bash
1. /team-health-check           # Check status
2. Review output for errors
3. Restart problematic server
4. Verify with /team-health-check
```

### Task Synchronization Issues
```bash
1. /team-task-master list       # Check Task Master
2. Shrimp: List tasks           # Check Shrimp
3. /team-sync-tasks            # Synchronize
4. Verify alignment
```

### Performance Problems
```bash
1. /team-health-check           # Check response times
2. Reduce concurrent operations
3. Clear caches if needed
4. Restart Claude Code
```

## Best Practices

### ✅ Do's
- Start every session with `/team-start-advanced`
- Use appropriate agent for each task type
- Save important decisions to Memory
- Sync tasks regularly
- Document patterns and learnings

### ❌ Don'ts
- Don't skip initialization
- Don't use wrong tool for the job
- Don't forget to save learnings
- Don't ignore health warnings
- Don't work without task tracking

## Success Metrics

### Productivity Indicators
- ✅ All MCP servers healthy
- ✅ Tasks in sync across systems
- ✅ Patterns saved to Memory
- ✅ Clear next priorities
- ✅ Quality gates passing

### Quality Indicators
- ✅ Code reviewed by Serena
- ✅ Tasks verified by Shrimp (80+)
- ✅ Decisions documented in Memory
- ✅ Tests passing
- ✅ Performance optimized

## Quick Reference

### Most Used Commands
```
/team-start-advanced      # Every session start
/daily-standup-mcp        # Every morning
/team-task-master next    # Get next work
/team-orchestrate         # Complex features
/team-serena-analyze      # Understand code
/team-memory-save         # Save insights
```

### Emergency Commands
```
/team-health-check        # System status
/team-sync-tasks         # Fix task conflicts
/team-research           # Quick answers
```

Your MCP team is ready! Start with `/team-start-advanced` 🚀
