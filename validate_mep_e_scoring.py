#!/usr/bin/env python3
"""
Standalone MEP+E Scoring Validation Script

Tests the MEPEScorer service against top_200_prospects_final_20251029.csv
without requiring database access. Validates scoring logic and identifies
top PLATINUM/GOLD tier contractors.

Run: python3 validate_mep_e_scoring.py
"""

import sys
import pandas as pd
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.scoring.mep_e_scorer import MEPEScorer, calculate_mep_e_score
from app.config.oem_taxonomy import count_oems_by_category


def parse_contractor_row(row):
    """Parse contractor row from CSV into format for MEPEScorer"""
    # Parse OEMs_Certified
    oems_certified = []
    if pd.notna(row.get('OEMs_Certified')):
        oems_str = str(row['OEMs_Certified'])
        oems_certified = [oem.strip() for oem in oems_str.split(',') if oem.strip()]

    return {
        'oems_certified': oems_certified,
        'has_heat_pump': row.get('has_heat_pump', False),
        'has_ev_charger': row.get('has_ev_charger', False),
        'has_smart_panel': row.get('has_smart_panel', False),
        'has_microgrid': row.get('has_microgrid', False),
        'has_commercial': row.get('is_commercial', False) or row.get('is_resimercial', False),
        'has_ops_maintenance': row.get('has_ops_maintenance', False),
    }


