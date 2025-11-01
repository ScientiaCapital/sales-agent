# California Multi-State ICP Analysis & Cross-Reference Design

**Date**: October 31, 2025
**Version**: 1.0
**Status**: Design Complete - Ready for Implementation

---

## Executive Summary

This design extends the Texas contractor pipeline to California, adding multi-state and multi-OEM detection to identify the highest-value ICP contractors: those operating across multiple states (CA, TX, FL) with multiple OEM certifications (Generac, Tesla, Cummins).

### Key Objectives

1. **CA License Cross-Reference**: Match 233 CA OEM contractors against 242,892 CA state licenses
2. **ICP License Filtering**: Focus on electrical (C10), HVAC (C20), plumbing (C36), and multi-license contractors
3. **Multi-State Detection**: Identify contractors operating in CA + TX (phone number matching)
4. **Multi-OEM Enhancement**: Leverage existing OEM overlap data from MASTER_CONTRACTOR_DATABASE
5. **ICP Tier Scoring**: Create PLATINUM/GOLD/SILVER/BRONZE tiers based on multi-state + multi-OEM dimensions

### Expected Outcomes

| Metric | Value |
|--------|-------|
| CA Cross-Referenced Contractors | ~165 (70-75% match rate) |
| ICP-Filtered CA Contractors | ~120-150 (C10, C20, C36, etc.) |
| Multi-State Contractors (CA+TX) | ~10-20 (5-10% overlap) |
| **PLATINUM Tier** (Multi-State + Multi-OEM) | **5-10 contractors** 🔥🔥🔥 |
| **GOLD Tier** (Multi-OEM only) | **20-30 contractors** 🔥🔥 |
| **SILVER Tier** (Multi-State OR Multi-OEM) | **50-80 contractors** 🔥 |
| **BRONZE Tier** (Single-State, Single-OEM) | **300-350 contractors** |

---

## Part 1: CA License ICP Analysis

### CA License Universe (242,892 total licenses)

**ICP-Aligned License Classifications**:

| License Code | Description | Count | ICP Alignment |
|--------------|-------------|-------|---------------|
| **C10** | Electrical Contractor | 32,207 | ✅ HIGH - Generator installations, backup power |
| **C20** | HVAC Contractor | 12,245 | ✅ HIGH - Energy systems, climate control |
| **C36** | Plumbing Contractor | 17,888 | ✅ MEDIUM - MEP capability |
| **C27** | Landscaping Contractor | 12,569 | ✅ MEDIUM - Site work, outdoor systems |
| **C15** | Flooring Contractor | 9,793 | ✅ LOW - Interior finishing |
| **C-7** | Low Voltage Contractor | 4,961 | ✅ HIGH - Security, communications, smart systems |
| **B** (multi-license) | General Building + Specialty | ~10,000 | ✅ HIGH - Multi-trade = MEP+R capability |
| **A** (multi-license) | General Engineering + Specialty | ~7,000 | ✅ HIGH - Commercial/industrial capability |
| **TOTAL** | **ICP-Aligned Contractors** | **~106,000** | |

### Multi-License Commercial Proxy Strategy

**Commercial General Contractors** (identified by multi-license combinations):
- **B|C10** (General Building + Electrical): 6,195 contractors
- **A|B** (General Engineering + Building): 6,224 contractors
- **B|C36** (General Building + Plumbing): 1,880 contractors
- **B|C27** (General Building + Landscaping): 1,257 contractors
- **B|C20** (General Building + HVAC): 1,150 contractors
- **A|C10** (General Engineering + Electrical): 488 contractors
- **A|C20** (General Engineering + HVAC): 22 contractors

**Total Multi-License**: ~17,216 contractors

**Rationale**: Multi-license = MEP+R self-performing capability (25% of ICP weight) + commercial capability proxy.

---

## Part 2: Multi-State & Multi-OEM Discovery

### The ICP Value Pyramid

