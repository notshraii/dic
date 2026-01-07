#!/usr/bin/env python3
"""Explore tables to find the one matching Compass web UI columns"""

from compass_db_query import CompassDatabaseClient, CompassDatabaseConfig

config = CompassDatabaseConfig.from_env()

# These column names are from the Compass web UI (Chrome inspector)
target_columns = [
    'studyInstanceUid',
    'patientName', 
    'patientId',
    'accessionNumber',
    'studyDate',
    'modalities',
    'sourceCallingAE',
    'sourceCalledAE',
    'destinationName',
    'sourceName',
    'createdTime',
    'state',
]

print("=" * 80)
print("SEARCHING FOR TABLE WITH COMPASS WEB UI COLUMNS")
print("=" * 80)
print(f"\nLooking for table with these columns:")
for col in target_columns:
    print(f"  - {col}")
print()

with CompassDatabaseClient(config) as client:
    # Get all tables
    all_tables = client.discover_tables()
    
    print(f"\nSearching through {len(all_tables)} tables...\n")
    
    best_match = None
    best_match_count = 0
    
    for table_name in all_tables:
        try:
            schema = client.get_table_schema(table_name)
            col_names = [col['COLUMN_NAME'] for col in schema]
            col_names_lower = [c.lower() for c in col_names]
            
            # Check how many target columns exist in this table
            matches = []
            for target_col in target_columns:
                target_lower = target_col.lower()
                if target_lower in col_names_lower:
                    # Find the actual case
                    actual_col = col_names[col_names_lower.index(target_lower)]
                    matches.append((target_col, actual_col))
            
            if len(matches) > 0:
                print(f"\n{table_name}: {len(matches)}/{len(target_columns)} columns match")
                for target, actual in matches:
                    print(f"  ✓ {target} -> {actual}")
                
                if len(matches) > best_match_count:
                    best_match_count = len(matches)
                    best_match = table_name
                    
        except Exception as e:
            pass  # Skip tables we can't access
    
    print("\n" + "=" * 80)
    print("RESULT")
    print("=" * 80)
    
    if best_match:
        print(f"\nBest match: {best_match} ({best_match_count}/{len(target_columns)} columns)")
        print(f"\nThis is the table to use in compass_db_query.py")
        
        # Show full schema of best match
        print(f"\n\nFull schema of {best_match}:")
        print("-" * 80)
        schema = client.get_table_schema(best_match)
        for col in schema:
            col_name = col['COLUMN_NAME']
            data_type = col['DATA_TYPE']
            max_len = f"({col['CHARACTER_MAXIMUM_LENGTH']})" if col['CHARACTER_MAXIMUM_LENGTH'] else ""
            nullable = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
            print(f"  {col_name:40s} {data_type:15s}{max_len:10s} {nullable}")
    else:
        print("\nNo matching table found!")
        print("The web UI might use a VIEW or the API transforms the data.")

