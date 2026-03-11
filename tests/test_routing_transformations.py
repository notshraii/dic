# tests/test_routing_transformations.py

"""
Tests that verify Compass applies DICOM tag transformations correctly using C-STORE and C-FIND.
"""

from __future__ import annotations

import os
from datetime import datetime

import pytest

def _accession(suffix: str) -> str:
    """Generate a unique AccessionNumber per test run using timestamp + suffix."""
    return f"TRFM-{datetime.now().strftime('%Y%m%d%H%M%S')}-{suffix}"

from data_loader import load_dataset
from metrics import PerfMetrics
from tests.conftest import manual_verification_required, verify_study_arrived


# ============================================================================
# Test Case Definitions
# ============================================================================

# Define transformation test cases here
# Each test case specifies input attributes and expected output
TRANSFORMATION_TEST_CASES = [
    {
        'name': 'OPV_GPA_VisualFields',
        'description': 'OPV modality with GPA series description should set Visual Fields study description',
        'route': 'HTM_OPH',
        'input': {
            'modality': 'OPV',
            'series_description': 'GPA',
            'accession_number': _accession('OPV-GPA'),
        },
        'expected': {
            'study_description': 'Visual Fields (VF) GPA',
        }
    },
    {
        'name': 'OPV_SFA_VisualFields',
        'description': 'OPV modality with SFA series description should set Visual Fields study description',
        'route': 'HTM_OPH',
        'input': {
            'modality': 'OPV',
            'series_description': 'SFA',
            'accession_number': _accession('OPV-SFA'),
        },
        'expected': {
            'study_description': 'Visual Fields (VF) SFA',
        }
    },
    {
        'name': 'OPV_Mixed_VisualFields',
        'description': 'OPV modality with mixed series description (GPA or SFA) should set Visual Fields',
        'route': 'HTM_OPH',
        'input': {
            'modality': 'OPV',
            'series_description': 'Mixed Analysis',
            'accession_number': _accession('OPV-MIX'),
        },
        'expected': {
            'study_description': 'Visual Fields (VF)',
        }
    },
    {
        'name': 'OPT_OCT',
        'description': 'OPT modality for Optical Coherence Tomography',
        'route': 'HTM_OPH',
        'input': {
            'modality': 'OPT',
            'accession_number': _accession('OPT'),
        },
        'expected': {
            'study_description': 'Optical Coherence Tomography (OCT)',
        }
    },
    # Supported modalities for transformation rules: OPT, OP, OPV, OAM, OPM, US
    # OT and DOC are NOT supported -- no transformation rules exist for them.
    # Add more test cases here following the same pattern:
    # {
    #     'name': 'TestCaseName',
    #     'description': 'Human-readable description',
    #     'route': 'HTM_OPH',  # Route name from .env (HTM_GI, HTM_OPH, HTM_ORTHO)
    #     'input': {
    #         'modality': 'CT',
    #         'series_description': 'BRAIN',
    #         'accession_number': _accession('YOUR-SUFFIX'),
    #         # Add any other DICOM attributes in snake_case
    #     },
    #     'expected': {
    #         'study_description': 'Expected Study Description',
    #         # Add other expected transformations
    #     }
    # },
]


# ============================================================================
# Test Implementation
# ============================================================================