```
┌─────────────────────────────────────────────────┐
│  PLATINUM: Multi-State + Multi-OEM (Score 80+)  │
│  - Operate in CA + TX (or more)                 │
│  - Certified by 2+ OEMs (Generac + Tesla)       │
│  - Multi-license (C10 + C20, B|C10, etc.)       │
│  → Estimated: 5-10 contractors                  │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  GOLD: Multi-OEM (Single State) (Score 60-79)   │
│  - Operate in CA only                           │
│  - Certified by 2+ OEMs (Generac + Tesla + Cummins)│
│  - Multi-license preferred                      │
│  → Estimated: 20-30 contractors                 │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  SILVER: Multi-State OR Multi-OEM (Score 40-59) │
│  - Multi-state (CA + TX) with single OEM        │
│  - OR single-state with multi-OEM               │
│  → Estimated: 50-80 contractors                 │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  BRONZE: Single-State + Single-OEM (Score <40)  │
│  - CA only, Generac only                        │
│  → Estimated: 300-350 contractors               │
└─────────────────────────────────────────────────┘
```

### ICP Scoring Formula (Enhanced)

```python
ICP_Score = (
    resimercial_score * 0.35 +      # Residential + Commercial capability
    multi_oem_score * 0.25 +        # Multi-OEM certifications (NEW WEIGHT)
    mepr_score * 0.25 +             # MEP+R self-performing
    om_score * 0.15 +               # Operations & Maintenance
    multi_state_bonus * 0.10        # NEW: Multi-state presence bonus
)

# Multi-State Bonus Calculation
multi_state_bonus = state_count * 20  # 20 points per additional state
# Examples:
#   - CA only: 0 bonus points
#   - CA + TX: 20 bonus points
#   - CA + TX + FL: 40 bonus points

# Multi-OEM Score Calculation
multi_oem_score = min(oem_count * 25, 100)  # 25 points per OEM, max 100
# Examples:
#   - Generac only: 25 points
#   - Generac + Tesla: 50 points
#   - Generac + Tesla + Cummins: 75 points
#   - 4+ OEMs: 100 points
```

---

## Part 3: Data Sources

### Existing Data Assets

#### 1. CA State Licenses (CSLB)
- **File**: `data/licenses/ca_licenses_raw_20251031.csv`
- **Records**: 242,892 contractor licenses
- **Source**: California Contractors State License Board
- **Key Columns**:
  - `LicenseNo`: Unique license number
  - `BusinessName`: Contractor business name
  - `BusinessPhone`: Primary phone (for matching)
  - `City`, `State`, `County`, `ZIPCode`: Location data
  - `Classifications(s)`: License types (C10, C20, B|C10, etc.)
  - `PrimaryStatus`: CLEAR/SUSPENDED/etc.
  - `ExpirationDate`: License expiration

#### 2. OEM Contractor Master Database
- **File**: `gtm-engineer-journey/projects/dealer-scraper-mvp/output/gtm/executive_package_20251025/MASTER_CONTRACTOR_DATABASE_with_overlap.csv`
- **CA Records**: 233 contractors
- **TX Records**: 333 contractors
- **Total**: ~1,700 contractors (all states)
- **Key Columns**:
  - `Contractor Name`: Business name
  - `Phone`: Primary phone (for matching)
  - `State`, `City`: Location
  - `OEM Count`: Number of OEM certifications (1, 2, 3, 4+)
  - `OEM Sources`: "Generac,Tesla,Cummins" (comma-separated)
  - `is_multi_oem`: TRUE/FALSE flag
  - `oem_count_verified`: Verified OEM count
  - `ICP Fit Score`: Existing ICP score (0-100)
  - `ICP Tier`: PLATINUM/GOLD/SILVER/BRONZE

#### 3. TX Enriched Contractors (Existing)
- **File**: `data/licenses/tx_final_hottest_leads_20251031.csv`
- **Records**: 242 enriched TX contractors
- **Key Columns**:
  - `name`, `phone`, `website`, `city`, `state`, `zip`
  - `oem_source`: Which OEM (Generac, Tesla, etc.)
  - `license_number`, `license_type`, `license_status`
  - `icp_score`, `tier`: ICP scoring
  - `resimercial_score`, `om_score`, `mepr_score`, `multi_oem_score`

---

## Part 4: Data Processing Pipeline

### Phase 1: CA License Cross-Reference (Replicate TX Pipeline)

**Input**:
- CA OEM contractors: 233 (from MASTER_CONTRACTOR_DATABASE)
- CA CSLB licenses: 242,892 (ca_licenses_raw_20251031.csv)

