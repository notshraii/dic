# tests/test_failure_modes.py

"""
Tests that validate Compass behavior under failure conditions like delays, duplicates, and interruptions.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List

import pytest
from pydicom.uid import generate_uid

from data_loader import load_dataset
from metrics import PerfMetrics
from tests.conftest import verify_study_arrived


# ============================================================================
# Test 1: Pause/Delay Between Sends
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
def test_send_with_2min_pause_between_files(
    dicom_sender,
    small_dicom_files: List[Path],
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    COMPASS_FailureMode_DelayDuringSend
    
    Send images one at a time with 2-minute pause between sends.
    Verifies Compass handles long delays between files gracefully.
    
    Expected Result: Entire study is routed to MIDIA and InfinityView
    
    Test Steps:
    1. Select multiple DICOM files (small for speed)
    2. Send first file
    3. Wait 2 minutes
    4. Send second file
    5. Repeat for all files
    6. Verify all files sent successfully
    """
    delay_seconds = 120  # 2 minutes
    
    # Limit to 3 files to keep test duration reasonable
    test_files = small_dicom_files[:3]
    
    print(f"\n{'='*70}")
    print(f"DELAY SEND TEST: {len(test_files)} files with {delay_seconds}s delays")
    print(f"{'='*70}")
    print(f"  Total estimated time: {len(test_files) * delay_seconds / 60:.1f} minutes")
    
    sent_uids = []
    for i, file in enumerate(test_files, 1):
        ds = load_dataset(file)

        # Generate unique UIDs for tracking
        ds.StudyInstanceUID = generate_uid()
        ds.SeriesInstanceUID = generate_uid()
        ds.SOPInstanceUID = generate_uid()
        sent_uids.append(str(ds.StudyInstanceUID))

        print(f"\n[{i}/{len(test_files)}] Sending file: {file.name}")
        print(f"  StudyInstanceUID: {ds.StudyInstanceUID}")

        start_time = time.time()
        dicom_sender._send_single_dataset(ds, metrics)
        send_duration = time.time() - start_time

        print(f"  Send completed in {send_duration:.2f}s")

        if i < len(test_files):
            print(f"  Pausing for {delay_seconds}s before next send...")
            time.sleep(delay_seconds)

    # Verify all files sent successfully
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"  Total sends: {metrics.total}")
    print(f"  Successes: {metrics.successes}")
    print(f"  Failures: {metrics.failures}")
    print(f"  Error rate: {metrics.error_rate:.1%}")

    assert metrics.successes == len(test_files), \
        f"Expected {len(test_files)} successes, got {metrics.successes}"

    assert metrics.error_rate == 0, \
        f"Some sends failed despite delays: {metrics.failures} failures"

    # C-FIND verification
    print(f"\n[C-FIND VERIFICATION]")
    for uid in sent_uids:
        verify_study_arrived(cfind_client, uid, perf_config)

    print(f"\n[SUCCESS] All {len(test_files)} files sent and verified with 2-min delays")


