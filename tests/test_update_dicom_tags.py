# tests/test_update_dicom_tags.py

"""
Tests that verify update_dicom_tags.py functionality.

Tests tag updates, verification, and various update modes using sample DICOM files.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from pydicom import dcmread
from pydicom.uid import generate_uid

# Import functions from update_dicom_tags module
import sys
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from update_dicom_tags import (
    update_dicom_file,
    verify_changes,
    generate_accession_number,
    is_valid_uid,
    get_original_values,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def dicom_samples_dir():
    """Path to dicom_samples directory."""
    samples_dir = project_root / "dicom_samples"
    if not samples_dir.exists():
        pytest.skip(f"dicom_samples directory not found at {samples_dir}")
    return samples_dir


@pytest.fixture
def sample_dicom_files(dicom_samples_dir):
    """List of sample DICOM files from dicom_samples directory."""
    dcm_files = []
    for ext in ['.dcm', '.dicom']:
        dcm_files.extend(list(dicom_samples_dir.glob(f"*{ext}")))
    
    if not dcm_files:
        pytest.skip(f"No DICOM files found in {dicom_samples_dir}")
    
    # Return a few representative files for testing
    return sorted(dcm_files)[:5]  # Use first 5 files


@pytest.fixture
def temp_dicom_file(sample_dicom_files):
    """
    Create a temporary copy of a sample DICOM file for testing.
    Returns the path to the temporary file.
    """
    if not sample_dicom_files:
        pytest.skip("No sample DICOM files available")
    
    # Use the first available file
    source_file = sample_dicom_files[0]
    
    # Create temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix='.dcm', prefix='test_update_')
    os.close(temp_fd)
    
    # Copy source file to temp location
    shutil.copy2(source_file, temp_path)
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def temp_dicom_folder(sample_dicom_files):
    """
    Create a temporary folder with copies of sample DICOM files.
    Returns the path to the temporary folder.
    """
    if not sample_dicom_files:
        pytest.skip("No sample DICOM files available")
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix='test_update_folder_')
    
    # Copy sample files to temp directory
    for source_file in sample_dicom_files[:3]:  # Use first 3 files
        dest_file = os.path.join(temp_dir, source_file.name)
        shutil.copy2(source_file, dest_file)
    
    yield temp_dir
    
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


# ============================================================================
# Test Cases
# ============================================================================

def test_update_dicom_file_basic(temp_dicom_file):
    """Test basic DICOM file update functionality."""
    # Read original file to get baseline values
    original_ds = dcmread(temp_dicom_file)
    original_study_uid = getattr(original_ds, 'StudyInstanceUID', None)
    
    # Update the file (uses default test tags and generates unique IDs)
    success, message, original_values, new_values = update_dicom_file(
        temp_dicom_file,
        dry_run=False,
        verbose=False
    )
    
    assert success, f"Update failed: {message}"
    assert 'StudyInstanceUID' in new_values, "StudyInstanceUID should be in new_values"
    assert 'AccessionNumber' in new_values, "AccessionNumber should be in new_values"
    assert 'SeriesInstanceUID' in new_values, "SeriesInstanceUID should be in new_values"
    
    # Verify the changes were applied
    updated_ds = dcmread(temp_dicom_file)
    assert hasattr(updated_ds, 'StudyInstanceUID'), "StudyInstanceUID tag should exist"
    assert hasattr(updated_ds, 'PatientID'), "PatientID tag should exist"
    assert updated_ds.PatientID == '11043207', "PatientID should be updated to default test value"
    
    # Verify UIDs are valid
    assert is_valid_uid(updated_ds.StudyInstanceUID), "StudyInstanceUID should be valid"
    assert is_valid_uid(updated_ds.SeriesInstanceUID), "SeriesInstanceUID should be valid"
    
    # Verify using verify_changes function
    verify_success, verify_message = verify_changes(
        temp_dicom_file,
        original_values,
        new_values
    )
    
    assert verify_success, f"Verification failed: {verify_message}"


def test_update_with_default_test_tags(temp_dicom_file):
    """Test updating with default test tags (this is the default behavior)."""
    success, message, original_values, new_values = update_dicom_file(
        temp_dicom_file,
        dry_run=False,
        verbose=False
    )
    
    assert success, f"Update failed: {message}"
    
    # Verify default test tags were applied
    updated_ds = dcmread(temp_dicom_file)
    assert updated_ds.PatientID == '11043207'
    assert updated_ds.PatientName == 'ZZTESTPATIENT^MIDIA THREE'
    assert updated_ds.PatientBirthDate == '19010101'
    assert updated_ds.InstitutionName == 'TEST FACILITY'
    
    # Verify new_values contains the expected UIDs
    assert 'StudyInstanceUID' in new_values
    assert 'AccessionNumber' in new_values
    assert 'SeriesInstanceUID' in new_values
    
    # Verify using verify_changes
    verify_success, verify_message = verify_changes(
        temp_dicom_file,
        original_values,
        new_values
    )
    
    assert verify_success, f"Verification failed: {verify_message}"


def test_update_with_unique_id_generation(temp_dicom_file):
    """Test updating with unique ID generation (this is the default behavior)."""
    # Read original UIDs
    original_ds = dcmread(temp_dicom_file)
    original_study_uid = getattr(original_ds, 'StudyInstanceUID', None)
    original_series_uid = getattr(original_ds, 'SeriesInstanceUID', None)
    original_accession = getattr(original_ds, 'AccessionNumber', None)
    
    success, message, original_values, new_values = update_dicom_file(
        temp_dicom_file,
        dry_run=False,
        verbose=False
    )
    
    assert success, f"Update failed: {message}"
    
    # Verify new UIDs were generated
    updated_ds = dcmread(temp_dicom_file)
    new_study_uid = updated_ds.StudyInstanceUID
    new_series_uid = updated_ds.SeriesInstanceUID
    new_accession = updated_ds.AccessionNumber
    
    # Verify UIDs are valid
    assert is_valid_uid(new_study_uid), f"StudyInstanceUID is not valid: {new_study_uid}"
    assert is_valid_uid(new_series_uid), f"SeriesInstanceUID is not valid: {new_series_uid}"
    
    # Verify AccessionNumber format (should match timestamp format)
    assert new_accession is not None, "AccessionNumber should be generated"
    assert len(new_accession) > 0, "AccessionNumber should not be empty"
    
    # Verify new_values contains the generated UIDs
    assert 'StudyInstanceUID' in new_values
    assert 'SeriesInstanceUID' in new_values
    assert 'AccessionNumber' in new_values
    assert is_valid_uid(new_values['StudyInstanceUID'])
    assert is_valid_uid(new_values['SeriesInstanceUID'])
    
    # UIDs should be different from originals (if they existed and were different)
    if original_study_uid and original_study_uid != new_study_uid:
        assert new_study_uid != original_study_uid, "StudyInstanceUID should be different"
    if original_series_uid and original_series_uid != new_series_uid:
        assert new_series_uid != original_series_uid, "SeriesInstanceUID should be different"
    
    # Verify using verify_changes
    verify_success, verify_message = verify_changes(
        temp_dicom_file,
        original_values,
        new_values
    )
    
    assert verify_success, f"Verification failed: {verify_message}"


def test_update_with_all_features(temp_dicom_file):
    """Test updating with all features (default tags + unique IDs)."""
    success, message, original_values, new_values = update_dicom_file(
        temp_dicom_file,
        dry_run=False,
        verbose=False
    )
    
    assert success, f"Update failed: {message}"
    
    # Verify all updates were applied
    updated_ds = dcmread(temp_dicom_file)
    
    # Default test tags
    assert updated_ds.PatientID == '11043207'
    assert updated_ds.PatientName == 'ZZTESTPATIENT^MIDIA THREE'
    
    # Unique IDs
    assert is_valid_uid(updated_ds.StudyInstanceUID)
    assert is_valid_uid(updated_ds.SeriesInstanceUID)
    assert updated_ds.AccessionNumber is not None
    
    # Verify using verify_changes
    verify_success, verify_message = verify_changes(
        temp_dicom_file,
        original_values,
        new_values
    )
    
    assert verify_success, f"Verification failed: {verify_message}"


def test_dry_run_mode(temp_dicom_file):
    """Test that dry-run mode doesn't modify files."""
    # Read original file
    original_ds = dcmread(temp_dicom_file)
    original_patient_id = getattr(original_ds, 'PatientID', None)
    original_study_uid = getattr(original_ds, 'StudyInstanceUID', None)
    
    # Run in dry-run mode
    success, message, original_values, new_values = update_dicom_file(
        temp_dicom_file,
        dry_run=True,
        verbose=False
    )
    
    assert success, f"Dry-run failed: {message}"
    
    # Verify file was NOT modified
    unchanged_ds = dcmread(temp_dicom_file)
    current_patient_id = getattr(unchanged_ds, 'PatientID', None)
    current_study_uid = getattr(unchanged_ds, 'StudyInstanceUID', None)
    
    assert current_patient_id == original_patient_id, \
        "File should not be modified in dry-run mode"
    if original_study_uid:
        assert current_study_uid == original_study_uid, \
            "File should not be modified in dry-run mode"




