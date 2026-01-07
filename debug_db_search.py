#!/usr/bin/env python3
"""
Debug script to search the database for recently sent studies.

Usage:
    python debug_db_search.py                     # Search for recent ZZTESTPATIENT records
    python debug_db_search.py "PATIENT_NAME"      # Search for specific patient name
    python debug_db_search.py --uid "1.2.3..."    # Search for specific Study UID
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
project_root = Path(__file__).resolve().parent
load_dotenv(project_root / ".env")

from compass_db_query import CompassDatabaseClient, CompassDatabaseConfig


def main():
    # Parse arguments
    search_term = "ZZTESTPATIENT"
    search_uid = None
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--uid" and len(sys.argv) > 2:
            search_uid = sys.argv[2]
        else:
            search_term = sys.argv[1]
    
    print("=" * 70)
    print("DATABASE DEBUG SEARCH")
    print("=" * 70)
    
    config = CompassDatabaseConfig.from_env()
    print(f"\nConnecting to: {config.server} / {config.database}")
    
    try:
        with CompassDatabaseClient(config) as client:
            print("Connected successfully!\n")
            
            if search_uid:
                # Search by UID
                print(f"Searching by Study UID: {search_uid}")
                print("-" * 70)
                
                result = client.get_job_by_study_uid(search_uid)
                if result:
                    print(f"FOUND in table: {result.get('_source_table')}")
                    for key, value in result.items():
                        if not key.startswith('_'):
                            print(f"  {key}: {value}")
                else:
                    print("NOT FOUND in any table")
                    
                    # Try raw search
                    print("\n--- Raw STUDY_MAPPING search ---")
                    raw_query = """
                    SELECT TOP 5 ORIGINAL_STUDY_UID, ORIGINAL_PATIENT_NAME, CREATION_TIME
                    FROM STUDY_MAPPING
                    ORDER BY CREATION_TIME DESC
                    """
                    results = client.execute_query(raw_query)
                    print(f"Latest 5 STUDY_MAPPING records:")
                    for r in results:
                        print(f"  {r}")
                    
                    print("\n--- Raw MCIE_ENTRIES search ---")
                    raw_query2 = """
                    SELECT TOP 5 STUDY_UID, DICOM_NAME, MCIE_ID
                    FROM MCIE_ENTRIES
                    ORDER BY MCIE_ID DESC
                    """
                    results2 = client.execute_query(raw_query2)
                    print(f"Latest 5 MCIE_ENTRIES records:")
                    for r in results2:
                        print(f"  {r}")
            else:
                # Search by patient name
                print(f"Searching by patient name: {search_term}")
                print("-" * 70)
                
                results = client.get_job_by_patient_name(search_term)
                print(f"Found {len(results)} records\n")
                
                for i, result in enumerate(results[:10], 1):
                    print(f"{i}. [{result.get('_source_table')}]")
                    print(f"   Patient: {result.get('PatientName') or result.get('OriginalPatientName')}")
                    print(f"   StudyUID: {result.get('StudyInstanceUID')}")
                    print(f"   StudyDesc: {result.get('StudyDescription', 'N/A')}")
                    if result.get('CreatedAt'):
                        print(f"   Created: {result.get('CreatedAt')}")
                    print()
            
            # Also show recent records
            print("\n" + "=" * 70)
            print("RECENT RECORDS (last 5 from each table)")
            print("=" * 70)
            
            print("\n--- STUDY_MAPPING (transformations) ---")
            recent_mapping = client.execute_query("""
                SELECT TOP 5 
                    CREATION_TIME,
                    ORIGINAL_PATIENT_NAME,
                    MAYO_PATIENT_NAME,
                    STUDY_DESC,
                    LEFT(ORIGINAL_STUDY_UID, 40) AS STUDY_UID_SHORT
                FROM STUDY_MAPPING
                ORDER BY CREATION_TIME DESC
            """)
            for r in recent_mapping:
                print(f"  {r.get('CREATION_TIME')} | {r.get('ORIGINAL_PATIENT_NAME')} | {r.get('STUDY_DESC')}")
            
            print("\n--- MCIE_ENTRIES (all received) ---")
            recent_mcie = client.execute_query("""
                SELECT TOP 5 
                    MCIE_ID,
                    DICOM_NAME,
                    LEFT(STUDY_UID, 40) AS STUDY_UID_SHORT
                FROM MCIE_ENTRIES
                ORDER BY MCIE_ID DESC
            """)
            for r in recent_mcie:
                print(f"  {r.get('MCIE_ID')} | {r.get('DICOM_NAME')} | {r.get('STUDY_UID_SHORT')}")
                
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

