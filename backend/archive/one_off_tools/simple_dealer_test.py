#!/usr/bin/env python3
"""
Simple Dealer Scraper Integration Test

This script demonstrates the integration between dealer-scraper-mvp and sales-agent
by analyzing the CSV data structure and showing how it maps to the sales-agent system.
"""

import pandas as pd
import os
from pathlib import Path


def analyze_dealer_data():
    """Analyze dealer scraper data structure and show integration points."""
    
    print("🚀 Dealer Scraper + Sales Agent Integration Analysis")
    print("=" * 60)
    
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
            
        print(f"\n📊 Analyzing: {file_path}")
        print("-" * 40)
        
        try:
            # Load CSV data
            df = pd.read_csv(file_path)
            print(f"✅ Loaded {len(df)} records")
            
            # Show column structure
            print(f"📋 Columns ({len(df.columns)}):")
            for i, col in enumerate(df.columns, 1):
                print(f"   {i:2d}. {col}")
            
            # Show basic statistics
            print(f"\n📈 Basic Statistics:")
            print(f"   Total Records: {len(df)}")
            
            # ICP tier distribution
            if 'ICP_Tier' in df.columns:
                tier_dist = df['ICP_Tier'].value_counts()
                print(f"   ICP Tier Distribution:")
                for tier, count in tier_dist.items():
                    print(f"     {tier}: {count}")
            
            # OEM count distribution
            if 'OEM_Count' in df.columns:
                oem_dist = df['OEM_Count'].value_counts()
                print(f"   OEM Count Distribution:")
                for count, freq in oem_dist.items():
                    print(f"     {count} OEMs: {freq}")
            
            # State distribution
            if 'state' in df.columns:
                state_dist = df['state'].value_counts().head(10)
                print(f"   Top 10 States:")
                for state, count in state_dist.items():
                    print(f"     {state}: {count}")
            
            # ICP score statistics
            if 'ICP_Score' in df.columns:
                print(f"   ICP Score Statistics:")
                print(f"     Average: {df['ICP_Score'].mean():.1f}")
                print(f"     Min: {df['ICP_Score'].min():.1f}")
                print(f"     Max: {df['ICP_Score'].max():.1f}")
            
            # Show sample record
            if len(df) > 0:
                print(f"\n📝 Sample Record:")
                sample = df.iloc[0]
                for col in ['name', 'phone', 'domain', 'ICP_Score', 'ICP_Tier', 'OEM_Count', 'OEMs_Certified']:
                    if col in sample:
                        print(f"     {col}: {sample[col]}")
            
        except Exception as e:
            print(f"❌ Error analyzing {file_path}: {e}")


def analyze_multi_oem_patterns():
    """Analyze multi-OEM contractor patterns."""
    
    print(f"\n🔍 Multi-OEM Contractor Analysis")
    print("=" * 60)
    
    file_path = "test_data/multi_oem_crossovers_expanded_20251029.csv"
    if not os.path.exists(file_path):
        print(f"❌ Multi-OEM file not found: {file_path}")
        return
    
    try:
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
            print(f"     {i:2d}. {combo}: {count} contractors")
        
        # Show triple-OEM unicorns
        triple_oem = df[df['OEM_Count'] >= 3]
        if len(triple_oem) > 0:
            print(f"\n   💎 Triple-OEM Unicorns ({len(triple_oem)}):")
            for _, row in triple_oem.iterrows():
                print(f"     {row['name']} - {row['OEMs_Certified']} (Score: {row['ICP_Score']})")
        
        # Show top dual-OEM contractors
        dual_oem = df[df['OEM_Count'] == 2]
        if len(dual_oem) > 0:
            print(f"\n   🥇 Top Dual-OEM Contractors (by ICP Score):")
            top_dual = dual_oem.nlargest(5, 'ICP_Score')
            for _, row in top_dual.iterrows():
                print(f"     {row['name']} - {row['OEMs_Certified']} (Score: {row['ICP_Score']})")
        
    except Exception as e:
        print(f"❌ Multi-OEM analysis failed: {e}")