**Process**:
```python
1. Normalize Phone Numbers
   - Remove formatting: (555) 123-4567 → 5551234567
   - Keep 10 digits only
   - Handle edge cases: 1-555-123-4567 → 5551234567

2. Match CA OEM Phones Against CA License Phones
   - Left join: OEM contractors → CSLB licenses (on phone)
   - Match method: Exact 10-digit phone match
   - Handle multiple licenses per phone (same business, multiple classifications)

3. Filter Matches by ICP License Types
   - C10 (Electrical) ✅
   - C20 (HVAC) ✅
   - C36 (Plumbing) ✅
   - C27 (Landscaping) ✅
   - C15 (Flooring) ✅
   - C-7 (Low Voltage) ✅
   - Multi-license (B|C10, A|B, B|C36, etc.) ✅
   - Exclude: Non-ICP licenses (C33 Painting, C54 Tile, etc.)

4. Calculate Multi-License Score
   - Single license: 25 points
   - Multi-license (2): 50 points
   - Multi-license (3+): 75 points
```

**Output**:
- `ca_cross_referenced_20251031.csv`: ~165 contractors (70-75% match rate)
- `ca_icp_scored_20251031.csv`: ~165 with full ICP scores

**Expected Match Rate**: 70-75% (similar to TX 73% match rate)

---

### Phase 2: Multi-State Detection (Cross-State Phone Matching)

**Input**:
- CA enriched contractors: ~165 (from Phase 1)
- TX enriched contractors: 242 (existing)

**Process**:
```python
1. Normalize Phones Across Both States
   - CA phones: 10-digit format
   - TX phones: 10-digit format
   - Create unified phone index

2. Match Phones CA ↔ TX
   - Inner join on phone number
   - Identify contractors with same phone in both states

3. Calculate State Presence Flags
   - has_ca: TRUE if in CA cross-referenced
   - has_tx: TRUE if in TX cross-referenced
   - state_count: COUNT(DISTINCT state)
   - state_list: "CA,TX" (comma-separated)

4. Multi-State Bonus
   - state_count = 1: 0 bonus points
   - state_count = 2: +20 ICP points
   - state_count = 3+: +40 ICP points
```

**Output**:
- `multi_state_contractors.csv`: ~10-20 contractors
- Columns added: `state_count`, `state_list`, `has_ca`, `has_tx`, `multi_state_bonus`

**Expected Overlap**: 5-10% (10-20 contractors operating in both CA and TX)

---

### Phase 3: Multi-OEM Enhancement (Join with Master Database)

**Input**:
- CA cross-referenced: ~165 contractors
- TX cross-referenced: 242 contractors
- MASTER_CONTRACTOR_DATABASE: 1,700 contractors (all states)

**Process**:
```python
1. Join by Phone Number
   - Left join: CA/TX contractors → MASTER_CONTRACTOR_DATABASE (on phone)
   - Preserve all cross-referenced contractors
   - Add OEM data where available

2. Enrich with OEM Dimensions
   - oem_count_verified: 1, 2, 3, 4+ (from Master DB)
   - oem_sources: "Generac,Tesla,Cummins" (from Master DB)
   - is_multi_oem: TRUE/FALSE (from Master DB)
   - oem_diversity_score: 0-100 (from Master DB)

3. Calculate Multi-OEM Score
   - 1 OEM: 25 points
   - 2 OEMs: 50 points
   - 3 OEMs: 75 points
   - 4+ OEMs: 100 points

4. Recalculate Final ICP Score
   ICP_Score = (
       resimercial_score * 0.35 +
       multi_oem_score * 0.25 +     # Now using actual OEM count
       mepr_score * 0.25 +
       om_score * 0.15 +
       multi_state_bonus * 0.10     # New dimension
   )

5. Assign Final Tier
   - PLATINUM: ICP_Score >= 80
   - GOLD: ICP_Score >= 60
   - SILVER: ICP_Score >= 40
   - BRONZE: ICP_Score < 40
```

**Output**:
- `ca_tx_multi_state_multi_oem_final.csv`: ~400 contractors (CA + TX combined)
- Columns: All CA/TX data + OEM data + multi-state flags + final ICP score

---

