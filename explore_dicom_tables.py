#!/usr/bin/env python3
"""Explore tables that might contain DICOM tag data"""

from compass_db_query import CompassDatabaseClient, CompassDatabaseConfig

config = CompassDatabaseConfig.from_env()

# Tables that might contain DICOM data
candidate_tables = [
    "MCIE_ENTRIES",
    "HS_ENTRIES", 
    "ODM_STUDY_HASHES",
    "STUDY_MAPPING",
    "ODM_PARAMETERS",
]

with CompassDatabaseClient(config) as client:
    for table_name in candidate_tables:
        print("=" * 80)
        print(f"{table_name} TABLE SCHEMA")
        print("=" * 80)
        
        try:
            schema = client.get_table_schema(table_name)
            print(f"\nFound {len(schema)} columns:\n")
            
            # Show just column names for quick scan
            for col in schema:
                col_name = col['COLUMN_NAME']
                data_type = col['DATA_TYPE']
                print(f"  {col_name:40s} {data_type:15s}")
            
            # Check if it has StudyInstanceUID or similar
            col_names = [col['COLUMN_NAME'].lower() for col in schema]
            
            dicom_indicators = ['study', 'patient', 'accession', 'modality', 
                               'uid', 'name', 'series', 'instance']
            
            matches = [indicator for indicator in dicom_indicators 
                      if any(indicator in col_name for col_name in col_names)]
            
            if matches:
                print(f"\n  >> LIKELY DICOM TABLE - Contains: {', '.join(matches)}")
            
            print()
            
        except Exception as e:
            print(f"  ERROR: {e}\n")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print("\nLook for tables with columns like:")
    print("  - StudyInstanceUID / STUDY_INSTANCE_UID / StudyUID")
    print("  - PatientName / PATIENT_NAME")
    print("  - PatientID / PATIENT_ID")
    print("  - AccessionNumber / ACCESSION_NUMBER")
    print("  - Modality")