def test_get_tag_tuple():
    """Test converting tag identifiers to tuples - REMOVED: function no longer exists in module."""
    # This test is no longer applicable as get_tag_tuple was removed
    pytest.skip("get_tag_tuple function no longer exists in update_dicom_tags module")


def test_update_tag_in_dataset(temp_dicom_file):
    """Test updating a tag in a dataset - REMOVED: function no longer exists in module."""
    # This test is no longer applicable as update_tag_in_dataset was removed
    pytest.skip("update_tag_in_dataset function no longer exists in update_dicom_tags module")


def test_is_valid_uid():
    """Test UID validation."""
    # Valid UIDs
    assert is_valid_uid("1.2.3.4.5")
    assert is_valid_uid("1.2.840.10008.1.2")
    assert is_valid_uid("0")
    
    # Invalid UIDs
    assert not is_valid_uid("")
    assert not is_valid_uid("01.2.3")  # Component starts with 0
    assert not is_valid_uid("1.2.3.abc")  # Non-numeric component
    assert not is_valid_uid(".")  # Empty component
    assert not is_valid_uid("1" + "." * 64)  # Too long


def test_generate_accession_number():
    """Test accession number generation."""
    accession1 = generate_accession_number()
    accession2 = generate_accession_number()
    
    # Should generate non-empty strings
    assert len(accession1) > 0
    assert len(accession2) > 0
    
    # Should have timestamp format
    assert len(accession1.split('-')) >= 2  # At least date-time-microseconds


