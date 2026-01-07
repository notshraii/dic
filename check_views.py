#!/usr/bin/env python3
"""Check for database VIEWS (virtual tables)"""

from compass_db_query import CompassDatabaseClient, CompassDatabaseConfig

config = CompassDatabaseConfig.from_env()

print("=" * 80)
print("SEARCHING FOR DATABASE VIEWS")
print("=" * 80)

with CompassDatabaseClient(config) as client:
    # Query for views
    query = """
    SELECT TABLE_NAME, TABLE_TYPE
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'VIEW'
    ORDER BY TABLE_NAME
    """
    
    views = client.execute_query(query)
    
    if views:
        print(f"\nFound {len(views)} views:\n")
        for i, view in enumerate(views, 1):
            print(f"  {i:2d}. {view['TABLE_NAME']}")
        
        # Check if any views contain the target columns
        print("\n" + "=" * 80)
        print("CHECKING VIEWS FOR DICOM COLUMNS")
        print("=" * 80)
        
        target_columns = ['studyinstanceuid', 'patientname', 'patientid', 'accessionnumber']
        
        for view in views:
            view_name = view['TABLE_NAME']
            try:
                schema = client.get_table_schema(view_name)
                col_names_lower = [col['COLUMN_NAME'].lower() for col in schema]
                
                matches = [tc for tc in target_columns if tc in col_names_lower]
                
                if len(matches) > 0:
                    print(f"\n{view_name}: {len(matches)}/{len(target_columns)} columns match")
                    print(f"  Columns: {', '.join([col['COLUMN_NAME'] for col in schema])}")
                    
            except Exception as e:
                print(f"\n{view_name}: ERROR - {e}")
    else:
        print("\nNo views found in database")
        print("\nThe web UI might be using an API that joins multiple tables.")

