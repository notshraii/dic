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
    
    uid_to_patient: dict = {}
    for i, file in enumerate(test_files, 1):
        ds = load_dataset(file)

        # Generate unique UIDs for tracking
        ds.StudyInstanceUID = generate_uid()
        ds.SeriesInstanceUID = generate_uid()
        ds.SOPInstanceUID = generate_uid()
        uid_to_patient[str(ds.StudyInstanceUID)] = str(ds.PatientID) if hasattr(ds, 'PatientID') else None

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
    for uid, patient_id in uid_to_patient.items():
        verify_study_arrived(cfind_client, uid, perf_config, patient_id=patient_id)

    print(f"\n[SUCCESS] All {len(test_files)} files sent and verified with 2-min delays")


@pytest.mark.integration
@pytest.mark.slow
def test_slow_send_one_at_a_time(
    dicom_sender,
    small_dicom_files: List[Path],
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    COMPASS_FailureMode_DelayDuringSend_Slow
    
    Send images one at a time with delay.
    Verifies images are routed to MIDIA and InfinityView despite slow send.
    
    Expected Result: Images routed to MIDIA and InfinityView
    
    Test Steps:
    1. Send files one at a time with unique StudyInstanceUIDs and 30-second delays
    2. Verify all files sent successfully
    3. C-FIND verification: Confirm each study arrived individually
    """
    delay_seconds = 30  # 30 seconds between files
    test_files = small_dicom_files[:5]  # Limit to 5 files
    
    print(f"\n{'='*70}")
    print(f"SLOW SEND TEST: {len(test_files)} files")
    print(f"{'='*70}")
    
    sent_study_uids = []
    
    for i, file in enumerate(test_files, 1):
        ds = load_dataset(file)
        
        study_uid = generate_uid()
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = generate_uid()
        ds.SOPInstanceUID = generate_uid()
        sent_study_uids.append(study_uid)
        
        print(f"\n[{i}/{len(test_files)}] Sending image {i}")
        print(f"  File: {file.name}")
        print(f"  StudyInstanceUID: {study_uid}")
        
        dicom_sender._send_single_dataset(ds, metrics)
        
        if i < len(test_files):
            print(f"  Waiting {delay_seconds}s before next image...")
            time.sleep(delay_seconds)
    
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"  Total images sent: {metrics.successes}")
    print(f"  Failures: {metrics.failures}")
    
    assert metrics.successes == len(test_files)
    assert metrics.error_rate == 0
    
    # C-FIND verification: confirm each study arrived individually
    print(f"\n[C-FIND VERIFICATION]")
    patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
    for i, uid in enumerate(sent_study_uids, 1):
        print(f"  [{i}/{len(sent_study_uids)}] Verifying StudyInstanceUID: {uid}")
        verify_study_arrived(cfind_client, str(uid), perf_config, patient_id=patient_id)
    
    print(f"\n[OK] All {len(sent_study_uids)} images verified via C-FIND")


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
    COMPASS_FailureMode_SendDuplicateStudy
    
    Send the same study multiple times.
    Verifies Compass handles duplicate sends appropriately.
    
    Expected Result: Each send creates a separate entry/record
    
    Test Steps:
    1. Send study first time
    2. Send exact same study again (same UIDs)
    3. Send third time
    4. Verify all sends succeed
    5. C-FIND verification: Confirm study arrived
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
    patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
    cfind_study = verify_study_arrived(cfind_client, str(fixed_study_uid), perf_config, patient_id=patient_id)
    if cfind_study is not None:
        instances = cfind_study.get('NumberOfStudyRelatedInstances')
        if instances is not None:
            print(f"  [OK] NumberOfStudyRelatedInstances: {instances}")
        else:
            print(f"  [OK] Study found (NumberOfStudyRelatedInstances not available)")


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
    patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
    cfind_study = verify_study_arrived(cfind_client, str(study_uid), perf_config, patient_id=patient_id)
    if cfind_study is not None:
        pn = cfind_study.get('PatientName', '')
        assert pn, (
            f"PatientName not returned by C-FIND after resend. "
            f"Response keys: {list(cfind_study.keys())}"
        )
        print(f"  PatientName in Compass: {pn}")
        print(f"  Original was '{original_patient}', modified was '{modified_patient}'")


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
    patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
    cfind_study = verify_study_arrived(cfind_client, str(study_uid), perf_config, patient_id=patient_id)
    if cfind_study is not None:
        instances = cfind_study.get('NumberOfStudyRelatedInstances')
        if instances is not None:
            print(f"  [OK] NumberOfStudyRelatedInstances: {instances}")
        else:
            print(f"  [OK] Study found (NumberOfStudyRelatedInstances not available)")


# ============================================================================
# Test 4: Interrupted Transmission / Partial Send Recovery
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
def test_interrupted_send_then_resend_complete_study(
    dicom_sender,
    small_dicom_files: List[Path],
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    COMPASS_FailureMode_InterruptedTransmission

    Send partial study (3 files), simulate interruption, wait 1 minute,
    then resend the complete study (10 files). Verify that Compass contains
    exactly the expected number of instances with no orphan duplicates from
    the aborted partial send.

    Expected Result:
    - All resent files are accepted
    - Study completeness = 10 instances (no duplicates from the orphan 3)
    - Study is fully routed to downstream systems

    Test Steps:
    1. Select 10 DICOM files and assign a shared StudyInstanceUID
    2. Pre-generate SOP Instance UIDs for all 10 files
    3. Send first 3 files (partial / interrupted transmission)
    4. Wait 60 seconds (simulate network outage / interruption gap)
    5. Resend all 10 files with the SAME SOP Instance UIDs (files 1-3
       are duplicates of the orphans; files 4-10 are new)
    6. C-FIND verification: confirm study arrived
    7. Assert NumberOfStudyRelatedInstances == 10 (orphans de-duplicated)
    """
    interrupt_after = 3
    total_files = 10
    interruption_wait = 60  # seconds

    if len(small_dicom_files) < total_files:
        pytest.skip(
            f"Need at least {total_files} small DICOM files, "
            f"only {len(small_dicom_files)} available"
        )

    test_files = small_dicom_files[:total_files]

    study_uid = generate_uid()
    series_uid = generate_uid()

    print(f"\n{'='*70}")
    print(f"INTERRUPTED TRANSMISSION TEST")
    print(f"{'='*70}")
    print(f"  StudyInstanceUID : {study_uid}")
    print(f"  Total files      : {total_files}")
    print(f"  Interrupt after  : {interrupt_after} files")
    print(f"  Wait before retry: {interruption_wait}s")

    # ------------------------------------------------------------------
    # Pre-generate SOP UIDs for all 10 files so the resend in Phase 2
    # reuses the same UIDs for files 1-3, allowing Compass to
    # de-duplicate the orphans from the interrupted partial send.
    # ------------------------------------------------------------------
    all_sop_uids = [generate_uid() for _ in range(total_files)]

    # ------------------------------------------------------------------
    # Phase 1: Partial send (simulate interrupted transmission)
    # ------------------------------------------------------------------
    print(f"\n--- PHASE 1: Partial send ({interrupt_after} files) ---")
    partial_metrics = PerfMetrics()

    for i, file in enumerate(test_files[:interrupt_after], 1):
        ds = load_dataset(file)
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = series_uid
        ds.SOPInstanceUID = all_sop_uids[i - 1]

        print(f"  [{i}/{interrupt_after}] Sending {file.name}  (SOP: ...{str(all_sop_uids[i-1])[-12:]})")
        dicom_sender._send_single_dataset(ds, partial_metrics)

    print(f"\n  Partial send results: {partial_metrics.successes}/{interrupt_after} succeeded")
    assert partial_metrics.successes == interrupt_after, (
        f"Partial send failed: expected {interrupt_after} successes, "
        f"got {partial_metrics.successes}"
    )

    # ------------------------------------------------------------------
    # Interruption gap
    # ------------------------------------------------------------------
    print(f"\n--- INTERRUPTION: waiting {interruption_wait}s ---")
    time.sleep(interruption_wait)

    # ------------------------------------------------------------------
    # Phase 2: Resend complete study (all 10 files, same SOP UIDs)
    # Files 1-3 reuse the UIDs already sent in Phase 1 so Compass
    # can recognise them as duplicates rather than new instances.
    # ------------------------------------------------------------------
    print(f"\n--- PHASE 2: Full resend ({total_files} files) ---")
    resend_metrics = PerfMetrics()

    for i, file in enumerate(test_files, 1):
        ds = load_dataset(file)
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = series_uid
        ds.SOPInstanceUID = all_sop_uids[i - 1]

        print(f"  [{i}/{total_files}] Sending {file.name}  (SOP: ...{str(all_sop_uids[i-1])[-12:]})")
        dicom_sender._send_single_dataset(ds, resend_metrics)

    print(f"\n  Full resend results: {resend_metrics.successes}/{total_files} succeeded")
    assert resend_metrics.successes == total_files, (
        f"Full resend failed: expected {total_files} successes, "
        f"got {resend_metrics.successes}"
    )

    # Aggregate into the test-level metrics fixture for reporting
    for sample in partial_metrics.samples:
        metrics.record(sample)
    for sample in resend_metrics.samples:
        metrics.record(sample)

    # ------------------------------------------------------------------
    # Phase 3: C-FIND verification
    # ------------------------------------------------------------------
    print(f"\n--- PHASE 3: C-FIND verification ---")

    ds_last = load_dataset(test_files[0])
    ds_last.StudyInstanceUID = study_uid
    patient_id = str(ds_last.PatientID) if hasattr(ds_last, 'PatientID') else None

    cfind_study = verify_study_arrived(
        cfind_client, str(study_uid), perf_config, patient_id=patient_id,
    )

    if cfind_study is None:
        print("  [CFIND VERIFY] Skipped (verification disabled)")
    else:
        instances_str = cfind_study.get('NumberOfStudyRelatedInstances')
        if instances_str is not None:
            instance_count = int(instances_str)
            print(f"  NumberOfStudyRelatedInstances: {instance_count}")

            orphan_duplicate_count = instance_count - total_files
            if orphan_duplicate_count > 0:
                print(
                    f"  DUPLICATE DETECTED: expected {total_files} instances "
                    f"but found {instance_count} ({orphan_duplicate_count} orphan duplicates)"
                )
            assert instance_count == total_files, (
                f"Study completeness check failed: expected {total_files} instances, "
                f"found {instance_count}. Orphan files from the interrupted partial "
                f"send were not de-duplicated by Compass."
            )
            print(f"  [OK] No orphan duplicates -- study has exactly {total_files} instances")
        else:
            print(
                "  [WARNING] NumberOfStudyRelatedInstances not returned by C-FIND. "
                "Cannot verify orphan de-duplication automatically."
            )

    print(f"\n{'='*70}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*70}")
    print(f"  Phase 1 (partial) : {partial_metrics.successes}/{interrupt_after} sent")
    print(f"  Phase 2 (resend)  : {resend_metrics.successes}/{total_files} sent")
    print(f"  Total sends       : {metrics.total}")
    print(f"  Overall error rate: {metrics.error_rate:.1%}")
    print(f"[DONE] Interrupted transmission test complete")


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

