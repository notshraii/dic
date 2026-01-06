"""
Debug script to test C-FIND query with the exact Study UID from your failed test.

This will show you exactly what C-FIND is querying and what it's returning.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from compass_cfind_client import CompassCFindClient, CompassCFindConfig
from pynetdicom import debug_logger

# Enable detailed pynetdicom logging
debug_logger()

def debug_cfind_query(study_uid: str):
    """
    Debug C-FIND query for a specific Study UID.
    Shows exactly what's being sent and received.
    """
    print("="*80)
    print("C-FIND DEBUG QUERY")
    print("="*80)
    
    # Load config from environment
    config = CompassCFindConfig.from_env()
    
    print(f"\nConfiguration:")
    print(f"  Host: {config.host}")
    print(f"  Port: {config.port}")
    print(f"  Called AE (Compass): {config.remote_ae_title}")
    print(f"  Calling AE (Us): {config.local_ae_title}")
    print(f"  Query Model: {config.query_model}")
    
    print(f"\nSearching for Study UID:")
    print(f"  {study_uid}")
    
    # Create client
    client = CompassCFindClient(config)
    
    # Try to find the study
    print(f"\nExecuting C-FIND query...")
    print("-"*80)
    
    try:
        result = client.find_study_by_uid(study_uid)
        
        print("-"*80)
        
        if result:
            print(f"\n✓ SUCCESS: Study found!")
            print(f"\nReturned attributes:")
            
            study_dict = client.dataset_to_dict(result)
            for key, value in study_dict.items():
                if value:
                    print(f"  {key}: {value}")
        else:
            print(f"\n✗ FAILED: Study NOT found")
            print(f"\nThis means C-FIND query returned no results.")
            print(f"\nPossible reasons:")
            print(f"  1. AE Title '{config.local_ae_title}' doesn't have C-FIND permissions")
            print(f"  2. Compass filters queries by Calling AE Title")
            print(f"  3. C-FIND queries a different database than web UI")
            print(f"  4. Study not yet indexed for C-FIND (timing issue)")
            print(f"  5. Query parameters don't match Compass requirements")
            
            print(f"\nTry with different Calling AE Title:")
            print(f"  export LOCAL_AE_TITLE=PERF_SENDER")
            print(f"  python debug_cfind_study.py {study_uid}")
            
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_cfind_study.py <StudyInstanceUID>")
        print("\nExample:")
        print("  python debug_cfind_study.py 1.2.826.0.1.3680043.8.498.12345678901234567890")
        sys.exit(1)
    
    study_uid = sys.argv[1]
    debug_cfind_query(study_uid)

