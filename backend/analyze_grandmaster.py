"""
Analyze grandmaster list and score leads to find the best 500.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Load deduped grandmaster
df = pd.read_csv("data/csv/inbox/grandmaster_deduped.csv")

print("=" * 60)
print("GRANDMASTER LIST ANALYSIS")
print("=" * 60)
print(f"\nTotal leads: {len(df)}")

# Show available columns for scoring
print("\n=== AVAILABLE SCORING SIGNALS ===")
score_columns = [
    'OEM_Count', 'multi_oem_score', 'capability_count', 'mep_score',
    'coperniq_score', 'rating', 'review_count', 'employee_count',
    'estimated_revenue', 'tier'
]
for col in score_columns:
    if col in df.columns:
        non_null = df[col].notna().sum()
        print(f"  {col}: {non_null} values")

# Create composite score for lead prioritization
print("\n=== SCORING LEADS ===")

def score_lead(row):
    score = 0

    # OEM certifications (high value - they're serious about business)
    if pd.notna(row.get('OEM_Count')):
        score += min(row['OEM_Count'] * 10, 50)  # Max 50 points

    # Multi-OEM score (direct quality indicator)
    if pd.notna(row.get('multi_oem_score')):
        score += row['multi_oem_score'] * 5  # Weight it

    # Capability count (more services = bigger company)
    if pd.notna(row.get('capability_count')):
        score += row['capability_count'] * 5

    # MEP score (contractor quality)
    if pd.notna(row.get('mep_score')):
        score += row['mep_score'] * 3

    # Coperniq score (their internal scoring)
    if pd.notna(row.get('coperniq_score')):
        score += row['coperniq_score'] * 2

    # Reviews & ratings (social proof)
    if pd.notna(row.get('rating')) and row['rating'] > 0:
        score += row['rating'] * 5  # Max 25 points
    if pd.notna(row.get('review_count')):
        score += min(row['review_count'] / 10, 20)  # Max 20 points

    # Employee count (company size)
    if pd.notna(row.get('employee_count')):
        if row['employee_count'] >= 100:
            score += 30
        elif row['employee_count'] >= 50:
            score += 20
        elif row['employee_count'] >= 20:
            score += 10
        elif row['employee_count'] >= 10:
            score += 5

    # Estimated revenue
    if pd.notna(row.get('estimated_revenue')):
        try:
            rev = float(str(row['estimated_revenue']).replace('$', '').replace(',', '').replace('M', '000000').replace('K', '000'))
            if rev >= 10000000:  # $10M+
                score += 40
            elif rev >= 5000000:  # $5M+
                score += 30
            elif rev >= 1000000:  # $1M+
                score += 20
            elif rev >= 500000:  # $500K+
                score += 10
        except:
            pass

    # Has key capabilities (bonus points)
    if row.get('has_generator') == True or row.get('has_generator') == 'True':
        score += 15  # Generator = high value
    if row.get('has_solar') == True or row.get('has_solar') == 'True':
        score += 10
    if row.get('has_battery') == True or row.get('has_battery') == 'True':
        score += 10
    if row.get('has_hvac') == True or row.get('has_hvac') == 'True':
        score += 5

    # Has website (basic qualification)
    if pd.notna(row.get('website')) and str(row['website']).startswith('http'):
        score += 10

    # Has email already (saves API costs)
    if pd.notna(row.get('email')) and '@' in str(row.get('email', '')):
        score += 5

    return score

# Calculate scores
df['lead_score'] = df.apply(score_lead, axis=1)

# Sort by score
df_sorted = df.sort_values('lead_score', ascending=False)

# Get top 500
top_500 = df_sorted.head(500)

print(f"\nScore distribution:")
print(f"  Max score: {df['lead_score'].max()}")
print(f"  Min score: {df['lead_score'].min()}")
print(f"  Mean score: {df['lead_score'].mean():.1f}")
print(f"  Median score: {df['lead_score'].median():.1f}")

print(f"\nTop 500 leads:")
print(f"  Min score in top 500: {top_500['lead_score'].min()}")
print(f"  Mean score in top 500: {top_500['lead_score'].mean():.1f}")

# Show top 20
print("\n=== TOP 20 HIGHEST VALUE LEADS ===")
for i, row in df_sorted.head(20).iterrows():
    name = row['name'][:40]
    score = row['lead_score']
    oems = row.get('OEM_Count', 0)
    emp = row.get('employee_count', 'N/A')
    has_gen = '🔌' if row.get('has_generator') else ''
    has_sol = '☀️' if row.get('has_solar') else ''
    rating = row.get('rating', 0)

    print(f"  {score:3.0f} | {name:<40} | OEMs:{oems} | Emp:{emp} | {has_gen}{has_sol} | ⭐{rating}")

# Capability breakdown
print("\n=== CAPABILITY BREAKDOWN (Top 500) ===")
caps = {
    'has_generator': 'Generators',
    'has_solar': 'Solar',
    'has_battery': 'Battery',
    'has_hvac': 'HVAC',
    'has_electrical': 'Electrical',
    'has_plumbing': 'Plumbing'
}
for col, name in caps.items():
    if col in top_500.columns:
        count = top_500[col].apply(lambda x: x == True or x == 'True').sum()
        print(f"  {name}: {count} ({count/5:.1f}%)")

# Save top 500
output_path = "data/csv/inbox/grandmaster_top_500.csv"
top_500.to_csv(output_path, index=False)
print(f"\n✅ Saved top 500: {output_path}")

# Also show data quality
print("\n=== DATA QUALITY (Top 500) ===")
has_website = top_500['website'].notna().sum()
has_email = top_500['email'].apply(lambda x: pd.notna(x) and '@' in str(x)).sum()
has_phone = top_500['phone'].notna().sum()

print(f"  With website: {has_website} ({has_website/5:.1f}%)")
print(f"  With email: {has_email} ({has_email/5:.1f}%)")
print(f"  With phone: {has_phone} ({has_phone/5:.1f}%)")

print("\n" + "=" * 60)
print("READY TO PROCESS TOP 500!")
print("=" * 60)
