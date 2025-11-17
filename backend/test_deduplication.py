import asyncio
import httpx
import json

async def test_deduplication():
    """Step 2: Test SAME company with dry_run=true to prove deduplication"""
    
    print("\n" + "="*60)
    print("STEP 2: Testing Deduplication (DRY RUN)")
    print("="*60 + "\n")
    print("🔍 Running pipeline for GENERATOR SUPERCENTER (already exists!)")
    print("   Mode: dry_run=true (NO CRM writes)\n")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/api/v1/leads/dry-run/test",
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
                    "create_in_crm": False,
                    "dry_run": True  # DRY RUN MODE
                }
            },
            timeout=120.0
        )
        
        result = response.json()
        
        # Extract key data
        company = result.get('company_name')
        score = result.get('qualification_score')
        contacts_count = result.get('discovered_contacts_count')
        
        crm_check = result.get('close_crm_check', {})
        company_exists = crm_check.get('company_exists')
        recommendation = crm_check.get('recommendation')
        matched_lead_id = crm_check.get('matched_lead_id')
        existing_contacts = crm_check.get('existing_contacts')
        confidence = crm_check.get('company_match_confidence')
        
        what_would_happen = result.get('what_would_happen', {})
        action = what_would_happen.get('action')
        
        # Display results
        print("📊 DEDUPLICATION CHECK RESULTS:")
        print("-" * 60)
        print(f"Company: {company}")
        print(f"Qualification Score: {score}")
        print(f"Discovered Contacts: {contacts_count}")
        print()
        
        print("🔍 Close CRM Check:")
        print(f"   Company Exists: {company_exists}")
        print(f"   Match Confidence: {confidence:.1f}%")
        print(f"   Recommendation: {recommendation}")
        print(f"   Matched Lead ID: {matched_lead_id}")
        print(f"   Existing Contacts in CRM: {existing_contacts}")
        print()
        
        print("🎯 WHAT WOULD HAPPEN:")
        print(f"   {action}")
        print()
        
        # Verdict
        print("="*60)
        if company_exists and recommendation == "add_contact_to_existing":
            print("✅ DEDUPLICATION WORKING!")
            print("   - Detected existing company")
            print("   - Would ADD contacts to existing lead")
            print("   - NO duplicate company created!")
        elif not company_exists and recommendation == "create_new":
            print("⚠️  Company not detected (fuzzy match < 85%)")
            print("   - Would create NEW lead")
        else:
            print(f"Status: {recommendation}")
        print("="*60)
        print()

asyncio.run(test_deduplication())