### Phase 4: PLATINUM Tier Extraction (The Ultimate Query)

**SQL-Style Query** (conceptual):
```sql
SELECT
    contractor_name,
    phone,
    state_list,
    state_count,
    oem_sources,
    oem_count,
    license_classifications,
    icp_score,
    tier
FROM ca_tx_multi_state_multi_oem_final
WHERE
    state_count >= 2              -- Multi-state (CA + TX minimum)
    AND oem_count >= 2            -- Multi-OEM (Generac + Tesla minimum)
    AND (
        license_classifications LIKE '%|%'  -- Multi-license
        OR license_classifications LIKE '%C10%'  -- Or electrical
    )
ORDER BY
    (state_count * 10) +          -- Prioritize multi-state
    (oem_count * 15) +            -- Prioritize multi-OEM
    (license_count * 5) DESC      -- Prioritize multi-license
LIMIT 50;                         -- Top 50 PLATINUM contractors
```

**Output**:
- `platinum_contractors_20251031.csv`: 5-10 contractors
- **These are the hottest leads** - call first!

---

## Part 5: Expected Tier Distribution

### CA-Only Contractors (After Cross-Reference)

| Tier | ICP Score | Estimated Count | % | Characteristics |
|------|-----------|----------------|---|-----------------|
| **PLATINUM** | 80-100 | 0-2 | 0-1% | Multi-OEM + Multi-license CA contractors |
| **GOLD** | 60-79 | 10-15 | 6-9% | Multi-OEM OR multi-license |
| **SILVER** | 40-59 | 30-50 | 18-30% | ICP-aligned single license |
| **BRONZE** | <40 | 100-115 | 60-70% | Single OEM, single license |
| **TOTAL** | | **~165** | 100% | |

### Multi-State Contractors (CA + TX Combined)

| Tier | ICP Score | Estimated Count | % | Characteristics |
|------|-----------|----------------|---|-----------------|
| **PLATINUM** | 80-100 | **5-10** | 1-2% | Multi-state + Multi-OEM + Multi-license 🔥🔥🔥 |
| **GOLD** | 60-79 | **20-30** | 5-7% | Multi-OEM only (single state) 🔥🔥 |
| **SILVER** | 40-59 | **50-80** | 12-20% | Multi-state OR multi-OEM 🔥 |
| **BRONZE** | <40 | **300-350** | 75-85% | Single-state, single-OEM |
| **TOTAL** | | **~400** | 100% | |

---

## Part 6: Implementation Steps

### Step 1: CA Cross-Reference Script (Python)

**File**: `backend/scripts/ca_cross_reference.py`

```python
"""
CA License Cross-Reference Pipeline
Replicates TX pipeline for California contractors
"""

import pandas as pd
import re

# Load data
ca_oem = pd.read_csv('gtm-engineer-journey/.../MASTER_CONTRACTOR_DATABASE_with_overlap.csv')
ca_oem = ca_oem[ca_oem['State'] == 'CA']  # Filter for CA only

ca_licenses = pd.read_csv('data/licenses/ca_licenses_raw_20251031.csv')

# Normalize phones
def normalize_phone(phone):
    if pd.isna(phone):
        return None
    digits = re.sub(r'\D', '', str(phone))
    if len(digits) == 11 and digits[0] == '1':
        return digits[1:]  # Remove leading 1
    return digits if len(digits) == 10 else None

ca_oem['phone_normalized'] = ca_oem['Phone'].apply(normalize_phone)
ca_licenses['phone_normalized'] = ca_licenses['BusinessPhone'].apply(normalize_phone)

# Cross-reference
matched = ca_oem.merge(
    ca_licenses,
    on='phone_normalized',
    how='left'
)

# Filter for ICP licenses
icp_licenses = ['C10', 'C20', 'C36', 'C27', 'C15', 'C-7']
multi_license_patterns = ['B|', 'A|', '|B', '|A']

def is_icp_license(classification):
    if pd.isna(classification):
        return False
    # Check for ICP single licenses
    for lic in icp_licenses:
        if lic in classification:
            return True
    # Check for multi-license patterns
    for pattern in multi_license_patterns:
        if pattern in classification:
            return True
    return False

matched['is_icp'] = matched['Classifications(s)'].apply(is_icp_license)
matched_icp = matched[matched['is_icp'] == True]

# Save
matched_icp.to_csv('data/licenses/ca_cross_referenced_20251031.csv', index=False)
print(f"✅ Matched {len(matched_icp)} CA contractors with ICP licenses")
```

