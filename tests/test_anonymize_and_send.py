# tests/test_anonymize_and_send.py

"""
Tests the end-to-end workflow of anonymizing DICOM files and sending them to Compass.
"""

import os
import shutil
import tempfile
from datetime import datetime
from typing import Tuple

import pytest
from pydicom import dcmread
from pydicom.uid import generate_uid

# Import framework modules from root
from data_loader import load_dataset
from dicom_sender import DicomSender
from metrics import PerfMetrics


def generate_accession_number() -> str:
    """Generate a unique accession number based on current timestamp."""
    now = datetime.now()
    microseconds = now.microsecond
    return f"{now.strftime('%Y%m%d-%H%M%S')}-{microseconds:06d}"


def update_tag_recursively(ds, tag_tuple: Tuple, value, vr: str = None) -> int:
    """
    Recursively update a tag in the dataset and all nested sequences.
    
    Args:
        ds: pydicom Dataset object
        tag_tuple: Tuple of (group, element) for the tag
        value: Value to set for the tag
        vr: Value Representation (e.g., 'PN', 'LO', 'DA')
        
    Returns:
        Count of how many times the tag was updated
    """
    count = 0
    
    if tag_tuple in ds:
        ds[tag_tuple].value = value
        count += 1
    
    for elem in ds:
        if elem.VR == "SQ" and elem.value:
            for seq_item in elem.value:
                count += update_tag_recursively(seq_item, tag_tuple, value, vr)
    
    return count


def anonymize_dicom_file(input_file: str, output_file: str) -> Tuple[bool, str, dict]:
    """
    Anonymize a DICOM file by updating all PHI tags.
    
    Returns:
        Tuple of (success, message, new_uids_dict)
    """
    try:
        print(f"\n{'='*60}")
        print("STEP 1: ANONYMIZING DICOM FILE")
        print(f"{'='*60}")
        
        # Use load_dataset for proper encoding consistency
        from pathlib import Path
        ds = load_dataset(Path(input_file))
        print(f"  [OK] File read successfully: {os.path.basename(input_file)}")
        
        # Generate new unique identifiers
        new_study_uid = generate_uid()
        new_accession_number = generate_accession_number()
        new_series_uid = generate_uid()
        new_sop_instance_uid = generate_uid()
        
        print(f"  [OK] Generated new StudyInstanceUID: {new_study_uid}")
        
        # Update UIDs (including nested sequences)
        if (0x0020, 0x000d) not in ds:
            ds.add_new((0x0020, 0x000d), 'UI', new_study_uid)
        update_tag_recursively(ds, (0x0020, 0x000d), new_study_uid, 'UI')
        
        if (0x0008, 0x0050) not in ds:
            ds.add_new((0x0008, 0x0050), 'SH', new_accession_number)
        update_tag_recursively(ds, (0x0008, 0x0050), new_accession_number, 'SH')
        
        if (0x0020, 0x000e) not in ds:
            ds.add_new((0x0020, 0x000e), 'UI', new_series_uid)
        update_tag_recursively(ds, (0x0020, 0x000e), new_series_uid, 'UI')
        
        if (0x0008, 0x0018) not in ds:
            ds.add_new((0x0008, 0x0018), 'UI', new_sop_instance_uid)
        update_tag_recursively(ds, (0x0008, 0x0018), new_sop_instance_uid, 'UI')
        
        # Anonymize patient demographics
        if (0x0010, 0x0020) not in ds:
            ds.add_new((0x0010, 0x0020), 'LO', "11043207")
        update_tag_recursively(ds, (0x0010, 0x0020), "11043207", 'LO')
        
        if (0x0010, 0x0010) not in ds:
            ds.add_new((0x0010, 0x0010), 'PN', "ZZTESTPATIENT^ANONYMIZED")
        update_tag_recursively(ds, (0x0010, 0x0010), "ZZTESTPATIENT^ANONYMIZED", 'PN')
        
        if (0x0010, 0x0030) not in ds:
            ds.add_new((0x0010, 0x0030), 'DA', "19010101")
        update_tag_recursively(ds, (0x0010, 0x0030), "19010101", 'DA')
        
        if (0x0008, 0x0080) not in ds:
            ds.add_new((0x0008, 0x0080), 'LO', "TEST FACILITY")
        update_tag_recursively(ds, (0x0008, 0x0080), "TEST FACILITY", 'LO')
        
        if (0x0008, 0x0090) not in ds:
            ds.add_new((0x0008, 0x0090), 'PN', "TEST^PROVIDER")
        update_tag_recursively(ds, (0x0008, 0x0090), "TEST^PROVIDER", 'PN')
        
        # Save anonymized file with proper encoding
        # Determine encoding based on transfer syntax
        transfer_syntax = str(ds.file_meta.TransferSyntaxUID) if hasattr(ds, 'file_meta') and hasattr(ds.file_meta, 'TransferSyntaxUID') else '1.2.840.10008.1.2.1'
        
        if transfer_syntax == '1.2.840.10008.1.2':  # Implicit VR Little Endian
            ds.save_as(output_file, implicit_vr=True, little_endian=True)
        elif transfer_syntax == '1.2.840.10008.1.2.2':  # Explicit VR Big Endian
            ds.save_as(output_file, implicit_vr=False, little_endian=False)
        else:  # Explicit VR Little Endian (default)
            ds.save_as(output_file, implicit_vr=False, little_endian=True)
        print(f"  [OK] Anonymized file saved")
        
        new_uids = {
            'study_uid': new_study_uid,
            'accession_number': new_accession_number,
            'series_uid': new_series_uid,
            'sop_instance_uid': new_sop_instance_uid
        }
        
        return True, "Successfully anonymized", new_uids
        
    except Exception as e:
        return False, f"Error during anonymization: {e}", {}


