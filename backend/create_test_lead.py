import asyncio
import httpx
import json

async def create_test_lead():
    """Step 1: Create ONE test lead in Close CRM (dry_run=FALSE)"""
    
    print("\n" + "="*60)
    print("STEP 1: Creating TEST lead in Close CRM")
    print("="*60 + "\n")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/api/v1/leads/test-pipeline",
            json={
                "lead": {
                    "name": "GENERATOR SUPERCENTER OF ORLANDO",
                    "website": "https://www.generatorsupercenter.com/",
                    "domain": "generatorsupercenter.com",
                    "industry": "Generator Services"
                },
                "options": {
                    "stop_on_duplicate": False,
                    "skip_enrichment": False,
                    "create_in_crm": True,
                    "dry_run": False  # ACTUAL CRM WRITE!
                }
            },
            timeout=120.0
        )
        
        result = response.json()
        
        # Show results
        print(f"✅ Pipeline Status: {result.get('success')}")
        print(f"📊 Total Latency: {result.get('total_latency_ms')}ms")
        print(f"💰 Total Cost: ${result.get('total_cost_usd'):.6f}\n")
        
        # Show qualification results
        qual = result.get('stages', {}).get('qualification', {})
        qual_output = qual.get('output', {})
        print(f"🎯 Qualification Score: {qual_output.get('qualification_score', 0)}")
        
        # Show discovered contacts
        metadata = qual_output.get('metadata', {})
        contacts = metadata.get('discovered_contacts', [])
        print(f"👥 Discovered Contacts: {len(contacts)}")
        for i, c in enumerate(contacts, 1):
            name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
            print(f"   {i}. {name} - {c.get('position', 'N/A')}")
        
        # Show CRM creation result
        crm = result.get('stages', {}).get('close_crm', {})
        crm_output = crm.get('output', {})
        print(f"\n🏢 Close CRM Creation:")
        print(f"   Status: {crm.get('status')}")
        print(f"   Lead ID: {crm_output.get('id', 'N/A')}")
        print(f"   Contacts Created: {crm_output.get('contacts_created', 0)}")
        
        if crm_output.get('atl_contacts'):
            print(f"   ATL Contacts: {', '.join(crm_output.get('atl_contacts', []))}")
        
        print("\n" + "="*60)
        print("✅ TEST LEAD CREATED IN CLOSE CRM")
        print("="*60 + "\n")
        
        return crm_output.get('id')

asyncio.run(create_test_lead())