@pytest.mark.integration
@pytest.mark.slow
def test_mcie_slow_send_one_at_a_time(
    dicom_sender,
    small_dicom_files: List[Path],
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    COMPASS_FailureMode_DelayDuringMCIESend
    
    Send images one at a time with delay (MCIE scenario).
    Verifies images are routed to MIDIA and InfinityView despite slow send.
    
    Expected Result: Images routed to MIDIA and InfinityView
    
    Test Steps:
    1. Set calling AET to MCIE variant
    2. Send files one at a time with 30-second delays
    3. Verify all files sent successfully
    4. Manual verification: Check MIDIA and InfinityView for files
    """
    delay_seconds = 30  # 30 seconds between files
    test_files = small_dicom_files[:5]  # Limit to 5 files
    
    print(f"\n{'='*70}")
    print(f"MCIE SLOW SEND TEST: {len(test_files)} files")
    print(f"{'='*70}")
    
    # Override to MCIE AET
    original_aet = dicom_sender.endpoint.local_ae_title
    dicom_sender.endpoint.local_ae_title = 'MCIE_TEST_SLOW'
    
    try:
        study_uid = generate_uid()  # Same study for all images
        
        for i, file in enumerate(test_files, 1):
            ds = load_dataset(file)
            
            # Same study, different series/SOP for each file
            ds.StudyInstanceUID = study_uid
            ds.SeriesInstanceUID = generate_uid()
            ds.SOPInstanceUID = generate_uid()
            
            print(f"\n[{i}/{len(test_files)}] Sending image {i} of study")
            print(f"  File: {file.name}")
            
            dicom_sender._send_single_dataset(ds, metrics)
            
            if i < len(test_files):
                print(f"  Waiting {delay_seconds}s before next image...")
                time.sleep(delay_seconds)
        
        print(f"\n{'='*70}")
        print(f"RESULTS")
        print(f"{'='*70}")
        print(f"  StudyInstanceUID: {study_uid}")
        print(f"  Total images sent: {metrics.successes}")
        print(f"  Failures: {metrics.failures}")
        
        assert metrics.successes == len(test_files)
        assert metrics.error_rate == 0
        
        # C-FIND verification
        print(f"\n[C-FIND VERIFICATION]")
        cfind_study = verify_study_arrived(cfind_client, str(study_uid), perf_config)
        if cfind_study:
            instances = cfind_study.get('NumberOfStudyRelatedInstances')
            if instances is not None:
                count = int(instances)
                assert count >= len(test_files), \
                    f"Expected >= {len(test_files)} instances, got {count}"
                print(f"  [OK] NumberOfStudyRelatedInstances: {count}")

    finally:
        dicom_sender.endpoint.local_ae_title = original_aet


# ============================================================================
# Test 2: Duplicate Study Handling
# ============================================================================

@pytest.mark.integration
def test_send_duplicate_study_multiple_times(
    dicom_sender,
    single_dicom_file: Path,
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    COMPASS_FailureMode_SendDuplicateMCIEStudy
    
    Send the same study multiple times.
    Verifies Compass handles duplicate sends appropriately.
    
    Expected Result: Each send creates a separate entry/record
    
    Test Steps:
    1. Send study first time
    2. Send exact same study again (same UIDs)
    3. Send third time
    4. Verify all sends succeed
    5. Manual verification: Check that multiple entries exist
    """
    num_sends = 3
    
    print(f"\n{'='*70}")
    print(f"DUPLICATE STUDY TEST: Sending same study {num_sends} times")
    print(f"{'='*70}")
    
    # Load and prepare study once
    ds = load_dataset(single_dicom_file)
    
    # Use fixed UIDs (same for all sends - this is the duplicate scenario)
    fixed_study_uid = generate_uid()
    fixed_series_uid = generate_uid()
    fixed_sop_uid = generate_uid()
    
    ds.StudyInstanceUID = fixed_study_uid
    ds.SeriesInstanceUID = fixed_series_uid
    ds.SOPInstanceUID = fixed_sop_uid
    
    print(f"  StudyInstanceUID: {fixed_study_uid}")
    print(f"  This same UID will be sent {num_sends} times")
    
    # Send multiple times
    for i in range(1, num_sends + 1):
        print(f"\n[Send {i}/{num_sends}]")
        
        send_metrics = PerfMetrics()  # Separate metrics per send
        dicom_sender._send_single_dataset(ds, send_metrics)
        
        if send_metrics.successes == 1:
            print(f"  Status: SUCCESS")
            print(f"  Latency: {send_metrics.avg_latency_ms:.2f}ms")
        else:
            print(f"  Status: FAILED")
            print(f"  Error rate: {send_metrics.error_rate:.1%}")
        
        # Track overall
        for sample in send_metrics.samples:
            metrics.record(sample)
        
        # Brief pause between sends
        if i < num_sends:
            time.sleep(2)
    
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"  Total sends attempted: {metrics.total}")
    print(f"  Successful sends: {metrics.successes}")
    print(f"  Failed sends: {metrics.failures}")
    
    # All sends should succeed (Compass should accept duplicates)
    assert metrics.successes == num_sends, \
        f"Expected {num_sends} successful sends, got {metrics.successes}"
    
    # C-FIND verification
    print(f"\n[C-FIND VERIFICATION]")
    cfind_study = verify_study_arrived(cfind_client, str(fixed_study_uid), perf_config)
    if cfind_study:
        instances = cfind_study.get('NumberOfStudyRelatedInstances')
        if instances is not None:
            print(f"  [OK] NumberOfStudyRelatedInstances: {instances}")

    print(f"\n[SUCCESS] All {num_sends} duplicate sends accepted by Compass")


