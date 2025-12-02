import asyncio
import httpx
import os
import base64
from dotenv import load_dotenv

load_dotenv()

async def delete_lead():
    api_key = os.getenv("CLOSE_API_KEY")
    auth_header = f"Basic {base64.b64encode(f'{api_key}:'.encode()).decode()}"
    
    # New test lead
    lead_id = "lead_DQoXeCmZOjle1ttuZ98JkBfclaYlJk7u3fGKRdq4QjI"
    
    print(f"\n🗑️  Deleting test lead: GENERATOR SUPERCENTER OF ORLANDO")
    print(f"   Lead ID: {lead_id}\n")
    
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"https://api.close.com/api/v1/lead/{lead_id}/",
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        
        if response.status_code in [200, 204]:
            print(f"✅ Successfully deleted test lead!")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)

asyncio.run(delete_lead())
