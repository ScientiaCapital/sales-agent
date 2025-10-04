# Project Init MCP - Complete Project Initialization

Initialize a project from scratch with all MCP servers and Task Master AI.

## Steps

1. **Verify Environment**
   - Check all required API keys
   - Verify MCP server connections
   - Confirm directory structure

2. **Initialize Task Master**
   - Run `task-master init` if not already done
   - Configure models with `task-master models`
   - Set up project structure

3. **Create Project Documentation**
   - Create README.md with project overview
   - Create CLAUDE.md with AI development guidelines
   - Set up .taskmaster/docs/prd.txt for requirements

4. **Generate Initial Tasks**
   - Parse PRD: `task-master parse-prd .taskmaster/docs/prd.txt`
   - Analyze complexity: `task-master analyze-complexity --research`
   - Expand tasks: `task-master expand --all --research`

5. **Set Up Git Workflow**
   - Initialize git if needed
   - Create .gitignore with proper exclusions
   - Make initial commit

6. **Verification**
   - Test all MCP connections
   - Verify task generation
   - Confirm environment is ready

## Output

Show completion status for each step and provide next actions.
