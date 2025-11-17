import asyncio
import httpx
import os
import base64
from dotenv import load_dotenv

load_dotenv()

async def verify():
    api_key = os.getenv("CLOSE_API_KEY")
    auth_header = f"Basic {base64.b64encode(f'{api_key}:'.encode()).decode()}"
    
    print("\n" + "="*70)
    print("VERIFYING: IS THIS REAL OR MOCK?")
    print("="*70 + "\n")
    
    # Check 1: Does the lead actually exist in Close CRM?
    lead_id = "lead_DQoXeCmZOjle1ttuZ98JkBfclaYlJk7u3fGKRdq4QjI"
    
    async with httpx.AsyncClient() as client:
        # Direct API call to Close CRM
        response = await client.get(
            f"https://api.close.com/api/v1/lead/{lead_id}/",
            headers={"Authorization": auth_header},
            timeout=30.0
        )
        
        if response.status_code == 200:
            print("✅ REAL! Lead exists in Close CRM API")
            lead = response.json()
            print(f"   Company: {lead.get('name')}")
            print(f"   Status: {lead.get('status_label')}")
            print(f"   Contacts: {len(lead.get('contacts', []))}")
            print()
        else:
            print("❌ NOT REAL! Lead doesn't exist")
            print(f"   Error: {response.status_code}")
            return
        
        # Check 2: Get the Validated ATL smart view details
        print("Checking 'Validated ATL Leads' smart view...")
        
        # Get all saved searches
        search_response = await client.get(
            "https://api.close.com/api/v1/saved_search/",
            headers={"Authorization": auth_header},
            timeout=30.0
        )
        
        if search_response.status_code == 200:
            searches = search_response.json().get("data", [])
            
            # Find Validated ATL view
            validated_view = None
            for s in searches:
                if "Validated ATL" in s.get("name", ""):
                    validated_view = s
                    break
            
            if validated_view:
                print(f"✅ Found smart view: {validated_view.get('name')}")
                print(f"   ID: {validated_view.get('id')}")
                print(f"\n📋 Smart View Filters:")
                
                query = validated_view.get("query", {})
                print(f"   Query: {query}")
                
                # Check if our lead matches these filters
                print(f"\n🔍 Checking if our lead matches:")
                
                # Get our lead's status_id
                our_status_id = lead.get("status_id")
                print(f"   Our lead status_id: {our_status_id}")
                
                # Check status filter in query
                if "status_id" in query:
                    expected_status = query.get("status_id")
                    print(f"   Smart view expects: {expected_status}")
                    
                    if our_status_id == expected_status:
                        print(f"   ✅ MATCH!")
                    else:
                        print(f"   ❌ MISMATCH! This is why it's not showing!")
                
                # Check other filters
                if "created_by" in query:
                    print(f"   Created by filter: {query.get('created_by')}")
                    print(f"   Our lead created by: {lead.get('created_by')}")
                
                if "date_created" in query:
                    print(f"   Date filter: {query.get('date_created')}")
                    print(f"   Our lead created: {lead.get('date_created')}")
                
                print()
        
        # Check 3: Query leads with the Validated ATL status
        print("Querying all leads with 'Validated ATL' status...")
        
        status_response = await client.get(
            "https://api.close.com/api/v1/lead/",
            headers={"Authorization": auth_header},
            params={
                "status_id": lead.get("status_id"),
                "_limit": 20
            },
            timeout=30.0
        )
        
        if status_response.status_code == 200:
            status_leads = status_response.json().get("data", [])
            print(f"   Found {len(status_leads)} leads with this status")
            
            # Check if our lead is in this list
            our_lead_in_list = False
            for l in status_leads:
                if l.get("id") == lead_id:
                    our_lead_in_list = True
                    print(f"   ✅ Our test lead IS in this list!")
                    break
            
            if not our_lead_in_list:
                print(f"   ❌ Our test lead is NOT in this list!")
            
            print(f"\n   First 5 leads with 'Validated ATL' status:")
            for i, l in enumerate(status_leads[:5], 1):
                marker = "👉" if l.get("id") == lead_id else "  "
                print(f"   {marker} {i}. {l.get('name')}")

asyncio.run(verify())