@pytest.mark.integration
def test_resend_after_modifications(
    dicom_sender,
    single_dicom_file: Path,
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    Send study, modify tags, resend with same StudyInstanceUID.
    
    Verifies Compass handling of modified duplicate studies.
    
    Test Steps:
    1. Send original study
    2. Modify PatientName but keep same StudyInstanceUID
    3. Resend modified study
    4. Verify both sends succeed
    """
    ds = load_dataset(single_dicom_file)
    
    study_uid = generate_uid()
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    
    original_patient = "ORIGINAL^PATIENT"
    ds.PatientName = original_patient
    
    print(f"\n{'='*70}")
    print(f"MODIFIED DUPLICATE TEST")
    print(f"{'='*70}")
    print(f"  StudyInstanceUID: {study_uid}")
    
    # First send
    print(f"\n[SEND 1: Original]")
    print(f"  PatientName: {original_patient}")
    
    send1_metrics = PerfMetrics()
    dicom_sender._send_single_dataset(ds, send1_metrics)
    
    assert send1_metrics.successes == 1, "First send failed"
    print(f"  Status: SUCCESS")
    
    time.sleep(5)  # Brief pause
    
    # Modify and resend
    modified_patient = "MODIFIED^PATIENT"
    ds.PatientName = modified_patient
    ds.SeriesInstanceUID = generate_uid()  # New series
    ds.SOPInstanceUID = generate_uid()  # New SOP
    
    print(f"\n[SEND 2: Modified]")
    print(f"  PatientName: {modified_patient} (CHANGED)")
    print(f"  StudyInstanceUID: {study_uid} (SAME)")
    
    send2_metrics = PerfMetrics()
    dicom_sender._send_single_dataset(ds, send2_metrics)
    
    assert send2_metrics.successes == 1, "Second send failed"
    print(f"  Status: SUCCESS")
    
    # C-FIND verification
    print(f"\n[C-FIND VERIFICATION]")
    cfind_study = verify_study_arrived(cfind_client, str(study_uid), perf_config)
    if cfind_study:
        pn = cfind_study.get('PatientName', '')
        print(f"  [INFO] PatientName in Compass: {pn}")
        print(f"  [INFO] Original was '{original_patient}', modified was '{modified_patient}'")


# ============================================================================
# Test 3: Network Resilience
# ============================================================================

@pytest.mark.integration
def test_send_with_variable_delays(
    dicom_sender,
    small_dicom_files: List[Path],
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    Send files with random variable delays to simulate network variability.
    
    Verifies Compass handles irregular send patterns.
    
    Test Steps:
    1. Send files with delays ranging from 5-60 seconds
    2. Verify all files send successfully
    """
    import random
    
    test_files = small_dicom_files[:5]
    study_uid = generate_uid()
    
    print(f"\n{'='*70}")
    print(f"VARIABLE DELAY TEST: {len(test_files)} files")
    print(f"{'='*70}")
    
    for i, file in enumerate(test_files, 1):
        ds = load_dataset(file)
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = generate_uid()
        ds.SOPInstanceUID = generate_uid()
        
        delay = random.uniform(5, 60) if i < len(test_files) else 0
        
        print(f"\n[{i}/{len(test_files)}] {file.name}")
        dicom_sender._send_single_dataset(ds, metrics)
        
        if delay > 0:
            print(f"  Next delay: {delay:.1f}s")
            time.sleep(delay)
    
    assert metrics.successes == len(test_files)
    assert metrics.error_rate == 0

    # C-FIND verification for the shared study
    print(f"\n[C-FIND VERIFICATION]")
    cfind_study = verify_study_arrived(cfind_client, str(study_uid), perf_config)
    if cfind_study:
        instances = cfind_study.get('NumberOfStudyRelatedInstances')
        if instances is not None:
            print(f"  [OK] NumberOfStudyRelatedInstances: {instances}")

    print(f"\n[SUCCESS] All files sent and verified despite variable delays")


# ============================================================================
# Helper: Quick Connectivity Check
# ============================================================================

@pytest.mark.integration
def test_connectivity_before_failure_tests(dicom_sender):
    """
    Pre-flight check: Verify Compass is reachable before running failure tests.
    
    This test should run first to ensure the test environment is ready.
    """
    print(f"\n{'='*70}")
    print(f"PRE-FLIGHT CHECK: Compass Connectivity")
    print(f"{'='*70}")
    print(f"  Host: {dicom_sender.endpoint.host}")
    print(f"  Port: {dicom_sender.endpoint.port}")
    print(f"  Remote AET: {dicom_sender.endpoint.remote_ae_title}")
    
    is_reachable = dicom_sender.ping(timeout_seconds=10)
    
    if is_reachable:
        print(f"  Status: REACHABLE (C-ECHO succeeded)")
    else:
        print(f"  Status: UNREACHABLE (C-ECHO failed)")
        pytest.fail("Compass is not reachable - check configuration and network")
    
    print(f"\n[SUCCESS] Compass is ready for failure mode testing")

