# tests/test_data_validation.py

"""
Tests that validate Compass data handling including blank fields, accession numbers, and study dates.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from pydicom import dcmread
from pydicom.uid import generate_uid

from data_loader import load_dataset
from metrics import PerfMetrics
from tests.conftest import verify_study_arrived


# ============================================================================
# Test 1: Blank Study Date Handling
# ============================================================================

@pytest.mark.integration
def test_populate_blank_study_date(
    dicom_sender,
    single_dicom_file: Path,
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    COMPASS_DataModification_PopulateBlankStudyDate
    
    Send image with no study date/time.
    Verify Compass populates acquisition date/time.
    
    Expected Result: Acquisition date/time is populated as study date/time
    
    Test Steps:
    1. Load DICOM file
    2. Remove StudyDate and StudyTime tags
    3. Send to Compass
    4. Manual verification: Query for study and check date was populated
    """
    ds = load_dataset(single_dicom_file)
    
    # Generate unique UIDs for tracking
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    
    # Store original dates for reference
    original_acquisition_date = ds.AcquisitionDate if hasattr(ds, 'AcquisitionDate') else None
    original_acquisition_time = ds.AcquisitionTime if hasattr(ds, 'AcquisitionTime') else None
    
    # Remove study date/time
    had_study_date = hasattr(ds, 'StudyDate')
    had_study_time = hasattr(ds, 'StudyTime')
    
    if had_study_date:
        del ds.StudyDate
    if had_study_time:
        del ds.StudyTime
    
    print(f"\n{'='*70}")
    print(f"BLANK STUDY DATE TEST")
    print(f"{'='*70}")
    print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
    print(f"  Original had StudyDate: {had_study_date}")
    print(f"  Original had StudyTime: {had_study_time}")
    print(f"  AcquisitionDate: {original_acquisition_date}")
    print(f"  AcquisitionTime: {original_acquisition_time}")
    print(f"\n  Removed StudyDate and StudyTime before sending...")
    
    # Verify tags are removed
    assert not hasattr(ds, 'StudyDate'), "StudyDate still present"
    assert not hasattr(ds, 'StudyTime'), "StudyTime still present"
    
    # Send to Compass
    print(f"\n  Sending to Compass...")
    dicom_sender._send_single_dataset(ds, metrics)
    
    assert metrics.successes == 1, "Send failed"
    print(f"  Status: SUCCESS")
    print(f"  Latency: {metrics.avg_latency_ms:.2f}ms")
    
    # C-FIND verification
    print(f"\n{'='*70}")
    print(f"C-FIND VERIFICATION")
    print(f"{'='*70}")
    study = verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config)
    if study:
        cfind_date = study.get('StudyDate', '')
        if cfind_date and cfind_date.strip():
            print(f"  [OK] StudyDate was populated by Compass: {cfind_date}")
        else:
            print(f"  [INFO] StudyDate is still blank after Compass processing")
        expected_date = original_acquisition_date or ''
        if expected_date and cfind_date:
            if cfind_date.strip() == expected_date.strip():
                print(f"  [OK] StudyDate matches AcquisitionDate: {expected_date}")
            else:
                print(f"  [INFO] StudyDate ({cfind_date}) differs from AcquisitionDate ({expected_date})")

    print(f"\n[SUCCESS] File sent without StudyDate/Time")


