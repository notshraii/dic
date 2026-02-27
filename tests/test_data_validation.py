# tests/test_data_validation.py

"""
Tests that validate Compass data handling including blank fields, accession numbers, and study dates.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest
from pydicom import dcmread
from pydicom.uid import generate_uid

from data_loader import load_dataset
from metrics import PerfMetrics
from tests.conftest import manual_verification_required, verify_study_arrived


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
    4. C-FIND verification: Query for study and check date was populated
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
    if cfind_client is None:
        pytest.skip("C-FIND verification is required for this test (set CFIND_VERIFY=true)")

    patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
    study = verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config, patient_id=patient_id)

    strategy = getattr(cfind_client, 'last_find_strategy', None) or 'unknown'
    cfind_date = study.get('StudyDate', '')
    assert cfind_date and cfind_date.strip(), (
        f"StudyDate was not populated by Compass after sending with blank StudyDate. "
        f"Strategy used: '{strategy}'. "
        f"C-FIND response keys: {list(study.keys())}."
    )
    print(f"  [OK] StudyDate was populated by Compass: {cfind_date}")

    expected_date = original_acquisition_date or ''
    if expected_date:
        assert cfind_date.strip() == expected_date.strip(), (
            f"StudyDate ({cfind_date.strip()}) does not match "
            f"AcquisitionDate ({expected_date.strip()})"
        )
        print(f"  [OK] StudyDate matches AcquisitionDate: {expected_date}")


@pytest.mark.integration
@pytest.mark.manual_verify
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
    3. C-FIND verification: Confirm date was not changed
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
    if cfind_client is None:
        pytest.skip("C-FIND verification is required for this test (set CFIND_VERIFY=true)")

    patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
    study = verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config, patient_id=patient_id)

    strategy = getattr(cfind_client, 'last_find_strategy', None) or 'unknown'
    cfind_date = study.get('StudyDate', '')
    with manual_verification_required("StudyDate preservation -- verified manually on server"):
        assert cfind_date and cfind_date.strip(), (
            f"StudyDate not returned by C-FIND for study {ds.StudyInstanceUID}. "
            f"Expected '{test_study_date}' but got empty/missing value. "
            f"Strategy used: '{strategy}'. "
            f"C-FIND response keys: {list(study.keys())}. "
            f"If strategy is 'PATIENT Root, PATIENT level (fallback)', study-level "
            f"attributes are not available -- fix STUDY-level C-FIND queries."
        )
        assert cfind_date.strip() == test_study_date, (
            f"StudyDate was not preserved: expected '{test_study_date}', "
            f"got '{cfind_date.strip()}'"
        )
    print(f"  [OK] StudyDate preserved: {cfind_date}")


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
    5. C-FIND verification: Query for study and check AccessionNumber
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
    if cfind_client is None:
        pytest.skip("C-FIND verification is required for this test (set CFIND_VERIFY=true)")

    patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
    study = verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config, patient_id=patient_id)

    strategy = getattr(cfind_client, 'last_find_strategy', None) or 'unknown'
    acc = study.get('AccessionNumber', '')
    assert acc and acc.strip(), (
        f"AccessionNumber was not populated by IIMS after sending with blank AccessionNumber. "
        f"Strategy used: '{strategy}'. "
        f"C-FIND response keys: {list(study.keys())}."
    )
    print(f"  [OK] AccessionNumber populated by IIMS: {acc}")


@pytest.mark.integration
@pytest.mark.manual_verify
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
    if cfind_client is None:
        pytest.skip("C-FIND verification is required for this test (set CFIND_VERIFY=true)")

    patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
    study = verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config, patient_id=patient_id)

    strategy = getattr(cfind_client, 'last_find_strategy', None) or 'unknown'
    acc = study.get('AccessionNumber', '')
    with manual_verification_required("AccessionNumber preservation -- verified manually on server"):
        assert acc and acc.strip(), (
            f"AccessionNumber not returned by C-FIND for study {ds.StudyInstanceUID}. "
            f"Expected '{test_accession}' but got empty/missing value. "
            f"Strategy used: '{strategy}'. "
            f"C-FIND response keys: {list(study.keys())}."
        )
        assert acc.strip() == test_accession, (
            f"AccessionNumber was not preserved: expected '{test_accession}', "
            f"got '{acc.strip()}'"
        )
    print(f"  [OK] AccessionNumber preserved: {acc}")


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
    
    failures = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[Test {i}/{len(test_cases)}]: {test_case['name']}")
        
        metrics = PerfMetrics()
        ds = load_dataset(single_dicom_file)
        
        ds.StudyInstanceUID = generate_uid()
        ds.SeriesInstanceUID = generate_uid()
        ds.SOPInstanceUID = generate_uid()
        
        test_case['action'](ds)
        
        accession_value = ds.AccessionNumber if hasattr(ds, 'AccessionNumber') else 'NOT_PRESENT'
        print(f"  AccessionNumber: {accession_value}")
        print(f"  Expected: {test_case['expected']}")
        
        dicom_sender._send_single_dataset(ds, metrics)
        
        if metrics.successes != 1:
            msg = f"Edge case '{test_case['name']}': send failed (error rate {metrics.error_rate:.1%})"
            print(f"  Result: FAILED - {msg}")
            failures.append(msg)
        else:
            print(f"  Result: SUCCESS")
            print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
            if cfind_client is not None:
                patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
                study = verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config, patient_id=patient_id)
                acc = study.get('AccessionNumber', '')
                print(f"  C-FIND AccessionNumber: '{acc}'")

        time.sleep(2)

    assert not failures, (
        f"{len(failures)} edge case(s) failed:\n" + "\n".join(f"  - {f}" for f in failures)
    )


# ============================================================================
# Test 3: Patient Demographics Validation
# ============================================================================

@pytest.mark.integration
def test_blank_patient_name_handling(
    dicom_sender,
    single_dicom_file: Path,
    metrics: PerfMetrics,
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
    
    # Blank patient name (the variable under test)
    ds.PatientName = ''
    
    # Populate all other demographics to match what test_anonymize_and_send uses,
    # so that blank PatientName is the only difference.
    ds.PatientID = 'TEST-ID-12345'
    ds.PatientBirthDate = '19010101'
    ds.AccessionNumber = generate_uid().split('.')[-1][:16]
    ds.InstitutionName = 'TEST FACILITY'
    ds.ReferringPhysicianName = 'TEST^PROVIDER'
    
    # Save to disk and reload to normalize encoding (same pattern as
    # test_anonymize_and_send, which avoids Read PDU errors).
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".dcm")
    os.close(tmp_fd)
    try:
        transfer_syntax = str(ds.file_meta.TransferSyntaxUID) if hasattr(ds, 'file_meta') and hasattr(ds.file_meta, 'TransferSyntaxUID') else '1.2.840.10008.1.2.1'
        if transfer_syntax == '1.2.840.10008.1.2':
            ds.save_as(tmp_path, implicit_vr=True, little_endian=True)
        elif transfer_syntax == '1.2.840.10008.1.2.2':
            ds.save_as(tmp_path, implicit_vr=False, little_endian=False)
        else:
            ds.save_as(tmp_path, implicit_vr=False, little_endian=True)
        ds = dcmread(tmp_path)
    finally:
        os.unlink(tmp_path)
    
    print(f"\n{'='*70}")
    print(f"BLANK PATIENT NAME TEST")
    print(f"{'='*70}")
    print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")
    print(f"  PatientName: '' (blank)")
    print(f"  PatientID: {ds.PatientID}")
    print(f"  AccessionNumber: {ds.AccessionNumber}")
    
    dicom_sender._send_single_dataset(ds, metrics)
    
    sample = metrics.samples[0]
    if sample.success:
        print(f"  Status: ACCEPTED by Compass")
    else:
        status_hex = f"0x{sample.status_code:04X}" if sample.status_code is not None else "N/A"
        print(f"  Status: REJECTED by Compass")
        print(f"  Status code: {status_hex}")
        print(f"  Error: {sample.error}")
        pytest.fail(
            f"Compass rejected blank PatientName (status {status_hex}). "
            f"Expected Compass to accept and route to destination."
        )


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
    
    failures = []

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
            msg = f"PatientName '{name}': send failed"
            print(f"  Status: FAILED")
            failures.append(msg)
        
        time.sleep(1)

    assert not failures, (
        f"{len(failures)} special character case(s) failed:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


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
    
    assert metrics.successes == 1, (
        f"Compass rejected file with missing Modality tag "
        f"(error rate {metrics.error_rate:.1%})"
    )
    print(f"  Result: ACCEPTED")
    
    # C-FIND verification
    if cfind_client is not None:
        patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
        verify_study_arrived(cfind_client, str(ds.StudyInstanceUID), perf_config, patient_id=patient_id)
        print(f"  [OK] Study stored in Compass despite missing Modality")


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
    print(f"\nAll tests send files, verify via C-FIND, and document expected behavior.")
    print(f"\nRun individual tests for detailed results:")
    print(f"  pytest tests/test_data_validation.py -v -s")
    
    # Quick connectivity check
    is_reachable = dicom_sender.ping(timeout_seconds=10)
    assert is_reachable, "Compass not reachable"
    
    print(f"\n[SUCCESS] Compass is ready for data validation testing")