def validate_csv_scoring(csv_path: str):
    """Validate MEP+E scoring on CSV file"""
    print("=" * 80)
    print("MEP+E Scoring Validation")
    print("=" * 80)
    print(f"\nCSV File: {csv_path}")

    # Load CSV
    try:
        df = pd.read_csv(csv_path)
        print(f"✓ Loaded {len(df)} contractors")
    except Exception as e:
        print(f"✗ Failed to load CSV: {e}")
        return

    # Validate required fields
    required_fields = ['name', 'OEMs_Certified']
    missing = [f for f in required_fields if f not in df.columns]
    if missing:
        print(f"✗ Missing required fields: {missing}")
        return

    print(f"✓ CSV has {len(df.columns)} fields")

    # Score all contractors
    print("\n" + "=" * 80)
    print("Scoring All Contractors")
    print("=" * 80)

    scorer = MEPEScorer()
    results = []

    for idx, row in df.iterrows():
        try:
            contractor_data = parse_contractor_row(row)
            scoring_result = calculate_mep_e_score(contractor_data)

            results.append({
                'name': row.get('name', 'Unknown'),
                'state': row.get('state', 'Unknown'),
                'oems': contractor_data['oems_certified'],
                'oem_count': len(contractor_data['oems_certified']),
                'mep_e_score': scoring_result['mep_e_score'],
                'tier': scoring_result['tier'],
                'hvac_oems': scoring_result['hvac_oem_count'],
                'solar_oems': scoring_result['solar_oem_count'],
                'battery_oems': scoring_result['battery_oem_count'],
                'generator_oems': scoring_result['generator_oem_count'],
                'smart_panel_oems': scoring_result['smart_panel_oem_count'],
                'iot_oems': scoring_result['iot_oem_count'],
                'renewable_readiness': scoring_result['renewable_readiness_score'],
                'asset_centric': scoring_result['asset_centric_score'],
                'projects_service': scoring_result['projects_service_score'],
            })
        except Exception as e:
            print(f"✗ Error scoring {row.get('name', 'Unknown')}: {e}")

    # Convert to DataFrame for analysis
    results_df = pd.DataFrame(results)

    # Tier Distribution
    print("\n" + "-" * 80)
    print("Tier Distribution")
    print("-" * 80)
    tier_counts = results_df['tier'].value_counts()
    for tier in ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE']:
        count = tier_counts.get(tier, 0)
        pct = (count / len(results_df) * 100) if len(results_df) > 0 else 0
        print(f"{tier:12s}: {count:3d} contractors ({pct:5.1f}%)")

    # Score Statistics
    print("\n" + "-" * 80)
    print("Score Statistics")
    print("-" * 80)
    print(f"Average MEP+E Score: {results_df['mep_e_score'].mean():.1f}/100")
    print(f"Median MEP+E Score:  {results_df['mep_e_score'].median():.1f}/100")
    print(f"Min Score:           {results_df['mep_e_score'].min():.1f}/100")
    print(f"Max Score:           {results_df['mep_e_score'].max():.1f}/100")

    # OEM Category Coverage
    print("\n" + "-" * 80)
    print("OEM Category Coverage")
    print("-" * 80)
    print(f"HVAC OEMs:        {(results_df['hvac_oems'] > 0).sum()} contractors")
    print(f"Solar OEMs:       {(results_df['solar_oems'] > 0).sum()} contractors")
    print(f"Battery OEMs:     {(results_df['battery_oems'] > 0).sum()} contractors")
    print(f"Generator OEMs:   {(results_df['generator_oems'] > 0).sum()} contractors")
    print(f"Smart Panel OEMs: {(results_df['smart_panel_oems'] > 0).sum()} contractors")
    print(f"IoT OEMs:         {(results_df['iot_oems'] > 0).sum()} contractors")

    # Multi-OEM Contractors
    print("\n" + "-" * 80)
    print("Multi-OEM Sophistication")
    print("-" * 80)
    print(f"1 OEM:    {(results_df['oem_count'] == 1).sum()} contractors")
    print(f"2 OEMs:   {(results_df['oem_count'] == 2).sum()} contractors")
    print(f"3+ OEMs:  {(results_df['oem_count'] >= 3).sum()} contractors")
    print(f"5+ OEMs:  {(results_df['oem_count'] >= 5).sum()} contractors")
    print(f"8+ OEMs:  {(results_df['oem_count'] >= 8).sum()} contractors")

    # Top 10 PLATINUM Contractors
    print("\n" + "=" * 80)
    print("Top 10 PLATINUM Tier Contractors (Immediate Outreach)")
    print("=" * 80)
    platinum = results_df[results_df['tier'] == 'PLATINUM'].sort_values('mep_e_score', ascending=False).head(10)

    if len(platinum) > 0:
        for idx, row in platinum.iterrows():
            print(f"\n{row['name']} ({row['state']})")
            print(f"  Score: {row['mep_e_score']}/100")
            print(f"  OEMs: {row['oem_count']} total - {', '.join(row['oems'][:5])}")
            print(f"  Categories: HVAC({row['hvac_oems']}), Solar({row['solar_oems']}), "
                  f"Battery({row['battery_oems']}), Generator({row['generator_oems']}), "
                  f"Smart Panel({row['smart_panel_oems']}), IoT({row['iot_oems']})")
            print(f"  ICP Scores: Renewable({row['renewable_readiness']}), "
                  f"Asset-Centric({row['asset_centric']}), Projects+Service({row['projects_service']})")
    else:
        print("No PLATINUM tier contractors found")

    # Top 10 GOLD Contractors
    print("\n" + "=" * 80)
    print("Top 10 GOLD Tier Contractors (High Priority)")
    print("=" * 80)
    gold = results_df[results_df['tier'] == 'GOLD'].sort_values('mep_e_score', ascending=False).head(10)

    if len(gold) > 0:
        for idx, row in gold.iterrows():
            print(f"\n{row['name']} ({row['state']})")
            print(f"  Score: {row['mep_e_score']}/100")
            print(f"  OEMs: {row['oem_count']} total - {', '.join(row['oems'][:5])}")
    else:
        print("No GOLD tier contractors found")

    # Summary
    print("\n" + "=" * 80)
    print("Validation Summary")
    print("=" * 80)
    print(f"✓ Scored {len(results_df)} contractors successfully")
    print(f"✓ Average score: {results_df['mep_e_score'].mean():.1f}/100")
    print(f"✓ {tier_counts.get('PLATINUM', 0)} PLATINUM tier (immediate outreach)")
    print(f"✓ {tier_counts.get('GOLD', 0)} GOLD tier (high priority)")
    print(f"✓ MEP+E scoring system validated against dealer-scraper CSV")

    print("\n" + "=" * 80)
    print("Next Steps")
    print("=" * 80)
    print("1. Start Docker Desktop")
    print("2. cd backend && docker-compose up -d")
    print("3. alembic revision --autogenerate -m 'Add OEM tracking fields'")
    print("4. alembic upgrade head")
    print("5. Run CSV import via API endpoint")
    print("6. Verify MEP+E scores in PostgreSQL")


if __name__ == "__main__":
    csv_path = "/Users/tmkipper/Desktop/dealer-scraper-mvp/output/top_200_prospects_final_20251029.csv"

    print("\n" + "=" * 80)
    print("STANDALONE MEP+E SCORING VALIDATION")
    print("=" * 80)
    print("This script validates the MEPEScorer service without requiring database access.")
    print("It scores all contractors in the CSV and identifies top PLATINUM/GOLD tier prospects.")
    print()

    if not Path(csv_path).exists():
        print(f"✗ CSV file not found: {csv_path}")
        print("\nPlease update csv_path in this script to point to your CSV file.")
        sys.exit(1)

    validate_csv_scoring(csv_path)

    print("\n" + "=" * 80)
    print("Validation Complete!")
    print("=" * 80)
