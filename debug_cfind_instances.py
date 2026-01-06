"""
Debug script to query Compass at INSTANCE level instead of STUDY level.

This will show ALL instances (images) for a Study UID, which might match
what the web UI is showing.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from compass_cfind_client import CompassCFindClient, CompassCFindConfig
from pydicom.dataset import Dataset

def query_instances_for_study(study_uid: str):
    """
    Query for all INSTANCES (images) in a study.
    This queries at IMAGE level, not STUDY level.
    """
    print("="*80)
    print("C-FIND INSTANCE-LEVEL QUERY")
    print("="*80)
    
    config = CompassCFindConfig.from_env()
    
    print(f"\nConfiguration:")
    print(f"  Host: {config.host}")
    print(f"  Port: {config.port}")
    print(f"  Called AE: {config.remote_ae_title}")
    print(f"  Calling AE: {config.local_ae_title}")
    
    print(f"\nSearching for Study UID:")
    print(f"  {study_uid}")
    print(f"\nQuery Level: IMAGE (not STUDY)")
    print(f"This will return ALL instances/images in the study")
    
    client = CompassCFindClient(config)
    
    # Create IMAGE-level query
    query_ds = Dataset()
    query_ds.QueryRetrieveLevel = "IMAGE"  # Query at instance level
    query_ds.StudyInstanceUID = study_uid
    
    # Return attributes
    query_ds.SeriesInstanceUID = ""
    query_ds.SOPInstanceUID = ""
    query_ds.InstanceNumber = ""
    query_ds.PatientID = ""
    query_ds.StudyDescription = ""
    query_ds.SeriesDescription = ""
    query_ds.Modality = ""
    
    print(f"\nExecuting C-FIND query...")
    print("-"*80)
    
    try:
        results = client._execute_find(query_ds)
        
        print("-"*80)
        print(f"\n✓ Found {len(results)} INSTANCES (images)")
        
        if results:
            for i, result in enumerate(results, 1):
                print(f"\nInstance {i}:")
                print(f"  StudyInstanceUID: {result.StudyInstanceUID}")
                print(f"  SeriesInstanceUID: {result.SeriesInstanceUID}")
                print(f"  SOPInstanceUID: {result.SOPInstanceUID}")
                if hasattr(result, 'InstanceNumber'):
                    print(f"  InstanceNumber: {result.InstanceNumber}")
                if hasattr(result, 'SeriesDescription'):
                    print(f"  SeriesDescription: {result.SeriesDescription}")
        else:
            print("\nNo instances found")
            
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("\nComparison:")
    print(f"  STUDY-level query: Returns 1 result per study")
    print(f"  IMAGE-level query: Returns 1 result per image/instance")
    print(f"\nIf web UI shows 3 records, they might be 3 instances/images")
    print("="*80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_cfind_instances.py <StudyInstanceUID>")
        print("\nThis queries at IMAGE level to see all instances in a study")
        sys.exit(1)
    
    study_uid = sys.argv[1]
    query_instances_for_study(study_uid)

