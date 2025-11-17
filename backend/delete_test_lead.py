import asyncio
import os
import sys
sys.path.insert(0, 'backend')

from dotenv import load_dotenv
load_dotenv()

from app.services.crm.close import CloseProvider

async def delete_lead():
    api_key = os.getenv("CLOSE_API_KEY")
    close = CloseProvider(api_key=api_key)
    
    # Lead to delete
    lead_id = "lead_irTFlgLq1c05ipSPVJTQTXgDIVEr7HhxbumjaVllbfc"
    lead_name = "GENERATOR SUPERCENTER OF ORLANDO"
    
    print(f"\n🗑️  Deleting test lead: {lead_name}")
    print(f"   Lead ID: {lead_id}\n")
    
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"https://api.close.com/api/v1/lead/{lead_id}/",
            headers={
                "Authorization": close.auth_header,
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
