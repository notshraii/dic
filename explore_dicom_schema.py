#!/usr/bin/env python3
"""
Comprehensive explorer to find DICOM data in database.

This will explore MCIE_ENTRIES and other key tables to find where
DICOM tags like PatientName, StudyInstanceUID, etc. are stored.
"""

from compass_db_query import CompassDatabaseClient, CompassDatabaseConfig

config = CompassDatabaseConfig.from_env()

# Tables most likely to contain DICOM data
candidate_tables = [
    "MCIE_ENTRIES",
    "HS_ENTRIES",
    "ODM_STUDY_HASHES",
    "STUDY_MAPPING",
]

print("=" * 80)
print("COMPREHENSIVE DICOM TABLE EXPLORATION")
print("=" * 80)

with CompassDatabaseClient(config) as client:
    for table_name in candidate_tables:
        print(f"\n\n{'=' * 80}")
        print(f"TABLE: {table_name}")
        print('=' * 80)
        
        try:
            # Get schema
            schema = client.get_table_schema(table_name)
            print(f"\n[SCHEMA] {len(schema)} columns:\n")
            
            for col in schema:
                col_name = col['COLUMN_NAME']
                data_type = col['DATA_TYPE']
                max_len = f"({col['CHARACTER_MAXIMUM_LENGTH']})" if col['CHARACTER_MAXIMUM_LENGTH'] else ""
                nullable = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
                print(f"  {col_name:40s} {data_type:15s}{max_len:10s} {nullable}")
            
            # Get sample data
            print(f"\n[SAMPLE DATA] Most recent 2 rows:\n")
            
            query = f"""
            SELECT TOP 2 *
            FROM {table_name}
            ORDER BY 1 DESC
            """
            
            results = client.execute_query(query)
            
            if results:
                for i, row in enumerate(results, 1):
                    print(f"Row {i}:")
                    for key, value in row.items():
                        value_str = str(value)[:80] if value else "NULL"
                        print(f"  {key:30s}: {value_str}")
                    print()
            else:
                print("  No data in table\n")
                
        except Exception as e:
            print(f"  ERROR: {e}\n")
    
    # Now try to find relationships
    print("\n\n" + "=" * 80)
    print("LOOKING FOR FOREIGN KEY RELATIONSHIPS")
    print("=" * 80)
    
    fk_query = """
    SELECT 
        FK.name AS ForeignKeyName,
        TP.name AS ParentTable,
        CP.name AS ParentColumn,
        TR.name AS ReferencedTable,
        CR.name AS ReferencedColumn
    FROM sys.foreign_keys FK
    INNER JOIN sys.foreign_key_columns FKC ON FK.object_id = FKC.constraint_object_id
    INNER JOIN sys.tables TP ON FKC.parent_object_id = TP.object_id
    INNER JOIN sys.columns CP ON FKC.parent_object_id = CP.object_id AND FKC.parent_column_id = CP.column_id
    INNER JOIN sys.tables TR ON FKC.referenced_object_id = TR.object_id
    INNER JOIN sys.columns CR ON FKC.referenced_object_id = CR.object_id AND FKC.referenced_column_id = CR.column_id
    WHERE TP.name IN ('ODM_ENTRIES', 'MCIE_ENTRIES', 'HS_ENTRIES', 'ODM_STUDY_HASHES')
       OR TR.name IN ('ODM_ENTRIES', 'MCIE_ENTRIES', 'HS_ENTRIES', 'ODM_STUDY_HASHES')
    ORDER BY TP.name, TR.name
    """
    
    try:
        relationships = client.execute_query(fk_query)
        if relationships:
            print("\nFound relationships:\n")
            for rel in relationships:
                print(f"  {rel['ParentTable']}.{rel['ParentColumn']}")
                print(f"    -> {rel['ReferencedTable']}.{rel['ReferencedColumn']}")
                print()
        else:
            print("\nNo explicit foreign keys found")
            print("Will need to infer relationships from column names")
    except Exception as e:
        print(f"\nCouldn't query foreign keys: {e}")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
print("\nNext: Review the output to identify:")
print("  1. Which table has DICOM tags (PatientName, PatientID, etc.)")
print("  2. How to link it to ODM_ENTRIES (the job table)")
print("  3. What JOIN query we need to write")

