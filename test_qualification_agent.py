#!/usr/bin/env python3
"""Test QualificationAgent with a real example."""

import requests
import json
import time

API_BASE = "http://localhost:8001/api/v1"

# Test data
test_lead = {
    "agent_type": "qualification",
    "input": {
        "company_name": "Tesla Inc",
        "industry": "Automotive & Clean Energy",
        "company_size": "100000+",
        "website": "https://tesla.com",
        "description": "Electric vehicles and clean energy solutions"
    }
}

print("🧪 Testing QualificationAgent (Cerebras-powered, target: <1000ms)")
print("=" * 60)
print(f"\n📊 Test Lead: {test_lead['input']['company_name']}")
print(f"   Industry: {test_lead['input']['industry']}")
print(f"   Size: {test_lead['input']['company_size']}")

print("\n⏱️  Invoking agent...")
start_time = time.time()

try:
    response = requests.post(
        f"{API_BASE}/langgraph/invoke",
        json=test_lead,
        timeout=30
    )

    elapsed_ms = (time.time() - start_time) * 1000

    if response.status_code == 200:
        result = response.json()
        output = result.get("output", {})

        print(f"\n✅ SUCCESS! Response time: {elapsed_ms:.0f}ms")
        print("=" * 60)
        print(f"\n📈 Qualification Results:")
        print(f"   Score: {output.get('score', 'N/A')}/100")
        print(f"   Tier: {output.get('tier', 'N/A').upper()}")
        print(f"\n💡 Reasoning:")
        print(f"   {output.get('reasoning', 'N/A')}")

        if 'recommendations' in output:
            print(f"\n🎯 Recommendations:")
            for rec in output['recommendations']:
                print(f"   • {rec}")

        # Performance check
        target_ms = 1000
        if elapsed_ms < target_ms:
            print(f"\n🚀 PERFORMANCE: {elapsed_ms:.0f}ms < {target_ms}ms target ✅")
            perc_faster = ((target_ms - elapsed_ms) / target_ms) * 100
            print(f"   {perc_faster:.0f}% faster than target!")
        else:
            print(f"\n⚠️  PERFORMANCE: {elapsed_ms:.0f}ms > {target_ms}ms target")

    else:
        print(f"\n❌ FAILED: HTTP {response.status_code}")
        print(f"Response: {response.text}")

except requests.exceptions.Timeout:
    print(f"\n❌ TIMEOUT after 30 seconds")
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")

print("\n" + "=" * 60)