### Step 2: Multi-State Detection Script

**File**: `backend/scripts/multi_state_detection.py`

```python
"""
Multi-State Contractor Detection
Identifies contractors operating in CA + TX
"""

import pandas as pd

# Load enriched contractors
ca_enriched = pd.read_csv('data/licenses/ca_cross_referenced_20251031.csv')
tx_enriched = pd.read_csv('data/licenses/tx_final_hottest_leads_20251031.csv')

# Add state flags
ca_enriched['has_ca'] = True
tx_enriched['has_tx'] = True

# Merge on phone
multi_state = pd.merge(
    ca_enriched,
    tx_enriched,
    on='phone_normalized',
    how='outer',
    suffixes=('_ca', '_tx')
)

# Calculate state presence
multi_state['has_ca'] = multi_state['has_ca'].fillna(False)
multi_state['has_tx'] = multi_state['has_tx'].fillna(False)
multi_state['state_count'] = multi_state['has_ca'].astype(int) + multi_state['has_tx'].astype(int)

# Create state list
def get_state_list(row):
    states = []
    if row['has_ca']:
        states.append('CA')
    if row['has_tx']:
        states.append('TX')
    return ','.join(states)

multi_state['state_list'] = multi_state.apply(get_state_list, axis=1)

# Multi-state bonus
multi_state['multi_state_bonus'] = (multi_state['state_count'] - 1) * 20

# Save
multi_state.to_csv('data/licenses/multi_state_contractors.csv', index=False)

# Print stats
print(f"✅ Total contractors: {len(multi_state)}")
print(f"✅ Multi-state contractors (CA+TX): {(multi_state['state_count'] >= 2).sum()}")
```

### Step 3: ICP Scoring & Tier Assignment

**File**: `backend/scripts/icp_scoring_multi_state.py`

```python
"""
Enhanced ICP Scoring with Multi-State and Multi-OEM Dimensions
"""

import pandas as pd

# Load multi-state contractors
contractors = pd.read_csv('data/licenses/multi_state_contractors.csv')

# Load OEM master database
oem_master = pd.read_csv('gtm-engineer-journey/.../MASTER_CONTRACTOR_DATABASE_with_overlap.csv')

# Join with OEM data
contractors = contractors.merge(
    oem_master[['Phone', 'OEM Count', 'OEM Sources', 'is_multi_oem']],
    left_on='phone_normalized',
    right_on='Phone',
    how='left'
)

# Calculate multi-OEM score
contractors['multi_oem_score'] = contractors['OEM Count'].fillna(1) * 25
contractors['multi_oem_score'] = contractors['multi_oem_score'].clip(upper=100)

# Calculate final ICP score
contractors['icp_score'] = (
    contractors['resimercial_score'] * 0.35 +
    contractors['multi_oem_score'] * 0.25 +
    contractors['mepr_score'] * 0.25 +
    contractors['om_score'] * 0.15 +
    contractors['multi_state_bonus'] * 0.10
)

# Assign tier
def assign_tier(score):
    if score >= 80:
        return 'PLATINUM'
    elif score >= 60:
        return 'GOLD'
    elif score >= 40:
        return 'SILVER'
    else:
        return 'BRONZE'

contractors['tier'] = contractors['icp_score'].apply(assign_tier)

# Save final
contractors.to_csv('data/licenses/ca_tx_multi_state_multi_oem_final.csv', index=False)

# Print tier distribution
print("\n=== ICP Tier Distribution ===")
print(contractors['tier'].value_counts().sort_index())

# Extract PLATINUM tier
platinum = contractors[contractors['tier'] == 'PLATINUM']
platinum.to_csv('data/licenses/platinum_contractors_20251031.csv', index=False)
print(f"\n🔥 PLATINUM Tier: {len(platinum)} contractors")
```

### Step 4: Execution Sequence