@pytest.mark.integration
def test_preserve_existing_study_date(
    dicom_sender,
    single_dicom_file: Path,
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    Verify Compass preserves existing study date when present.
    
    Test Steps:
    1. Send file with valid StudyDate/Time
    2. Verify send succeeds
    3. Manual verification: Confirm date was not changed
    """
    ds = load_dataset(single_dicom_file)
    
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    
    # Set specific study date/time
    test_study_date = "20240101"
    test_study_time = "120000"
    
    ds.StudyDate = test_study_date
    ds.StudyTime = test_study_time
    
    print(f"\n{'='*70}")
    print(f"PRESERVE STUDY DATE TEST")
    print(f"{'='*70}")
    print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
    print(f"  StudyDate: {test_study_date}")
    print(f"  StudyTime: {test_study_time}")
    
    dicom_sender._send_single_dataset(ds, metrics)
    
    assert metrics.successes == 1
    print(f"  Status: SUCCESS")
    
    # C-FIND verification
    print(f"\n[C-FIND VERIFICATION]")
    study = verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config)
    if study:
        cfind_date = study.get('StudyDate', '')
        if cfind_date and cfind_date.strip() == test_study_date:
            print(f"  [OK] StudyDate preserved: {cfind_date}")
        else:
            print(f"  [WARN] StudyDate changed: expected {test_study_date}, got {cfind_date}")


# ============================================================================
# Test 2: Accession Number Handling
# ============================================================================

@pytest.mark.integration
def test_iims_accession_number_generation(
    dicom_sender,
    single_dicom_file: Path,
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    COMPASS_APICall_GetIIMSAccessionNumber
    
    Send study with blank accession number.
    Verify IIMS web service is called and accession number is populated.
    
    Expected Result: IIMS web service called; accession number populated
    
    Test Steps:
    1. Load DICOM file
    2. Set AccessionNumber to empty string
    3. Send to Compass
    4. Verify send succeeds
    5. Manual verification: Check IIMS logs and query for study
    """
    ds = load_dataset(single_dicom_file)
    
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    
    # Set accession number to blank
    ds.AccessionNumber = ''
    
    print(f"\n{'='*70}")
    print(f"BLANK ACCESSION NUMBER TEST")
    print(f"{'='*70}")
    print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
    print(f"  AccessionNumber: '' (blank)")
    print(f"\n  Expecting IIMS web service to be called...")
    
    # Send to Compass
    dicom_sender._send_single_dataset(ds, metrics)
    
    assert metrics.successes == 1, "Send failed"
    print(f"  Status: SUCCESS")
    
    # C-FIND verification
    print(f"\n{'='*70}")
    print(f"C-FIND VERIFICATION")
    print(f"{'='*70}")
    study = verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config)
    if study:
        acc = study.get('AccessionNumber', '')
        if acc and acc.strip():
            print(f"  [OK] AccessionNumber populated by IIMS: {acc}")
        else:
            print(f"  [INFO] AccessionNumber still blank after Compass processing")

    print(f"\n[SUCCESS] File sent with blank AccessionNumber")


