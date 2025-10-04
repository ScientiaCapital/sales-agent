#!/usr/bin/env python3
"""
Test script for the Sales Agent API
"""
import requests
import json
import time

API_BASE = "http://localhost:8001"


def test_health():
    """Test health endpoint"""
    print("\n=== Testing Health Endpoint ===")
    response = requests.get(f"{API_BASE}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_qualify_lead():
    """Test lead qualification with Cerebras"""
    print("\n=== Testing Lead Qualification ===")

    lead_data = {
        "company_name": "TechCorp Inc",
        "company_website": "https://techcorp.example.com",
        "company_size": "50-200",
        "industry": "SaaS",
        "contact_name": "John Smith",
        "contact_email": "john.smith@techcorp.example.com",
        "contact_title": "VP of Sales",
        "notes": "Expressed interest in automation tools"
    }

    print(f"Qualifying lead: {lead_data['company_name']}")
    start = time.time()

    try:
        response = requests.post(
            f"{API_BASE}/api/leads/qualify",
            json=lead_data,
            timeout=30
        )
        end = time.time()
        total_time = int((end - start) * 1000)

        print(f"\nStatus: {response.status_code}")
        print(f"Total API call time: {total_time}ms")

        if response.status_code == 201:
            result = response.json()
            print(f"\n✓ Lead qualified successfully!")
            print(f"  Lead ID: {result['id']}")
            print(f"  Company: {result['company_name']}")
            print(f"  Score: {result['qualification_score']}/100")
            print(f"  Cerebras latency: {result['qualification_latency_ms']}ms")
            print(f"  Reasoning: {result['qualification_reasoning']}")
            return True
        else:
            print(f"Error: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return False


def test_list_leads():
    """Test listing leads"""
    print("\n=== Testing List Leads ===")
    response = requests.get(f"{API_BASE}/api/leads/")
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        leads = response.json()
        print(f"Found {len(leads)} leads")
        for lead in leads:
            print(f"  - {lead['company_name']}: {lead.get('qualification_score', 'N/A')}/100")
        return True
    else:
        print(f"Error: {response.text}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Sales Agent API Test Suite")
    print("=" * 60)

    # Wait for server to be ready
    print("\nWaiting for API server to be ready...")
    for i in range(10):
        try:
            requests.get(f"{API_BASE}/api/health", timeout=1)
            print("✓ API server is ready!")
            break
        except:
            time.sleep(1)
            print(f"  Attempt {i+1}/10...")
    else:
        print("✗ API server not ready after 10 seconds")
        exit(1)

    # Run tests
    results = []
    results.append(("Health Check", test_health()))
    results.append(("Lead Qualification", test_qualify_lead()))
    results.append(("List Leads", test_list_leads()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name}: {status}")

    all_passed = all(result[1] for result in results)
    print("\n" + ("✓ All tests passed!" if all_passed else "✗ Some tests failed"))
    exit(0 if all_passed else 1)
