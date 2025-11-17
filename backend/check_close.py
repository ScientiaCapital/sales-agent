import asyncio
import os
import sys
sys.path.insert(0, 'backend')

from dotenv import load_dotenv
load_dotenv()

from app.services.crm.close import CloseProvider

async def check_leads():
    api_key = os.getenv("CLOSE_API_KEY")
    close = CloseProvider(api_key=api_key)
    
    # Check smart view for "My New Leads (Last 7 days)"
    print("\n🔍 Checking Close CRM for recent leads...\n")
    
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.close.com/api/v1/lead/",
            headers={
                "Authorization": close.auth_header,
                "Content-Type": "application/json"
            },
            params={
                "_limit": 10,
                "_order_by": "-date_created"
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            leads = data.get("data", [])
            
            print(f"📊 Found {len(leads)} most recent leads:\n")
            
            for i, lead in enumerate(leads, 1):
                name = lead.get("name", "Unknown")
                status = lead.get("status_label", "Unknown")
                contacts = lead.get("contacts", [])
                date_created = lead.get("date_created", "")[:19]
                lead_id = lead.get("id", "")
                
                print(f"{i}. {name}")
                print(f"   ID: {lead_id}")
                print(f"   Status: {status}")
                print(f"   Contacts: {len(contacts)}")
                print(f"   Created: {date_created}")
                
                # Show first contact if available
                if contacts:
                    first = contacts[0]
                    email = first.get("emails", [{}])[0].get("email", "No email")
                    print(f"   First Contact: {first.get('name', 'N/A')} ({email})")
                print()
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)

asyncio.run(check_leads())