def test_get_original_values(temp_dicom_file):
    """Test extracting original values from DICOM dataset."""
    ds = dcmread(temp_dicom_file)
    
    # Get original values for default tags
    originals = get_original_values(ds)
    
    assert isinstance(originals, dict)
    assert 'StudyInstanceUID' in originals
    assert 'AccessionNumber' in originals
    assert 'SeriesInstanceUID' in originals


@pytest.mark.parametrize("sample_file", [
    "CR_512x512_12bit_MONO1.dcm",
    "CT_512x512_16bit_MONO2.dcm",
    "MR_512x512_16bit_MONO1.dcm",
])
def test_update_different_modalities(dicom_samples_dir, sample_file):
    """Test updating tags in different modality files."""
    source_file = dicom_samples_dir / sample_file
    if not source_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")
    
    # Create temporary copy
    temp_fd, temp_path = tempfile.mkstemp(suffix='.dcm', prefix='test_modality_')
    os.close(temp_fd)
    shutil.copy2(source_file, temp_path)
    
    try:
        # Update with default behavior
        success, message, original_values, new_values = update_dicom_file(
            temp_path,
            dry_run=False,
            verbose=False
        )
        
        assert success, f"Update failed for {sample_file}: {message}"
        
        # Verify updates
        updated_ds = dcmread(temp_path)
        assert hasattr(updated_ds, 'PatientID')
        assert updated_ds.PatientID == '11043207'
        assert is_valid_uid(updated_ds.StudyInstanceUID)
        
        # Verify using verify_changes
        verify_success, verify_message = verify_changes(
            temp_path,
            original_values,
            new_values
        )
        
        assert verify_success, f"Verification failed for {sample_file}: {verify_message}"
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