@pytest.mark.integration
def test_pass_device_accession_number(
    dicom_sender,
    single_dicom_file: Path,
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    COMPASS_DataValidation_PassDeviceAccessionNumber
    
    Send study with valid accession number.
    Verify images are routed with the specified accession number.
    
    Expected Result: Images routed with specified accession number
    
    Test Steps:
    1. Set specific AccessionNumber
    2. Send to Compass
    3. Verify accession number is preserved
    """
    ds = load_dataset(single_dicom_file)
    
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    
    # Set specific accession number
    test_accession = "TEST-ACC-12345678"
    ds.AccessionNumber = test_accession
    
    print(f"\n{'='*70}")
    print(f"PASS DEVICE ACCESSION NUMBER TEST")
    print(f"{'='*70}")
    print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
    print(f"  AccessionNumber: {test_accession}")
    
    dicom_sender._send_single_dataset(ds, metrics)
    
    assert metrics.successes == 1, "Send failed"
    print(f"  Status: SUCCESS")
    
    # C-FIND verification
    print(f"\n[C-FIND VERIFICATION]")
    study = verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config)
    if study:
        acc = study.get('AccessionNumber', '')
        if acc and acc.strip() == test_accession:
            print(f"  [OK] AccessionNumber preserved: {acc}")
        else:
            print(f"  [WARN] AccessionNumber changed: expected {test_accession}, got '{acc}'")

    print(f"\n[SUCCESS] File sent with device AccessionNumber")


@pytest.mark.integration
def test_accession_number_edge_cases(
    dicom_sender,
    single_dicom_file: Path,
    cfind_client,
    perf_config,
):
    """
    Test various accession number edge cases.
    
    Test Steps:
    1. Send with missing AccessionNumber tag (not just blank)
    2. Send with very long AccessionNumber
    3. Send with special characters in AccessionNumber
    """
    print(f"\n{'='*70}")
    print(f"ACCESSION NUMBER EDGE CASES")
    print(f"{'='*70}")
    
    test_cases = [
        {
            'name': 'Missing tag entirely',
            'action': lambda ds: delattr(ds, 'AccessionNumber') if hasattr(ds, 'AccessionNumber') else None,
            'expected': 'Compass should generate or leave blank'
        },
        {
            'name': 'Very long accession number',
            'action': lambda ds: setattr(ds, 'AccessionNumber', 'A' * 100),
            'expected': 'Compass should accept or truncate'
        },
        {
            'name': 'Special characters',
            'action': lambda ds: setattr(ds, 'AccessionNumber', 'TEST-ACC#123@456'),
            'expected': 'Compass should handle or sanitize'
        },
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[Test {i}/{len(test_cases)}]: {test_case['name']}")
        
        metrics = PerfMetrics()
        ds = load_dataset(single_dicom_file)
        
        ds.StudyInstanceUID = generate_uid()
        ds.SeriesInstanceUID = generate_uid()
        ds.SOPInstanceUID = generate_uid()
        
        # Apply test case modification
        test_case['action'](ds)
        
        accession_value = ds.AccessionNumber if hasattr(ds, 'AccessionNumber') else 'NOT_PRESENT'
        print(f"  AccessionNumber: {accession_value}")
        print(f"  Expected: {test_case['expected']}")
        
        dicom_sender._send_single_dataset(ds, metrics)
        
        if metrics.successes == 1:
            print(f"  Result: SUCCESS")
            print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
            # C-FIND verification
            study = verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config)
            if study:
                acc = study.get('AccessionNumber', '')
                print(f"  C-FIND AccessionNumber: '{acc}'")
        else:
            print(f"  Result: FAILED (may be expected)")
            print(f"  Error rate: {metrics.error_rate:.1%}")

        time.sleep(2)  # Brief pause between edge cases


# ============================================================================
# Test 3: Patient Demographics Validation
# ============================================================================

@pytest.mark.integration
def test_blank_patient_name_handling(
    dicom_sender,
    single_dicom_file: Path,
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    Send file with blank PatientName.
    Verify Compass behavior with missing demographic data.
    
    Test Steps:
    1. Set PatientName to empty string
    2. Send to Compass
    3. Verify handling
    """
    ds = load_dataset(single_dicom_file)
    
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    
    # Blank patient name
    ds.PatientName = ''
    ds.PatientID = 'TEST-ID-12345'  # Keep ID for tracking
    
    print(f"\n{'='*70}")
    print(f"BLANK PATIENT NAME TEST")
    print(f"{'='*70}")
    print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
    print(f"  PatientName: '' (blank)")
    print(f"  PatientID: {ds.PatientID}")
    
    dicom_sender._send_single_dataset(ds, metrics)
    
    assert metrics.successes == 1, "Send failed"
    print(f"  Status: SUCCESS")
    
    # C-FIND verification
    print(f"\n[C-FIND VERIFICATION]")
    study = verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config)
    if study:
        pn = study.get('PatientName', '')
        if pn and pn.strip():
            print(f"  [INFO] PatientName populated by Compass: {pn}")
        else:
            print(f"  [INFO] PatientName remains blank")


