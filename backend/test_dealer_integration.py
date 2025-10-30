#!/usr/bin/env python3
"""
Test Dealer Scraper Integration

This script demonstrates the integration between dealer-scraper-mvp and sales-agent
by importing and processing contractor data with ICP scoring and tier classification.

Usage:
    python test_dealer_integration.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.services.dealer_scraper_importer import DealerScraperImporter
from app.core.logging import setup_logging

logger = setup_logging(__name__)


async def test_dealer_integration():
    """Test the dealer scraper integration with sample data."""
    
    print("🚀 Testing Dealer Scraper Integration")
    print("=" * 50)
    
    # Initialize importer
    importer = DealerScraperImporter()
    
    # Test files from dealer scraper output
    test_files = [
        "test_data/gold_tier_prospects_20251029.csv",
        "test_data/icp_scored_contractors_final_20251029.csv",
        "test_data/multi_oem_crossovers_expanded_20251029.csv"
    ]
    
    for file_path in test_files:
        if not os.path.exists(file_path):
            print(f"❌ Test file not found: {file_path}")
            continue
            
        print(f"\n📊 Processing: {file_path}")
        print("-" * 30)
        
        try:
            # Validate CSV format
            validation = await importer.validate_csv_format(file_path)
            print(f"✅ CSV Validation: {'Valid' if validation['valid'] else 'Invalid'}")
            if not validation['valid']:
                print(f"   Missing fields: {validation['missing_fields']}")
                continue
            
            # Get summary statistics
            summary = await importer.get_import_summary(file_path)
            print(f"📈 Summary Statistics:")
            print(f"   Total Contractors: {summary['total_contractors']}")
            print(f"   Tier Distribution: {summary['tier_distribution']}")
            print(f"   Multi-OEM Contractors: {summary['multi_oem_contractors']}")
            print(f"   High Priority: {summary['high_priority_contractors']}")
            print(f"   Average ICP Score: {summary['average_icp_score']:.1f}")
            
            # Show top OEM certifications
            top_oems = summary.get('top_oem_certifications', {})
            if top_oems:
                print(f"   Top OEM Certifications:")
                for oem, count in list(top_oems.items())[:5]:
                    print(f"     {oem}: {count}")
            
            # Show capability distribution
            capabilities = summary.get('capability_distribution', {})
            if capabilities:
                print(f"   Capability Distribution:")
                for cap, count in capabilities.items():
                    if count > 0:
                        print(f"     {cap}: {count}")
            
            # Test import (small batch for demo)
            print(f"\n🔄 Testing Import (first 10 records)...")
            import_result = await importer.import_contractors_csv(
                file_path=file_path,
                batch_size=10,
                qualification_enabled=False,  # Disable for demo
                enrichment_enabled=False     # Disable for demo
            )
            
            print(f"✅ Import Results:")
            print(f"   Processed: {import_result['processed']}")
            print(f"   Qualified: {import_result['qualified']}")
            print(f"   Enriched: {import_result['enriched']}")
            print(f"   Errors: {import_result['errors']}")
            print(f"   Success Rate: {import_result['success_rate']:.1f}%")
            
        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
            logger.error(f"Error processing {file_path}: {e}")
    
    print(f"\n🎯 Integration Test Complete!")
    print("=" * 50)


async def test_multi_oem_analysis():
    """Test multi-OEM contractor analysis."""
    
    print("\n🔍 Testing Multi-OEM Analysis")
    print("=" * 50)
    
    try:
        import pandas as pd
        
        # Load the multi-OEM crossovers file
        file_path = "test_data/multi_oem_crossovers_expanded_20251029.csv"
        if not os.path.exists(file_path):
            print(f"❌ Multi-OEM file not found: {file_path}")
            return
        
        df = pd.read_csv(file_path)
        print(f"📊 Multi-OEM Analysis:")
        print(f"   Total Multi-OEM Contractors: {len(df)}")
        
        # Analyze OEM combinations
        oem_combinations = {}
        for _, row in df.iterrows():
            oems = str(row['OEMs_Certified']).split(', ')
            if len(oems) >= 2:
                combo = ', '.join(sorted(oems))
                oem_combinations[combo] = oem_combinations.get(combo, 0) + 1
        
        # Show top combinations
        top_combinations = sorted(oem_combinations.items(), key=lambda x: x[1], reverse=True)[:10]
        print(f"   Top OEM Combinations:")
        for i, (combo, count) in enumerate(top_combinations, 1):
            print(f"     {i}. {combo}: {count} contractors")
        
        # Show triple-OEM unicorns
        triple_oem = df[df['OEM_Count'] >= 3]
        if len(triple_oem) > 0:
            print(f"   💎 Triple-OEM Unicorns ({len(triple_oem)}):")
            for _, row in triple_oem.iterrows():
                print(f"     {row['name']} - {row['OEMs_Certified']} (Score: {row['ICP_Score']})")
        
        # Show top dual-OEM contractors
        dual_oem = df[df['OEM_Count'] == 2]
        if len(dual_oem) > 0:
            print(f"   🥇 Top Dual-OEM Contractors (by ICP Score):")
            top_dual = dual_oem.nlargest(5, 'ICP_Score')
            for _, row in top_dual.iterrows():
                print(f"     {row['name']} - {row['OEMs_Certified']} (Score: {row['ICP_Score']})")
        
    except Exception as e:
        print(f"❌ Multi-OEM analysis failed: {e}")
        logger.error(f"Multi-OEM analysis failed: {e}")


async def test_messaging_templates():
    """Test messaging templates for different contractor types."""
    
    print("\n💬 Testing Messaging Templates")
    print("=" * 50)
    
    # Multi-OEM messaging
    print("🎯 Multi-OEM Messaging:")
    print("   Triple-OEM Pain Point: 'Managing 3+ separate monitoring platforms?")
    print("   That's 3 different logins, 3 UIs, 3 customer experiences.'")
    print("   Solution: 'Coperniq consolidates all monitoring into one unified dashboard'")
    
    print("\n   Dual-OEM Pain Point: 'Managing Generac and Enphase separately?")
    print("   Your customers are confused about which app to use.'")
    print("   Solution: 'Coperniq gives your customers one app for both systems'")
    
    # Tier-based messaging
    print("\n🏆 Tier-Based Messaging:")
    print("   GOLD Tier (60-79): 'You're juggling multiple platforms and serving")
    print("   diverse markets - Coperniq can simplify your operations.'")
    print("   Approach: BDR outreach, standard demo, 30-day pilot program")
    
    print("\n   SILVER Tier (40-59): 'As your business grows, platform consolidation")
    print("   becomes more important. Let's explore how Coperniq can help.'")
    print("   Approach: Email nurture sequence, educational content")


async def main():
    """Main test function."""
    print("🧪 Dealer Scraper + Sales Agent Integration Test")
    print("=" * 60)
    
    # Test basic integration
    await test_dealer_integration()
    
    # Test multi-OEM analysis
    await test_multi_oem_analysis()
    
    # Test messaging templates
    await test_messaging_templates()
    
    print(f"\n✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
