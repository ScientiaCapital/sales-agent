"""Test suite for Context7 MCP Load Balancer.

Run tests:
    python test_mcp_server.py
    python test_mcp_server.py -v  (verbose output)
"""

import sys
import time
import requests
from typing import Optional

# Configuration
BASE_URL = "http://localhost:8002"
TIMEOUT = 30  # seconds


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_pass(self, test_name: str):
        self.passed += 1
        print(f"✅ PASS: {test_name}")
    
    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"❌ FAIL: {test_name}")
        print(f"   Error: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print("\n" + "="*60)
        print(f"Test Results: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"\nFailed Tests:")
            for test_name, error in self.errors:
                print(f"  - {test_name}: {error}")
        print("="*60)
        return self.failed == 0


def test_server_running(results: TestResults) -> bool:
    """Test if server is accessible."""
    test_name = "Server Running"
    try:
        response = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
        if response.status_code == 200:
            results.add_pass(test_name)
            return True
        else:
            results.add_fail(test_name, f"Expected 200, got {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        results.add_fail(test_name, "Cannot connect to server. Is it running?")
        return False
    except Exception as e:
        results.add_fail(test_name, str(e))
        return False


def test_health_check(results: TestResults):
    """Test /ping health check endpoint."""
    test_name = "Health Check (/ping)"
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}/ping", timeout=TIMEOUT)
        latency_ms = int((time.time() - start) * 1000)
        
        if response.status_code != 200:
            results.add_fail(test_name, f"Expected 200, got {response.status_code}")
            return
        
        data = response.json()
        
        # Verify required fields
        required_fields = ["status", "service", "timestamp", "vllm_configured"]
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            results.add_fail(test_name, f"Missing fields: {missing_fields}")
            return
        
        # Verify status is healthy
        if data["status"] != "healthy":
            results.add_fail(test_name, f"Expected status='healthy', got '{data['status']}'")
            return
        
        # Verify service name
        if data["service"] != "context7-mcp":
            results.add_fail(test_name, f"Expected service='context7-mcp', got '{data['service']}'")
            return
        
        print(f"   Latency: {latency_ms}ms")
        print(f"   vLLM Configured: {data['vllm_configured']}")
        results.add_pass(test_name)
        
    except Exception as e:
        results.add_fail(test_name, str(e))


def test_health_check_performance(results: TestResults):
    """Test health check response time."""
    test_name = "Health Check Performance (<100ms)"
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}/ping", timeout=TIMEOUT)
        latency_ms = int((time.time() - start) * 1000)
        
        if response.status_code == 200 and latency_ms < 100:
            print(f"   Latency: {latency_ms}ms")
            results.add_pass(test_name)
        else:
            results.add_fail(test_name, f"Latency {latency_ms}ms exceeds 100ms threshold")
            
    except Exception as e:
        results.add_fail(test_name, str(e))


def test_research_endpoint_validation(results: TestResults):
    """Test research endpoint input validation."""
    test_name = "Research Endpoint Validation"
    try:
        # Test with empty query (should fail)
        response = requests.post(
            f"{BASE_URL}/v1/research",
            json={},
            timeout=TIMEOUT
        )
        
        if response.status_code == 422:  # Validation error expected
            results.add_pass(test_name)
        else:
            results.add_fail(test_name, f"Expected 422 validation error, got {response.status_code}")
            
    except Exception as e:
        results.add_fail(test_name, str(e))


def test_research_endpoint_success(results: TestResults, skip_if_unconfigured: bool = True):
    """Test research endpoint with valid query.
    
    Args:
        skip_if_unconfigured: Skip test if vLLM backend is not configured
    """
    test_name = "Research Endpoint Success"
    
    try:
        # First check if vLLM is configured
        health_response = requests.get(f"{BASE_URL}/ping", timeout=TIMEOUT)
        vllm_configured = health_response.json().get("vllm_configured", False)
        
        if not vllm_configured and skip_if_unconfigured:
            print(f"⚠️  SKIP: {test_name} (vLLM backend not configured)")
            return
        
        # Test research query
        start = time.time()
        response = requests.post(
            f"{BASE_URL}/v1/research",
            json={
                "query": "What is FastAPI?",
                "max_tokens": 100,
                "temperature": 0.7
            },
            timeout=TIMEOUT
        )
        latency_ms = int((time.time() - start) * 1000)
        
        if not vllm_configured:
            # Should return 500 if not configured
            if response.status_code == 500:
                results.add_pass(f"{test_name} (Expected Error)")
                return
            else:
                results.add_fail(test_name, f"Expected 500 when unconfigured, got {response.status_code}")
                return
        
        # If configured, should succeed
        if response.status_code != 200:
            results.add_fail(test_name, f"Expected 200, got {response.status_code}: {response.text}")
            return
        
        data = response.json()
        
        # Verify required fields
        required_fields = ["result", "model", "latency_ms", "timestamp"]
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            results.add_fail(test_name, f"Missing fields: {missing_fields}")
            return
        
        # Verify result is not empty
        if not data["result"] or len(data["result"]) < 10:
            results.add_fail(test_name, "Result is empty or too short")
            return
        
        print(f"   Latency: {latency_ms}ms")
        print(f"   Model: {data['model']}")
        print(f"   Tokens Used: {data.get('tokens_used', 'N/A')}")
        print(f"   Result Length: {len(data['result'])} chars")
        results.add_pass(test_name)
        
    except requests.exceptions.Timeout:
        results.add_fail(test_name, "Request timeout (>30s)")
    except Exception as e:
        results.add_fail(test_name, str(e))


def test_root_endpoint(results: TestResults):
    """Test root endpoint."""
    test_name = "Root Endpoint (/)"
    try:
        response = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
        
        if response.status_code != 200:
            results.add_fail(test_name, f"Expected 200, got {response.status_code}")
            return
        
        data = response.json()
        
        # Verify service info
        if data.get("service") != "Context7 MCP Load Balancer":
            results.add_fail(test_name, "Invalid service name")
            return
        
        # Verify endpoints info exists
        if "endpoints" not in data:
            results.add_fail(test_name, "Missing endpoints info")
            return
        
        results.add_pass(test_name)
        
    except Exception as e:
        results.add_fail(test_name, str(e))


def main():
    """Run all tests."""
    print("="*60)
    print("Context7 MCP Load Balancer - Test Suite")
    print("="*60)
    print(f"Testing server at: {BASE_URL}\n")
    
    results = TestResults()
    
    # Test server is running
    if not test_server_running(results):
        print("\n❌ Server is not running. Start with: python context7_load_balancer.py")
        return 1
    
    print()  # Blank line
    
    # Run tests
    test_root_endpoint(results)
    test_health_check(results)
    test_health_check_performance(results)
    test_research_endpoint_validation(results)
    test_research_endpoint_success(results, skip_if_unconfigured=True)
    
    # Print summary
    success = results.summary()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
