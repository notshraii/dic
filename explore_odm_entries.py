#!/usr/bin/env python3
"""Quick script to explore ODM_ENTRIES table schema"""

from compass_db_query import CompassDatabaseClient, CompassDatabaseConfig

config = CompassDatabaseConfig.from_env()

with CompassDatabaseClient(config) as client:
    print("=" * 80)
    print("ODM_ENTRIES TABLE SCHEMA")
    print("=" * 80)
    
    schema = client.get_table_schema("ODM_ENTRIES")
    print(f"\nFound {len(schema)} columns:\n")
    
    for col in schema:
        nullable = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
        data_type = col['DATA_TYPE']
        max_len = f"({col['CHARACTER_MAXIMUM_LENGTH']})" if col['CHARACTER_MAXIMUM_LENGTH'] else ""
        col_name = col['COLUMN_NAME']
        print(f"  {col_name:40s} {data_type:15s}{max_len:10s} {nullable}")
    
    print("\n" + "=" * 80)
    print("SAMPLE DATA FROM ODM_ENTRIES (most recent 3 rows)")
    print("=" * 80)
    
    query = """
    SELECT TOP 3 *
    FROM ODM_ENTRIES
    ORDER BY ID DESC
    """
    
    results = client.execute_query(query)
    
    if results:
        print(f"\nFound {len(results)} recent entries\n")
        for i, row in enumerate(results, 1):
            print(f"Row {i}:")
            for key, value in row.items():
                # Truncate long values
                value_str = str(value)[:100] if value else "NULL"
                print(f"  {key:30s}: {value_str}")
            print()
    else:
        print("\nNo data found in ODM_ENTRIES")

