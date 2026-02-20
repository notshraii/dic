"""
Raw C-FIND diagnostic script with full pynetdicom debug logging.

Shows the exact DICOM protocol exchange so you can see what the server returns.

Usage:
    # Test broad query (all studies today - checks AE authorization):
    python3 debug_cfind_raw.py

    # Test specific study UID:
    python3 debug_cfind_raw.py <StudyInstanceUID>
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pynetdicom import AE, debug_logger
from pynetdicom.sop_class import (
    StudyRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelFind,
)
from pydicom.dataset import Dataset

load_dotenv(Path(__file__).resolve().parent / ".env")

# Full pynetdicom protocol debug output
debug_logger()

HOST = os.getenv("CFIND_HOST") or os.getenv("COMPASS_HOST", "127.0.0.1")
PORT = int(os.getenv("CFIND_PORT") or os.getenv("COMPASS_PORT", "11112"))
CALLED_AE = os.getenv("CFIND_AE_TITLE") or os.getenv("COMPASS_AE_TITLE", "COMPASS")
ROUTE = os.getenv("COMPASS_ROUTE", "")
CALLING_AE_MAP = {
    "HTM_GI": os.getenv("LOCAL_AE_HTM_GI", "HTM-GI"),
    "HTM_OPH": os.getenv("LOCAL_AE_HTM_OPH", "HTM-OPH"),
    "HTM_ORTHO": os.getenv("LOCAL_AE_HTM_ORTHO", "HTM-ORTHO"),
}
CALLING_AE = (
    os.getenv("CFIND_LOCAL_AE_TITLE")
    or CALLING_AE_MAP.get(ROUTE)
    or os.getenv("LOCAL_AE_TITLE", "QUERY_SCU")
)

print("=" * 60)
print("C-FIND RAW DIAGNOSTIC")
print("=" * 60)
print(f"  Server   : {HOST}:{PORT}")
print(f"  Called AE: {CALLED_AE}")
print(f"  Calling AE: {CALLING_AE}")
print(f"  Route    : {ROUTE}")
print("=" * 60)


def run_cfind(ds: Dataset, model_name: str, model_sop):
    ae = AE(ae_title=CALLING_AE)
    ae.add_requested_context(model_sop)

    print(f"\n--- Trying {model_name} ---")
    assoc = ae.associate(HOST, PORT, ae_title=CALLED_AE)
    if not assoc.is_established:
        print(f"  Association FAILED for {model_name}")
        return []

    results = []
    responses = assoc.send_c_find(ds, model_sop)
    for status, identifier in responses:
        if status:
            print(f"  Status: 0x{status.Status:04X}")
            if status.Status in (0xFF00, 0xFF01):
                results.append(identifier)
                print(f"  Match: {identifier}")
            elif status.Status == 0x0000:
                print(f"  C-FIND complete. Total matches: {len(results)}")
            else:
                print(f"  Unexpected status: 0x{status.Status:04X}")
        else:
            print("  No status returned (timeout or abort)")
    assoc.release()
    return results


study_uid = sys.argv[1] if len(sys.argv) > 1 else None

if study_uid:
    print(f"\nQuerying for specific StudyInstanceUID: {study_uid}")
    ds = Dataset()
    ds.QueryRetrieveLevel = "STUDY"
    ds.StudyInstanceUID = study_uid
    ds.PatientID = ""
    ds.PatientName = ""
    ds.StudyDate = ""
    ds.AccessionNumber = ""
    ds.NumberOfStudyRelatedInstances = ""
else:
    print(f"\nBroad query: all studies for today ({datetime.now().strftime('%Y%m%d')})")
    ds = Dataset()
    ds.QueryRetrieveLevel = "STUDY"
    ds.StudyDate = datetime.now().strftime("%Y%m%d")
    ds.StudyInstanceUID = ""
    ds.PatientID = ""
    ds.PatientName = ""
    ds.AccessionNumber = ""

for name, sop in [
    ("Study Root", StudyRootQueryRetrieveInformationModelFind),
    ("Patient Root", PatientRootQueryRetrieveInformationModelFind),
]:
    results = run_cfind(ds, name, sop)
    if results:
        print(f"\n  {name} returned {len(results)} result(s) - stopping here.")
        break
else:
    print("\nNo results from either query model.")
    print("Check the debug output above for the server's raw response.")
