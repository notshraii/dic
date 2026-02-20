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

queries = []

if study_uid:
    # Query 1: UID only at STUDY level
    ds1 = Dataset()
    ds1.QueryRetrieveLevel = "STUDY"
    ds1.StudyInstanceUID = study_uid
    ds1.PatientID = ""
    ds1.PatientName = ""
    ds1.StudyDate = ""
    ds1.AccessionNumber = ""
    ds1.NumberOfStudyRelatedInstances = ""
    queries.append((f"STUDY level, StudyInstanceUID={study_uid}", ds1))

    # Query 2: UID + PatientID at STUDY level
    ds2 = Dataset()
    ds2.QueryRetrieveLevel = "STUDY"
    ds2.StudyInstanceUID = study_uid
    ds2.PatientID = "11043207"
    ds2.PatientName = ""
    ds2.StudyDate = ""
    ds2.AccessionNumber = ""
    queries.append((f"STUDY level, StudyInstanceUID + PatientID=11043207", ds2))

    # Query 3: PATIENT level query
    ds3 = Dataset()
    ds3.QueryRetrieveLevel = "PATIENT"
    ds3.PatientID = "11043207"
    ds3.PatientName = ""
    queries.append(("PATIENT level, PatientID=11043207", ds3))
else:
    # Query 1: today's date
    ds1 = Dataset()
    ds1.QueryRetrieveLevel = "STUDY"
    ds1.StudyDate = datetime.now().strftime("%Y%m%d")
    ds1.StudyInstanceUID = ""
    ds1.PatientID = ""
    ds1.PatientName = ""
    ds1.AccessionNumber = ""
    queries.append((f"StudyDate={ds1.StudyDate} (today)", ds1))

    # Query 2: no date filter at all (finds all studies visible to this AE)
    ds2 = Dataset()
    ds2.QueryRetrieveLevel = "STUDY"
    ds2.StudyDate = ""
    ds2.StudyInstanceUID = ""
    ds2.PatientID = ""
    ds2.PatientName = ""
    ds2.AccessionNumber = ""
    queries.append(("No date filter (all studies)", ds2))

    # Query 3: by anonymized PatientID used in tests
    ds3 = Dataset()
    ds3.QueryRetrieveLevel = "STUDY"
    ds3.PatientID = "11043207"
    ds3.StudyDate = ""
    ds3.StudyInstanceUID = ""
    ds3.PatientName = ""
    ds3.AccessionNumber = ""
    queries.append(("PatientID=11043207 (anonymized test patient)", ds3))

    # Query 4: PATIENT level
    ds4 = Dataset()
    ds4.QueryRetrieveLevel = "PATIENT"
    ds4.PatientID = "11043207"
    ds4.PatientName = ""
    queries.append(("PATIENT level, PatientID=11043207", ds4))

for label, ds in queries:
    print(f"\n{'='*60}")
    print(f"Query: {label}")
    print(f"{'='*60}")
    found = False
    for name, sop in [
        ("Study Root", StudyRootQueryRetrieveInformationModelFind),
        ("Patient Root", PatientRootQueryRetrieveInformationModelFind),
    ]:
        results = run_cfind(ds, name, sop)
        if results:
            print(f"\n  {name} returned {len(results)} result(s).")
            found = True
            break
    if not found:
        print(f"  No results for: {label}")