```bash
# Activate environment
cd ~/Desktop/tk_projects/sales-agent
source venv/bin/activate

# Run CA cross-reference
python backend/scripts/ca_cross_reference.py

# Run multi-state detection
python backend/scripts/multi_state_detection.py

# Run ICP scoring
python backend/scripts/icp_scoring_multi_state.py

# Check outputs
ls -lh data/licenses/*.csv

# View PLATINUM contractors
cat data/licenses/platinum_contractors_20251031.csv
```

**Estimated Runtime**: ~5-10 minutes total

---

## Part 7: Success Criteria

### Quantitative Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| CA Match Rate | 70-75% | (Matched / 233 CA OEM) * 100 |
| ICP License Filter Rate | 90%+ | (ICP licenses / Total matched) * 100 |
| Multi-State Discovery | 10-20 contractors | COUNT(state_count >= 2) |
| PLATINUM Tier | 5-10 contractors | COUNT(tier = 'PLATINUM') |
| GOLD Tier | 20-30 contractors | COUNT(tier = 'GOLD') |

### Qualitative Validation

1. **Manual Review**: Review top 10 PLATINUM contractors - verify multi-state + multi-OEM claims
2. **Phone Number Validation**: Check 10 random matches - confirm phones match correctly
3. **License Type Accuracy**: Verify ICP license filtering (no C33 Painting, C54 Tile, etc.)
4. **Business Name Consistency**: Check business names match across CA/TX records

---

## Part 8: Next Steps After CA Analysis

Once CA cross-reference complete:

1. **Florida Cross-Reference** (if FL license data available)
   - Expand to 3-state detection (CA + TX + FL)
   - Increase PLATINUM tier to 15-25 contractors

2. **LinkedIn ATL Discovery** (as designed in previous doc)
   - Start with PLATINUM tier (5-10 contractors)
   - Find ATL contacts (CEO, CTO, VP) at each company
   - Enrich with Hunter.io emails
   - Export to Close CRM

3. **Outreach Prioritization**:
   - **Week 1**: PLATINUM tier (InMail + connection requests)
   - **Week 2**: GOLD tier (InMail for no-email, connection requests for others)
   - **Week 3+**: SILVER/BRONZE tier (connection requests only)

---

## Appendix A: CA License Classification Reference

| Code | Description | ICP Alignment | Notes |
|------|-------------|---------------|-------|
| **A** | General Engineering Contractor | HIGH | Heavy construction, utilities, infrastructure |
| **B** | General Building Contractor | MEDIUM | Residential + commercial construction |
| **C10** | Electrical Contractor | HIGH | Power systems, generators, backup power ✅ |
| **C15** | Flooring Contractor | LOW | Interior finishing |
| **C20** | Warm-Air Heating, Ventilation, Air-Conditioning | HIGH | HVAC systems ✅ |
| **C27** | Landscaping Contractor | MEDIUM | Site work, irrigation |
| **C33** | Painting and Decorating | NONE | Cosmetic only ❌ |
| **C36** | Plumbing Contractor | MEDIUM | MEP capability ✅ |
| **C-7** | Low Voltage Systems | HIGH | Security, communications ✅ |
| **C54** | Ceramic and Mosaic Tile | NONE | Cosmetic only ❌ |

**Multi-License Patterns**:
- `B| C10` = General Building + Electrical
- `A| B` = General Engineering + Building
- `C10| C20` = Electrical + HVAC
- `C20| C36` = HVAC + Plumbing

---

## Appendix B: File Outputs

| File | Records | Description |
|------|---------|-------------|
| `ca_licenses_raw_20251031.csv` | 242,892 | Raw CA CSLB licenses (input) |
| `ca_cross_referenced_20251031.csv` | ~165 | CA OEM contractors matched with licenses |
| `ca_icp_scored_20251031.csv` | ~165 | CA contractors with initial ICP scores |
| `multi_state_contractors.csv` | ~400 | CA + TX combined with state flags |
| `ca_tx_multi_state_multi_oem_final.csv` | ~400 | Final enriched with OEM data |
| `platinum_contractors_20251031.csv` | 5-10 | PLATINUM tier only (hottest leads) |
| `gold_contractors_20251031.csv` | 20-30 | GOLD tier only |

---

**Questions or Issues?**

Contact: Sales-agent development team
Reference: `backend/docs/plans/2025-10-31-ca-multi-state-icp-analysis.md`
