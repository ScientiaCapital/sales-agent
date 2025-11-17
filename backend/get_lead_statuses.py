import asyncio
import httpx
import os
import base64
from dotenv import load_dotenv

load_dotenv()

async def get_statuses():
    api_key = os.getenv("CLOSE_API_KEY")
    auth_header = f"Basic {base64.b64encode(f'{api_key}:'.encode()).decode()}"
    
    print("\n" + "="*70)
    print("COPERNIQ'S EXISTING LEAD STATUSES IN CLOSE CRM")
    print("="*70 + "\n")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.close.com/api/v1/status/lead/",
            headers={"Authorization": auth_header},
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            statuses = data.get("data", [])
            
            print(f"📊 Found {len(statuses)} existing lead statuses:\n")
            
            for i, status in enumerate(statuses, 1):
                status_id = status.get("id")
                label = status.get("label")
                
                print(f"{i}. {label}")
                print(f"   ID: {status_id}")
                print()
            
            print("="*70)
            print("Which statuses should we use for the smart views?")
            print("="*70)
            print()
            print("We need to map:")
            print("  🔥 Hot ATL Leads → Which status?")
            print("  ⭐ Validated ATL Leads → Which status?")
            print("  📋 BTL Leads → Which status?")
            print()
        else:
            print(f"❌ Error: {response.status_code}")

asyncio.run(get_statuses())