@pytest.fixture
def temp_anonymized_file(dicom_files):
    """
    Fixture that creates an anonymized copy of the first DICOM file.
    Cleans up after test completes.
    """
    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix="test_anon_")
    anonymized_path = os.path.join(temp_dir, "anonymized.dcm")
    
    # Anonymize the first file
    success, message, uids = anonymize_dicom_file(str(dicom_files[0]), anonymized_path)
    
    if not success:
        shutil.rmtree(temp_dir)
        pytest.fail(f"Failed to create anonymized file: {message}")
    
    yield anonymized_path, uids
    
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.mark.integration
def test_anonymize_and_send_single_file(
    dicom_sender: DicomSender,
    temp_anonymized_file,
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
):
    """
    Integration test: Anonymize a file and send to Compass.
    
    This test validates:
    - Anonymization removes/replaces PHI correctly
    - Compass accepts the anonymized file
    - Transmission completes successfully with acceptable latency
    """
    anonymized_path, new_uids = temp_anonymized_file
    
    print(f"\n{'='*60}")
    print("STEP 2: SENDING TO COMPASS SERVER")
    print(f"{'='*60}")
    
    # Verify Compass is reachable
    print("  Checking Compass connectivity (C-ECHO)...")
    assert dicom_sender.ping(timeout_seconds=10), "Compass did not respond to C-ECHO ping"
    print("  [OK] Compass server is reachable")
    
    # Load and verify the anonymized dataset
    print(f"  Loading anonymized file...")
    ds = dcmread(anonymized_path)
    
    # Verify anonymization was successful
    assert str(ds.StudyInstanceUID) == new_uids['study_uid'], "StudyInstanceUID mismatch"
    assert str(ds.PatientName) == "ZZTESTPATIENT^ANONYMIZED", "PatientName not anonymized"
    assert str(ds.PatientID) == "11043207", "PatientID not anonymized"
    print(f"  [OK] Anonymization verified: StudyUID={ds.StudyInstanceUID}")
    
    # Send to Compass
    print("  Sending via C-STORE...")
    dicom_sender._send_single_dataset(ds, metrics)
    
    print(f"\n{'='*60}")
    print("STEP 3: VERIFYING SUCCESS")
    print(f"{'='*60}")
    
    # Verify transmission
    snapshot = metrics.snapshot()
    
    assert metrics.total == 1, f"Expected 1 file sent, got {metrics.total}"
    print(f"  [OK] Confirmed 1 file sent")
    
    assert metrics.successes == 1, f"Send failed: {metrics.failures} failures"
    print(f"  [OK] Send reported as successful")
    
    assert metrics.error_rate == 0, f"Error rate {metrics.error_rate:.1%} > 0%"
    print(f"  [OK] Error rate: {metrics.error_rate:.1%}")
    
    latency = snapshot['avg_latency_ms']
    assert latency is not None, "No latency data available"
    assert latency < 5000, f"Latency {latency:.2f}ms exceeds threshold of 5000ms"
    print(f"  [OK] Average latency: {latency:.2f} ms")
    
    # C-FIND verification (uses C-FIND against IM server; see [CFIND VERIFY] logs)
    from tests.conftest import verify_study_arrived
    print(f"\n{'='*60}")
    print("STEP 4: C-FIND VERIFICATION (querying C-FIND server for study)")
    print(f"{'='*60}")
    study = verify_study_arrived(
        cfind_client, new_uids['study_uid'], perf_config, patient_id="11043207"
    )
    if study is not None:
        instances = study.get('NumberOfStudyRelatedInstances')
        assert instances is not None, (
            f"NumberOfStudyRelatedInstances not returned by C-FIND. "
            f"Response keys: {list(study.keys())}"
        )
        assert int(instances) >= 1, f"Expected >= 1 instance, got {instances}"
        print(f"  [OK] NumberOfStudyRelatedInstances: {instances}")

    print(f"\n  [SUCCESS] ALL VERIFICATIONS PASSED")
    print(f"  Summary: {snapshot}")


