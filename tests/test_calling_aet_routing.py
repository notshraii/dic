# tests/test_calling_aet_routing.py

"""
Tests that validate Compass correctly handles and routes studies to different called AE titles.
"""

from __future__ import annotations

import pytest
from pydicom.uid import generate_uid

from data_loader import load_dataset
from metrics import PerfMetrics
from tests.conftest import manual_verification_required, verify_study_arrived


# ============================================================================
# Called AE Title Test Cases
# ============================================================================

# Define the called AE Titles (destinations) to test
# Add your actual called AE Titles here
CALLED_AET_TEST_CASES = [
    {
        'name': 'LB_HTM_GI',
        'description': 'GI Compass destination',
        'aet': 'LB-HTM-GI',
    },
    {
        'name': 'LB_HTM_ORTHO',
        'description': 'Ortho Compass destination',
        'aet': 'LB-HTM-ORTHO',
    },
    {
        'name': 'LB_HTM_OPH',
        'description': 'Ophthalmology Compass destination',
        'aet': 'LB-HTM-OPH',
    },
    # Add more called AE Titles as needed:
    # {
    #     'name': 'YOUR_DESTINATION_NAME',
    #     'description': 'Destination description',
    #     'aet': 'YOUR_AE_TITLE',
    # },
]


# ============================================================================
# Individual Called AET Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.parametrize("test_case", CALLED_AET_TEST_CASES, ids=lambda tc: tc['name'])
def test_called_aet_routing(
    test_case: dict,
    single_dicom_file,
    dicom_sender,
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    Test that Compass accepts and correctly routes studies to different called AE Titles.

    This test:
    1. Loads a DICOM file
    2. Generates unique study UID for tracking
    3. Sends to specified called AE Title
    4. Verifies send succeeds via C-FIND query

    To add more called AE Titles:
    - Add entries to CALLED_AET_TEST_CASES list above
    - Run: pytest tests/test_calling_aet_routing.py -v -s
    """
    called_aet = test_case['aet']

    print(f"\n{'='*70}")
    print(f"TEST: Called AET = {called_aet}")
    print(f"{'='*70}")
    print(f"Description: {test_case['description']}")

    # Load base file
    ds = load_dataset(single_dicom_file)

    # Generate unique study UID for this test
    test_study_uid = generate_uid()
    test_series_uid = generate_uid()
    test_sop_uid = generate_uid()

    ds.StudyInstanceUID = test_study_uid
    ds.SeriesInstanceUID = test_series_uid
    ds.SOPInstanceUID = test_sop_uid

    # Add marker in StudyDescription for easy identification
    study_desc = f"AET_TEST_{called_aet}"
    if hasattr(ds, 'StudyDescription'):
        ds.StudyDescription = study_desc
    else:
        ds.add_new((0x0008, 0x1030), 'LO', study_desc)

    print(f"\n[TEST IDENTIFIERS]")
    print(f"  StudyInstanceUID: {test_study_uid}")
    print(f"  StudyDescription: {ds.StudyDescription}")
    print(f"  Called AE Title: {called_aet}")

    # Override the remote AE title (called AET)
    original_aet = dicom_sender.endpoint.remote_ae_title
    dicom_sender.endpoint.remote_ae_title = called_aet

    try:
        # Send to Compass
        print(f"\n[SENDING]")
        print(f"  From (Calling AET): {dicom_sender.endpoint.local_ae_title}")
        print(f"  To (Called AET): {called_aet}")
        print(f"  Host: {dicom_sender.endpoint.host}:{dicom_sender.endpoint.port}")

        dicom_sender._send_single_dataset(ds, metrics)

        # Verify send succeeded
        assert metrics.successes == 1, \
            f"Send failed to {called_aet}: {metrics.failures} failures, " \
            f"error rate: {metrics.error_rate:.1%}"

        print(f"  Status: SUCCESS")
        print(f"  Latency: {metrics.avg_latency_ms:.2f}ms")

        # C-FIND verification
        print(f"\n[C-FIND VERIFICATION]")
        patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
        study = verify_study_arrived(cfind_client, test_study_uid, perf_config, patient_id=patient_id)
        if study is not None:
            print(f"  [OK] Study confirmed in Compass for called AET: {called_aet}")

    finally:
        # Restore original AE title
        dicom_sender.endpoint.remote_ae_title = original_aet


# ============================================================================
# Summary Test
# ============================================================================

@pytest.mark.integration
def test_all_called_aets_summary():
    """
    Summary of all called AE Titles being tested.

    Run this first to see what AETs will be tested.
    This test doesn't send anything - just displays configuration.
    """
    print(f"\n{'='*70}")
    print(f"CALLED AE TITLE TEST SUITE")
    print(f"{'='*70}")
    print(f"\nTotal called AE Titles configured: {len(CALLED_AET_TEST_CASES)}")
    print(f"\nCalled AE Titles:")

    for i, test_case in enumerate(CALLED_AET_TEST_CASES, 1):
        print(f"\n{i}. {test_case['aet']}")
        print(f"   Description: {test_case['description']}")

    print(f"\n{'='*70}")
    print(f"To run all AET tests:")
    print(f"  pytest tests/test_calling_aet_routing.py::test_called_aet_routing -v -s")
    print(f"\nTo run specific AET test:")
    print(f"  pytest tests/test_calling_aet_routing.py::test_called_aet_routing[LB_HTM_GI] -v -s")
    print(f"\nTo run batch test (multiple AETs):")
    print(f"  pytest tests/test_calling_aet_routing.py::test_multiple_aets_batch_send -v -s")
    print(f"{'='*70}\n")


# ============================================================================
# Batch Test - Multiple AETs
# ============================================================================

@pytest.mark.integration
def test_multiple_aets_batch_send(
    small_dicom_files,
    dicom_sender,
    cfind_client,
    perf_config,
):
    """
    Advanced test: Send multiple files to multiple different called AETs.

    This simulates a more realistic scenario where studies are
    sent to different Compass destinations in sequence.

    Tests:
    - All called AETs accept studies
    - Multiple destinations can receive studies
    - Each destination's studies are tracked independently
    """
    from itertools import cycle

    print(f"\n{'='*70}")
    print(f"BATCH TEST: Multiple Files with Rotating Called AETs")
    print(f"{'='*70}")
    print(f"  Files to send: {len(small_dicom_files)}")
    print(f"  Called AETs: {len(CALLED_AET_TEST_CASES)}")

    # Cycle through called AETs for each file
    aet_cycle = cycle([tc['aet'] for tc in CALLED_AET_TEST_CASES])

    results = []
    original_aet = dicom_sender.endpoint.remote_ae_title

    print(f"\n[SENDING]")

    try:
        for i, file in enumerate(small_dicom_files):
            called_aet = next(aet_cycle)
            metrics = PerfMetrics()

            # Load and modify file
            ds = load_dataset(file)
            ds.StudyInstanceUID = generate_uid()
            ds.SeriesInstanceUID = generate_uid()
            ds.SOPInstanceUID = generate_uid()

            # Set called AET
            dicom_sender.endpoint.remote_ae_title = called_aet

            # Send
            dicom_sender._send_single_dataset(ds, metrics)

            # Track results
            result = {
                'file': file.name,
                'called_aet': called_aet,
                'study_uid': ds.StudyInstanceUID,
                'patient_id': str(ds.PatientID) if hasattr(ds, 'PatientID') else None,
                'success': metrics.successes == 1,
                'latency': metrics.avg_latency_ms
            }
            results.append(result)

            status = 'OK  ' if result['success'] else 'FAIL'
            print(f"  [{i+1:2d}/{len(small_dicom_files)}] {called_aet:20} -> "
                  f"{status} ({result['latency']:.0f}ms) | StudyUID: {ds.StudyInstanceUID[:40]}...")

        # Summary
        print(f"\n{'='*70}")
        print(f"[RESULTS SUMMARY]")
        print(f"{'='*70}")
        print(f"  Total sent: {len(results)}")
        print(f"  Successful: {sum(1 for r in results if r['success'])}")
        print(f"  Failed: {sum(1 for r in results if not r['success'])}")

        # Group by called AET
        from collections import Counter
        aet_counts = Counter(r['called_aet'] for r in results)
        print(f"\n  Sends per called AET:")
        for aet, count in sorted(aet_counts.items()):
            successes = sum(1 for r in results if r['called_aet'] == aet and r['success'])
            avg_latency = sum(r['latency'] for r in results if r['called_aet'] == aet) / count
            print(f"    {aet:20} : {successes}/{count} succeeded, avg {avg_latency:.0f}ms")

        # Verify all succeeded
        failed = [r for r in results if not r['success']]
        if failed:
            print(f"\n  Failed sends:")
            for r in failed:
                print(f"    - {r['called_aet']} : {r['file']}")

        assert all(r['success'] for r in results), \
            f"Some sends failed: {len(failed)}/{len(results)}"

        print(f"\n[SUCCESS: All {len(results)} sends completed successfully]")

        # C-FIND verification: verify first UID per AET
        print(f"\n[C-FIND VERIFICATION]")
        verified_aets = set()
        for r in results:
            if r['called_aet'] not in verified_aets and r['success']:
                verified_aets.add(r['called_aet'])
                study = verify_study_arrived(cfind_client, str(r['study_uid']), perf_config, patient_id=r.get('patient_id'))
                if study is not None:
                    print(f"  [OK] Verified sample study for AET {r['called_aet']}")

    finally:
        dicom_sender.endpoint.remote_ae_title = original_aet


# ============================================================================
# Unknown Called AET Test
# ============================================================================

@pytest.mark.integration
@pytest.mark.manual_verify
def test_unknown_called_aet(
    single_dicom_file,
    dicom_sender,
    metrics: PerfMetrics,
):
    """
    Test that Compass rejects a send to an unknown/unregistered called AE Title.

    Expected behavior: Compass should reject the association or refuse the
    C-STORE when the called AET is not configured, ensuring studies are not
    silently routed to an unintended destination.
    """
    unknown_aet = 'UNKNOWN_TEST_AET'

    print(f"\n{'='*70}")
    print(f"TEST: Unknown Called AET")
    print(f"{'='*70}")
    print(f"  Called AET: {unknown_aet} (not registered in Compass)")

    ds = load_dataset(single_dicom_file)
    test_study_uid = generate_uid()
    ds.StudyInstanceUID = test_study_uid
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()

    study_desc = f"UNKNOWN_AET_TEST_{unknown_aet}"
    if hasattr(ds, 'StudyDescription'):
        ds.StudyDescription = study_desc
    else:
        ds.add_new((0x0008, 0x1030), 'LO', study_desc)

    print(f"  StudyInstanceUID: {test_study_uid}")

    original_aet = dicom_sender.endpoint.remote_ae_title
    dicom_sender.endpoint.remote_ae_title = unknown_aet

    try:
        print(f"\n[SENDING]")
        dicom_sender._send_single_dataset(ds, metrics)

        print(f"\n[RESULT]")
        print(f"  Successes: {metrics.successes}, Failures: {metrics.failures}")

        with manual_verification_required(
            "Unknown called AET rejection -- verify on Compass server that "
            f"'{unknown_aet}' is not a configured destination"
        ):
            assert metrics.failures >= 1, (
                f"Compass ACCEPTED unknown called AET '{unknown_aet}' — "
                f"expected rejection. Study {test_study_uid} may have been "
                f"routed to an unintended destination."
            )
        print(f"  Compass correctly rejected unknown called AET '{unknown_aet}'")

    finally:
        dicom_sender.endpoint.remote_ae_title = original_aet


# ============================================================================
# Called AET with Different Modalities
# ============================================================================

@pytest.mark.integration
@pytest.mark.parametrize("modality", ["CT", "MR", "CR", "US", "OPV"])
def test_called_aet_with_modality_combinations(
    dicom_by_modality: dict,
    dicom_sender,
    modality: str,
    cfind_client,
    perf_config,
):
    """
    Test called AET routing with different modalities.

    Some routing rules may depend on both called AET and modality.
    This test validates that all called AETs work with all modalities.
    """
    from tests.conftest import get_files_by_modality

    # Get files for this modality (will skip if not available)
    files = get_files_by_modality(dicom_by_modality, modality, count=1)

    print(f"\n{'='*70}")
    print(f"TEST: All Called AETs with Modality {modality}")
    print(f"{'='*70}")

    results = []
    original_aet = dicom_sender.endpoint.remote_ae_title

    try:
        for test_case in CALLED_AET_TEST_CASES:
            called_aet = test_case['aet']
            metrics = PerfMetrics()

            # Load and modify file
            ds = load_dataset(files[0])
            ds.Modality = modality  # Ensure modality is set
            ds.StudyInstanceUID = generate_uid()
            ds.SeriesInstanceUID = generate_uid()
            ds.SOPInstanceUID = generate_uid()

            # Set called AET
            dicom_sender.endpoint.remote_ae_title = called_aet

            # Send
            dicom_sender._send_single_dataset(ds, metrics)

            # Track results
            result = {
                'aet': called_aet,
                'modality': modality,
                'study_uid': ds.StudyInstanceUID,
                'patient_id': str(ds.PatientID) if hasattr(ds, 'PatientID') else None,
                'success': metrics.successes == 1,
                'latency': metrics.avg_latency_ms
            }
            results.append(result)

            status = 'OK  ' if result['success'] else 'FAIL'
            print(f"  {called_aet:20} + {modality:3} -> {status} ({result['latency']:.0f}ms)")

        # Summary
        successful = sum(1 for r in results if r['success'])
        print(f"\n  Results: {successful}/{len(results)} succeeded for modality {modality}")

        # Verify all succeeded
        assert all(r['success'] for r in results), \
            f"Some AET+Modality combinations failed for {modality}"

        # C-FIND verification for each send
        print(f"\n[C-FIND VERIFICATION]")
        for r in results:
            if r['success']:
                study = verify_study_arrived(cfind_client, str(r['study_uid']), perf_config, patient_id=r.get('patient_id'))
                if study is not None:
                    print(f"  [OK] Verified {r['aet']} + {modality}")

    finally:
        dicom_sender.endpoint.remote_ae_title = original_aet


# ============================================================================
# Helper: Add New Called AET Template
# ============================================================================

def add_called_aet_template():
    """
    Template for adding new called AE Titles.

    Copy this structure and add to CALLED_AET_TEST_CASES list:
    """
    new_called_aet = {
        'name': 'DESTINATION_NAME',  # Short identifier (no spaces)
        'description': 'Human-readable description of the destination',
        'aet': 'ACTUAL_AE_TITLE',  # The actual AE Title string
    }
    return new_called_aet
