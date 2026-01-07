# SQL Server Management Studio Query Guide

Quick reference for exploring the Compass ODM database to understand the schema.

## Connection Info

- **Server:** `ROCFDN019Q`
- **Database:** `ODM`
- **Authentication:** SQL Server Authentication
- **Login:** Your username
- **Password:** Your password

---

## Step 1: Find Tables with StudyUID Column

```sql
-- Find all tables/columns containing Study UID
SELECT 
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME LIKE '%Study%UID%'
   OR COLUMN_NAME LIKE '%StudyInstance%'
   OR COLUMN_NAME LIKE '%STUDY_UID%'
ORDER BY TABLE_NAME, COLUMN_NAME
```

**Result:** `MCIE_ENTRIES` has `STUDY_UID` column

---

## Step 2: Get Full Schema of MCIE_ENTRIES

```sql
-- See all columns in MCIE_ENTRIES
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE,
    COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'MCIE_ENTRIES'
ORDER BY ORDINAL_POSITION
```

**Look for:** PatientName, PatientID, AccessionNumber, Modality columns

---

## Step 3: Find Linking Columns

```sql
-- Find columns in MCIE_ENTRIES that might link to ODM_ENTRIES
SELECT COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'MCIE_ENTRIES'
  AND (COLUMN_NAME LIKE '%ODM%' 
    OR COLUMN_NAME LIKE '%ID'
    OR COLUMN_NAME LIKE '%ENTRY%'
    OR COLUMN_NAME LIKE '%MC_ID%'
    OR COLUMN_NAME LIKE '%INTERNAL%')
ORDER BY COLUMN_NAME
```

**Expected:** `ODM_ID`, `INTERNAL_ID`, `MC_ID`, or `MCIE_ID`

---

## Step 4: View Sample Data from MCIE_ENTRIES

```sql
-- Get most recent 10 DICOM entries
SELECT TOP 10 *
FROM MCIE_ENTRIES
ORDER BY MCIE_ID DESC
```

---

## Step 5: Search by Specific StudyUID

```sql
-- Find specific study by UID
SELECT *
FROM MCIE_ENTRIES
WHERE STUDY_UID = '1.2.840.113619.2.55.3.REPLACE_WITH_YOUR_UID'
```

Replace `REPLACE_WITH_YOUR_UID` with actual StudyInstanceUID from your test.

---

## Step 6: JOIN MCIE_ENTRIES with ODM_ENTRIES

```sql
-- Get complete job + DICOM data
SELECT 
    o.ODM_ID,
    o.STATUS,
    o.CREATION_TIME,
    o.MODIFIED_TIME,
    o.NUM_DICOM,
    o.NUM_FILES,
    m.STUDY_UID,
    m.PATIENT_NAME,
    m.PATIENT_ID,
    m.ACCESSION_NUMBER,
    m.MODALITY,
    m.STUDY_DATE
FROM ODM_ENTRIES o
INNER JOIN MCIE_ENTRIES m ON o.INTERNAL_ID = m.INTERNAL_ID  
-- ^^ ADJUST THIS JOIN - could be o.ODM_ID = m.ODM_ID or other column
WHERE m.STUDY_UID = '1.2.840.113619.2.55.3.REPLACE_WITH_YOUR_UID'
```

**Note:** Try different JOIN conditions:
- `o.ODM_ID = m.ODM_ID`
- `o.INTERNAL_ID = m.INTERNAL_ID`
- `o.MC_ID = m.MC_ID`

---

## Step 7: Find Foreign Key Relationships

```sql
-- Show foreign keys between tables
SELECT 
    FK.name AS ForeignKeyName,
    TP.name AS ParentTable,
    CP.name AS ParentColumn,
    TR.name AS ReferencedTable,
    CR.name AS ReferencedColumn
FROM sys.foreign_keys FK
INNER JOIN sys.foreign_key_columns FKC ON FK.object_id = FKC.constraint_object_id
INNER JOIN sys.tables TP ON FKC.parent_object_id = TP.object_id
INNER JOIN sys.columns CP ON FKC.parent_object_id = CP.object_id 
    AND FKC.parent_column_id = CP.column_id
INNER JOIN sys.tables TR ON FKC.referenced_object_id = TR.object_id
INNER JOIN sys.columns CR ON FKC.referenced_object_id = CR.object_id 
    AND FKC.referenced_column_id = CR.column_id
WHERE TP.name IN ('ODM_ENTRIES', 'MCIE_ENTRIES')
   OR TR.name IN ('ODM_ENTRIES', 'MCIE_ENTRIES')
ORDER BY TP.name, TR.name
```

---

## Step 8: Test Your Recent Test Study

```sql
-- Find your most recent test studies
SELECT TOP 20
    o.ODM_ID,
    o.CREATION_TIME,
    o.STATUS,
    m.STUDY_UID,
    m.PATIENT_NAME,
    m.PATIENT_ID
FROM ODM_ENTRIES o
INNER JOIN MCIE_ENTRIES m ON o.INTERNAL_ID = m.INTERNAL_ID  -- ADJUST JOIN
WHERE o.CREATION_TIME > DATEADD(hour, -1, GETDATE())  -- Last 1 hour
ORDER BY o.CREATION_TIME DESC
```

---

## Step 9: Count Records

```sql
-- See how much data exists
SELECT 
    'ODM_ENTRIES' AS TableName,
    COUNT(*) AS RowCount,
    MIN(CREATION_TIME) AS OldestRecord,
    MAX(CREATION_TIME) AS NewestRecord
FROM ODM_ENTRIES

UNION ALL

SELECT 
    'MCIE_ENTRIES',
    COUNT(*),
    NULL,
    NULL
FROM MCIE_ENTRIES
```

---

## What to Report Back

After running these queries, please share:

1. **All column names from MCIE_ENTRIES** (from Step 2)
   - Especially: PatientName, PatientID, AccessionNumber columns
   
2. **The linking column** (from Step 3)
   - Which column in MCIE_ENTRIES links to ODM_ENTRIES?
   
3. **Sample row** (from Step 4 or 5)
   - What do the actual values look like?

4. **Working JOIN** (from Step 6)
   - Which JOIN condition works? `o.ODM_ID = m.ODM_ID`? or different?

---

## Common Column Name Patterns

Based on what we've seen, likely column names:

| DICOM Attribute | Possible Column Names |
|----------------|----------------------|
| StudyInstanceUID | `STUDY_UID`, `STUDY_UUID` |
| PatientName | `PATIENT_NAME`, `PAT_NAME` |
| PatientID | `PATIENT_ID`, `PAT_ID` |
| AccessionNumber | `ACCESSION_NUMBER`, `ACC_NUM` |
| Modality | `MODALITY`, `MOD` |
| StudyDate | `STUDY_DATE`, `STUDY_DT` |
| StudyDescription | `STUDY_DESC`, `STUDY_DESCRIPTION` |

---

## Next Steps

Once you have the column names and JOIN condition, we'll update:
- `compass_db_query.py` with the correct table/column names
- The JOIN query to get complete DICOM data
- `get_job_by_study_uid()` function to work properly

Then the tests will work!

