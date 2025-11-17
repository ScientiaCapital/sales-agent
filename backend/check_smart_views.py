import asyncio
import httpx
import os
import base64
from dotenv import load_dotenv

load_dotenv()

async def check_smart_views():
    api_key = os.getenv("CLOSE_API_KEY")
    auth_header = f"Basic {base64.b64encode(f'{api_key}:'.encode()).decode()}"
    
    print("\n" + "="*70)
    print("CHECKING SMART VIEWS IN CLOSE CRM")
    print("="*70 + "\n")
    
    async with httpx.AsyncClient() as client:
        # Get all saved searches (smart views)
        response = await client.get(
            "https://api.close.com/api/v1/saved_search/",
            headers={"Authorization": auth_header},
            timeout=30.0
        )
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            return
        
        data = response.json()
        smart_views = data.get("data", [])
        
        print(f"📊 Found {len(smart_views)} Smart Views\n")
        
        # The 5 smart views we care about
        target_views = [
            "High-Intent ATL Conta",  # Truncated name
            "Hot ATL Leads (Priority)",
            "Validated ATL Leads",
            "BTL Leads (Lower Prio",  # Truncated
            "My New Leads (Last 7 Days)"
        ]
        
        for view in smart_views:
            name = view.get("name", "")
            view_id = view.get("id", "")
            
            # Check if this is one of our target views
            if any(target in name for target in target_views):
                print(f"📁 {name}")
                print(f"   ID: {view_id}")
                
                # Get leads in this view
                query = view.get("query", {})
                
                # Execute the search
                search_response = await client.post(
                    "https://api.close.com/api/v1/data/search/",
                    headers={
                        "Authorization": auth_header,
                        "Content-Type": "application/json"
                    },
                    json={
                        "_type": "lead",
                        "query": query,
                        "_limit": 10
                    },
                    timeout=30.0
                )
                
                if search_response.status_code == 200:
                    search_data = search_response.json()
                    leads = search_data.get("data", [])
                    
                    print(f"   📈 Leads in view: {len(leads)}")
                    
                    if leads:
                        for i, lead in enumerate(leads[:5], 1):  # Show first 5
                            lead_name = lead.get("name", "Unknown")
                            lead_id = lead.get("id", "")
                            status = lead.get("status_label", "N/A")
                            contacts_count = len(lead.get("contacts", []))
                            
                            # Highlight our test lead
                            if "GENERATOR SUPERCENTER" in lead_name.upper():
                                print(f"   ✅ {i}. {lead_name} (OUR TEST LEAD!)")
                            else:
                                print(f"      {i}. {lead_name}")
                            
                            print(f"          Status: {status} | Contacts: {contacts_count}")
                    else:
                        print(f"   (Empty)")
                else:
                    print(f"   ❌ Error querying: {search_response.status_code}")
                
                print()

asyncio.run(check_smart_views())
