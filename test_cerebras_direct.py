#!/usr/bin/env python3
"""Direct Cerebras API test to verify connectivity and usage"""
import os
from openai import OpenAI
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key from environment
api_key = os.getenv("CEREBRAS_API_KEY")
if not api_key:
    print("❌ ERROR: CEREBRAS_API_KEY not found in environment variables")
    print("Please ensure .env file contains CEREBRAS_API_KEY")
    exit(1)

# Initialize Cerebras client
client = OpenAI(
    api_key=api_key,
    base_url=os.getenv("CEREBRAS_API_BASE", "https://api.cerebras.ai/v1")
)

print("🧪 Direct Cerebras API Test")
print("=" * 60)

# Make a simple API call
start = time.time()
response = client.chat.completions.create(
    model="llama3.1-8b",
    messages=[
        {"role": "user", "content": "Say 'Cerebras is working!' in exactly 3 words"}
    ],
    max_tokens=20
)
end = time.time()

# Extract results
content = response.choices[0].message.content
usage = response.usage
latency_ms = int((end - start) * 1000)

print(f"\n✅ API Call Successful!")
print(f"Response: {content}")
print(f"Latency: {latency_ms}ms")
print(f"\nToken Usage:")
print(f"  Prompt tokens: {usage.prompt_tokens}")
print(f"  Completion tokens: {usage.completion_tokens}")
print(f"  Total tokens: {usage.total_tokens}")
print(f"\nModel: {response.model}")
print(f"\n💰 This call used {usage.total_tokens} tokens")
print(f"Check your Cerebras dashboard at: https://cloud.cerebras.ai/")
