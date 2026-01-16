# Close CRM Deduplication Flow - COMPLETE LOGIC

## 🎯 The 4 Scenarios

### Scenario 1: "create_new"
**When**: Company does NOT exist in Close CRM (< 85% fuzzy match)
**Action**: Create NEW lead with ALL discovered contacts
**Example**: "Generator Supercenter" not in Close → Create company + 7 contacts

### Scenario 2: "add_contact_to_existing"
**When**: Company EXISTS in Close, but this specific contact does NOT
**Action**: ADD new contact(s) to EXISTING lead_id (NO new company)
**Example**: "Generator Supercenter" exists with 2 contacts → Add 5 new contacts to SAME lead

### Scenario 3: "skip_duplicate"
**When**: Company EXISTS + Contact EXISTS with SAME data (no updates needed)
**Action**: SKIP entirely (log warning, don't touch Close CRM)
**Example**: "john@acme.com" already in Close with same phone/title → Skip

### Scenario 4: "update_existing_contact"
**When**: Company EXISTS + Contact EXISTS but has OUTDATED data
**Action**: UPDATE existing contact with new phone/linkedin/department
**Example**: "john@acme.com" exists but we found new phone number → Update contact

---

## 🔍 Current Pipeline Flow (WITH BUGS!)

### Stage 1: Qualification
- Cerebras scores lead (0-100)
- Hunter.io discovers ATL contacts (if no email provided)
- Output: `lead["_discovered_contacts"] = [7 contacts]`

### Stage 2: Close CRM Check (`_check_close_crm_for_atl`)
- Calls `deduplication_service.check_duplicate(company_name, email)`
- Returns: `recommendation` = one of 4 scenarios above

### Stage 3: Enrichment
- Skipped if ATL contacts already found in Stage 2

### Stage 4: Deduplication (`_run_deduplication`)
- **PROBLEM**: This is the SAME check as Stage 2! Redundant!

### Stage 5: Close CRM Create/Update (`_run_close_crm`) - 🚨 **BUGS HERE**

#### Bug #1: "add_contact_to_existing" (Line 661-679)
```python
elif recommendation == "add_contact_to_existing":
    # TODO: Implement add_contact_to_lead method
    # For now, create new lead (will be implemented separately)
    result = await self.close_service.create_lead(lead)  # 🚨 BUG!
```
**PROBLEM**: Creates DUPLICATE company instead of adding to existing!

#### Bug #2: "update_existing_contact" (Line 641-659)
```python
elif recommendation == "update_existing_contact":
    # TODO: Implement contact update with merged data
    # For now, return success
    return PipelineStageResult(status="updated", ...)  # 🚨 BUG!
```
**PROBLEM**: Returns "updated" but doesn't actually update anything!

#### Bug #3: "create_new" (Line 681-694)
```python
else:  # "create_new"
    result = await self.close_service.create_lead(lead)  # Calls create_lead()
```
**THIS ONE IS CORRECT** - But `create_lead()` has my new bug...

#### Bug #4: My New Code in `close.py` (Line 466-546)
```python
if discovered_contacts:
    # Create lead with ALL contacts via Close API
    # 🚨 BUG: Doesn't check if lead_id already exists!
    response = await client.post(f"{self.BASE_URL}/lead/", ...)
```
**PROBLEM**: Always creates NEW lead, even when should ADD to existing!

---

## ✅ What We Need to Fix

### Fix #1: Update `create_lead()` signature
```python
async def create_lead(
    self,
    lead: Dict[str, Any],
    matched_lead_id: Optional[str] = None  # NEW parameter
) -> Dict[str, Any]:
```

### Fix #2: Handle existing lead_id in `create_lead()`
```python
if discovered_contacts:
    if matched_lead_id:
        # ADD contacts to existing lead
        for contact in discovered_contacts:
            await self._add_contact_to_lead(matched_lead_id, contact)
    else:
        # CREATE new lead with all contacts
        response = await client.post(f"{self.BASE_URL}/lead/", ...)
```

### Fix #3: Implement `_add_contact_to_lead()` method
```python
async def _add_contact_to_lead(self, lead_id: str, contact: Dict) -> Dict:
    """Add a single contact to existing lead"""
    response = await client.post(
        f"{self.BASE_URL}/lead/{lead_id}/contact/",
        json={"name": ..., "emails": [...], "title": ...}
    )
```

### Fix #4: Implement `update_contact()` method
```python
async def update_contact(
    self,
    lead_id: str,
    contact_id: str,
    updates: Dict
) -> Dict:
    """Update existing contact with new data"""
    response = await client.put(
        f"{self.BASE_URL}/contact/{contact_id}/",
        json=updates
    )
```

### Fix #5: Pass `matched_lead_id` to `create_lead()`
In `pipeline_orchestrator.py` line 661-679:
```python
elif recommendation == "add_contact_to_existing":
    result = await self.close_service.create_lead(
        lead,
        matched_lead_id=matched_lead_id  # Pass existing lead ID!
    )
```

---

## 🧪 Test Plan (DRY RUN ONLY!)

### Test Case 1: New Company
**Input**: "Test Company ABC" (not in Close)
**Expected**: `recommendation="create_new"` → Create lead with 7 contacts
**Verify**: 1 new lead created, 7 contacts total

### Test Case 2: Existing Company, New Contacts
**Input**: "Generator Supercenter" (already in Close with 2 contacts)
**Expected**: `recommendation="add_contact_to_existing"` → Add 5 contacts to existing lead
**Verify**: 0 new leads, existing lead now has 7 contacts (2 old + 5 new)

### Test Case 3: Duplicate Contact
**Input**: "john@generatorsupercenter.com" (already exists)
**Expected**: `recommendation="skip_duplicate"` → Skip entirely
**Verify**: 0 changes, log warning

### Test Case 4: Outdated Contact
**Input**: "john@generatorsupercenter.com" (exists but we found new phone)
**Expected**: `recommendation="update_existing_contact"` → Update phone field
**Verify**: Contact updated, no new contacts created

---

## 🚨 CRITICAL RULES

1. **NEVER create duplicate companies** - Check Close CRM first ALWAYS
2. **NEVER create duplicate contacts** - Check email match within company
3. **ALWAYS use dry_run=true** until deduplication proven
4. **ALWAYS log recommendations** - So we can audit decisions
5. **NEVER skip deduplication** - Even if it adds latency

---

## 📊 Current Status

- ✅ Deduplication check logic (`close_deduplication.py`) - **CORRECT**
- ❌ Pipeline orchestrator handling - **3 BUGS**
- ❌ CloseService.create_lead() - **1 BUG (mine!)**
- ❌ CloseService._add_contact_to_lead() - **NOT IMPLEMENTED**
- ❌ CloseService.update_contact() - **NOT IMPLEMENTED**

**NEXT STEP**: Fix all 5 issues, then test with dry_run=true to PROVE it works.
