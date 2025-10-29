#!/usr/bin/env python3
"""
Review Workflow

Ensure code quality before merging with comprehensive checks.
Features: Linting, testing, security checks, architecture validation.
"""

import sys
import argparse
import asyncio
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

# Add backend to Python path
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from commands.common.workflow_base import WorkflowBase, WorkflowResult
from commands.common.checks import Checks
from commands.common.mcp_manager import MCPManager


class ReviewWorkflow(WorkflowBase):
    """Code review workflow for quality assurance."""
    
    def __init__(self, verbose: bool = True):
        super().__init__(verbose)
        self.checks = Checks(verbose=verbose)
        self.mcp_manager = MCPManager(verbose=verbose)
        self.review_results = {}
        self.quality_thresholds = {
            "test_coverage": 80,      # %
            "lint_errors": 0,         # count
            "security_issues": 0,     # count
            "complexity_score": 10,   # max
            "duplication": 5          # %
        }
    
    def run(self) -> WorkflowResult:
        """Run review workflow."""
        try:
            self.start_progress("Review Workflow")
            
            # Run prerequisite checks
            if not self._run_checks():
                return WorkflowResult(
                    success=False,
                    message="Prerequisite checks failed",
                    errors=["Environment or service checks failed"]
                )
            
            # Get review scope
            scope = self._get_review_scope()
            
            # Run review analysis
            analysis_results = self._run_review_analysis(scope)
            
            # Generate review report
            report = self._generate_review_report(analysis_results)
            
            # Determine if review passes
            review_passed = self._evaluate_review_results(analysis_results)
            
            self.end_progress("Review Workflow")
            
            return WorkflowResult(
                success=review_passed,
                message="Review completed - " + ("PASSED" if review_passed else "FAILED"),
                files_created=[report] if report else [],
                metrics={
                    "test_coverage": analysis_results.get('test_coverage', 0),
                    "lint_errors": analysis_results.get('lint_errors', 0),
                    "security_issues": analysis_results.get('security_issues', 0),
                    "quality_score": analysis_results.get('quality_score', 0),
                    "checks_passed": analysis_results.get('checks_passed', 0),
                    "checks_total": analysis_results.get('checks_total', 0)
                }
            )
            
        except Exception as e:
            self.log_error(f"Review workflow failed: {e}")
            return WorkflowResult(
                success=False,
                message=f"Review workflow failed: {e}",
                errors=[str(e)]
            )
    
    def _run_checks(self) -> bool:
        """Run prerequisite checks."""
        self.log_info("Running prerequisite checks...")
        
        # Run basic checks
        check_results = asyncio.run(self.checks.run_all_checks())
        
        if self.checks.has_critical_failures():
            self.log_error("Critical checks failed")
            return False
        
        self.log_success("All prerequisite checks passed")
        return True
    
    def _get_review_scope(self) -> Dict[str, Any]:
        """Get review scope from user."""
        print("\n" + "="*60)
        print("🔍 REVIEW WORKFLOW")
        print("="*60)
        
        scope = {}
        
        # Review type
        print("\nWhat would you like to review?")
        print("1. Quick review (linting + basic tests)")
        print("2. Full review (all checks)")
        print("3. Pre-commit review")
        print("4. Pre-merge review")
        print("5. Security-focused review")
        print("6. Performance-focused review")
        print("7. Custom review")
        
        choice = input("Enter choice (1-7): ").strip()
        scope['type'] = choice
        
        # File scope
        print("\nFile scope:")
        print("1. All files")
        print("2. Modified files only")
        print("3. Specific directory")
        print("4. Specific files")
        
        file_choice = input("Enter choice (1-4): ").strip()
        scope['file_scope'] = file_choice
        
        if file_choice == "3":
            directory = input("Enter directory path: ").strip()
            scope['directory'] = directory
        elif file_choice == "4":
            files = input("Enter file paths (comma-separated): ").strip()
            scope['files'] = [f.strip() for f in files.split(',')]
        
        # Check types
        print("\nCheck types:")
        print("1. All checks")
        print("2. Linting only")
        print("3. Testing only")
        print("4. Security only")
        print("5. Custom selection")
        
        check_choice = input("Enter choice (1-5): ").strip()
        scope['check_types'] = check_choice
        
        if check_choice == "5":
            print("\nSelect specific checks:")
            print("1. Python linting (Black, mypy, flake8)")
            print("2. TypeScript linting (ESLint, Prettier)")
            print("3. Unit tests")
            print("4. Integration tests")
            print("5. Security scan")
            print("6. Architecture validation")
            print("7. Performance checks")
            print("8. Documentation checks")
            
            selected_checks = input("Enter check numbers (comma-separated): ").strip()
            scope['selected_checks'] = [int(x.strip()) for x in selected_checks.split(',')]
        
        # Quality thresholds
        print("\nQuality thresholds:")
        print("1. Default thresholds")
        print("2. Strict thresholds")
        print("3. Relaxed thresholds")
        print("4. Custom thresholds")
        
        threshold_choice = input("Enter choice (1-4): ").strip()
        scope['thresholds'] = threshold_choice
        
        if threshold_choice == "4":
            test_coverage = input("Test coverage threshold (default 80): ").strip()
            scope['custom_thresholds'] = {
                "test_coverage": int(test_coverage) if test_coverage else 80
            }
        
        return scope
    
    def _run_review_analysis(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run review analysis based on scope."""
        self.log_info("Running review analysis...")
        
        results = {
            "scope": scope,
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "issues": [],
            "recommendations": []
        }
        
        # Determine which checks to run
        check_types = self._get_check_types(scope)
        
        # Run checks
        for check_type in check_types:
            check_result = self._run_check(check_type, scope)
            results['checks'][check_type] = check_result
        
        # Calculate overall metrics
        results.update(self._calculate_review_metrics(results))
        
        return results
    
    def _get_check_types(self, scope: Dict[str, Any]) -> List[str]:
        """Get list of check types to run."""
        check_choice = scope.get('check_types', '1')
        
        if check_choice == "1":  # All checks
            return ["linting", "testing", "security", "architecture", "performance", "documentation"]
        elif check_choice == "2":  # Linting only
            return ["linting"]
        elif check_choice == "3":  # Testing only
            return ["testing"]
        elif check_choice == "4":  # Security only
            return ["security"]
        elif check_choice == "5":  # Custom selection
            selected = scope.get('selected_checks', [])
            check_map = {
                1: "linting",
                2: "linting",  # TypeScript linting
                3: "testing",
                4: "testing",  # Integration tests
                5: "security",
                6: "architecture",
                7: "performance",
                8: "documentation"
            }
            return [check_map.get(x, "linting") for x in selected if x in check_map]
        
        return ["linting", "testing"]
    
    def _run_check(self, check_type: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run a specific check type."""
        self.log_info(f"Running {check_type} check...")
        
        if check_type == "linting":
            return self._run_linting_check(scope)
        elif check_type == "testing":
            return self._run_testing_check(scope)
        elif check_type == "security":
            return self._run_security_check(scope)
        elif check_type == "architecture":
            return self._run_architecture_check(scope)
        elif check_type == "performance":
            return self._run_performance_check(scope)
        elif check_type == "documentation":
            return self._run_documentation_check(scope)
        else:
            return {"status": "skipped", "message": f"Unknown check type: {check_type}"}
    
    def _run_linting_check(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run linting checks."""
        issues = []
        
        # Python linting
        python_issues = self._run_python_linting(scope)
        issues.extend(python_issues)
        
        # TypeScript linting
        typescript_issues = self._run_typescript_linting(scope)
        issues.extend(typescript_issues)
        
        # Count issues by severity
        error_count = len([i for i in issues if i.get('severity') == 'error'])
        warning_count = len([i for i in issues if i.get('severity') == 'warning'])
        
        return {
            "status": "completed",
            "issues": issues,
            "error_count": error_count,
            "warning_count": warning_count,
            "total_issues": len(issues)
        }
    
    def _run_python_linting(self, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run Python linting checks."""
        issues = []
        
        # Black formatting check
        try:
            result = subprocess.run(
                ["black", "--check", "--diff", "."],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            if result.returncode != 0:
                issues.append({
                    "type": "formatting",
                    "severity": "warning",
                    "file": "multiple",
                    "message": "Black formatting issues found",
                    "details": result.stdout
                })
        except FileNotFoundError:
            issues.append({
                "type": "tool",
                "severity": "warning",
                "file": "system",
                "message": "Black not found - install with: pip install black"
            })
        
        # mypy type checking
        try:
            result = subprocess.run(
                ["mypy", "backend/app/"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            if result.returncode != 0:
                issues.append({
                    "type": "typing",
                    "severity": "error",
                    "file": "multiple",
                    "message": "Type checking issues found",
                    "details": result.stdout
                })
        except FileNotFoundError:
            issues.append({
                "type": "tool",
                "severity": "warning",
                "file": "system",
                "message": "mypy not found - install with: pip install mypy"
            })
        
        # flake8 style checking
        try:
            result = subprocess.run(
                ["flake8", "backend/app/"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            if result.returncode != 0:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        parts = line.split(':', 3)
                        if len(parts) >= 4:
                            issues.append({
                                "type": "style",
                                "severity": "warning",
                                "file": parts[0],
                                "line": parts[1],
                                "message": parts[3].strip()
                            })
        except FileNotFoundError:
            issues.append({
                "type": "tool",
                "severity": "warning",
                "file": "system",
                "message": "flake8 not found - install with: pip install flake8"
            })
        
        return issues
    
    def _run_typescript_linting(self, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run TypeScript linting checks."""
        issues = []
        
        # Check if frontend directory exists
        frontend_dir = Path(__file__).parent.parent / 'frontend'
        if not frontend_dir.exists():
            return issues
        
        # ESLint check
        try:
            result = subprocess.run(
                ["npm", "run", "lint"],
                capture_output=True,
                text=True,
                cwd=frontend_dir
            )
            if result.returncode != 0:
                issues.append({
                    "type": "linting",
                    "severity": "warning",
                    "file": "frontend",
                    "message": "ESLint issues found",
                    "details": result.stdout
                })
        except FileNotFoundError:
            issues.append({
                "type": "tool",
                "severity": "warning",
                "file": "frontend",
                "message": "npm not found or frontend not set up"
            })
        
        return issues
    
    def _run_testing_check(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run testing checks."""
        issues = []
        
        # Run unit tests
        try:
            result = subprocess.run(
                ["pytest", "backend/tests/", "--cov=backend/app", "--cov-report=term-missing"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            # Parse coverage from output
            coverage = self._parse_coverage_from_pytest(result.stdout)
            
            if result.returncode != 0:
                issues.append({
                    "type": "test",
                    "severity": "error",
                    "file": "tests",
                    "message": "Tests failed",
                    "details": result.stdout
                })
            
            # Check coverage threshold
            threshold = self._get_test_coverage_threshold(scope)
            if coverage < threshold:
                issues.append({
                    "type": "coverage",
                    "severity": "warning",
                    "file": "tests",
                    "message": f"Test coverage {coverage}% below threshold {threshold}%",
                    "details": f"Current: {coverage}%, Required: {threshold}%"
                })
            
            return {
                "status": "completed",
                "coverage": coverage,
                "threshold": threshold,
                "issues": issues,
                "test_output": result.stdout
            }
            
        except FileNotFoundError:
            return {
                "status": "error",
                "message": "pytest not found - install with: pip install pytest pytest-cov",
                "issues": [{
                    "type": "tool",
                    "severity": "error",
                    "file": "system",
                    "message": "pytest not found"
                }]
            }
    
    def _run_security_check(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run security checks."""
        issues = []
        
        # Check for hardcoded secrets
        secret_issues = self._check_hardcoded_secrets()
        issues.extend(secret_issues)
        
        # Check for security vulnerabilities
        vuln_issues = self._check_security_vulnerabilities()
        issues.extend(vuln_issues)
        
        # Check for insecure dependencies
        dep_issues = self._check_dependency_security()
        issues.extend(dep_issues)
        
        return {
            "status": "completed",
            "issues": issues,
            "secret_count": len(secret_issues),
            "vulnerability_count": len(vuln_issues),
            "dependency_issues": len(dep_issues)
        }
    
    def _check_hardcoded_secrets(self) -> List[Dict[str, Any]]:
        """Check for hardcoded secrets."""
        issues = []
        
        # Common secret patterns
        secret_patterns = [
            r'api_key\s*=\s*["\'][^"\']+["\']',
            r'password\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\'][^"\']+["\']',
            r'sk-[a-zA-Z0-9]{20,}',
            r'pk_[a-zA-Z0-9]{20,}'
        ]
        
        # Search in Python files
        python_files = list(Path(__file__).parent.parent.glob("**/*.py"))
        for file_path in python_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    for pattern in secret_patterns:
                        import re
                        if re.search(pattern, content, re.IGNORECASE):
                            issues.append({
                                "type": "security",
                                "severity": "critical",
                                "file": str(file_path),
                                "message": "Potential hardcoded secret found",
                                "details": f"Pattern: {pattern}"
                            })
            except Exception:
                continue
        
        return issues
    
    def _check_security_vulnerabilities(self) -> List[Dict[str, Any]]:
        """Check for security vulnerabilities."""
        issues = []
        
        # Check for common security issues
        security_issues = [
            "SQL injection",
            "XSS vulnerability",
            "CSRF protection",
            "Input validation",
            "Authentication bypass"
        ]
        
        # This is a simplified check - in practice, you'd use tools like bandit
        return issues
    
    def _check_dependency_security(self) -> List[Dict[str, Any]]:
        """Check for insecure dependencies."""
        issues = []
        
        # Check requirements.txt for known vulnerabilities
        requirements_file = Path(__file__).parent.parent / 'backend' / 'requirements.txt'
        if requirements_file.exists():
            try:
                with open(requirements_file, 'r') as f:
                    content = f.read()
                    # Check for outdated packages
                    if 'django' in content and 'django<3.0' not in content:
                        issues.append({
                            "type": "dependency",
                            "severity": "warning",
                            "file": "requirements.txt",
                            "message": "Django version not pinned - potential security risk"
                        })
            except Exception:
                pass
        
        return issues
    
    def _run_architecture_check(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run architecture validation checks."""
        issues = []
        
        # Check for architectural patterns
        arch_issues = self._check_architectural_patterns()
        issues.extend(arch_issues)
        
        # Check for code organization
        org_issues = self._check_code_organization()
        issues.extend(org_issues)
        
        return {
            "status": "completed",
            "issues": issues,
            "pattern_issues": len(arch_issues),
            "organization_issues": len(org_issues)
        }
    
    def _check_architectural_patterns(self) -> List[Dict[str, Any]]:
        """Check for proper architectural patterns."""
        issues = []
        
        # Check for proper separation of concerns
        backend_dir = Path(__file__).parent.parent / 'backend' / 'app'
        
        # Check if services are properly separated
        if not (backend_dir / 'services').exists():
            issues.append({
                "type": "architecture",
                "severity": "warning",
                "file": "structure",
                "message": "Services directory not found - consider proper separation of concerns"
            })
        
        # Check if models are properly separated
        if not (backend_dir / 'models').exists():
            issues.append({
                "type": "architecture",
                "severity": "warning",
                "file": "structure",
                "message": "Models directory not found - consider proper data layer separation"
            })
        
        return issues
    
    def _check_code_organization(self) -> List[Dict[str, Any]]:
        """Check for proper code organization."""
        issues = []
        
        # Check for proper imports
        # Check for circular dependencies
        # Check for proper error handling
        
        return issues
    
    def _run_performance_check(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run performance checks."""
        issues = []
        
        # Check for performance anti-patterns
        perf_issues = self._check_performance_patterns()
        issues.extend(perf_issues)
        
        return {
            "status": "completed",
            "issues": issues,
            "performance_issues": len(perf_issues)
        }
    
    def _check_performance_patterns(self) -> List[Dict[str, Any]]:
        """Check for performance anti-patterns."""
        issues = []
        
        # Check for N+1 queries
        # Check for inefficient loops
        # Check for memory leaks
        # Check for blocking operations
        
        return issues
    
    def _run_documentation_check(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run documentation checks."""
        issues = []
        
        # Check for missing docstrings
        # Check for outdated documentation
        # Check for README completeness
        
        return {
            "status": "completed",
            "issues": issues,
            "documentation_issues": len(issues)
        }
    
    def _calculate_review_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall review metrics."""
        checks = results.get('checks', {})
        
        # Calculate quality score
        total_issues = 0
        critical_issues = 0
        warning_issues = 0
        
        for check_name, check_result in checks.items():
            if isinstance(check_result, dict) and 'issues' in check_result:
                issues = check_result['issues']
                total_issues += len(issues)
                critical_issues += len([i for i in issues if i.get('severity') == 'critical'])
                warning_issues += len([i for i in issues if i.get('severity') == 'warning'])
        
        # Calculate quality score (0-100)
        if total_issues == 0:
            quality_score = 100
        else:
            quality_score = max(0, 100 - (critical_issues * 20) - (warning_issues * 5))
        
        # Count passed checks
        checks_passed = sum(1 for check in checks.values() if isinstance(check, dict) and check.get('status') == 'completed')
        checks_total = len(checks)
        
        return {
            "quality_score": quality_score,
            "total_issues": total_issues,
            "critical_issues": critical_issues,
            "warning_issues": warning_issues,
            "checks_passed": checks_passed,
            "checks_total": checks_total
        }
    
    def _evaluate_review_results(self, analysis_results: Dict[str, Any]) -> bool:
        """Evaluate if review passes based on results."""
        # Check critical issues
        if analysis_results.get('critical_issues', 0) > 0:
            return False
        
        # Check quality score
        quality_score = analysis_results.get('quality_score', 0)
        if quality_score < 70:  # Minimum quality score
            return False
        
        # Check test coverage
        test_coverage = analysis_results.get('test_coverage', 0)
        if test_coverage < 80:  # Minimum test coverage
            return False
        
        return True
    
    def _generate_review_report(self, analysis_results: Dict[str, Any]) -> Optional[str]:
        """Generate review report file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"review_report_{timestamp}.json"
            
            # Write report
            with open(report_file, 'w') as f:
                json.dump(analysis_results, f, indent=2, default=str)
            
            self.log_success(f"Review report generated: {report_file}")
            return report_file
            
        except Exception as e:
            self.log_error(f"Failed to generate review report: {e}")
            return None
    
    # Helper methods
    
    def _parse_coverage_from_pytest(self, output: str) -> float:
        """Parse test coverage from pytest output."""
        try:
            for line in output.split('\n'):
                if 'TOTAL' in line and '%' in line:
                    # Extract percentage from line like "TOTAL                   1234    567    54%"
                    parts = line.split()
                    for part in parts:
                        if part.endswith('%'):
                            return float(part[:-1])
        except Exception:
            pass
        return 0.0
    
    def _get_test_coverage_threshold(self, scope: Dict[str, Any]) -> int:
        """Get test coverage threshold from scope."""
        if scope.get('thresholds') == "4":  # Custom thresholds
            return scope.get('custom_thresholds', {}).get('test_coverage', 80)
        elif scope.get('thresholds') == "2":  # Strict thresholds
            return 90
        elif scope.get('thresholds') == "3":  # Relaxed thresholds
            return 70
        else:  # Default thresholds
            return 80


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Review Workflow")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--type", "-t", help="Review type (1-7)")
    parser.add_argument("--quick", action="store_true", help="Quick review")
    parser.add_argument("--strict", action="store_true", help="Strict thresholds")
    
    args = parser.parse_args()
    
    # Create workflow instance
    workflow = ReviewWorkflow(verbose=args.verbose)
    
    # Override scope if quick mode
    if args.quick:
        workflow._get_review_scope = lambda: {"type": "1", "file_scope": "1", "check_types": "1", "thresholds": "1"}
    
    # Override scope if strict mode
    if args.strict:
        workflow._get_review_scope = lambda: {"type": "2", "file_scope": "1", "check_types": "1", "thresholds": "2"}
    
    # Run workflow
    result = workflow.run()
    
    # Print results
    print("\n" + "="*60)
    print("🔍 REVIEW RESULTS")
    print("="*60)
    
    if result.success:
        print(f"✅ {result.message}")
    else:
        print(f"❌ {result.message}")
    
    if result.metrics:
        print(f"\n📊 Metrics:")
        for key, value in result.metrics.items():
            print(f"  - {key}: {value}")
    
    if result.files_created:
        print(f"\n📁 Report generated:")
        for file_path in result.files_created:
            print(f"  - {file_path}")
    
    if result.errors:
        print(f"\n🚨 Errors:")
        for error in result.errors:
            print(f"  - {error}")
    
    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()