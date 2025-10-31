#!/usr/bin/env python3
"""
Task 30: Qualify All 200 Leads with Cerebras

Runs QualificationAgent (Cerebras ultra-fast inference) on all 200 imported leads:
- Generate qualification scores (0-100)
- Generate AI reasoning for each score
- Update PostgreSQL leads table with qualification_score and reasoning
- Track API calls in cerebras_api_calls table (latency_ms, cost, tokens)

Expected:
- Total time: ~2 minutes for 200 leads
- Total cost: ~$0.0012 ($0.000006 per request)
- Target latency: <1000ms per lead
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    root_env = Path(__file__).parent.parent.parent / '.env'
    if root_env.exists():
        load_dotenv(root_env)

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.lead import Lead
# Import QualificationAgent directly to avoid import chain issues
from app.services.langgraph.agents.qualification_agent import QualificationAgent
import asyncio
from typing import Dict, Any
from datetime import datetime
import time

async def qualify_all_leads():
    """Qualify all 200 leads with Cerebras."""
    db: Session = next(get_db())
    
    try:
        # Get all imported leads (from dealer-scraper)
        print("📋 Fetching all leads for qualification...")
        all_leads = db.query(Lead).filter(
            Lead.additional_data.isnot(None)
        ).limit(200).all()
        
        total_leads = len(all_leads)
        print(f"✅ Found {total_leads} leads to qualify\n")
        
        # Filter to only leads without qualification scores
        unqualified_leads = [lead for lead in all_leads if lead.qualification_score is None]
        
        if unqualified_leads:
            print(f"📊 Found {len(unqualified_leads)} unqualified leads")
            print(f"   Skipping {total_leads - len(unqualified_leads)} already qualified leads\n")
            leads_to_qualify = unqualified_leads
        else:
            print("⚠️  All leads already qualified. Re-qualifying all leads...\n")
            leads_to_qualify = all_leads
        
        if not leads_to_qualify:
            print("✅ No leads to qualify!")
            return
        
        # Initialize QualificationAgent
        print("🔧 Initializing QualificationAgent...")
        agent = QualificationAgent()
        
        # Qualify each lead
        print(f"\n🧪 Qualifying {len(leads_to_qualify)} leads...")
        print("="*60)
        
        results = []
        start_time = time.time()
        
        for i, lead in enumerate(leads_to_qualify, 1):
            print(f"\n[{i}/{len(leads_to_qualify)}] {lead.company_name}")
            
            # Extract ICP data from additional_data
            additional = lead.additional_data if isinstance(lead.additional_data, dict) else {}
            icp_score = additional.get('icp_score') or additional.get('ICP_Score')
            icp_tier = additional.get('icp_tier') or additional.get('ICP_Tier')
            oem_count = additional.get('oem_count') or additional.get('OEM_Count')
            has_hvac = additional.get('has_hvac', False)
            has_solar = additional.get('has_solar', False)
            employee_count = additional.get('employee_count') or lead.company_size
            
            # Build qualification context
            qualification_context = {
                "company_name": lead.company_name,
                "company_website": lead.company_website,
                "industry": lead.industry or "Energy Contractors",
                "company_size": employee_count or lead.company_size,
                "notes": f"ICP Score: {icp_score}, ICP Tier: {icp_tier}, OEM Count: {oem_count}, HVAC: {has_hvac}, Solar: {has_solar}"
            }
            
            try:
                # Qualify lead
                result = await agent.qualify(
                    company_name=qualification_context["company_name"],
                    company_website=qualification_context.get("company_website"),
                    company_size=qualification_context.get("company_size"),
                    industry=qualification_context.get("industry"),
                    contact_name=None,
                    contact_title=None,
                    notes=qualification_context.get("notes")
                )
                
                # Update lead in database
                lead.qualification_score = result.qualification_score
                lead.qualification_reasoning = result.qualification_reasoning
                lead.qualification_model = result.qualification_model or "cerebras-llama3.1-8b"
                lead.qualification_latency_ms = result.latency_ms
                lead.qualified_at = datetime.now()
                
                # Update additional_data with qualification metadata
                if not isinstance(lead.additional_data, dict):
                    lead.additional_data = {}
                lead.additional_data['qualified_at'] = datetime.now().isoformat()
                lead.additional_data['qualification_tier'] = result.tier
                lead.additional_data['qualification_recommendations'] = result.recommendations
                
                db.commit()
                
                print(f"   ✅ Qualified: Score {result.qualification_score:.1f} ({result.tier})")
                print(f"      Latency: {result.latency_ms}ms")
                print(f"      Reasoning: {result.qualification_reasoning[:100]}...")
                
                results.append({
                    'lead_id': lead.id,
                    'company_name': lead.company_name,
                    'success': True,
                    'score': result.qualification_score,
                    'tier': result.tier,
                    'latency_ms': result.latency_ms
                })
                
            except Exception as e:
                print(f"   ❌ Qualification failed: {str(e)}")
                db.rollback()
                
                results.append({
                    'lead_id': lead.id,
                    'company_name': lead.company_name,
                    'success': False,
                    'error': str(e)
                })
            
            # Progress indicator
            if i % 25 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                remaining = (len(leads_to_qualify) - i) / rate
                print(f"\n   📊 Progress: {i}/{len(leads_to_qualify)} ({i/len(leads_to_qualify)*100:.1f}%)")
                print(f"      Rate: {rate:.1f} leads/sec")
                print(f"      ETA: {remaining:.0f} seconds\n")
        
        total_time = time.time() - start_time
        
        # Summary
        print("\n" + "="*60)
        print("📈 Qualification Summary")
        print("="*60)
        successful = sum(1 for r in results if r['success'])
        print(f"Total Leads: {len(leads_to_qualify)}")
        print(f"Successfully Qualified: {successful}")
        print(f"Failed: {len(leads_to_qualify) - successful}")
        print(f"Total Time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        print(f"Average Rate: {len(leads_to_qualify)/total_time:.1f} leads/sec")
        
        if successful > 0:
            avg_score = sum(r['score'] for r in results if r['success']) / successful
            avg_latency = sum(r['latency_ms'] for r in results if r['success']) / successful
            
            # Score distribution
            tiers = {}
            for r in results:
                if r['success']:
                    tier = r.get('tier', 'unknown')
                    tiers[tier] = tiers.get(tier, 0) + 1
            
            print(f"\n📊 Performance Metrics:")
            print(f"   - Average Score: {avg_score:.1f}/100")
            print(f"   - Average Latency: {avg_latency:.0f}ms")
            print(f"   - Target: <1000ms per lead")
            
            if avg_latency > 1000:
                print(f"   ⚠️  Average latency exceeds target")
            else:
                print(f"   ✅ Average latency within target")
            
            print(f"\n📈 Score Distribution:")
            for tier, count in sorted(tiers.items(), key=lambda x: x[1], reverse=True):
                print(f"   - {tier}: {count} leads ({count/successful*100:.1f}%)")
            
            # Cost estimate
            estimated_cost = successful * 0.000006  # $0.000006 per Cerebras request
            print(f"\n💰 Cost Estimate:")
            print(f"   - Requests: {successful}")
            print(f"   - Cost per Request: $0.000006")
            print(f"   - Total Cost: ${estimated_cost:.6f}")
        
        print("\n✅ Task 30 complete!")
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(qualify_all_leads())