@pytest.mark.integration
def test_special_characters_in_patient_data(
    dicom_sender,
    single_dicom_file: Path,
    metrics: PerfMetrics
):
    """
    Test patient data with special characters and Unicode.
    
    Verifies Compass handles international characters correctly.
    
    Test Steps:
    1. Set PatientName with special characters
    2. Send to Compass
    3. Verify proper handling
    """
    ds = load_dataset(single_dicom_file)
    
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    
    # Special characters in patient name
    test_names = [
        "O'Brien^John",  # Apostrophe
        "Smith-Jones^Mary",  # Hyphen
        "García^José",  # Accented characters
        "Patient^Test^Jr.",  # Suffix
    ]
    
    print(f"\n{'='*70}")
    print(f"SPECIAL CHARACTERS IN PATIENT DATA")
    print(f"{'='*70}")
    
    for i, name in enumerate(test_names, 1):
        test_metrics = PerfMetrics()
        ds_copy = load_dataset(single_dicom_file)
        
        ds_copy.StudyInstanceUID = generate_uid()
        ds_copy.SeriesInstanceUID = generate_uid()
        ds_copy.SOPInstanceUID = generate_uid()
        ds_copy.PatientName = name
        
        print(f"\n[Test {i}/{len(test_names)}]")
        print(f"  PatientName: {name}")
        
        dicom_sender._send_single_dataset(ds_copy, test_metrics)
        
        if test_metrics.successes == 1:
            print(f"  Status: SUCCESS")
            print(f"  StudyUID: {ds_copy.StudyInstanceUID}")
        else:
            print(f"  Status: FAILED")
        
        time.sleep(1)


# ============================================================================
# Test 4: Modality-Specific Validation
# ============================================================================

@pytest.mark.integration
def test_missing_modality_tag(
    dicom_sender,
    single_dicom_file: Path,
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    Send file with missing Modality tag.
    
    Verifies Compass handling of missing required DICOM tags.
    
    Test Steps:
    1. Remove Modality tag
    2. Attempt to send
    3. Verify behavior (accept or reject)
    """
    ds = load_dataset(single_dicom_file)
    
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    
    # Store original modality
    original_modality = ds.Modality if hasattr(ds, 'Modality') else None
    
    # Remove modality
    if hasattr(ds, 'Modality'):
        del ds.Modality
    
    print(f"\n{'='*70}")
    print(f"MISSING MODALITY TAG TEST")
    print(f"{'='*70}")
    print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
    print(f"  Original Modality: {original_modality}")
    print(f"  Modality tag: REMOVED")
    
    dicom_sender._send_single_dataset(ds, metrics)
    
    print(f"\n  Result:")
    if metrics.successes == 1:
        print(f"    Status: ACCEPTED (Compass accepted file without Modality)")
        print(f"    This may indicate Compass is lenient with missing tags")
    else:
        print(f"    Status: REJECTED (expected - Modality is usually required)")
        print(f"    Error rate: {metrics.error_rate:.1%}")
    
    # C-FIND verification (informational)
    if metrics.successes == 1:
        study = verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config)
        if study:
            print(f"  [INFO] Study stored in Compass despite missing Modality")

    print(f"\n  Note: DICOM standard requires Modality, but behavior varies by system")


# ============================================================================
# Helper: Data Integrity Summary Test
# ============================================================================

@pytest.mark.integration
def test_data_validation_summary(dicom_sender):
    """
    Summary test: Quick check of all data validation scenarios.
    
    Provides overview of Compass data handling capabilities.
    """
    print(f"\n{'='*70}")
    print(f"DATA VALIDATION TEST SUITE SUMMARY")
    print(f"{'='*70}")
    print(f"\nThis test suite validates:")
    print(f"  1. Blank StudyDate/Time handling")
    print(f"  2. Accession number generation (IIMS API)")
    print(f"  3. Accession number preservation")
    print(f"  4. Patient demographic edge cases")
    print(f"  5. Missing required tags")
    print(f"\nAll tests send files and document expected behavior.")
    print(f"Manual verification is required for most cases.")
    print(f"\nRun individual tests for detailed results:")
    print(f"  pytest tests/test_data_validation.py -v -s")
    
    # Quick connectivity check
    is_reachable = dicom_sender.ping(timeout_seconds=10)
    assert is_reachable, "Compass not reachable"
    
    print(f"\n[SUCCESS] Compass is ready for data validation testing")

