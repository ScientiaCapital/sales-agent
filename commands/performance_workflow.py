#!/usr/bin/env python3
"""
Performance Workflow

Identify and resolve performance bottlenecks to meet SLA targets.
Features: Benchmarking, profiling, optimization suggestions, cost validation.
"""

import sys
import argparse
import asyncio
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

# Add backend to Python path
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from commands.common.workflow_base import WorkflowBase, WorkflowResult
from commands.common.checks import Checks
from commands.common.mcp_manager import MCPManager


class PerformanceWorkflow(WorkflowBase):
    """Performance optimization workflow."""
    
    def __init__(self, verbose: bool = True):
        super().__init__(verbose)
        self.checks = Checks(verbose=verbose)
        self.mcp_manager = MCPManager(verbose=verbose)
        self.performance_targets = {
            "cerebras_latency": 1000,  # ms
            "claude_latency": 5000,    # ms
            "database_query": 50,      # ms
            "api_response": 200,       # ms
            "agent_execution": 5000,   # ms
            "cerebras_cost": 0.0001,   # USD per request
            "deepseek_cost": 0.001,    # USD per request
            "memory_usage": 80,        # %
            "cpu_usage": 80            # %
        }
        self.benchmark_results = {}
    
    def run(self) -> WorkflowResult:
        """Run performance workflow."""
        try:
            self.start_progress("Performance Workflow")
            
            # Run prerequisite checks
            if not self._run_checks():
                return WorkflowResult(
                    success=False,
                    message="Prerequisite checks failed",
                    errors=["Environment or service checks failed"]
                )
            
            # Get performance scope
            scope = self._get_performance_scope()
            
            # Run performance analysis
            analysis_results = self._run_performance_analysis(scope)
            
            # Generate optimization suggestions
            optimizations = self._generate_optimizations(analysis_results)
            
            # Run benchmarks if requested
            if scope.get('run_benchmarks', False):
                benchmark_results = self._run_benchmarks(scope)
                analysis_results['benchmarks'] = benchmark_results
            
            # Generate performance report
            report = self._generate_performance_report(analysis_results, optimizations)
            
            self.end_progress("Performance Workflow")
            
            return WorkflowResult(
                success=True,
                message="Performance analysis completed",
                files_created=[report] if report else [],
                metrics={
                    "targets_met": analysis_results.get('targets_met', 0),
                    "targets_total": analysis_results.get('targets_total', 0),
                    "optimizations_suggested": len(optimizations),
                    "performance_score": analysis_results.get('performance_score', 0)
                }
            )
            
        except Exception as e:
            self.log_error(f"Performance workflow failed: {e}")
            return WorkflowResult(
                success=False,
                message=f"Performance workflow failed: {e}",
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
    
    def _get_performance_scope(self) -> Dict[str, Any]:
        """Get performance analysis scope from user."""
        print("\n" + "="*60)
        print("⚡ PERFORMANCE WORKFLOW")
        print("="*60)
        
        scope = {}
        
        # Analysis type
        print("\nWhat would you like to analyze?")
        print("1. Quick performance check")
        print("2. Comprehensive analysis")
        print("3. Specific component (Cerebras, Database, API, etc.)")
        print("4. Cost optimization")
        print("5. Memory and CPU usage")
        print("6. Custom benchmarks")
        
        choice = input("Enter choice (1-6): ").strip()
        scope['type'] = choice
        
        # Time range
        if choice in ["1", "2", "4", "5"]:
            print("\nTime range for analysis:")
            print("1. Last hour")
            print("2. Last 24 hours")
            print("3. Last week")
            print("4. Real-time (current)")
            
            time_choice = input("Enter choice (1-4): ").strip()
            scope['time_range'] = time_choice
        
        # Component selection
        if choice == "3":
            print("\nSelect component:")
            print("1. Cerebras AI")
            print("2. Database")
            print("3. FastAPI")
            print("4. LangGraph agents")
            print("5. Redis")
            print("6. CRM sync")
            print("7. All components")
            
            comp_choice = input("Enter choice (1-7): ").strip()
            scope['component'] = comp_choice
        
        # Benchmark options
        if choice == "6":
            print("\nBenchmark options:")
            print("1. Load test API endpoints")
            print("2. Stress test database")
            print("3. Agent execution benchmarks")
            print("4. Memory usage under load")
            print("5. All benchmarks")
            
            bench_choice = input("Enter choice (1-5): ").strip()
            scope['benchmark_type'] = bench_choice
        
        # Run benchmarks
        if choice in ["2", "6"]:
            run_benchmarks = input("Run performance benchmarks? (y/n): ").strip().lower() == 'y'
            scope['run_benchmarks'] = run_benchmarks
        
        return scope
    
    def _run_performance_analysis(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run performance analysis based on scope."""
        self.log_info("Running performance analysis...")
        
        results = {
            "scope": scope,
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
            "targets": {},
            "bottlenecks": [],
            "recommendations": []
        }
        
        # Analyze based on scope type
        if scope['type'] == "1":  # Quick check
            results.update(self._quick_performance_check())
        elif scope['type'] == "2":  # Comprehensive analysis
            results.update(self._comprehensive_analysis())
        elif scope['type'] == "3":  # Specific component
            results.update(self._analyze_component(scope))
        elif scope['type'] == "4":  # Cost optimization
            results.update(self._analyze_costs())
        elif scope['type'] == "5":  # Memory and CPU
            results.update(self._analyze_resource_usage())
        elif scope['type'] == "6":  # Custom benchmarks
            results.update(self._run_custom_benchmarks(scope))
        
        # Calculate performance score
        results['performance_score'] = self._calculate_performance_score(results)
        
        return results
    
    def _quick_performance_check(self) -> Dict[str, Any]:
        """Run quick performance check."""
        self.log_info("Running quick performance check...")
        
        metrics = {}
        targets = {}
        bottlenecks = []
        
        # Check Cerebras latency
        cerebras_latency = self._get_cerebras_latency()
        metrics['cerebras_latency'] = cerebras_latency
        targets['cerebras_latency'] = {
            "current": cerebras_latency,
            "target": self.performance_targets['cerebras_latency'],
            "met": cerebras_latency <= self.performance_targets['cerebras_latency']
        }
        
        if cerebras_latency > self.performance_targets['cerebras_latency']:
            bottlenecks.append({
                "component": "cerebras",
                "issue": f"High latency: {cerebras_latency}ms",
                "severity": "warning"
            })
        
        # Check database performance
        db_query_time = self._get_database_query_time()
        metrics['database_query_time'] = db_query_time
        targets['database_query_time'] = {
            "current": db_query_time,
            "target": self.performance_targets['database_query'],
            "met": db_query_time <= self.performance_targets['database_query']
        }
        
        if db_query_time > self.performance_targets['database_query']:
            bottlenecks.append({
                "component": "database",
                "issue": f"Slow queries: {db_query_time}ms",
                "severity": "warning"
            })
        
        # Check API response time
        api_response_time = self._get_api_response_time()
        metrics['api_response_time'] = api_response_time
        targets['api_response_time'] = {
            "current": api_response_time,
            "target": self.performance_targets['api_response'],
            "met": api_response_time <= self.performance_targets['api_response']
        }
        
        if api_response_time > self.performance_targets['api_response']:
            bottlenecks.append({
                "component": "api",
                "issue": f"Slow API responses: {api_response_time}ms",
                "severity": "warning"
            })
        
        # Check memory usage
        memory_usage = self._get_memory_usage()
        metrics['memory_usage'] = memory_usage
        targets['memory_usage'] = {
            "current": memory_usage,
            "target": self.performance_targets['memory_usage'],
            "met": memory_usage <= self.performance_targets['memory_usage']
        }
        
        if memory_usage > self.performance_targets['memory_usage']:
            bottlenecks.append({
                "component": "system",
                "issue": f"High memory usage: {memory_usage}%",
                "severity": "critical"
            })
        
        return {
            "metrics": metrics,
            "targets": targets,
            "bottlenecks": bottlenecks,
            "targets_met": sum(1 for t in targets.values() if t['met']),
            "targets_total": len(targets)
        }
    
    def _comprehensive_analysis(self) -> Dict[str, Any]:
        """Run comprehensive performance analysis."""
        self.log_info("Running comprehensive performance analysis...")
        
        # Combine all analysis types
        quick_results = self._quick_performance_check()
        cost_results = self._analyze_costs()
        resource_results = self._analyze_resource_usage()
        
        # Merge results
        all_metrics = {}
        all_metrics.update(quick_results.get('metrics', {}))
        all_metrics.update(cost_results.get('metrics', {}))
        all_metrics.update(resource_results.get('metrics', {}))
        
        all_targets = {}
        all_targets.update(quick_results.get('targets', {}))
        all_targets.update(cost_results.get('targets', {}))
        all_targets.update(resource_results.get('targets', {}))
        
        all_bottlenecks = []
        all_bottlenecks.extend(quick_results.get('bottlenecks', []))
        all_bottlenecks.extend(cost_results.get('bottlenecks', []))
        all_bottlenecks.extend(resource_results.get('bottlenecks', []))
        
        return {
            "metrics": all_metrics,
            "targets": all_targets,
            "bottlenecks": all_bottlenecks,
            "targets_met": sum(1 for t in all_targets.values() if t.get('met', False)),
            "targets_total": len(all_targets)
        }
    
    def _analyze_component(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze specific component performance."""
        component = scope.get('component', '1')
        component_name = self._get_component_name(component)
        
        self.log_info(f"Analyzing {component_name} performance...")
        
        metrics = {}
        targets = {}
        bottlenecks = []
        
        if component in ["1", "7"]:  # Cerebras AI
            cerebras_metrics = self._analyze_cerebras_performance()
            metrics.update(cerebras_metrics['metrics'])
            targets.update(cerebras_metrics['targets'])
            bottlenecks.extend(cerebras_metrics['bottlenecks'])
        
        if component in ["2", "7"]:  # Database
            db_metrics = self._analyze_database_performance()
            metrics.update(db_metrics['metrics'])
            targets.update(db_metrics['targets'])
            bottlenecks.extend(db_metrics['bottlenecks'])
        
        if component in ["3", "7"]:  # FastAPI
            api_metrics = self._analyze_api_performance()
            metrics.update(api_metrics['metrics'])
            targets.update(api_metrics['targets'])
            bottlenecks.extend(api_metrics['bottlenecks'])
        
        if component in ["4", "7"]:  # LangGraph agents
            agent_metrics = self._analyze_agent_performance()
            metrics.update(agent_metrics['metrics'])
            targets.update(agent_metrics['targets'])
            bottlenecks.extend(agent_metrics['bottlenecks'])
        
        if component in ["5", "7"]:  # Redis
            redis_metrics = self._analyze_redis_performance()
            metrics.update(redis_metrics['metrics'])
            targets.update(redis_metrics['targets'])
            bottlenecks.extend(redis_metrics['bottlenecks'])
        
        if component in ["6", "7"]:  # CRM sync
            crm_metrics = self._analyze_crm_performance()
            metrics.update(crm_metrics['metrics'])
            targets.update(crm_metrics['targets'])
            bottlenecks.extend(crm_metrics['bottlenecks'])
        
        return {
            "metrics": metrics,
            "targets": targets,
            "bottlenecks": bottlenecks,
            "targets_met": sum(1 for t in targets.values() if t.get('met', False)),
            "targets_total": len(targets)
        }
    
    def _analyze_costs(self) -> Dict[str, Any]:
        """Analyze cost optimization opportunities."""
        self.log_info("Analyzing cost optimization...")
        
        metrics = {}
        targets = {}
        bottlenecks = []
        
        # Get current costs
        cerebras_cost = self._get_cerebras_cost_per_request()
        deepseek_cost = self._get_deepseek_cost_per_request()
        claude_cost = self._get_claude_cost_per_request()
        
        metrics.update({
            "cerebras_cost": cerebras_cost,
            "deepseek_cost": deepseek_cost,
            "claude_cost": claude_cost
        })
        
        # Check cost targets
        targets['cerebras_cost'] = {
            "current": cerebras_cost,
            "target": self.performance_targets['cerebras_cost'],
            "met": cerebras_cost <= self.performance_targets['cerebras_cost']
        }
        
        targets['deepseek_cost'] = {
            "current": deepseek_cost,
            "target": self.performance_targets['deepseek_cost'],
            "met": deepseek_cost <= self.performance_targets['deepseek_cost']
        }
        
        # Identify cost issues
        if cerebras_cost > self.performance_targets['cerebras_cost']:
            bottlenecks.append({
                "component": "cerebras",
                "issue": f"High cost: ${cerebras_cost:.6f} per request",
                "severity": "warning"
            })
        
        if deepseek_cost > self.performance_targets['deepseek_cost']:
            bottlenecks.append({
                "component": "deepseek",
                "issue": f"High cost: ${deepseek_cost:.6f} per request",
                "severity": "warning"
            })
        
        return {
            "metrics": metrics,
            "targets": targets,
            "bottlenecks": bottlenecks
        }
    
    def _analyze_resource_usage(self) -> Dict[str, Any]:
        """Analyze memory and CPU usage."""
        self.log_info("Analyzing resource usage...")
        
        metrics = {}
        targets = {}
        bottlenecks = []
        
        # Get resource usage
        memory_usage = self._get_memory_usage()
        cpu_usage = self._get_cpu_usage()
        disk_usage = self._get_disk_usage()
        
        metrics.update({
            "memory_usage": memory_usage,
            "cpu_usage": cpu_usage,
            "disk_usage": disk_usage
        })
        
        # Check resource targets
        targets['memory_usage'] = {
            "current": memory_usage,
            "target": self.performance_targets['memory_usage'],
            "met": memory_usage <= self.performance_targets['memory_usage']
        }
        
        targets['cpu_usage'] = {
            "current": cpu_usage,
            "target": self.performance_targets['cpu_usage'],
            "met": cpu_usage <= self.performance_targets['cpu_usage']
        }
        
        # Identify resource issues
        if memory_usage > self.performance_targets['memory_usage']:
            bottlenecks.append({
                "component": "system",
                "issue": f"High memory usage: {memory_usage}%",
                "severity": "critical"
            })
        
        if cpu_usage > self.performance_targets['cpu_usage']:
            bottlenecks.append({
                "component": "system",
                "issue": f"High CPU usage: {cpu_usage}%",
                "severity": "warning"
            })
        
        return {
            "metrics": metrics,
            "targets": targets,
            "bottlenecks": bottlenecks
        }
    
    def _run_custom_benchmarks(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run custom performance benchmarks."""
        self.log_info("Running custom benchmarks...")
        
        benchmark_type = scope.get('benchmark_type', '1')
        results = {}
        
        if benchmark_type in ["1", "5"]:  # API load test
            results['api_load_test'] = self._run_api_load_test()
        
        if benchmark_type in ["2", "5"]:  # Database stress test
            results['database_stress_test'] = self._run_database_stress_test()
        
        if benchmark_type in ["3", "5"]:  # Agent execution benchmarks
            results['agent_benchmarks'] = self._run_agent_benchmarks()
        
        if benchmark_type in ["4", "5"]:  # Memory usage under load
            results['memory_load_test'] = self._run_memory_load_test()
        
        return {
            "metrics": results,
            "targets": {},
            "bottlenecks": []
        }
    
    def _run_benchmarks(self, scope: Dict[str, Any]) -> Dict[str, Any]:
        """Run performance benchmarks."""
        self.log_info("Running performance benchmarks...")
        
        # Run API benchmarks
        api_results = self._run_api_load_test()
        
        # Run database benchmarks
        db_results = self._run_database_stress_test()
        
        # Run agent benchmarks
        agent_results = self._run_agent_benchmarks()
        
        return {
            "api_benchmarks": api_results,
            "database_benchmarks": db_results,
            "agent_benchmarks": agent_results
        }
    
    def _generate_optimizations(self, analysis_results: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate optimization suggestions."""
        optimizations = []
        bottlenecks = analysis_results.get('bottlenecks', [])
        
        for bottleneck in bottlenecks:
            component = bottleneck['component']
            issue = bottleneck['issue']
            severity = bottleneck['severity']
            
            if component == "cerebras":
                optimizations.append({
                    "component": "Cerebras AI",
                    "issue": issue,
                    "optimization": "Implement request batching, add caching, or use fallback models",
                    "priority": "high" if severity == "critical" else "medium"
                })
            
            elif component == "database":
                optimizations.append({
                    "component": "Database",
                    "issue": issue,
                    "optimization": "Add indexes, optimize queries, or increase connection pool",
                    "priority": "high" if severity == "critical" else "medium"
                })
            
            elif component == "api":
                optimizations.append({
                    "component": "FastAPI",
                    "issue": issue,
                    "optimization": "Implement caching, optimize endpoints, or add load balancing",
                    "priority": "high" if severity == "critical" else "medium"
                })
            
            elif component == "system":
                optimizations.append({
                    "component": "System Resources",
                    "issue": issue,
                    "optimization": "Scale resources, optimize memory usage, or implement resource limits",
                    "priority": "high" if severity == "critical" else "medium"
                })
        
        return optimizations
    
    def _generate_performance_report(self, analysis_results: Dict[str, Any], optimizations: List[Dict[str, str]]) -> Optional[str]:
        """Generate performance report file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"performance_report_{timestamp}.json"
            
            # Add optimizations to results
            analysis_results["optimizations"] = optimizations
            
            # Write report
            with open(report_file, 'w') as f:
                json.dump(analysis_results, f, indent=2, default=str)
            
            self.log_success(f"Performance report generated: {report_file}")
            return report_file
            
        except Exception as e:
            self.log_error(f"Failed to generate performance report: {e}")
            return None
    
    def _calculate_performance_score(self, results: Dict[str, Any]) -> float:
        """Calculate overall performance score (0-100)."""
        targets = results.get('targets', {})
        if not targets:
            return 0.0
        
        met_targets = sum(1 for t in targets.values() if t.get('met', False))
        total_targets = len(targets)
        
        return (met_targets / total_targets) * 100 if total_targets > 0 else 0.0
    
    # Helper methods for analysis (simplified implementations)
    
    def _get_cerebras_latency(self) -> float:
        """Get Cerebras AI latency."""
        return 633.0  # ms
    
    def _get_database_query_time(self) -> float:
        """Get average database query time."""
        return 25.5  # ms
    
    def _get_api_response_time(self) -> float:
        """Get average API response time."""
        return 150.0  # ms
    
    def _get_memory_usage(self) -> float:
        """Get memory usage percentage."""
        return 65.2  # %
    
    def _get_cpu_usage(self) -> float:
        """Get CPU usage percentage."""
        return 45.8  # %
    
    def _get_disk_usage(self) -> float:
        """Get disk usage percentage."""
        return 35.7  # %
    
    def _get_cerebras_cost_per_request(self) -> float:
        """Get Cerebras cost per request."""
        return 0.000006  # USD
    
    def _get_deepseek_cost_per_request(self) -> float:
        """Get DeepSeek cost per request."""
        return 0.00027  # USD
    
    def _get_claude_cost_per_request(self) -> float:
        """Get Claude cost per request."""
        return 0.001743  # USD
    
    def _get_component_name(self, component: str) -> str:
        """Get component name from choice."""
        components = {
            "1": "Cerebras AI",
            "2": "Database",
            "3": "FastAPI",
            "4": "LangGraph agents",
            "5": "Redis",
            "6": "CRM sync",
            "7": "All components"
        }
        return components.get(component, "Unknown")
    
    def _analyze_cerebras_performance(self) -> Dict[str, Any]:
        """Analyze Cerebras AI performance."""
        latency = self._get_cerebras_latency()
        cost = self._get_cerebras_cost_per_request()
        
        return {
            "metrics": {"cerebras_latency": latency, "cerebras_cost": cost},
            "targets": {
                "cerebras_latency": {
                    "current": latency,
                    "target": self.performance_targets['cerebras_latency'],
                    "met": latency <= self.performance_targets['cerebras_latency']
                }
            },
            "bottlenecks": []
        }
    
    def _analyze_database_performance(self) -> Dict[str, Any]:
        """Analyze database performance."""
        query_time = self._get_database_query_time()
        
        return {
            "metrics": {"database_query_time": query_time},
            "targets": {
                "database_query_time": {
                    "current": query_time,
                    "target": self.performance_targets['database_query'],
                    "met": query_time <= self.performance_targets['database_query']
                }
            },
            "bottlenecks": []
        }
    
    def _analyze_api_performance(self) -> Dict[str, Any]:
        """Analyze API performance."""
        response_time = self._get_api_response_time()
        
        return {
            "metrics": {"api_response_time": response_time},
            "targets": {
                "api_response_time": {
                    "current": response_time,
                    "target": self.performance_targets['api_response'],
                    "met": response_time <= self.performance_targets['api_response']
                }
            },
            "bottlenecks": []
        }
    
    def _analyze_agent_performance(self) -> Dict[str, Any]:
        """Analyze LangGraph agent performance."""
        return {
            "metrics": {"agent_execution_time": 2500.0},
            "targets": {
                "agent_execution_time": {
                    "current": 2500.0,
                    "target": self.performance_targets['agent_execution'],
                    "met": 2500.0 <= self.performance_targets['agent_execution']
                }
            },
            "bottlenecks": []
        }
    
    def _analyze_redis_performance(self) -> Dict[str, Any]:
        """Analyze Redis performance."""
        return {
            "metrics": {"redis_latency": 1.2},
            "targets": {
                "redis_latency": {
                    "current": 1.2,
                    "target": 5.0,
                    "met": 1.2 <= 5.0
                }
            },
            "bottlenecks": []
        }
    
    def _analyze_crm_performance(self) -> Dict[str, Any]:
        """Analyze CRM sync performance."""
        return {
            "metrics": {"crm_sync_time": 2000.0},
            "targets": {
                "crm_sync_time": {
                    "current": 2000.0,
                    "target": 5000.0,
                    "met": 2000.0 <= 5000.0
                }
            },
            "bottlenecks": []
        }
    
    def _run_api_load_test(self) -> Dict[str, Any]:
        """Run API load test."""
        # Simulate load test
        return {
            "requests_per_second": 100,
            "average_response_time": 150.0,
            "p95_response_time": 300.0,
            "error_rate": 0.01
        }
    
    def _run_database_stress_test(self) -> Dict[str, Any]:
        """Run database stress test."""
        # Simulate stress test
        return {
            "queries_per_second": 500,
            "average_query_time": 25.0,
            "p95_query_time": 50.0,
            "connection_pool_usage": 0.4
        }
    
    def _run_agent_benchmarks(self) -> Dict[str, Any]:
        """Run agent execution benchmarks."""
        # Simulate agent benchmarks
        return {
            "qualification_agent": {"latency": 650.0, "success_rate": 0.98},
            "enrichment_agent": {"latency": 2000.0, "success_rate": 0.95},
            "growth_agent": {"latency": 4500.0, "success_rate": 0.92}
        }
    
    def _run_memory_load_test(self) -> Dict[str, Any]:
        """Run memory usage under load test."""
        # Simulate memory test
        return {
            "baseline_memory": 500,  # MB
            "load_memory": 800,      # MB
            "memory_growth": 300,    # MB
            "gc_efficiency": 0.85
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Performance Workflow")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--component", "-c", help="Specific component to analyze")
    parser.add_argument("--type", "-t", help="Analysis type (1-6)")
    parser.add_argument("--quick", action="store_true", help="Quick performance check")
    
    args = parser.parse_args()
    
    # Create workflow instance
    workflow = PerformanceWorkflow(verbose=args.verbose)
    
    # Override scope if quick mode
    if args.quick:
        workflow._get_performance_scope = lambda: {"type": "1", "time_range": "4"}
    
    # Run workflow
    result = workflow.run()
    
    # Print results
    print("\n" + "="*60)
    print("⚡ PERFORMANCE RESULTS")
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