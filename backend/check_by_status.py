import asyncio
import httpx
import os
import base64
from dotenv import load_dotenv

load_dotenv()

async def check_leads_by_status():
    api_key = os.getenv("CLOSE_API_KEY")
    auth_header = f"Basic {base64.b64encode(f'{api_key}:'.encode()).decode()}"
    
    # Status IDs from .env
    statuses = {
        "Hot ATL": os.getenv("CLOSE_STATUS_HOT_ATL"),
        "Validated ATL": os.getenv("CLOSE_STATUS_VALIDATED_ATL"),
        "BTL": os.getenv("CLOSE_STATUS_BTL")
    }
    
    print("\n" + "="*70)
    print("CHECKING LEADS BY STATUS (SMART VIEW ASSIGNMENT)")
    print("="*70 + "\n")
    
    async with httpx.AsyncClient() as client:
        for status_name, status_id in statuses.items():
            if not status_id:
                continue
                
            print(f"📁 {status_name}")
            print(f"   Status ID: {status_id}")
            
            # Query leads with this status
            response = await client.get(
                "https://api.close.com/api/v1/lead/",
                headers={"Authorization": auth_header},
                params={
                    "status_id": status_id,
                    "_limit": 10,
                    "_order_by": "-date_created"
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                leads = data.get("data", [])
                
                print(f"   📈 Leads with this status: {len(leads)}\n")
                
                if leads:
                    for i, lead in enumerate(leads[:5], 1):
                        name = lead.get("name", "Unknown")
                        lead_id = lead.get("id", "")
                        contacts = lead.get("contacts", [])
                        date_created = lead.get("date_created", "")[:19]
                        
                        # Highlight our test lead
                        if "GENERATOR" in name.upper():
                            print(f"   ✅ {i}. {name} (TEST LEAD!)")
                            print(f"          Lead ID: {lead_id}")
                            print(f"          Contacts: {len(contacts)}")
                            print(f"          Created: {date_created}")
                            
                            # Show all contacts
                            print(f"          All Contacts:")
                            for j, contact in enumerate(contacts, 1):
                                contact_name = contact.get("name", "N/A")
                                title = contact.get("title", "N/A")
                                emails = contact.get("emails", [])
                                email = emails[0].get("email") if emails else "N/A"
                                print(f"             {j}. {contact_name} - {title}")
                                print(f"                Email: {email}")
                        else:
                            print(f"      {i}. {name}")
                            print(f"          Contacts: {len(contacts)} | Created: {date_created[:10]}")
                        print()
                else:
                    print(f"   (No leads with this status)\n")
            else:
                print(f"   ❌ Error: {response.status_code}\n")
            
            print("-" * 70)
            print()

asyncio.run(check_leads_by_status())
