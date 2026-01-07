-- ============================================================================
-- Search ALL Tables for a Specific String
-- ============================================================================
-- Purpose: Find which table(s) contain a specific value anywhere in the database
-- Usage: Run in SQL Server Management Studio against the ODM database
-- ============================================================================

-- ============================================================================
-- OPTION 1: Full Search - Returns matching rows with table/column info
-- ============================================================================
-- This searches every text column in every table and returns full rows

DECLARE @SearchValue NVARCHAR(100) = 'ZZTESTPATIENT^ANONYMIZED'  -- Change this
DECLARE @SQL NVARCHAR(MAX) = ''

-- Build dynamic SQL to search every text column in every table
SELECT @SQL = @SQL + 
    'IF EXISTS (SELECT 1 FROM [' + TABLE_NAME + '] WHERE [' + COLUMN_NAME + '] LIKE ''%' + @SearchValue + '%'') ' +
    'SELECT ''' + TABLE_NAME + ''' AS TableName, ''' + COLUMN_NAME + ''' AS ColumnName, * ' +
    'FROM [' + TABLE_NAME + '] WHERE [' + COLUMN_NAME + '] LIKE ''%' + @SearchValue + '%''; '
FROM INFORMATION_SCHEMA.COLUMNS
WHERE DATA_TYPE IN ('varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext')
  AND TABLE_NAME NOT LIKE '%backup%'
  AND TABLE_NAME NOT LIKE '%_20%'

-- Execute the search
PRINT 'Searching all tables for: ' + @SearchValue
EXEC sp_executesql @SQL

GO

-- ============================================================================
-- OPTION 2: Quick Count - Just shows which tables have matches
-- ============================================================================
-- Faster - only returns table name, column name, and count of matches

DECLARE @SearchValue2 NVARCHAR(100) = '%ZZTESTPATIENT%'  -- Change this (use % wildcards)
DECLARE @SQL2 NVARCHAR(MAX) = ''

SELECT @SQL2 = @SQL2 + 
    'SELECT ''' + TABLE_NAME + ''' AS TableName, ''' + COLUMN_NAME + ''' AS ColumnName, COUNT(*) AS MatchCount ' +
    'FROM [' + TABLE_NAME + '] WHERE [' + COLUMN_NAME + '] LIKE ''' + @SearchValue2 + ''' HAVING COUNT(*)>0 UNION ALL '
FROM INFORMATION_SCHEMA.COLUMNS
WHERE DATA_TYPE IN ('varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext')
  AND TABLE_NAME NOT LIKE '%backup%'
  AND TABLE_NAME NOT LIKE '%_20%'

-- Remove trailing UNION ALL and execute
IF LEN(@SQL2) > 10
BEGIN
    SET @SQL2 = LEFT(@SQL2, LEN(@SQL2) - 10)
    PRINT 'Quick count search for: ' + @SearchValue2
    EXEC sp_executesql @SQL2
END

GO

-- ============================================================================
-- OPTION 3: Search by Study Instance UID
-- ============================================================================

DECLARE @StudyUID NVARCHAR(100) = '1.2.840.113619'  -- Change this (first part of UID)
DECLARE @SQL3 NVARCHAR(MAX) = ''

SELECT @SQL3 = @SQL3 + 
    'SELECT ''' + TABLE_NAME + ''' AS TableName, ''' + COLUMN_NAME + ''' AS ColumnName, COUNT(*) AS MatchCount ' +
    'FROM [' + TABLE_NAME + '] WHERE [' + COLUMN_NAME + '] LIKE ''%' + @StudyUID + '%'' HAVING COUNT(*)>0 UNION ALL '
FROM INFORMATION_SCHEMA.COLUMNS
WHERE (COLUMN_NAME LIKE '%UID%' OR COLUMN_NAME LIKE '%Study%')
  AND DATA_TYPE IN ('varchar', 'nvarchar', 'char', 'text')
  AND TABLE_NAME NOT LIKE '%backup%'

IF LEN(@SQL3) > 10
BEGIN
    SET @SQL3 = LEFT(@SQL3, LEN(@SQL3) - 10)
    PRINT 'Searching UID columns for: ' + @StudyUID
    EXEC sp_executesql @SQL3
END

GO

-- ============================================================================
-- OPTION 4: Search by Patient ID
-- ============================================================================

DECLARE @PatientID NVARCHAR(100) = '%11043207%'  -- Change this
DECLARE @SQL4 NVARCHAR(MAX) = ''

SELECT @SQL4 = @SQL4 + 
    'SELECT ''' + TABLE_NAME + ''' AS TableName, ''' + COLUMN_NAME + ''' AS ColumnName, COUNT(*) AS MatchCount ' +
    'FROM [' + TABLE_NAME + '] WHERE [' + COLUMN_NAME + '] LIKE ''' + @PatientID + ''' HAVING COUNT(*)>0 UNION ALL '
FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME LIKE '%PATIENT%ID%'
  AND DATA_TYPE IN ('varchar', 'nvarchar', 'char', 'text')
  AND TABLE_NAME NOT LIKE '%backup%'

IF LEN(@SQL4) > 10
BEGIN
    SET @SQL4 = LEFT(@SQL4, LEN(@SQL4) - 10)
    PRINT 'Searching Patient ID columns for: ' + @PatientID
    EXEC sp_executesql @SQL4
END

GO

-- ============================================================================
-- OPTION 5: List all tables with record counts (overview)
-- ============================================================================

SELECT 
    t.TABLE_NAME,
    p.rows AS RecordCount
FROM INFORMATION_SCHEMA.TABLES t
INNER JOIN sys.partitions p ON p.object_id = OBJECT_ID(t.TABLE_NAME)
WHERE t.TABLE_TYPE = 'BASE TABLE'
  AND p.index_id IN (0, 1)
  AND p.rows > 0
ORDER BY p.rows DESC

GO

