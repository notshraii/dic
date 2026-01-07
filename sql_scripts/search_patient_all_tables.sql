-- ============================================================================
-- Search All Tables for Patient Data
-- ============================================================================
-- Purpose: Find which table(s) contain your test patient records
-- Usage: Run in SQL Server Management Studio against the ODM database
-- ============================================================================

-- Set your search value here
DECLARE @SearchValue NVARCHAR(100) = '%ANONYMIZED%'

-- ============================================================================
-- OPTION 1: Quick Search - Known DICOM Tables
-- ============================================================================

PRINT '=== Searching known DICOM tables ==='

-- Search MCIE_ENTRIES (main DICOM entries table)
PRINT 'Searching MCIE_ENTRIES...'
SELECT 'MCIE_ENTRIES' AS TableName, * 
FROM MCIE_ENTRIES 
WHERE PATIENT_ID LIKE @SearchValue 
   OR DICOM_NAME LIKE @SearchValue 
   OR MDM_NAME LIKE @SearchValue

-- Search MCIE_WORK_ITEM
PRINT 'Searching MCIE_WORK_ITEM...'
SELECT 'MCIE_WORK_ITEM' AS TableName, *
FROM MCIE_WORK_ITEM
WHERE PATIENT_ID LIKE @SearchValue
   OR FIRST_NAME LIKE @SearchValue
   OR LAST_NAME LIKE @SearchValue

-- Search IMPORT_WORK_ITEM
PRINT 'Searching IMPORT_WORK_ITEM...'
SELECT 'IMPORT_WORK_ITEM' AS TableName, *
FROM IMPORT_WORK_ITEM
WHERE PATIENT_ID LIKE @SearchValue

-- Search STUDY_MAPPING (transformation tracking)
PRINT 'Searching STUDY_MAPPING...'
SELECT 'STUDY_MAPPING' AS TableName, *
FROM STUDY_MAPPING
WHERE ORIGINAL_PATIENT_NAME LIKE @SearchValue
   OR MAYO_PATIENT_NAME LIKE @SearchValue
   OR ORIGINAL_PATIENT_ID LIKE @SearchValue

-- Search HS_ENTRIES
PRINT 'Searching HS_ENTRIES...'
SELECT 'HS_ENTRIES' AS TableName, *
FROM HS_ENTRIES
WHERE SITE_PATIENT_ID LIKE @SearchValue

GO

-- ============================================================================
-- OPTION 2: Dynamic Search - All Tables with Patient Columns
-- ============================================================================
-- This searches ALL tables that have patient-related columns
-- Returns count of matches per table/column combination

PRINT '=== Dynamic search across all tables ==='

DECLARE @SearchValue2 NVARCHAR(100) = '%ANONYMIZED%'
DECLARE @SQL NVARCHAR(MAX) = ''

-- Build dynamic SQL for all tables with patient columns
SELECT @SQL = @SQL + 
    'SELECT ''' + TABLE_NAME + ''' AS TableName, ''' + COLUMN_NAME + ''' AS ColumnName, COUNT(*) AS Matches ' +
    'FROM [' + TABLE_NAME + '] WHERE [' + COLUMN_NAME + '] LIKE ''' + @SearchValue2 + ''' HAVING COUNT(*) > 0 UNION ALL '
FROM INFORMATION_SCHEMA.COLUMNS
WHERE (COLUMN_NAME LIKE '%PATIENT%' OR COLUMN_NAME LIKE '%NAME%')
  AND DATA_TYPE IN ('varchar', 'nvarchar', 'char', 'text')
  AND TABLE_NAME NOT LIKE '%_20%'  -- Skip dated backup tables

-- Check if we have any SQL to execute
IF LEN(@SQL) > 10
BEGIN
    -- Remove trailing UNION ALL
    SET @SQL = LEFT(@SQL, LEN(@SQL) - 10)
    
    -- Execute dynamic search
    PRINT 'Executing dynamic search...'
    EXEC sp_executesql @SQL
END
ELSE
BEGIN
    PRINT 'No tables with patient columns found'
END

GO

-- ============================================================================
-- OPTION 3: Search by Study Instance UID
-- ============================================================================
-- If you know the Study UID, search for it directly

DECLARE @StudyUID NVARCHAR(255) = '1.2.840.113619.2.55.3'  -- Replace with your UID (first 37 chars)

PRINT '=== Searching by Study UID ==='

-- STUDY_MAPPING (uses truncated UID)
SELECT 'STUDY_MAPPING' AS TableName, *
FROM STUDY_MAPPING
WHERE LEFT(ORIGINAL_STUDY_UID, 37) = LEFT(@StudyUID, 37)

-- MCIE_ENTRIES (if it has study UID column)
SELECT 'MCIE_ENTRIES' AS TableName, *
FROM MCIE_ENTRIES
WHERE STUDY_UID LIKE @StudyUID + '%'

GO

-- ============================================================================
-- OPTION 4: Recent Records (Last Hour)
-- ============================================================================
-- Find recently added records across key tables

PRINT '=== Recent records (last hour) ==='

-- Recent MCIE_ENTRIES
SELECT TOP 20 'MCIE_ENTRIES' AS TableName, *
FROM MCIE_ENTRIES
ORDER BY MCIE_ID DESC

-- Recent STUDY_MAPPING
SELECT TOP 20 'STUDY_MAPPING' AS TableName, *
FROM STUDY_MAPPING
ORDER BY CREATION_TIME DESC

-- Recent MCIE_WORK_ITEM
SELECT TOP 20 'MCIE_WORK_ITEM' AS TableName, *
FROM MCIE_WORK_ITEM
ORDER BY MCIE_WORK_ITEM_ID DESC

GO

-- ============================================================================
-- OPTION 5: Find Table with Study Description
-- ============================================================================
-- The test_routing_transformations.py tests check study_description
-- Find which table stores this

PRINT '=== Tables with Study Description column ==='

SELECT TABLE_NAME, COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME LIKE '%STUDY%DESC%'
   OR COLUMN_NAME LIKE '%STUDY_DESC%'
   OR COLUMN_NAME LIKE '%StudyDescription%'
ORDER BY TABLE_NAME

GO

