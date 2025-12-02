#!/usr/bin/env python3
"""
Create RunPod Serverless Endpoint via GraphQL API
Two-step process: Create Template → Create Endpoint
"""
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

RUNPOD_API_KEY = os.getenv('RUNPOD_API_KEY')
RUNPOD_API_URL = "https://api.runpod.io/graphql"

if not RUNPOD_API_KEY:
    raise ValueError("RUNPOD_API_KEY not found in environment variables")

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {RUNPOD_API_KEY}"
}

print("=" * 60)
print("RunPod Serverless Endpoint Creation")
print("=" * 60)

# Step 1: Create Serverless Template
print("\n📦 Step 1: Creating Serverless Template...")

create_template_mutation = f"""
mutation {{
    saveTemplate(input: {{
        containerDiskInGb: 10
        dockerArgs: ""
        env: [
            {{ key: "SUPABASE_DATABASE_URL", value: "{os.getenv('SUPABASE_DATABASE_URL')}" }}
            {{ key: "CLOSE_API_KEY", value: "{os.getenv('CLOSE_API_KEY')}" }}
            {{ key: "ANTHROPIC_API_KEY", value: "{os.getenv('ANTHROPIC_API_KEY')}" }}
            {{ key: "DEEPSEEK_API_KEY", value: "{os.getenv('DEEPSEEK_API_KEY')}" }}
        ]
        imageName: "ghcr.io/tmkipper/sales-agent-social-intelligence:latest"
        isServerless: true
        name: "Social Intelligence Template"
        readme: "# Social Intelligence System\\\\n\\\\nAutomated LinkedIn + Twitter monitoring with AI-powered email drafts in Close CRM."
        volumeInGb: 0
    }}) {{
        id
        name
        imageName
        isServerless
        containerDiskInGb
    }}
}}
"""

response = requests.post(
    RUNPOD_API_URL,
    headers=headers,
    json={"query": create_template_mutation}
)

if response.status_code == 200:
    data = response.json()

    if "errors" in data:
        print(f"\n❌ Template Creation Failed:")
        for error in data["errors"]:
            print(f"   - {error.get('message', 'Unknown error')}")
        exit(1)

    template = data.get("data", {}).get("saveTemplate", {})
    template_id = template.get("id")

    if not template_id:
        print("\n❌ No template ID returned")
        print(json.dumps(data, indent=2))
        exit(1)

    print(f"✅ Template Created Successfully!")
    print(f"   ID: {template_id}")
    print(f"   Name: {template.get('name')}")
    print(f"   Image: {template.get('imageName')}")
else:
    print(f"\n❌ HTTP Error: {response.status_code}")
    print(response.text)
    exit(1)

# Step 2: Create Serverless Endpoint
print(f"\n🚀 Step 2: Creating Serverless Endpoint...")

create_endpoint_mutation = f"""
mutation {{
    saveEndpoint(input: {{
        gpuIds: "AMPERE_16"
        name: "social-intelligence"
        templateId: "{template_id}"
        workersMin: 0
        workersMax: 1
        idleTimeout: 5
        scalerType: "QUEUE_DELAY"
        scalerValue: 4
        locations: "US"
    }}) {{
        id
        name
        templateId
        gpuIds
        workersMin
        workersMax
        idleTimeout
        scalerType
        scalerValue
    }}
}}
"""

response = requests.post(
    RUNPOD_API_URL,
    headers=headers,
    json={"query": create_endpoint_mutation}
)

if response.status_code == 200:
    data = response.json()

    if "errors" in data:
        print(f"\n❌ Endpoint Creation Failed:")
        for error in data["errors"]:
            print(f"   - {error.get('message', 'Unknown error')}")
        print(f"\n⚠️  Template ID: {template_id} (you may want to delete this)")
        exit(1)

    endpoint = data.get("data", {}).get("saveEndpoint", {})
    endpoint_id = endpoint.get("id")

    if not endpoint_id:
        print("\n❌ No endpoint ID returned")
        print(json.dumps(data, indent=2))
        exit(1)

    print(f"✅ Endpoint Created Successfully!")
    print(f"   ID: {endpoint_id}")
    print(f"   Name: {endpoint.get('name')}")
    print(f"   Template: {endpoint.get('templateId')}")
    print(f"   GPU: {endpoint.get('gpuIds')}")
    print(f"   Workers: {endpoint.get('workersMin')}-{endpoint.get('workersMax')}")

    print("\n" + "=" * 60)
    print("✅ SUCCESS - Add these to GitHub Secrets:")
    print("=" * 60)
    print(f"RUNPOD_ENDPOINT_ID={endpoint_id}")
    print(f"RUNPOD_API_KEY={os.getenv('RUNPOD_API_KEY')}")
    print(f"SUPABASE_DATABASE_URL={os.getenv('SUPABASE_DATABASE_URL')}")
    print(f"CLOSE_API_KEY={os.getenv('CLOSE_API_KEY')}")
    print("=" * 60)
else:
    print(f"\n❌ HTTP Error: {response.status_code}")
    print(response.text)
    exit(1)