def show_integration_mapping():
    """Show how dealer scraper data maps to sales-agent fields."""
    
    print(f"\n🔗 Data Integration Mapping")
    print("=" * 60)
    
    mapping = {
        'Dealer Scraper Field': 'Sales Agent Field',
        'name': 'company_name',
        'phone': 'phone',
        'website': 'website',
        'email': 'email',
        'street': 'address',
        'city': 'city',
        'state': 'state',
        'zip': 'zip_code',
        'domain': 'domain',
        'ICP_Score': 'icp_score',
        'ICP_Tier': 'icp_tier',
        'OEM_Count': 'oem_count',
        'OEMs_Certified': 'oem_certifications',
        'has_hvac': 'has_hvac',
        'has_solar': 'has_solar',
        'has_generator': 'has_generator',
        'has_electrical': 'has_electrical',
        'has_plumbing': 'has_plumbing',
        'is_mep_r_contractor': 'is_mep_r_contractor',
        'is_resimercial': 'is_resimercial',
        'is_commercial': 'is_commercial',
        'employee_count': 'employee_count',
        'estimated_revenue': 'estimated_revenue',
        'rating': 'rating',
        'review_count': 'review_count'
    }
    
    print("📋 Field Mapping:")
    for dealer_field, sales_field in mapping.items():
        print(f"   {dealer_field:<25} → {sales_field}")
    
    print(f"\n🎯 Key Integration Points:")
    print("   1. ICP Scoring: Preserves 4-dimension scoring (Resimercial, Multi-OEM, MEP+R, O&M)")
    print("   2. Tier Classification: PLATINUM/GOLD/SILVER/BRONZE prioritization")
    print("   3. Multi-OEM Detection: Identifies platform consolidation pain points")
    print("   4. Capability Mapping: HVAC, Solar, Generator, Electrical, Plumbing flags")
    print("   5. Geographic Targeting: SREC state priority and ITC urgency")
    print("   6. Business Signals: Commercial capability, employee count, revenue estimates")


def show_messaging_strategy():
    """Show messaging strategy for different contractor types."""
    
    print(f"\n💬 Messaging Strategy")
    print("=" * 60)
    
    print("🎯 Multi-OEM Messaging:")
    print("   Triple-OEM Pain Point: 'Managing 3+ separate monitoring platforms?")
    print("   That's 3 different logins, 3 UIs, 3 customer experiences.'")
    print("   Solution: 'Coperniq consolidates all monitoring into one unified dashboard'")
    
    print("\n   Dual-OEM Pain Point: 'Managing Generac and Enphase separately?")
    print("   Your customers are confused about which app to use.'")
    print("   Solution: 'Coperniq gives your customers one app for both systems'")
    
    print(f"\n🏆 Tier-Based Messaging:")
    print("   GOLD Tier (60-79): 'You're juggling multiple platforms and serving")
    print("   diverse markets - Coperniq can simplify your operations.'")
    print("   Approach: BDR outreach, standard demo, 30-day pilot program")
    
    print("\n   SILVER Tier (40-59): 'As your business grows, platform consolidation")
    print("   becomes more important. Let's explore how Coperniq can help.'")
    print("   Approach: Email nurture sequence, educational content")
    
    print(f"\n🚀 Value Propositions:")
    print("   1. Platform Consolidation: 'Stop juggling multiple monitoring platforms'")
    print("   2. Brand Agnostic: 'Only platform for microinverters + batteries + generators + HVAC'")
    print("   3. ITC Urgency: 'Residential Dec 2025, Commercial Q2 2026'")
    print("   4. SREC Focus: 'Sustainable markets post-ITC (state incentives continue)'")


def main():
    """Main analysis function."""
    
    # Analyze dealer data structure
    analyze_dealer_data()
    
    # Analyze multi-OEM patterns
    analyze_multi_oem_patterns()
    
    # Show integration mapping
    show_integration_mapping()
    
    # Show messaging strategy
    show_messaging_strategy()
    
    print(f"\n✅ Integration Analysis Complete!")
    print("=" * 60)
    print("🎯 Next Steps:")
    print("   1. Import dealer data via API: POST /api/v1/dealer-import/import")
    print("   2. Analyze multi-OEM patterns: GET /api/v1/dealer-import/multi-oem-analysis")
    print("   3. Get tier-based messaging: GET /api/v1/dealer-import/messaging/tier-based")
    print("   4. Run AI qualification and enrichment on imported leads")


if __name__ == "__main__":
    main()