@pytest.mark.integration
def test_anonymize_and_send_from_shared_drive(
    dicom_sender: DicomSender,
    metrics: PerfMetrics,
    perf_config,
    cfind_client,
):
    """
    Integration test using a file path from environment variable.
    
    Usage:
        export TEST_DICOM_FILE="/path/to/shared/drive/image.dcm"
        pytest tests/test_anonymize_and_send.py::test_anonymize_and_send_from_shared_drive -v -s
    
    This test is useful for testing with specific files from network shares.
    """
    input_file = perf_config.integration.test_dicom_file
    
    if not input_file:
        pytest.skip("TEST_DICOM_FILE environment variable not set")
    
    if not os.path.exists(input_file):
        pytest.fail(f"Input file does not exist: {input_file}")
    
    # Create temp directory for anonymized file
    temp_dir = tempfile.mkdtemp(prefix="test_shared_")
    anonymized_path = os.path.join(temp_dir, "anonymized.dcm")
    
    try:
        # Step 1: Anonymize
        success, message, new_uids = anonymize_dicom_file(input_file, anonymized_path)
        assert success, f"Anonymization failed: {message}"
        
        # Step 2: Verify connectivity
        assert dicom_sender.ping(), "Compass did not respond to C-ECHO ping"
        
        # Step 3: Send to Compass
        ds = dcmread(anonymized_path)
        dicom_sender._send_single_dataset(ds, metrics)
        
        # Step 4: Verify success
        assert metrics.successes == 1, f"Send failed with {metrics.failures} failures"
        assert metrics.error_rate == 0, f"Error rate {metrics.error_rate:.1%} too high"
        
        snapshot = metrics.snapshot()
        print(f"\n[SUCCESS] Test passed. Metrics: {snapshot}")

        # C-FIND verification
        from tests.conftest import verify_study_arrived
        study = verify_study_arrived(
            cfind_client, new_uids['study_uid'], perf_config, patient_id="11043207"
        )
        if study is not None:
            instances = study.get('NumberOfStudyRelatedInstances')
            assert instances is not None, (
                f"NumberOfStudyRelatedInstances not returned by C-FIND. "
                f"Response keys: {list(study.keys())}"
            )
            assert int(instances) >= 1, f"Expected >= 1 instance, got {instances}"
            print(f"  [OK] NumberOfStudyRelatedInstances: {instances}")

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@pytest.mark.integration
def test_cfind_verification_fails_for_wrong_study_uid(
    cfind_client,
    perf_config,
):
    """
    Negative test: C-FIND verification must fail when querying for a non-existent study.
    Confirms that the C-FIND check is actually running and that a wrong StudyInstanceUID
    does not pass.
    """
    if cfind_client is None:
        pytest.skip("C-FIND verification disabled (CFIND_VERIFY=false); cannot run negative C-FIND test")

    from tests.conftest import verify_study_arrived

    wrong_study_uid = "1.2.3.99999.nonexistent.wrong.study.uid"
    print(f"\n[CFIND NEGATIVE] Querying for non-existent study: {wrong_study_uid}")
    print("[CFIND NEGATIVE] Expecting C-FIND to return no match and assertion to fail...")

    with pytest.raises(AssertionError) as exc_info:
        verify_study_arrived(cfind_client, wrong_study_uid, perf_config)

    assert "not found" in str(exc_info.value)
    assert wrong_study_uid in str(exc_info.value)
    print(f"[CFIND NEGATIVE] C-FIND correctly failed for wrong study UID: {exc_info.value}")

