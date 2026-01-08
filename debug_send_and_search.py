#!/usr/bin/env python3
"""
Debug script: Send a test image and search for it in the database.

This script:
1. Sends a single DICOM image with a unique patient name (DEBUGTEST^NOW)
2. Prints the Study UID
3. Waits for you to check the Compass dashboard
4. Searches the database for the record

Usage:
    python debug_send_and_search.py
"""

import os
import sys
import time
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).resolve().parent
load_dotenv(project_root / ".env")

import pydicom
import pydicom.uid

from data_loader import load_dataset
from dicom_sender import DicomSender
from config import DicomEndpointConfig, LoadProfileConfig
from metrics import PerfMetrics


def main():
    print("=" * 70)
    print("DEBUG: SEND AND SEARCH TEST")
    print("=" * 70)
    
    # Load config
    config = DicomEndpointConfig.from_env()
    print(f"\n[CONFIGURATION]")
    print(f"  Compass Host: {config.host}")
    print(f"  Compass Port: {config.port}")
    print(f"  Called AE (Compass): {config.remote_ae_title}")
    print(f"  Calling AE (You): {config.local_ae_title}")
    
    # Find a sample DICOM file - check multiple locations
    sample_file = None
    search_paths = [
        project_root / "dicom_samples",
        Path("dicom_samples"),
        Path.cwd() / "dicom_samples",
    ]
    
    for search_path in search_paths:
        if search_path.exists():
            sample_files = list(search_path.glob("*.dcm"))
            if sample_files:
                sample_file = sample_files[0]
                break
    
    if sample_file:
        print(f"\n[SOURCE FILE]")
        print(f"  Using: {sample_file}")
        ds = pydicom.dcmread(str(sample_file))
    else:
        # Create a synthetic DICOM if no samples found
        print(f"\n[SOURCE FILE]")
        print(f"  No sample files found - creating synthetic DICOM")
        
        import numpy as np
        from pydicom.dataset import Dataset, FileDataset
        from pydicom.uid import ExplicitVRLittleEndian
        
        # Create minimal valid DICOM
        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
        file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
        file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        
        ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
        ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
        ds.Modality = "CT"
        ds.Rows = 64
        ds.Columns = 64
        ds.BitsAllocated = 16
        ds.BitsStored = 12
        ds.HighBit = 11
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.PixelData = np.zeros((64, 64), dtype=np.uint16).tobytes()
    
    # Set unique identifiers
    timestamp = time.strftime("%H%M%S")
    ds.PatientName = f"DEBUGTEST^NOW_{timestamp}"
    ds.PatientID = f"DEBUG{timestamp}"
    ds.StudyInstanceUID = pydicom.uid.generate_uid()
    ds.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    
    print(f"\n[TEST DATA]")
    print(f"  PatientName: {ds.PatientName}")
    print(f"  PatientID: {ds.PatientID}")
    print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
    
    # Save to temp file and send
    print(f"\n[SENDING TO COMPASS]")
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.dcm', delete=False) as f:
            temp_file = f.name
            ds.save_as(f.name)
        
        load_profile = LoadProfileConfig()  # Use defaults
        sender = DicomSender(config, load_profile)
        metrics = PerfMetrics()
        dataset = load_dataset(Path(temp_file))
        sender._send_single_dataset(dataset, metrics)
        
        if metrics.successes > 0:
            print(f"  Status: SUCCESS")
            print(f"  Latency: {metrics.avg_latency_ms:.2f}ms")
        else:
            print(f"  Status: FAILED")
            print(f"  Errors: {metrics.failures}")
            
    finally:
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)
    
    # Now search for it
    print(f"\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    print(f"\n[STEP 1] Check Compass Web Dashboard:")
    print(f"  Search for: {ds.PatientName}")
    print(f"  Or Study UID: {ds.StudyInstanceUID}")
    
    print(f"\n[STEP 2] Waiting 5 seconds for Compass to process...")
    time.sleep(5)
    
    print(f"\n[STEP 3] Searching database...")
    
    try:
        from compass_db_query import CompassDatabaseClient, CompassDatabaseConfig
        
        db_config = CompassDatabaseConfig.from_env()
        print(f"  Database: {db_config.database} on {db_config.server}")
        
        with CompassDatabaseClient(db_config) as client:
            # Search by Study UID
            print(f"\n  Searching by Study UID...")
            result = client.get_job_by_study_uid(ds.StudyInstanceUID)
            
            if result:
                print(f"  FOUND in {result.get('_source_table')}!")
                print(f"    PatientName: {result.get('PatientName')}")
                print(f"    StudyDescription: {result.get('StudyDescription')}")
            else:
                print(f"  NOT FOUND by Study UID")
                
                # Search by patient name
                print(f"\n  Searching by patient name...")
                results = client.get_job_by_patient_name("DEBUGTEST")
                
                if results:
                    print(f"  Found {len(results)} DEBUGTEST records:")
                    for r in results[:5]:
                        print(f"    - {r.get('PatientName')} | {r.get('_source_table')}")
                else:
                    print(f"  No DEBUGTEST records found")
            
            # Show recent records
            print(f"\n  Recent STUDY_MAPPING records:")
            recent = client.execute_query("""
                SELECT TOP 3 CREATION_TIME, ORIGINAL_PATIENT_NAME, STUDY_DESC
                FROM STUDY_MAPPING
                ORDER BY CREATION_TIME DESC
            """)
            for r in recent:
                print(f"    {r.get('CREATION_TIME')} | {r.get('ORIGINAL_PATIENT_NAME')}")
            
            print(f"\n  Recent MCIE_ENTRIES records:")
            recent2 = client.execute_query("""
                SELECT TOP 3 MCIE_ID, DICOM_NAME
                FROM MCIE_ENTRIES
                ORDER BY MCIE_ID DESC
            """)
            for r in recent2:
                print(f"    {r.get('MCIE_ID')} | {r.get('DICOM_NAME')}")
                
    except Exception as e:
        print(f"  Database error: {e}")
    
    print(f"\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  PatientName sent: {ds.PatientName}")
    print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
    print(f"\nIf record appears in dashboard but not in database query,")
    print(f"the query logic needs adjustment.")
    print(f"\nIf record doesn't appear in dashboard either,")
    print(f"Compass is not storing images from this source.")
    print("=" * 70)


if __name__ == "__main__":
    main()


