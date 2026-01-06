# How to Verify C-FIND Assertions Are Actually Working

## The Problem
You got 7 passing tests, but how do you know C-FIND verification actually ran?

## 3 Ways to Verify

### Method 1: Check Test Output (EASIEST)

Run tests with `-s` flag to see print statements:

```bash
pytest tests/test_routing_transformations.py -v -s
```

**Look for this section in the output:**

#### ✅ C-FIND IS WORKING:
```
[STEP 2: AUTOMATED VERIFICATION]
  Querying Compass for study: 1.2.840.113619...
  SUCCESS: Study found in Compass!
  
  Verifying expected transformations:
    StudyDescription: 'Visual Fields (VF) GPA' ✓ MATCH
    
  ✓ C-FIND VERIFICATION PASSED - All transformations correct!

[RESULT: TEST COMPLETE]
```

#### ❌ C-FIND IS NOT WORKING (Skipped):
```
[STEP 2: AUTOMATED VERIFICATION]
  WARNING: compass_cfind_client not available
  Skipping automated verification

[RESULT: TEST COMPLETE]
```

#### ❌ C-FIND IS NOT WORKING (Connection Failed):
```
[STEP 2: AUTOMATED VERIFICATION]
  Querying Compass for study: 1.2.840.113619...
  ERROR: C-FIND connection failed: Failed to establish association
  C-FIND may not be enabled on Compass
  Falling back to manual verification

[RESULT: TEST COMPLETE]
```

### Method 2: Intentionally Break a Test (ACID TEST)

Temporarily change an expected value to something wrong:

#### Step 1: Edit the test file

```python
# In tests/test_routing_transformations.py, line 34
'expected': {
    'study_description': 'WRONG VALUE',  # Changed from 'Visual Fields (VF) GPA'
}
```

#### Step 2: Run the test

```bash
pytest tests/test_routing_transformations.py::test_routing_transformation[OPV_GPA_VisualFields] -v -s
```

#### Step 3: Check the result

**If C-FIND is working, you should see:**
```
FAILED - AssertionError: StudyDescription mismatch: expected 'WRONG VALUE', got 'Visual Fields (VF) GPA'
```

**If C-FIND is NOT working:**
```
PASSED  # ← Test passes even though expected value is wrong!
```

#### Step 4: Revert the change

```python
'expected': {
    'study_description': 'Visual Fields (VF) GPA',  # Back to correct value
}
```

### Method 3: Add Debug Logging

Add this at the start of `query_and_verify()` function:

```python
def query_and_verify(dicom_sender, study_uid: str, expected_attributes: dict):
    """Query Compass via C-FIND and verify transformations were applied."""
    
    # ADD THIS LINE TO FORCE VISIBILITY
    import sys
    print(f"\n{'='*70}", file=sys.stderr)
    print(f"C-FIND VERIFICATION RUNNING FOR: {study_uid}", file=sys.stderr)
    print(f"{'='*70}", file=sys.stderr)
    
    # Rest of function...
```

This will print to stderr and always be visible.

## What Your 7 Passes Mean

Since you got 7 passes, it means one of these:

### Scenario A: ✅ C-FIND Is Working (Good!)
- All 7 tests sent DICOM to Compass
- C-FIND successfully queried each study
- All transformations matched expected values
- **This is what we want!**

### Scenario B: ⚠️ C-FIND Is Skipping (Not Good)
- Tests passed because send succeeded
- C-FIND verification silently skipped (module not imported)
- No actual verification happened
- **Tests are passing without checking!**

### Scenario C: ⚠️ C-FIND Connection Failed (Not Good)
- Tests passed because send succeeded
- C-FIND tried to connect but failed
- Fell back to "manual verification"
- **Tests are passing without checking!**

## How to Confirm Which Scenario

Run ONE test with output:

```bash
pytest tests/test_routing_transformations.py::test_routing_transformation[OPV_GPA_VisualFields] -v -s | grep -A 10 "AUTOMATED VERIFICATION"
```

You should see:
```
[STEP 2: AUTOMATED VERIFICATION]
  Querying Compass for study: 1.2.840.113619.2.408.20221110.9999999.99999.9999999999
  SUCCESS: Study found in Compass!
  
  Verifying expected transformations:
    StudyDescription: 'Visual Fields (VF) GPA' ✓ MATCH
    
  ✓ C-FIND VERIFICATION PASSED - All transformations correct!
```

**If you see the ✓ checkmarks, your C-FIND verification IS working!**

## Quick Test Commands

```bash
# Run one test and show only the verification section
pytest tests/test_routing_transformations.py::test_routing_transformation[OPV_GPA_VisualFields] -v -s 2>&1 | grep -A 15 "AUTOMATED VERIFICATION"

# Run all tests and count how many times C-FIND succeeded
pytest tests/test_routing_transformations.py -v -s 2>&1 | grep "C-FIND VERIFICATION PASSED" | wc -l
# Should output: 7 (if all C-FIND verifications worked)

# Check for any skipped verifications
pytest tests/test_routing_transformations.py -v -s 2>&1 | grep -i "skipping\|warning.*compass_cfind\|falling back"
# Should output: nothing (if C-FIND is working)
```

## Summary

**To verify your tests are really checking:**

1. Run with `-s` flag and look for "✓ C-FIND VERIFICATION PASSED"
2. Count how many times you see it (should be 7)
3. If you see 7 passes AND 7 "✓ C-FIND VERIFICATION PASSED", you're good!
4. If you only see passes but no verification messages, C-FIND is skipping

**The most reliable test: Intentionally break an expected value and confirm the test FAILS.**

