# Database Query Setup Guide

## Quick Start (3 Steps)

### 1. Add Database Credentials to `.env`

Open your `.env` file and add:

```env
# Database credentials
COMPASS_DB_SERVER=ROCFDN019Q
COMPASS_DB_NAME=ODM
COMPASS_DB_PORT=1433
COMPASS_DB_USER=your_username_here
COMPASS_DB_PASSWORD=your_password_here
COMPASS_DB_WINDOWS_AUTH=false
```

If using Windows Authentication instead:

```env
COMPASS_DB_SERVER=ROCFDN019Q
COMPASS_DB_NAME=ODM
COMPASS_DB_WINDOWS_AUTH=true
```

### 2. Test Database Connection

```bash
python test_database_connection.py
```

This will:
- Verify credentials work
- Discover all database tables
- Show schema for Jobs and DicomTags tables
- Display sample query results

**Expected Output:**

```
[TEST 1: Connection]
SUCCESS: Database connection established!

[TEST 2: Discover Tables]
Found X tables:
  1. Jobs
  2. DicomTags
  ...

[TEST 3: Jobs Table Schema]
Jobs table has Y columns:
  StudyInstanceUID     nvarchar(64)      NOT NULL
  PatientID            nvarchar(64)      NULL
  ...

ALL TESTS COMPLETED SUCCESSFULLY!
```

### 3. Run Tests

```bash
# Run all transformation tests with database verification
pytest tests/test_routing_transformations.py -v

# Run a specific test
pytest tests/test_routing_transformations.py::test_patient_name_transformation -v
```

---

## What Changed?

### Before (C-FIND - Failed)

Tests were using C-FIND to verify studies in Compass, but Compass was rejecting queries with `0x0110 (Processing Failure)`.

### After (Database Queries - Works)

Tests now query the Compass database directly to verify:
- Study was received
- Transformations were applied correctly
- All expected DICOM tags are present

---

## How It Works

1. **Test sends DICOM study** to Compass
2. **Test queries database** for that StudyInstanceUID
3. **Polls for 30 seconds** waiting for study to appear
4. **Verifies transformations** by comparing expected vs actual DICOM tags
5. **Test fails** if study not found or tags don't match

---

## Troubleshooting

### "pyodbc not installed"

```bash
pip install pyodbc
```

### "Connection failed"

**Check credentials:**
- Username correct?
- Password correct?
- Server name correct? (`ROCFDN019Q`)
- Database name correct? (`ODM`)

**Check network:**
- Can you reach the server? (`ping ROCFDN019Q`)
- Is port 1433 open? (SQL Server default)
- Are you on the Mayo network/VPN?

### "Table 'Jobs' not found"

Run discovery to find actual table names:

```bash
python test_database_connection.py
```

Look for tables that might contain DICOM job data. Update `compass_db_query.py` with correct table names.

### "Study not found in Compass after 30s"

Possible reasons:
1. **Processing delay** - Compass might take longer than 30s
   - Increase timeout: Edit `query_and_verify()` in `test_routing_transformations.py`
   
2. **Routing without storage** - Compass might forward without storing locally
   - Check Compass routing rules
   
3. **Study rejected** - Compass might filter/reject the study
   - Check Compass logs
   - Verify sending AE Title is allowed

### "Tags don't match"

If test fails with mismatch:

```
PatientName: 'ORIGINAL_NAME' MISMATCH
  Expected: 'ANONYMIZED_NAME'
```

This means:
1. Study was received (good!)
2. But transformation didn't work as expected (investigate routing rules)

---

## Database Schema (Typical)

### Jobs Table

Stores one row per DICOM job/study received:

| Column | Type | Description |
|--------|------|-------------|
| JobID | int | Primary key |
| StudyInstanceUID | nvarchar(64) | DICOM Study UID |
| PatientID | nvarchar(64) | Patient identifier |
| PatientName | nvarchar(255) | Patient name |
| AccessionNumber | nvarchar(64) | Accession number |
| Modality | nvarchar(16) | Modality (CT, MR, etc.) |
| StudyDate | date | Study date |
| CallingAET | nvarchar(16) | Source AE Title |
| DestinationAET | nvarchar(16) | Destination AE Title |
| Status | nvarchar(32) | Job status |
| CreatedAt | datetime | When received |
| CompletedAt | datetime | When completed |
| ImageCount | int | Number of images |

### DicomTags Table

Stores all DICOM tags for each job:

| Column | Type | Description |
|--------|------|-------------|
| TagID | int | Primary key |
| JobID | int | Foreign key to Jobs |
| TagGroup | nvarchar(4) | DICOM tag group (e.g., "0010") |
| TagElement | nvarchar(4) | DICOM tag element (e.g., "0010") |
| TagName | nvarchar(255) | Tag name (e.g., "PatientName") |
| VR | nvarchar(2) | Value representation |
| Value | nvarchar(max) | Tag value |

**Note:** Actual schema may differ. Run `test_database_connection.py` to discover real schema.

---

## Files Modified

### `test_routing_transformations.py`

**Changed:** `query_and_verify()` function now uses database queries instead of C-FIND

**Key changes:**
- Imports `CompassDatabaseClient` instead of `CompassCFindClient`
- Calls `client.get_job_by_study_uid()` to retrieve study + tags
- Polls database for 30 seconds with 2-second intervals
- Raises `AssertionError` if study not found or tags mismatch

### `compass_db_query.py`

**Enhanced:** `get_job_by_study_uid()` now includes DICOM tags

**Key changes:**
- New parameter: `include_tags=True`
- Fetches job record from Jobs table
- Fetches all DICOM tags from DicomTags table
- Merges tags into result dictionary
- Returns single dict with all data

### `test_database_connection.py` (NEW)

**Purpose:** Verify database credentials and discover schema

**Features:**
- Tests connection
- Discovers all tables
- Shows schema for Jobs and DicomTags
- Displays sample query results

---

## Next Steps

1. **Test connection:** `python test_database_connection.py`
2. **Run tests:** `pytest tests/test_routing_transformations.py -v`
3. **If tables/columns don't match:** Update `compass_db_query.py` with actual names
4. **Update other test files:** Apply same pattern to other test modules

---

## Security Notes

- `.env` file is **NEVER** committed to git (already in `.gitignore`)
- Use **read-only** database credentials when possible
- Follow Mayo Clinic security policies
- Database credentials are only used for **verification**, not sending DICOM data

---

## Alternative: If Database Access Not Available

If you cannot get database credentials:

1. **Use REST API** (if available) - See `compass_api_client.py`
2. **Manual verification** - Check Compass web UI after each test
3. **Request C-FIND access** - Ask admin to enable C-FIND for your AE Titles

But database queries are the **most reliable** method for automated testing.

