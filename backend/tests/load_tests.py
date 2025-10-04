"""Load tests with Locust for 1000 concurrent leads."""

from locust import HttpUser, task, between, events
import random
import json
from datetime import datetime


class LeadQualificationUser(HttpUser):
    """Simulated user performing lead qualification operations."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    # Sample data for generating realistic leads
    companies = [
        "Acme Corp", "TechStart Inc", "Global Solutions", "DataFlow Systems",
        "CloudNine Technologies", "AI Innovations", "Quantum Computing Ltd",
        "NextGen Software", "Enterprise Solutions", "Digital Dynamics"
    ]
    
    industries = [
        "SaaS", "E-commerce", "FinTech", "HealthTech", "EdTech",
        "AI/ML", "Cybersecurity", "Cloud Computing", "IoT", "Blockchain"
    ]
    
    company_sizes = [
        "1-10", "11-50", "51-200", "201-500", "501-1000",
        "1001-5000", "5000+"
    ]
    
    titles = [
        "CEO", "CTO", "VP Engineering", "VP Sales", "Director of Marketing",
        "Head of Growth", "Product Manager", "Sales Manager"
    ]

    def on_start(self):
        """Initialize user session."""
        self.lead_count = 0
        self.errors = []

    @task(10)  # Weight: 10 (most common operation)
    def qualify_lead(self):
        """Qualify a single lead."""
        lead_data = self._generate_lead_data()
        
        with self.client.post(
            "/api/leads/qualify",
            json=lead_data,
            catch_response=True,
            name="POST /api/leads/qualify"
        ) as response:
            if response.status_code == 201:
                self.lead_count += 1
                data = response.json()
                
                # Validate response
                if "qualification_score" not in data:
                    response.failure("Missing qualification_score in response")
                elif not (0 <= data["qualification_score"] <= 100):
                    response.failure(f"Invalid score: {data['qualification_score']}")
                else:
                    response.success()
                    
                # Track latency
                if response.elapsed.total_seconds() * 1000 > 2000:
                    self.errors.append(
                        f"Slow response: {response.elapsed.total_seconds() * 1000}ms"
                    )
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(3)  # Weight: 3
    def health_check(self):
        """Check API health."""
        with self.client.get(
            "/api/health",
            catch_response=True,
            name="GET /api/health"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    response.success()
                else:
                    response.failure("API not healthy")
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(2)  # Weight: 2
    def list_leads(self):
        """List all leads."""
        with self.client.get(
            "/api/leads/",
            catch_response=True,
            name="GET /api/leads/"
        ) as response:
            if response.status_code in [200, 503]:  # 503 if DB not configured
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(1)  # Weight: 1 (least common)
    def detailed_health_check(self):
        """Get detailed health status."""
        with self.client.get(
            "/api/health/detailed",
            catch_response=True,
            name="GET /api/health/detailed"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "services" in data:
                    response.success()
                else:
                    response.failure("Missing services in response")
            else:
                response.failure(f"Got status code {response.status_code}")

    def _generate_lead_data(self):
        """Generate random but realistic lead data."""
        return {
            "company_name": random.choice(self.companies) + f" {random.randint(1, 100)}",
            "company_website": f"https://{random.choice(self.companies).lower().replace(' ', '')}.com",
            "industry": random.choice(self.industries),
            "company_size": random.choice(self.company_sizes),
            "contact_name": f"Contact {random.randint(1, 1000)}",
            "contact_title": random.choice(self.titles),
            "notes": f"Generated at {datetime.now().isoformat()}"
        }


class BurstTrafficUser(HttpUser):
    """Simulated user creating burst traffic patterns."""
    
    wait_time = between(0.1, 0.5)  # Very short wait times for burst
    
    @task
    def rapid_fire_qualifications(self):
        """Rapidly qualify multiple leads."""
        lead_data = {
            "company_name": f"BurstTest {random.randint(1, 10000)}",
            "industry": "Technology"
        }
        
        self.client.post("/api/leads/qualify", json=lead_data)


# Event listeners for custom reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    print("\n" + "="*80)
    print("LOAD TEST STARTING")
    print(f"Target: {environment.host}")
    print(f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    print("="*80 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    stats = environment.stats
    
    print("\n" + "="*80)
    print("LOAD TEST SUMMARY")
    print("="*80)
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Total failures: {stats.total.num_failures}")
    print(f"Median response time: {stats.total.median_response_time}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95)}ms")
    print(f"99th percentile: {stats.total.get_response_time_percentile(0.99)}ms")
    print(f"Requests/sec: {stats.total.total_rps:.2f}")
    print(f"Failure rate: {stats.total.fail_ratio * 100:.2f}%")
    print("="*80 + "\n")
    
    # Check SLA compliance
    p95_latency = stats.total.get_response_time_percentile(0.95)
    failure_rate = stats.total.fail_ratio
    
    print("SLA COMPLIANCE CHECK:")
    print(f"✓ P95 latency < 2000ms: {p95_latency < 2000} ({p95_latency}ms)")
    print(f"✓ Failure rate < 1%: {failure_rate < 0.01} ({failure_rate * 100:.2f}%)")
    print("="*80 + "\n")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Called for each request to track custom metrics."""
    if exception:
        # Log errors for debugging
        pass
    
    # Track extremely slow requests
    if response_time > 5000:
        print(f"⚠️  SLOW REQUEST: {name} took {response_time}ms")


# Custom task sets for different load patterns
class SpikeLoadUser(HttpUser):
    """User that creates spike load patterns."""
    
    wait_time = between(0, 0.1)
    
    @task
    def spike_request(self):
        """Send requests with minimal delay."""
        self.client.post(
            "/api/leads/qualify",
            json={"company_name": "Spike Test"}
        )


class SustainedLoadUser(HttpUser):
    """User that creates sustained load."""
    
    wait_time = between(2, 5)
    
    @task
    def sustained_request(self):
        """Send requests at steady pace."""
        self.client.post(
            "/api/leads/qualify",
            json={"company_name": "Sustained Test"}
        )


"""
USAGE INSTRUCTIONS:

1. Basic load test (100 users, 10/sec spawn rate):
   locust -f backend/tests/load_tests.py --host=http://localhost:8001 --users 100 --spawn-rate 10

2. High concurrency test (1000 users):
   locust -f backend/tests/load_tests.py --host=http://localhost:8001 --users 1000 --spawn-rate 50

3. Spike test (sudden burst):
   locust -f backend/tests/load_tests.py --host=http://localhost:8001 --users 500 --spawn-rate 100 -t 60s

4. Headless mode with CSV output:
   locust -f backend/tests/load_tests.py --host=http://localhost:8001 --users 1000 --spawn-rate 50 --run-time 5m --headless --csv=results/load_test

5. Web UI mode (default):
   locust -f backend/tests/load_tests.py --host=http://localhost:8001
   # Then open http://localhost:8089

EXPECTED PERFORMANCE:
- P95 latency: < 2000ms (target: <1000ms for Cerebras)
- P99 latency: < 5000ms
- Failure rate: < 1%
- Throughput: > 100 requests/sec
- 1000 concurrent users: System should remain stable
"""