@pytest.mark.integration
@pytest.mark.parametrize("test_case", TRANSFORMATION_TEST_CASES, ids=lambda tc: tc['name'])
def test_routing_transformation(
    test_case: dict,
    test_dicom_with_attributes,
    dicom_sender,
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    Test Compass routing transformations based on input attributes.
    
    This test:
    1. Creates a DICOM file with specified input attributes
    2. Sends it to Compass using the specified AE Title
    3. Verifies the send was successful
    4. Automatically verifies transformations using C-FIND
    
    To add new test cases:
    - Add entries to TRANSFORMATION_TEST_CASES list above
    - Run: pytest tests/test_routing_transformations.py -v
    
    Automated verification:
    - Uses C-FIND to query Compass for the study
    - Verifies expected transformations were applied
    - Test fails if transformations don't match expected values
    """
    test_name = test_case['name']
    test_desc = test_case['description']
    
    print(f"\n{'='*70}")
    print(f"TEST CASE: {test_name}")
    print(f"{'='*70}")
    print(f"Description: {test_desc}")
    
    # Create test file with input attributes
    test_file_path, test_dataset = test_dicom_with_attributes(**test_case['input'])
    
    try:
        # Resolve AE titles from route config
        route_name = test_case['route']
        route_aes = dicom_sender.endpoint.routes.get(route_name)
        assert route_aes is not None, (
            f"Route '{route_name}' not found in config. "
            f"Available routes: {list(dicom_sender.endpoint.routes.keys())}. "
            f"Check .env for REMOTE_AE_{route_name} and LOCAL_AE_{route_name}."
        )
        remote_ae, local_ae = route_aes

        # Display test configuration
        print(f"\n[CONFIGURATION]")
        print(f"  Route: {route_name}")
        print(f"  Called AE (remote): {remote_ae}")
        print(f"  Calling AE (local): {local_ae}")
        print(f"\n[INPUT ATTRIBUTES]")
        for attr_name, attr_value in test_case['input'].items():
            display_name = ''.join(word.capitalize() for word in attr_name.split('_'))
            print(f"  {display_name}: {attr_value}")
        
        print(f"\n[EXPECTED TRANSFORMATIONS]")
        for attr_name, attr_value in test_case['expected'].items():
            display_name = ''.join(word.capitalize() for word in attr_name.split('_'))
            print(f"  {display_name}: '{attr_value}'")
        
        print(f"\n[TEST IDENTIFIERS]")
        print(f"  StudyInstanceUID: {test_dataset.StudyInstanceUID}")
        print(f"  SeriesInstanceUID: {test_dataset.SeriesInstanceUID}")
        print(f"  SOPInstanceUID: {test_dataset.SOPInstanceUID}")
        
        # Override both AE titles to match the test case's route
        original_local_ae = dicom_sender.endpoint.local_ae_title
        original_remote_ae = dicom_sender.endpoint.remote_ae_title
        dicom_sender.endpoint.local_ae_title = local_ae
        dicom_sender.endpoint.remote_ae_title = remote_ae
        
        try:
            # Send to Compass
            print(f"\n[STEP 1: SENDING TO COMPASS]")
            print(f"  Compass Host: {dicom_sender.endpoint.host}")
            print(f"  Compass Port: {dicom_sender.endpoint.port}")
            
            ds = load_dataset(test_file_path)
            dicom_sender._send_single_dataset(ds, metrics)
            
            # Verify send was successful
            assert metrics.successes == 1, \
                f"Send failed: {metrics.failures} failures, error rate: {metrics.error_rate:.1%}"
            
            print(f"  Status: SUCCESS")
            print(f"  Latency: {metrics.avg_latency_ms:.2f}ms")
            
            # Automated verification via C-FIND
            print(f"\n[STEP 2: AUTOMATED VERIFICATION VIA C-FIND]")
            patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
            query_and_verify(
                cfind_client, perf_config,
                str(test_dataset.StudyInstanceUID), test_case['expected'],
                patient_id=patient_id,
            )
            
            print(f"\n[RESULT: TEST COMPLETE]")
            
        finally:
            dicom_sender.endpoint.local_ae_title = original_local_ae
            dicom_sender.endpoint.remote_ae_title = original_remote_ae
    
    finally:
        # Cleanup temp file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)


# ============================================================================
# Automated Verification via C-FIND
# ============================================================================

def query_and_verify(cfind_client, perf_config, study_uid: str, expected_attributes: dict, patient_id: str = None):
    """
    Query Compass via C-FIND and verify transformations were applied.

    Args:
        cfind_client: CompassCFindClient instance (or None).
        perf_config: TestConfig with timeout / poll settings.
        study_uid: StudyInstanceUID to query.
        expected_attributes: Dict of expected attribute values (snake_case keys).
        patient_id: Optional PatientID for fallback PATIENT-level C-FIND query.
    """
    print(f"\n  [AUTOMATED VERIFICATION VIA C-FIND]")

    if cfind_client is None:
        pytest.skip("C-FIND verification is required for transformation tests (set CFIND_VERIFY=true)")

    study_data = verify_study_arrived(cfind_client, study_uid, perf_config, patient_id=patient_id)
    strategy = getattr(cfind_client, 'last_find_strategy', None) or 'unknown'

    # STUDY-level: verify each expected attribute

    for attr_name, expected_value in expected_attributes.items():
        # Convert snake_case to PascalCase DICOM attribute name
        dicom_attr = ''.join(word.capitalize() for word in attr_name.split('_'))

        actual_value = study_data.get(dicom_attr, None)

        if actual_value is None:
            with manual_verification_required(
                f"{dicom_attr} transformation -- verify manually on Compass server. "
                f"C-FIND strategy '{strategy}' did not return this attribute. "
                f"Expected: '{expected_value}' for study {study_uid}"
            ):
                assert False, (
                    f"{dicom_attr} not returned by C-FIND (strategy: {strategy}). "
                    f"Expected value: '{expected_value}'. "
                    f"C-FIND response keys: {list(study_data.keys())}. "
                    f"Open Compass admin UI and verify {dicom_attr}='{expected_value}' "
                    f"for StudyInstanceUID: {study_uid}"
                )
        elif str(actual_value).strip() == str(expected_value).strip():
            print(f"    {dicom_attr}: '{actual_value}' - MATCH")
        else:
            print(f"    {dicom_attr}: '{actual_value}' - MISMATCH")
            print(f"      Expected: '{expected_value}'")
            raise AssertionError(
                f"{dicom_attr} mismatch: expected '{expected_value}', got '{actual_value}'"
            )

    print(f"\n  C-FIND VERIFICATION PASSED - All transformations correct!")


# ============================================================================
# Test: PatientID / OtherPatientIDs Swap (CSN vs MRN coercion)
# ============================================================================

@pytest.mark.integration
def test_patient_id_coerced_from_other_patient_ids(
    single_dicom_file,
    dicom_sender,
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    COMPASS_Transformation_PatientID_Coercion

    Send a study via the LB-HTM-IM route (non-ordered, same as IIMS test) with
    an "AC"-prefixed value in PatientID (0010,0020) and the MRN in
    OtherPatientIDs (0010,1000). The "AC" prefix triggers a Compass filter that
    copies OtherPatientIDs into PatientID (Swap CSN for MRN).

    For the study to be ROUTED to the destination (not just Inbound Logging
    Only), use a real CSN/MRN pair from your system: set TEST_AC_CSN and
    TEST_MRN in .env. Without them, the test uses placeholder values; the send
    succeeds but Compass may not route the study, so C-FIND verification is
    skipped.

    Route: SCU=TEAM_SCP -> SCP=LB-HTM-IM (same as IIMS tests)

    Test Steps:
    1. Load a DICOM file
    2. Set PatientID (0010,0020) = "AC" + CSN (triggers coercion)
    3. Set OtherPatientIDs (0010,1000) = MRN value
    4. Send via LB-HTM-IM route
    5. If TEST_AC_CSN and TEST_MRN are set: C-FIND verify PatientID == MRN
    """
    import os
    from pydicom.uid import generate_uid

    ds = load_dataset(single_dicom_file)

    study_uid = generate_uid()
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()

    # Optional: real CSN/MRN from .env so Compass routes the study to destination
    env_csn = os.getenv("TEST_AC_CSN", "").strip()
    env_mrn = os.getenv("TEST_MRN", "").strip()
    use_real_ids = bool(env_csn and env_mrn)

    # Optional: set TEST_USE_AC_PREFIX=0 or false to omit "AC" so the study routes
    # (like IIMS test). When AC is present, Compass may not route without a real CSN.
    use_ac_prefix = os.getenv("TEST_USE_AC_PREFIX", "1").strip().lower() not in ("0", "false", "no", "")

    # Keep the original PatientID from the file for reference / fallback
    original_patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None

    if use_real_ids:
        # CSN may be provided with or without "AC" prefix
        csn_part = env_csn if not env_csn.upper().startswith("AC") else env_csn[2:].lstrip()
        ac_csn_value = f"AC{csn_part}" if not env_csn.upper().startswith("AC") else env_csn
        mrn_value = env_mrn
    else:
        timestamp = datetime.now().strftime('%H%M%S')
        ac_csn_value = f"AC{timestamp}"
        mrn_value = f"MRN{timestamp}"

    # Blank AccessionNumber (like IIMS test) so the non-ordered route accepts the study
    ds.AccessionNumber = ''

    if not use_ac_prefix:
        # No AC: keep everything from the original file (like IIMS test) so the
        # study routes. Do NOT set OtherPatientIDs -- that may trigger Compass
        # filters that prevent routing.
        patient_id_value = original_patient_id
        mrn_value = original_patient_id
    else:
        patient_id_value = ac_csn_value
        ds.PatientID = patient_id_value        # (0010,0020)
        ds.OtherPatientIDs = mrn_value         # (0010,1000)

    # Use the IIMS route: SCU=TEAM_SCP, SCP=LB-HTM-IM
    iims_scu = perf_config.integration.iims_scu_ae_title
    iims_scp = perf_config.integration.iims_scp_ae_title
    default_local_ae = dicom_sender.endpoint.local_ae_title
    default_remote_ae = dicom_sender.endpoint.remote_ae_title

    print(f"\n{'='*70}")
    print(f"PATIENT ID COERCION TEST (OtherPatientIDs -> PatientID)")
    print(f"{'='*70}")
    print(f"  StudyInstanceUID      : {study_uid}")
    print(f"  PatientID  (0010,0020): {patient_id_value}  {'(AC-prefixed -- triggers coercion)' if use_ac_prefix else '(no AC -- study should route)'}")
    print(f"  OtherPatientIDs (0010,1000): {mrn_value}  (MRN)")
    if use_ac_prefix:
        print(f"  Expected PatientID after Compass: {mrn_value}  (coerced from 0010,1000)")
    else:
        print(f"  Expected PatientID after Compass: {mrn_value}  (unchanged; Swap filter not triggered)")
    print(f"  Route: SCU={iims_scu} -> SCP={iims_scp}")
    if not use_real_ids and use_ac_prefix:
        print(f"  Note: TEST_AC_CSN/TEST_MRN not set; study may be Inbound Logging Only.")
        print(f"        Set both in .env to a real CSN/MRN pair to verify routing.")
    if not use_ac_prefix:
        print(f"  Note: TEST_USE_AC_PREFIX=0; AC omitted so study should route to MIDIA.")

    # Override AE titles for the LB-HTM-IM route
    dicom_sender.endpoint.local_ae_title = iims_scu
    dicom_sender.endpoint.remote_ae_title = iims_scp

    try:
        # Send to Compass
        print(f"\n[STEP 1: SENDING TO COMPASS via {iims_scp}]")
        dicom_sender._send_single_dataset(ds, metrics)

        assert metrics.successes == 1, (
            f"Send failed: {metrics.failures} failure(s), "
            f"error rate: {metrics.error_rate:.1%}"
        )
        print(f"  Status : SUCCESS")
        print(f"  Latency: {metrics.avg_latency_ms:.2f}ms")

        # C-FIND verification when we expect the study to have been routed
        print(f"\n[STEP 2: C-FIND VERIFICATION]")

        # Skip only when we used AC prefix and no real CSN/MRN (study likely not routed)
        if use_ac_prefix and not use_real_ids:
            pytest.skip(
                "TEST_AC_CSN and TEST_MRN not set in .env. With AC prefix and placeholder "
                "values Compass may not route the study (Inbound Logging Only). Set both to "
                "a real CSN/MRN pair, or set TEST_USE_AC_PREFIX=0 to test routing without AC."
            )

        if cfind_client is None:
            pytest.skip(
                "C-FIND verification is required for this test (set CFIND_VERIFY=true)"
            )

        cfind_study = verify_study_arrived(
            cfind_client, str(study_uid), perf_config, patient_id=mrn_value,
        )

        actual_patient_id = cfind_study.get('PatientID', '') if cfind_study else ''

        print(f"\n  [CHECK]")
        print(f"    Sent PatientID (0010,0020)        : {patient_id_value}")
        print(f"    Sent OtherPatientIDs (0010,1000)  : {mrn_value} (MRN)")
        print(f"    Received PatientID via C-FIND     : {actual_patient_id}")

        if use_ac_prefix:
            with manual_verification_required(
                f"PatientID coercion -- verify on Compass that PatientID "
                f"for study {study_uid} equals '{mrn_value}' (coerced from "
                f"OtherPatientIDs). Sent PatientID was '{patient_id_value}'."
            ):
                assert actual_patient_id == mrn_value, (
                    f"PatientID coercion failed: expected '{mrn_value}' "
                    f"(from OtherPatientIDs) but C-FIND returned '{actual_patient_id}'. "
                    f"Original PatientID sent was '{patient_id_value}'. "
                    f"Route: SCU={iims_scu}, SCP={iims_scp}."
                )
            print(f"    Result: PatientID correctly coerced from OtherPatientIDs")
        else:
            assert actual_patient_id == mrn_value, (
                f"Expected PatientID '{mrn_value}' (no coercion), got '{actual_patient_id}'"
            )
            print(f"    Result: Study routed; PatientID unchanged (no AC prefix).")

        print(f"\n[DONE] PatientID coercion test complete")

    finally:
        dicom_sender.endpoint.local_ae_title = default_local_ae
        dicom_sender.endpoint.remote_ae_title = default_remote_ae


# ============================================================================
# Summary Test - Run All Transformation Tests
# ============================================================================

@pytest.mark.integration
def test_all_transformations_summary(
    test_dicom_with_attributes,
    dicom_sender,
):
    """
    Summary test that displays all configured transformation test cases.
    
    This test doesn't send anything - it just documents what will be tested.
    Run this first to see what transformation rules are being validated.
    """
    print(f"\n{'='*70}")
    print(f"COMPASS ROUTING TRANSFORMATION TEST SUITE")
    print(f"{'='*70}")
    print(f"\nTotal test cases configured: {len(TRANSFORMATION_TEST_CASES)}")
    print(f"\nTest cases:")
    
    for i, test_case in enumerate(TRANSFORMATION_TEST_CASES, 1):
        route_name = test_case['route']
        route_aes = dicom_sender.endpoint.routes.get(route_name, (None, None))
        remote_ae, local_ae = route_aes
        print(f"\n{i}. {test_case['name']}")
        print(f"   Description: {test_case['description']}")
        print(f"   Route: {route_name} (called={remote_ae}, calling={local_ae})")
        print(f"   Input: {', '.join(f'{k}={v}' for k, v in test_case['input'].items())}")
        print(f"   Expected: {', '.join(f'{k}={v}' for k, v in test_case['expected'].items())}")
    
    print(f"\n{'='*70}")
    print(f"To run all transformation tests:")
    print(f"  pytest tests/test_routing_transformations.py::test_routing_transformation -v")
    print(f"\nTo run a specific test case:")
    print(f"  pytest tests/test_routing_transformations.py::test_routing_transformation[OPV_GPA_VisualFields] -v")
    print(f"{'='*70}\n")


# ============================================================================
# Helper: Add New Test Case Interactively
# ============================================================================

def add_test_case_template():
    """
    Template for adding new test cases.
    
    Copy this structure and add to TRANSFORMATION_TEST_CASES list:
    """
    new_test_case = {
        'name': 'YourTestCaseName',  # Short identifier (no spaces)
        'description': 'Human-readable description of what this tests',
        'route': 'HTM_OPH',  # Route name from .env (HTM_GI, HTM_OPH, HTM_ORTHO)
        'input': {
            # Input DICOM attributes (snake_case)
            'modality': 'XX',
            'series_description': 'Description',
            'institution_name': 'Hospital Name',
            # Add more attributes as needed
        },
        'expected': {
            # Expected output after Compass transformation (snake_case)
            'study_description': 'Expected Study Description',
            # Add more expected transformations
        }
    }
    return new_test_case

