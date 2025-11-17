# Smart Views Setup - Using Raw Status

## Overview
ALL leads are created with status = "Raw". Smart views filter **within** Raw leads based on:
- Custom fields (is_atl, qualification_score)
- Description text (priority labels)
- Contact job titles (ATL keywords)

---

## The 4 Smart Views

### 1. 🔥 Hot ATL Leads (Priority)
**Purpose**: High-scoring decision-makers for immediate calling

**Filters**:
```
Status = "Raw"
AND Description contains "🔥 Hot ATL"
AND Created by = Tim Kipper
AND Created date >= Last 7 days
```

**Alternative (using custom fields)**:
```
Status = "Raw"
AND custom.is_atl = true
AND custom.qualification_score >= 70
AND Created by = Tim Kipper
AND Created date >= Last 7 days
```

---

### 2. ⭐ Validated ATL Leads
**Purpose**: Decision-makers with lower scores, still valuable

**Filters**:
```
Status = "Raw"
AND Description contains "⭐ Validated ATL"
AND Created by = Tim Kipper
```

**Alternative (using custom fields)**:
```
Status = "Raw"
AND custom.is_atl = true
AND custom.qualification_score < 70
AND Created by = Tim Kipper
```

---

### 3. 📋 BTL Leads (Lower Priority)
**Purpose**: Individual contributors, not decision-makers

**Filters**:
```
Status = "Raw"
AND Description contains "📋 BTL"
AND Created by = Tim Kipper
```

**Alternative (using custom fields)**:
```
Status = "Raw"
AND custom.is_atl = false
AND Created by = Tim Kipper
```

---

### 4. 🔥 High-Intent ATL Contacts (3+ Opens)
**Purpose**: Hot prospects showing active email engagement

**Filters**:
```
Status = "Raw"
AND Custom field "High Intent Flag" = "Yes"
AND (Description contains "🔥 Hot ATL" OR Description contains "⭐ Validated ATL")
AND Created by = Tim Kipper
```

---

## Custom Fields Used

### 1. qualification_score (Number)
- **Field Name**: `custom.qualification_score`
- **Type**: Number (0-100)
- **Purpose**: AI-generated lead quality score
- **Usage**: Filter Hot ATL (>=70) vs Validated ATL (<70)

### 2. is_atl (Boolean)
- **Field Name**: `custom.is_atl`
- **Type**: Boolean (true/false)
- **Purpose**: Is contact a decision-maker?
- **Usage**: Filter ATL vs BTL leads

### 3. priority_label (Text)
- **Field Name**: `custom.priority_label`
- **Type**: Text
- **Values**: "🔥 Hot ATL", "⭐ Validated ATL", "📋 BTL"
- **Purpose**: Quick visual indicator
- **Usage**: Can filter by this instead of score/is_atl

---

## Lead Status Lifecycle

```
CSV Import → Status: Raw (with custom fields)
             ↓
[Sales team qualifies manually]
             ↓
Status: MQL → SAL → SQL → Opportunity → Customer
```

**Key Point**: Our automation creates leads as "Raw". Your team moves them through the lifecycle as they qualify them.

---

## How to Set Up in Close CRM

### Method 1: Filter by Description (Simplest)
1. Go to Close CRM → Smart Views
2. Edit each smart view
3. Add filters:
   - Status = "Raw"
   - Description contains "[emoji + text]"
   - Created by = [Your user ID]

### Method 2: Filter by Custom Fields (Most Robust)
1. First, create custom fields in Close CRM:
   - Go to Settings → Custom Fields
   - Create: `is_atl` (boolean)
   - Create: `qualification_score` (number)
   - Create: `priority_label` (text)

2. Update smart views to filter on these fields

---

## Example: Hot ATL Smart View Setup

**In Close CRM UI**:
1. Click "Smart Views" → "Edit" on "🔥 Hot ATL Leads"
2. Set filters:
   ```
   Lead Status is "Raw"
   AND Lead Description contains "🔥 Hot ATL"
   AND Lead Created By is "Tim Kipper"
   AND Lead Date Created is after "7 days ago"
   ```

**Result**: Only shows Raw leads that are hot ATL contacts from last 7 days

---

## Benefits of This Approach

### ✅ Pros:
1. **Respects existing workflow** - Uses Coperniq's standard statuses
2. **No status pollution** - Doesn't create new statuses
3. **Standard lifecycle** - Raw → MQL → SAL → SQL → etc.
4. **Flexible filtering** - Can filter on scores, ATL flag, or text
5. **Easy to understand** - "Raw" means "needs qualification"

### ❌ Old Approach (What We Fixed):
- Created custom statuses ("Hot ATL", "Validated ATL", "BTL")
- Broke Coperniq's existing workflow
- Confused status meaning
- Hard to integrate with existing processes

---

## Testing the Setup

### Step 1: Create a Test Lead
```bash
# This will create a lead with status="Raw"
/Users/tmkipper/Desktop/tk_projects/sales-agent/venv/bin/python create_test_lead.py
```

### Step 2: Check it appears in "All Leads" with status="Raw"
- Go to Close CRM → All Leads
- Search for "GENERATOR SUPERCENTER"
- Verify Status = "Raw"
- Check Description has "⭐ Validated ATL" (score was 45 < 70)

### Step 3: Check smart view filters
- Click "⭐ Validated ATL Leads" smart view
- Test lead should appear there
- If not, check the filters match what's in the description

---

## What the Code Does Now

```python
# OLD CODE (WRONG):
if is_atl and score >= 70:
    status = "Hot ATL"  # ❌ Custom status
elif is_atl and score < 70:
    status = "Validated ATL"  # ❌ Custom status
else:
    status = "BTL"  # ❌ Custom status

# NEW CODE (CORRECT):
status = "Raw"  # ✅ Always Raw!

# Store priority in description and custom fields:
lead_data = {
    "status_id": "stat_4qxeqdfEDGNFmh93pFmXz4l8bw78DuQtTlATratY2Qb",  # Raw
    "description": f"{priority_label}\n\nQualification Score: {score}/100",
    "custom": {
        "is_atl": is_atl,
        "qualification_score": score,
        "priority_label": priority_label
    }
}
```

---

## Summary

- ✅ **ALL leads** → Status = "Raw"
- ✅ **Smart views** → Filter Raw leads by custom fields/description
- ✅ **Respects workflow** → Raw → MQL → SAL → SQL → Customer
- ✅ **Easy filtering** → Description contains priority labels
- ✅ **No custom statuses** → Uses Coperniq's existing statuses

**Next Step**: Update your smart views in Close CRM to filter on status="Raw" + description text!
