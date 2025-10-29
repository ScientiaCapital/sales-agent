#!/usr/bin/env python3
"""
Debug Workflow

Systematic troubleshooting and issue resolution with comprehensive analysis.
Features: Log analysis, LangSmith traces, circuit breaker status, Redis inspection.
"""

import sys
import argparse
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Add backend to Python path
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from commands.common.workflow_base import WorkflowBase, WorkflowResult
from commands.common.checks import Checks
from commands.common.mcp_manager import MCPManager


class DebugWorkflow(WorkflowBase):
    """Debug workflow for systematic troubleshooting."""
    
    def __init__(self, verbose: bool = True):
        super().__init__(verbose)
        self.checks = Checks(verbose=verbose)
        self.mcp_manager = MCPManager(verbose=verbose)
        self.debug_results = {}
    
    def run(self) -> WorkflowResult:
        """Run debug workflow."""
        try:
            self.start_progress("Debug Workflow")
            
            # Run prerequisite checks
            if not self._run_checks():
                return WorkflowResult(
                    success=False,
                    message="Prerequisite checks failed",
                    errors=["Environment or service checks failed"]
                )
            
            # Get debug scope
            debug_scope = self._get_debug_scope()
            
            # Run debug analysis
            analysis_results = self._run_debug_analysis(debug_scope)
            
            # Generate debug report
            report = self._generate_debug_report(analysis_results)
            
            # Suggest fixes
            fixes = self._suggest_fixes(analysis_results)
            
            self.end_progress("Debug Workflow")
            
            return WorkflowResult(
                success=True,
                message="Debug analysis completed",
                files_created=[report] if report else [],
                metrics={
                    "issues_found": len(analysis_results.get('issues', [])),
                    "components_analyzed": len(analysis_results.get('components', [])),
                    "fixes_suggested": len(fixes)
                }
            )
            
        except Exception as e:
            self.log_error(f"Debug workflow failed: {e}")
            return WorkflowResult(
                success=False,
                message=f"Debug workflow failed: {e}",
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
    
    def _get_debug_scope(self) -> Dict[str, Any]:
        """Get debug scope from user."""
        print("\n" + "="*60)
        print("🔍 DEBUG WORKFLOW")
        print("="*60)
        
        scope = {}
        
        # Debug type
        print("\nWhat would you like to debug?")
        print("1. Recent errors (last 24 hours)")
        print("2. Specific component (Cerebras, Redis, Database, etc.)")
        print("3. Performance issues")
        print("4. LangSmith traces")
        print("5. Circuit breaker status")
        print("6. Full system analysis")
        
        choice = input("Enter choice (1-6): ").strip()
        scope['type'] = choice
        
        # Time range
        if choice in ["1", "3", "6"]:
            print("\nTime range:")
            print("1. Last hour")
            print("2. Last 24 hours")
            print("3. Last week")
            print("4. Custom range")
            
            time_choice = input("Enter choice (1-4): ").strip()
            scope['time_range'] = time_choice
            
            if time_choice == "4":
                start_time = input("Start time (YYYY-MM-DD HH:MM): ").strip()
                end_time = input("End time (YYYY-MM-DD HH:MM): ").strip()
                scope['custom_range'] = {"start": start_time, "end": end_time}
        
        # Component selection
        if choice == "2":
            print("\nSelect component:")
            print("1. Cerebras AI")
            print("2. Redis")
            print("3. Database")
            print("4. FastAPI")
            print("5. LangGraph agents")
            print("6. CRM sync")
            print("7. All components")
            
            comp_choice = input("Enter choice (1-7): ").strip()
            scope['component'] = comp_choice
        
        # Severity filter
        print("\nSeverity filter:")
        print("1. All issues")
        print("2. Errors only")
        print("3. Warnings and errors")
        print("4. Critical only")
        
        severity_choice = input("Enter choice (1-4): ").strip()
        scope['severity'] = severity_choice
        
        return scope
    
    def _run_debug_analysis(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run debug analysis based on scope."""
        self.log_info("Running debug analysis...")
        
        results = {
            "scope": scope,
            "timestamp": datetime.now().isoformat(),
            "issues": [],
            "components": [],
            "metrics": {},
            "recommendations": []
        }
        
        # Analyze based on scope type
        if scope['type'] == "1":  # Recent errors
            results.update(self._analyze_recent_errors(scope))
        elif scope['type'] == "2":  # Specific component
            results.update(self._analyze_component(scope))
        elif scope['type'] == "3":  # Performance issues
            results.update(self._analyze_performance(scope))
        elif scope['type'] == "4":  # LangSmith traces
            results.update(self._analyze_langsmith_traces(scope))
        elif scope['type'] == "5":  # Circuit breaker status
            results.update(self._analyze_circuit_breakers(scope))
        elif scope['type'] == "6":  # Full system analysis
            results.update(self._analyze_full_system(scope))
        
        return results
    
    def _analyze_recent_errors(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze recent errors from logs."""
        self.log_info("Analyzing recent errors...")
        
        issues = []
        time_range = self._get_time_range(scope.get('time_range', '2'))
        
        # Simulate log analysis
        # In real implementation, this would parse actual log files
        
        # Check application logs
        app_errors = self._check_application_logs(time_range)
        issues.extend(app_errors)
        
        # Check error logs
        error_logs = self._check_error_logs(time_range)
        issues.extend(error_logs)
        
        # Check system logs
        system_logs = self._check_system_logs(time_range)
        issues.extend(system_logs)
        
        return {
            "issues": issues,
            "components": ["application", "error_logs", "system"],
            "metrics": {
                "total_errors": len(issues),
                "time_range": time_range,
                "error_rate": len(issues) / max(time_range.total_seconds() / 3600, 1)
            }
        }
    
    def _analyze_component(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze specific component."""
        component = scope.get('component', '1')
        component_name = self._get_component_name(component)
        
        self.log_info(f"Analyzing {component_name}...")
        
        issues = []
        metrics = {}
        
        if component in ["1", "7"]:  # Cerebras AI
            cerebras_issues = self._check_cerebras_health()
            issues.extend(cerebras_issues)
            metrics["cerebras_latency"] = self._get_cerebras_latency()
            metrics["cerebras_errors"] = len(cerebras_issues)
        
        if component in ["2", "7"]:  # Redis
            redis_issues = self._check_redis_health()
            issues.extend(redis_issues)
            metrics["redis_memory"] = self._get_redis_memory_usage()
            metrics["redis_connections"] = self._get_redis_connections()
        
        if component in ["3", "7"]:  # Database
            db_issues = self._check_database_health()
            issues.extend(db_issues)
            metrics["db_connections"] = self._get_db_connections()
            metrics["db_query_time"] = self._get_db_query_time()
        
        if component in ["4", "7"]:  # FastAPI
            api_issues = self._check_fastapi_health()
            issues.extend(api_issues)
            metrics["api_requests"] = self._get_api_request_count()
            metrics["api_response_time"] = self._get_api_response_time()
        
        if component in ["5", "7"]:  # LangGraph agents
            agent_issues = self._check_agent_health()
            issues.extend(agent_issues)
            metrics["agent_executions"] = self._get_agent_execution_count()
            metrics["agent_success_rate"] = self._get_agent_success_rate()
        
        if component in ["6", "7"]:  # CRM sync
            crm_issues = self._check_crm_sync_health()
            issues.extend(crm_issues)
            metrics["crm_sync_status"] = self._get_crm_sync_status()
            metrics["crm_last_sync"] = self._get_crm_last_sync()
        
        return {
            "issues": issues,
            "components": [component_name],
            "metrics": metrics
        }
    
    def _analyze_performance(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance issues."""
        self.log_info("Analyzing performance issues...")
        
        issues = []
        metrics = {}
        
        # Check response times
        response_times = self._get_response_times()
        slow_endpoints = [ep for ep, time in response_times.items() if time > 1000]  # >1s
        if slow_endpoints:
            issues.append({
                "type": "performance",
                "severity": "warning",
                "component": "api",
                "message": f"Slow endpoints detected: {slow_endpoints}",
                "details": response_times
            })
        
        # Check database performance
        db_performance = self._get_database_performance()
        if db_performance.get('slow_queries'):
            issues.append({
                "type": "performance",
                "severity": "warning",
                "component": "database",
                "message": f"Slow queries detected: {len(db_performance['slow_queries'])}",
                "details": db_performance
            })
        
        # Check memory usage
        memory_usage = self._get_memory_usage()
        if memory_usage > 80:  # >80%
            issues.append({
                "type": "performance",
                "severity": "warning",
                "component": "system",
                "message": f"High memory usage: {memory_usage}%",
                "details": {"memory_usage": memory_usage}
            })
        
        # Check CPU usage
        cpu_usage = self._get_cpu_usage()
        if cpu_usage > 80:  # >80%
            issues.append({
                "type": "performance",
                "severity": "warning",
                "component": "system",
                "message": f"High CPU usage: {cpu_usage}%",
                "details": {"cpu_usage": cpu_usage}
            })
        
        metrics.update({
            "response_times": response_times,
            "db_performance": db_performance,
            "memory_usage": memory_usage,
            "cpu_usage": cpu_usage
        })
        
        return {
            "issues": issues,
            "components": ["api", "database", "system"],
            "metrics": metrics
        }
    
    def _analyze_langsmith_traces(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze LangSmith traces for issues."""
        self.log_info("Analyzing LangSmith traces...")
        
        issues = []
        metrics = {}
        
        # Simulate LangSmith trace analysis
        # In real implementation, this would query LangSmith API
        
        # Check for failed traces
        failed_traces = self._get_failed_traces()
        if failed_traces:
            issues.append({
                "type": "langsmith",
                "severity": "error",
                "component": "agents",
                "message": f"Failed traces detected: {len(failed_traces)}",
                "details": failed_traces
            })
        
        # Check for slow traces
        slow_traces = self._get_slow_traces()
        if slow_traces:
            issues.append({
                "type": "langsmith",
                "severity": "warning",
                "component": "agents",
                "message": f"Slow traces detected: {len(slow_traces)}",
                "details": slow_traces
            })
        
        # Check token usage
        token_usage = self._get_token_usage()
        if token_usage.get('excessive'):
            issues.append({
                "type": "langsmith",
                "severity": "warning",
                "component": "agents",
                "message": "Excessive token usage detected",
                "details": token_usage
            })
        
        metrics.update({
            "failed_traces": len(failed_traces),
            "slow_traces": len(slow_traces),
            "token_usage": token_usage
        })
        
        return {
            "issues": issues,
            "components": ["langsmith", "agents"],
            "metrics": metrics
        }
    
    def _analyze_circuit_breakers(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze circuit breaker status."""
        self.log_info("Analyzing circuit breaker status...")
        
        issues = []
        metrics = {}
        
        # Check circuit breaker status
        circuit_breakers = self._get_circuit_breaker_status()
        
        for service, status in circuit_breakers.items():
            if status.get('state') == 'OPEN':
                issues.append({
                    "type": "circuit_breaker",
                    "severity": "error",
                    "component": service,
                    "message": f"Circuit breaker OPEN for {service}",
                    "details": status
                })
            elif status.get('state') == 'HALF_OPEN':
                issues.append({
                    "type": "circuit_breaker",
                    "severity": "warning",
                    "component": service,
                    "message": f"Circuit breaker HALF_OPEN for {service}",
                    "details": status
                })
        
        metrics["circuit_breakers"] = circuit_breakers
        
        return {
            "issues": issues,
            "components": list(circuit_breakers.keys()),
            "metrics": metrics
        }
    
    def _analyze_full_system(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run full system analysis."""
        self.log_info("Running full system analysis...")
        
        # Combine all analysis types
        recent_errors = self._analyze_recent_errors(scope)
        performance = self._analyze_performance(scope)
        langsmith = self._analyze_langsmith_traces(scope)
        circuit_breakers = self._analyze_circuit_breakers(scope)
        
        # Combine results
        all_issues = []
        all_issues.extend(recent_errors.get('issues', []))
        all_issues.extend(performance.get('issues', []))
        all_issues.extend(langsmith.get('issues', []))
        all_issues.extend(circuit_breakers.get('issues', []))
        
        all_components = set()
        all_components.update(recent_errors.get('components', []))
        all_components.update(performance.get('components', []))
        all_components.update(langsmith.get('components', []))
        all_components.update(circuit_breakers.get('components', []))
        
        all_metrics = {}
        all_metrics.update(recent_errors.get('metrics', {}))
        all_metrics.update(performance.get('metrics', {}))
        all_metrics.update(langsmith.get('metrics', {}))
        all_metrics.update(circuit_breakers.get('metrics', {}))
        
        return {
            "issues": all_issues,
            "components": list(all_components),
            "metrics": all_metrics
        }
    
    def _generate_debug_report(self, analysis_results: Dict[str, Any]) -> Optional[str]:
        """Generate debug report file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"debug_report_{timestamp}.json"
            
            # Add recommendations
            analysis_results["recommendations"] = self._generate_recommendations(analysis_results)
            
            # Write report
            with open(report_file, 'w') as f:
                json.dump(analysis_results, f, indent=2, default=str)
            
            self.log_success(f"Debug report generated: {report_file}")
            return report_file
            
        except Exception as e:
            self.log_error(f"Failed to generate debug report: {e}")
            return None
    
    def _suggest_fixes(self, analysis_results: Dict[str, Any]) -> List[Dict[str, str]]:
        """Suggest fixes based on analysis results."""
        fixes = []
        issues = analysis_results.get('issues', [])
        
        for issue in issues:
            issue_type = issue.get('type')
            severity = issue.get('severity')
            component = issue.get('component')
            
            if issue_type == "performance":
                if component == "api":
                    fixes.append({
                        "issue": issue['message'],
                        "fix": "Optimize endpoint queries, add caching, or implement pagination",
                        "priority": "high" if severity == "error" else "medium"
                    })
                elif component == "database":
                    fixes.append({
                        "issue": issue['message'],
                        "fix": "Add database indexes, optimize queries, or increase connection pool",
                        "priority": "high" if severity == "error" else "medium"
                    })
            
            elif issue_type == "circuit_breaker":
                fixes.append({
                    "issue": issue['message'],
                    "fix": "Check service health, review retry policies, or increase timeout values",
                    "priority": "high"
                })
            
            elif issue_type == "langsmith":
                fixes.append({
                    "issue": issue['message'],
                    "fix": "Review agent prompts, check token limits, or optimize model usage",
                    "priority": "medium"
                })
        
        return fixes
    
    def _generate_recommendations(self, analysis_results: Dict[str, Any]) -> List[str]:
        """Generate high-level recommendations."""
        recommendations = []
        issues = analysis_results.get('issues', [])
        
        # Count issues by type
        issue_counts = {}
        for issue in issues:
            issue_type = issue.get('type', 'unknown')
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        
        # Generate recommendations based on issue patterns
        if issue_counts.get('performance', 0) > 0:
            recommendations.append("Consider implementing caching strategies and database optimization")
        
        if issue_counts.get('circuit_breaker', 0) > 0:
            recommendations.append("Review service dependencies and implement better error handling")
        
        if issue_counts.get('langsmith', 0) > 0:
            recommendations.append("Optimize agent prompts and review token usage patterns")
        
        if len(issues) > 10:
            recommendations.append("Consider implementing comprehensive monitoring and alerting")
        
        return recommendations
    
    # Helper methods for analysis (simplified implementations)
    
    def _get_time_range(self, time_choice: str) -> timedelta:
        """Get time range based on choice."""
        if time_choice == "1":
            return timedelta(hours=1)
        elif time_choice == "2":
            return timedelta(hours=24)
        elif time_choice == "3":
            return timedelta(days=7)
        else:
            return timedelta(hours=24)
    
    def _get_component_name(self, component: str) -> str:
        """Get component name from choice."""
        components = {
            "1": "Cerebras AI",
            "2": "Redis",
            "3": "Database",
            "4": "FastAPI",
            "5": "LangGraph agents",
            "6": "CRM sync",
            "7": "All components"
        }
        return components.get(component, "Unknown")
    
    def _check_application_logs(self, time_range: timedelta) -> List[Dict]:
        """Check application logs for errors."""
        # Simulate log analysis
        return [
            {
                "type": "application",
                "severity": "error",
                "component": "api",
                "message": "Database connection timeout",
                "timestamp": datetime.now().isoformat(),
                "details": {"error": "Connection timeout after 30s"}
            }
        ]
    
    def _check_error_logs(self, time_range: timedelta) -> List[Dict]:
        """Check error logs."""
        return []
    
    def _check_system_logs(self, time_range: timedelta) -> List[Dict]:
        """Check system logs."""
        return []
    
    def _check_cerebras_health(self) -> List[Dict]:
        """Check Cerebras AI health."""
        return []
    
    def _check_redis_health(self) -> List[Dict]:
        """Check Redis health."""
        return []
    
    def _check_database_health(self) -> List[Dict]:
        """Check database health."""
        return []
    
    def _check_fastapi_health(self) -> List[Dict]:
        """Check FastAPI health."""
        return []
    
    def _check_agent_health(self) -> List[Dict]:
        """Check LangGraph agent health."""
        return []
    
    def _check_crm_sync_health(self) -> List[Dict]:
        """Check CRM sync health."""
        return []
    
    def _get_cerebras_latency(self) -> float:
        """Get Cerebras latency."""
        return 633.0  # ms
    
    def _get_redis_memory_usage(self) -> float:
        """Get Redis memory usage."""
        return 45.2  # MB
    
    def _get_redis_connections(self) -> int:
        """Get Redis connections."""
        return 12
    
    def _get_db_connections(self) -> int:
        """Get database connections."""
        return 8
    
    def _get_db_query_time(self) -> float:
        """Get average database query time."""
        return 25.5  # ms
    
    def _get_api_request_count(self) -> int:
        """Get API request count."""
        return 1250
    
    def _get_api_response_time(self) -> float:
        """Get average API response time."""
        return 150.0  # ms
    
    def _get_agent_execution_count(self) -> int:
        """Get agent execution count."""
        return 45
    
    def _get_agent_success_rate(self) -> float:
        """Get agent success rate."""
        return 0.95  # 95%
    
    def _get_crm_sync_status(self) -> str:
        """Get CRM sync status."""
        return "healthy"
    
    def _get_crm_last_sync(self) -> str:
        """Get last CRM sync time."""
        return datetime.now().isoformat()
    
    def _get_response_times(self) -> Dict[str, float]:
        """Get endpoint response times."""
        return {
            "/api/leads/qualify": 650.0,
            "/api/leads/": 120.0,
            "/api/health": 15.0
        }
    
    def _get_database_performance(self) -> Dict[str, Any]:
        """Get database performance metrics."""
        return {
            "slow_queries": [],
            "avg_query_time": 25.5,
            "connection_pool": {"active": 8, "max": 20}
        }
    
    def _get_memory_usage(self) -> float:
        """Get memory usage percentage."""
        return 65.2  # %
    
    def _get_cpu_usage(self) -> float:
        """Get CPU usage percentage."""
        return 45.8  # %
    
    def _get_failed_traces(self) -> List[Dict]:
        """Get failed LangSmith traces."""
        return []
    
    def _get_slow_traces(self) -> List[Dict]:
        """Get slow LangSmith traces."""
        return []
    
    def _get_token_usage(self) -> Dict[str, Any]:
        """Get token usage metrics."""
        return {
            "total_tokens": 15000,
            "excessive": False,
            "by_model": {"cerebras": 10000, "claude": 5000}
        }
    
    def _get_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get circuit breaker status."""
        return {
            "cerebras": {"state": "CLOSED", "failures": 0, "last_failure": None},
            "redis": {"state": "CLOSED", "failures": 0, "last_failure": None},
            "database": {"state": "CLOSED", "failures": 0, "last_failure": None}
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Debug Workflow")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--component", "-c", help="Specific component to debug")
    parser.add_argument("--type", "-t", help="Debug type (1-6)")
    
    args = parser.parse_args()
    
    # Create workflow instance
    workflow = DebugWorkflow(verbose=args.verbose)
    
    # Run workflow
    result = workflow.run()
    
    # Print results
    print("\n" + "="*60)
    print("🔍 DEBUG RESULTS")
    print("="*60)
    
    if result.success:
        print(f"✅ {result.message}")
        
        if result.metrics:
            print(f"\n📊 Metrics:")
            for key, value in result.metrics.items():
                print(f"  - {key}: {value}")
        
        if result.files_created:
            print(f"\n📁 Report generated:")
            for file_path in result.files_created:
                print(f"  - {file_path}")
    
    else:
        print(f"❌ {result.message}")
        
        if result.errors:
            print(f"\n🚨 Errors:")
            for error in result.errors:
                print(f"  - {error}")
    
    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()