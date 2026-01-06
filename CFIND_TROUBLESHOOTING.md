# C-FIND Troubleshooting Guide

## Problem: Studies Exist in Compass Web UI But C-FIND Can't Find Them

You found that:
- ✅ Study EXISTS in Compass web dashboard (3 records)
- ❌ C-FIND query returns NOTHING

This is an **AE Title permissions issue** or **query parameter mismatch**.

## Diagnosis Steps

### Step 1: Test with the Study UID You Found

```bash
# Use the exact Study UID from your failed test
python debug_cfind_study.py "1.2.840.XXXX.YOUR.STUDY.UID.HERE"
```

This will show:
- What C-FIND is querying
- What Compass is returning
- Detailed DICOM protocol messages

### Step 2: Try Different Calling AE Titles

Compass might filter C-FIND queries based on who's asking. Try these:

```bash
# Try with PERF_SENDER (your default sending AE)
export LOCAL_AE_TITLE=PERF_SENDER
python debug_cfind_study.py "YOUR_STUDY_UID"

# Try with ULTRA_MCR_FORUM (test sending AE)
export LOCAL_AE_TITLE=ULTRA_MCR_FORUM
python debug_cfind_study.py "YOUR_STUDY_UID"

# Try with same AE as Compass
export LOCAL_AE_TITLE=COMPASS
python debug_cfind_study.py "YOUR_STUDY_UID"

# Try with a generic query AE
export LOCAL_AE_TITLE=QUERY
python debug_cfind_study.py "YOUR_STUDY_UID"
```

### Step 3: Check Compass Configuration

Ask your Compass administrator:

**Question 1:** "Which AE Titles have C-FIND query permissions?"
- The web UI might use a special internal AE
- External queries might be restricted to specific AEs

**Question 2:** "Does Compass filter C-FIND results by Calling AE Title?"
- Some systems only return studies that were sent by the same AE
- E.g., if you sent as `ULTRA_MCR_FORUM`, you can only query as `ULTRA_MCR_FORUM`

**Question 3:** "Is there a delay between C-STORE and C-FIND availability?"
- Studies might be in the database but not yet indexed for C-FIND
- Web UI might query the raw database, C-FIND might query an index

## Common Scenarios

### Scenario A: AE Title Filtering (Most Common)

**Problem:** Compass only allows C-FIND from specific AE Titles

**Solution:** 
```python
# In tests/test_routing_transformations.py, line 239
# Change from:
local_ae_title='TEST_QUERY',

# To match the sending AE:
local_ae_title=dicom_sender.endpoint.local_ae_title,  # Use same AE as sending
```

### Scenario B: Study Association Filtering

**Problem:** Compass only returns studies to the AE that sent them

**Solution:** Query with the **same AE Title** used to send:
```python
config = CompassCFindConfig(
    host=dicom_sender.endpoint.host,
    port=dicom_sender.endpoint.port,
    remote_ae_title=dicom_sender.endpoint.remote_ae_title,
    local_ae_title=test_case['aet'],  # Use the sending AE Title!
    timeout=30
)
```

### Scenario C: Web UI Uses Different Query Method

**Problem:** Web UI queries database directly, not via DICOM C-FIND

**Solution:** 
- Use database query instead of C-FIND
- Or get special C-FIND AE Title from administrator

## Quick Fix to Test

Try this modification to see if using the **sending AE Title** for queries works:

### In `tests/test_routing_transformations.py`, modify line 174 and 239:

**Current (line 239):**
```python
local_ae_title='TEST_QUERY',
```

**Change to:**
```python
local_ae_title=test_case['aet'],  # Use same AE as sending!
```

This makes C-FIND query with the **same AE Title** that sent the study.

## Test the Fix

```bash
# Test with the modified code
pytest tests/test_routing_transformations.py::test_routing_transformation[OPV_GPA_VisualFields] -v -s
```

If it works, you'll see:
```
SUCCESS: Study found in Compass after 0.5s
```

## What to Document

When you find the solution, document:

1. **Which AE Title worked for C-FIND?**
   - Same as sending AE?
   - Different specific AE?
   - Any AE?

2. **Does Compass filter by AE Title?**
   - Yes: Only returns studies sent by that AE
   - No: Returns all studies

3. **Is there a delay?**
   - How long between C-STORE and C-FIND availability?

This info will help configure tests correctly.

## Most Likely Solution

Based on your symptoms, **Compass probably filters C-FIND queries by AE Title**.

**Quick test:**
```bash
# Get your Study UID that you found in web UI
STUDY_UID="1.2.840.YOUR.UID"

# Try querying with ULTRA_MCR_FORUM (the AE that sent it)
export LOCAL_AE_TITLE=ULTRA_MCR_FORUM
python debug_cfind_study.py "$STUDY_UID"
```

If that works, update the test to use `test_case['aet']` instead of `'TEST_QUERY'`.

