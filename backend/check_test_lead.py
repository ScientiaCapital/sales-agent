import asyncio
import httpx
import os
import base64
from dotenv import load_dotenv

load_dotenv()

async def check_test_lead():
    api_key = os.getenv("CLOSE_API_KEY")
    auth_header = f"Basic {base64.b64encode(f'{api_key}:'.encode()).decode()}"
    
    lead_id = "lead_DQoXeCmZOjle1ttuZ98JkBfclaYlJk7u3fGKRdq4QjI"
    
    print("\n" + "="*70)
    print("CHECKING TEST LEAD IN CLOSE CRM")
    print("="*70 + "\n")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.close.com/api/v1/lead/{lead_id}/",
            headers={"Authorization": auth_header},
            timeout=30.0
        )
        
        if response.status_code == 200:
            lead = response.json()
            
            name = lead.get("name", "Unknown")
            status = lead.get("status_label", "N/A")
            status_id = lead.get("status_id", "N/A")
            contacts = lead.get("contacts", [])
            description = lead.get("description", "")
            
            print(f"🏢 Company: {name}")
            print(f"📊 Status: {status}")
            print(f"   Status ID: {status_id}")
            print(f"👥 Contacts: {len(contacts)}\n")
            
            print(f"📝 Description:")
            print(f"{description}\n")
            
            print(f"👥 All Contacts:")
            for i, contact in enumerate(contacts, 1):
                contact_name = contact.get("name", "N/A")
                title = contact.get("title", "N/A")
                emails = contact.get("emails", [])
                email = emails[0].get("email") if emails else "N/A"
                urls = contact.get("urls", [])
                linkedin = next((u.get("url") for u in urls if u.get("type") == "linkedin"), "N/A")
                
                print(f"\n   {i}. {contact_name}")
                print(f"      Title: {title}")
                print(f"      Email: {email}")
                print(f"      LinkedIn: {linkedin}")
            
            print("\n" + "="*70)
            print(f"✅ Lead is in Close CRM with status: {status}")
            print("="*70)
            
            # Check which smart view this should be in
            print("\n📁 Expected Smart View Assignment:")
            if "Hot ATL" in status:
                print("   🔥 Hot ATL Leads (Priority)")
            elif "Validated ATL" in status:
                print("   ⭐ Validated ATL Leads")
            elif "BTL" in status:
                print("   📋 BTL Leads (Lower Priority)")
            else:
                print(f"   Status: {status}")
            print()
        else:
            print(f"❌ Error: {response.status_code}")

asyncio.run(check_test_lead())
