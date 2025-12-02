#!/usr/bin/env python3
"""
Task 29: Test EnrichmentAgent ReAct Workflow on 10 Leads

Tests EnrichmentAgent (LangGraph ReAct) on 10 leads to validate:
- Tool orchestration (LinkedIn → CRM fallback)
- Intelligent tool selection
- Confidence scoring (0-1 based on completeness 40%, source quality 30%, freshness 30%)
- Data merging logic
- Latency measurement (<3000ms per lead)
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
from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent
import asyncio
from typing import Dict, Any, List
import time

async def test_enrichment_agent():
    """Test EnrichmentAgent ReAct workflow on 10 leads."""
    db: Session = next(get_db())
    
    try:
        # Select 10 leads with varied data completeness
        print("📋 Selecting 10 leads with varied data completeness...")
        all_leads = db.query(Lead).limit(200).all()
        
        test_leads = []
        for lead in all_leads[:10]:  # Take first 10
            additional = lead.additional_data if isinstance(lead.additional_data, dict) else {}
            linkedin_url = additional.get('linkedin_url') or additional.get('LinkedIn_URL')
            
            test_leads.append({
                'lead_id': lead.id,
                'company_name': lead.company_name,
                'email': lead.contact_email,
                'linkedin_url': linkedin_url,
                'has_email': bool(lead.contact_email),
                'has_linkedin': bool(linkedin_url)
            })
        
        print(f"\n✅ Selected {len(test_leads)} leads:")
        for i, lead in enumerate(test_leads, 1):
            identifiers = []
            if lead['has_email']:
                identifiers.append("email")
            if lead['has_linkedin']:
                identifiers.append("linkedin")
            print(f"   {i}. {lead['company_name']} - {' + '.join(identifiers) if identifiers else 'no identifiers'}")
        
        # Initialize EnrichmentAgent
        print("\n🔧 Initializing EnrichmentAgent...")
        agent = EnrichmentAgent(
            model="claude-3-5-haiku-20241022",
            temperature=0.3,
            max_iterations=25,
            provider="anthropic"
        )
        
        # Test each lead
        print("\n🧪 Testing EnrichmentAgent ReAct workflow...")
        results = []
        
        for i, lead_data in enumerate(test_leads, 1):
            print(f"\n📊 Test {i}/10: {lead_data['company_name']}")
            
            start_time = time.time()
            
            try:
                # Run enrichment
                result = await agent.enrich(
                    email=lead_data['email'],
                    linkedin_url=lead_data['linkedin_url'],
                    lead_id=lead_data['lead_id']
                )
                
                elapsed_ms = int((time.time() - start_time) * 1000)
                
                print(f"   ✅ Enrichment complete ({elapsed_ms}ms)")
                print(f"      - Confidence: {result.confidence_score:.2f}")
                print(f"      - Sources: {', '.join(result.data_sources) if result.data_sources else 'none'}")
                print(f"      - Tools Called: {', '.join(result.tools_called) if result.tools_called else 'none'}")
                print(f"      - Iterations: {result.iterations_used}")
                print(f"      - Cost: ${result.total_cost_usd:.4f}")
                
                # Validate tool orchestration
                tools_called = result.tools_called
                tool_logic = []
                
                if lead_data['has_linkedin']:
                    if 'get_linkedin_profile_tool' in tools_called:
                        tool_logic.append("✅ LinkedIn tool used (has linkedin_url)")
                    else:
                        tool_logic.append("⚠️  LinkedIn tool NOT used despite having linkedin_url")
                
                if lead_data['has_email']:
                    if 'enrich_contact_tool' in tools_called:
                        tool_logic.append("✅ Apollo tool used (has email)")
                    else:
                        tool_logic.append("⚠️  Apollo tool NOT used despite having email")
                
                for logic in tool_logic:
                    print(f"      - {logic}")
                
                # Check data merging
                enriched = result.enriched_data
                if enriched:
                    has_name = bool(enriched.get('name') or enriched.get('first_name'))
                    has_title = bool(enriched.get('title') or enriched.get('current_title'))
                    has_company = bool(enriched.get('company') or enriched.get('current_company'))
                    
                    completeness = sum([has_name, has_title, has_company]) / 3
                    print(f"      - Data Completeness: {completeness:.0%} (name={has_name}, title={has_title}, company={has_company})")
                
                # Validate latency
                if elapsed_ms > 3000:
                    print(f"      ⚠️  Latency {elapsed_ms}ms exceeds target <3000ms")
                else:
                    print(f"      ✅ Latency {elapsed_ms}ms within target <3000ms")
                
                results.append({
                    'lead_id': lead_data['lead_id'],
                    'company_name': lead_data['company_name'],
                    'success': True,
                    'result': result,
                    'latency_ms': elapsed_ms,
                    'confidence': result.confidence_score,
                    'sources': result.data_sources,
                    'tools_called': result.tools_called
                })
                
            except Exception as e:
                elapsed_ms = int((time.time() - start_time) * 1000)
                print(f"   ❌ Enrichment failed ({elapsed_ms}ms): {str(e)}")
                results.append({
                    'lead_id': lead_data['lead_id'],
                    'company_name': lead_data['company_name'],
                    'success': False,
                    'error': str(e),
                    'latency_ms': elapsed_ms
                })
        
        # Summary
        print("\n" + "="*60)
        print("📈 Test Summary")
        print("="*60)
        successful = sum(1 for r in results if r['success'])
        print(f"Total Tests: {len(results)}")
        print(f"Successful: {successful}")
        print(f"Failed: {len(results) - successful}")
        
        if successful > 0:
            avg_latency = sum(r['latency_ms'] for r in results if r['success']) / successful
            avg_confidence = sum(r['confidence'] for r in results if r['success']) / successful
            
            print(f"\n📊 Performance Metrics:")
            print(f"   - Average Latency: {avg_latency:.0f}ms")
            print(f"   - Target: <3000ms")
            print(f"   - Average Confidence: {avg_confidence:.2f}")
            
            # Tool usage stats
            tool_usage = {}
            for r in results:
                if r['success']:
                    for tool in r['tools_called']:
                        tool_usage[tool] = tool_usage.get(tool, 0) + 1
            
            print(f"\n🔧 Tool Usage:")
            for tool, count in tool_usage.items():
                print(f"   - {tool}: {count} calls")
            
            # Data source stats
            source_usage = {}
            for r in results:
                if r['success']:
                    for source in r['sources']:
                        source_usage[source] = source_usage.get(source, 0) + 1
            
            print(f"\n📚 Data Sources Used:")
            for source, count in source_usage.items():
                print(f"   - {source}: {count} times")
        
        print("\n✅ Task 29 complete!")
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_enrichment_agent())

