#!/usr/bin/env python3
"""
Standalone debug script - no project imports required.
Just sends a test DICOM and searches the database.

Usage:
    python standalone_debug_send.py
"""

import os
import sys
import time
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    print("Warning: python-dotenv not installed, using system env vars")

import pydicom
import pydicom.uid
import numpy as np
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian
from pynetdicom import AE, AllStoragePresentationContexts


def main():
    print("=" * 70)
    print("STANDALONE DEBUG: SEND AND SEARCH TEST")
    print("=" * 70)
    
    # Get config from environment
    host = os.environ.get("COMPASS_HOST", "10.146.185.74")
    port = int(os.environ.get("COMPASS_PORT", "4242"))
    remote_ae = os.environ.get("COMPASS_AE_TITLE", "COMPASS")
    local_ae = os.environ.get("LOCAL_AE_TITLE", "LB-HTM-OPH")
    
    print(f"\n[CONFIGURATION]")
    print(f"  Compass Host: {host}")
    print(f"  Compass Port: {port}")
    print(f"  Called AE (Compass): {remote_ae}")
    print(f"  Calling AE (You): {local_ae}")
    
    # Create synthetic DICOM
    print(f"\n[CREATING SYNTHETIC DICOM]")
    
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    
    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
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
    ds.PatientName = f"STANDALONE^DEBUG_{timestamp}"
    ds.PatientID = f"STDEBUG{timestamp}"
    ds.StudyInstanceUID = pydicom.uid.generate_uid()
    ds.SeriesInstanceUID = pydicom.uid.generate_uid()
    
    # Set encoding flags
    ds.is_implicit_VR = False
    ds.is_little_endian = True
    
    print(f"  PatientName: {ds.PatientName}")
    print(f"  PatientID: {ds.PatientID}")
    print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
    
    # Build AE and send
    print(f"\n[SENDING TO COMPASS]")
    
    ae = AE(ae_title=local_ae)
    for context in list(AllStoragePresentationContexts)[:127]:
        ae.requested_contexts.append(context)
    
    try:
        assoc = ae.associate(host, port, ae_title=remote_ae)
        
        if not assoc.is_established:
            print(f"  ERROR: Association failed")
            return
        
        print(f"  Association established")
        
        status = assoc.send_c_store(ds)
        assoc.release()
        
        if status and status.Status == 0x0000:
            print(f"  Status: SUCCESS (0x0000)")
        else:
            print(f"  Status: {status}")
            
    except Exception as e:
        print(f"  ERROR: {e}")
        return
    finally:
        ae.shutdown()
    
    # Wait and search database
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
        import pyodbc
        
        db_server = os.environ.get("COMPASS_DB_SERVER", "ROCFDN019Q")
        db_name = os.environ.get("COMPASS_DB_NAME", "ODM")
        db_user = os.environ.get("COMPASS_DB_USER", "")
        db_password = os.environ.get("COMPASS_DB_PASSWORD", "")
        
        # Find ODBC driver
        drivers = [d for d in pyodbc.drivers() if 'SQL Server' in d]
        if not drivers:
            print(f"  ERROR: No SQL Server ODBC driver found")
            return
        driver = drivers[0]
        print(f"  Using driver: {driver}")
        
        conn_str = f"DRIVER={{{driver}}};SERVER={db_server};DATABASE={db_name};UID={db_user};PWD={db_password};TrustServerCertificate=yes"
        
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Search STUDY_MAPPING
        print(f"\n  Searching STUDY_MAPPING for 'STANDALONE'...")
        cursor.execute("""
            SELECT TOP 5 CREATION_TIME, ORIGINAL_PATIENT_NAME, ORIGINAL_STUDY_UID
            FROM STUDY_MAPPING
            WHERE ORIGINAL_PATIENT_NAME LIKE '%STANDALONE%'
            ORDER BY CREATION_TIME DESC
        """)
        rows = cursor.fetchall()
        if rows:
            print(f"  Found {len(rows)} records:")
            for row in rows:
                print(f"    {row.CREATION_TIME} | {row.ORIGINAL_PATIENT_NAME}")
        else:
            print(f"  No STANDALONE records in STUDY_MAPPING")
        
        # Search MCIE_ENTRIES
        print(f"\n  Searching MCIE_ENTRIES for 'STANDALONE'...")
        cursor.execute("""
            SELECT TOP 5 CREATION_TIME, DICOM_NAME, STUDY_UID
            FROM MCIE_ENTRIES
            WHERE DICOM_NAME LIKE '%STANDALONE%'
            ORDER BY CREATION_TIME DESC
        """)
        rows = cursor.fetchall()
        if rows:
            print(f"  Found {len(rows)} records:")
            for row in rows:
                print(f"    {row.CREATION_TIME} | {row.DICOM_NAME}")
        else:
            print(f"  No STANDALONE records in MCIE_ENTRIES")
        
        # Show recent records
        print(f"\n  Most recent STUDY_MAPPING records:")
        cursor.execute("""
            SELECT TOP 3 CREATION_TIME, ORIGINAL_PATIENT_NAME
            FROM STUDY_MAPPING
            ORDER BY CREATION_TIME DESC
        """)
        for row in cursor.fetchall():
            print(f"    {row.CREATION_TIME} | {row.ORIGINAL_PATIENT_NAME}")
        
        conn.close()
        
    except ImportError:
        print(f"  pyodbc not installed - skipping database search")
    except Exception as e:
        print(f"  Database error: {e}")
    
    print(f"\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  PatientName: {ds.PatientName}")
    print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
    print("=" * 70)


if __name__ == "__main__":
    main()

