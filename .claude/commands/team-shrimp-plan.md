---
description: "Shrimp Task Manager planning and verification workflow"
---

# 🦐 Shrimp Task Manager - Planning & Verification

Advanced task planning with complexity analysis and quality verification.

## Planning Workflow:

### Step 1: Analyze Task Complexity
Use Shrimp to understand task scope:
- Assess complexity score (1-10 scale)
- Identify required subtasks
- Estimate effort and risks

Tool: `mcp__shrimp_task_manager__plan_task(description, requirements)`

### Step 2: Split into Subtasks
Break down complex tasks systematically:
- Create actionable subtasks (1-2 day chunks)
- Define clear acceptance criteria
- Establish dependencies between subtasks

Tool: `mcp__shrimp_task_manager__split_tasks(tasksRaw, globalAnalysisResult)`

### Step 3: Create Implementation Guide
For each subtask, provide:
- Detailed implementation steps
- Code examples and patterns
- Verification checkpoints

Tool: `mcp__shrimp_task_manager__execute_task(taskId)`

### Step 4: Verify Completion
Quality assurance for completed tasks:
- Check against verification criteria
- Score completion quality (0-100)
- Provide feedback for improvements

Tool: `mcp__shrimp_task_manager__verify_task(taskId, summary, score)`

## Shrimp's Strengths:

✅ **Detailed Planning** - Breaks tasks into granular steps
✅ **Quality Gates** - 80+ score required for completion
✅ **Context Awareness** - Uses codebase analysis for planning
✅ **Verification** - Ensures tasks meet standards

## Example Flow:

1. **Plan** - "Add real-time chat feature with LiveKit"
2. **Analyze** - Complexity: 8/10, needs 5 subtasks
3. **Split** - Create subtasks with implementation guides
4. **Execute** - Follow step-by-step instructions
5. **Verify** - Score: 95/100, task complete ✅

## Integration with Task Master:

Shrimp provides detailed execution guidance while Task Master handles project-level coordination. Use both for comprehensive task management!
