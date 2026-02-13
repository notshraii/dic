# tests/test_data_selection_examples.py

"""
Example tests demonstrating how to use test data selection fixtures for different scenarios.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import List

from metrics import PerfMetrics
from tests.conftest import verify_study_arrived


# ============================================================================
# Example 1: Testing with Large Files
# ============================================================================

@pytest.mark.integration
def test_send_large_file(dicom_sender, large_dicom_file: Path, metrics: PerfMetrics,
                         cfind_client, perf_config):
    """
    Test sending a large DICOM file (>10MB).

    Automatically skips if no large file is available.
    Uses the large_dicom_file fixture which selects appropriately.
    """
    from data_loader import load_dataset

    file_size_mb = large_dicom_file.stat().st_size / (1024 * 1024)
    print(f"Testing with large file: {file_size_mb:.2f}MB")

    ds = load_dataset(large_dicom_file)
    dicom_sender._send_single_dataset(ds, metrics)

    assert metrics.successes == 1, "Large file send failed"
    assert metrics.error_rate == 0, "Errors occurred during large file send"

    # Large files may take longer, so use higher latency threshold
    assert metrics.avg_latency_ms < 10000, f"Large file took too long: {metrics.avg_latency_ms}ms"

    # C-FIND verification
    study_uid = str(ds.StudyInstanceUID) if hasattr(ds, 'StudyInstanceUID') else None
    if study_uid:
        verify_study_arrived(cfind_client, study_uid, perf_config)


# ============================================================================
# Example 2: Testing with Small Files Batch
# ============================================================================

@pytest.mark.integration
def test_send_batch_small_files(dicom_sender, small_dicom_files: List[Path], metrics: PerfMetrics,
                                cfind_client, perf_config):
    """
    Test sending a batch of small files (<1MB each).

    Automatically skips if fewer than 3 small files available.
    Returns up to 10 small files from the dataset.
    """
    from data_loader import load_dataset

    print(f"Sending batch of {len(small_dicom_files)} small files...")

    sent_uids = []
    for file in small_dicom_files:
        ds = load_dataset(file)
        dicom_sender._send_single_dataset(ds, metrics)
        if hasattr(ds, 'StudyInstanceUID'):
            sent_uids.append(str(ds.StudyInstanceUID))

    expected_count = len(small_dicom_files)
    assert metrics.total == expected_count, f"Expected {expected_count} sends, got {metrics.total}"
    assert metrics.error_rate == 0, f"Some sends failed: {metrics.failures} failures"

    print(f"Successfully sent {metrics.successes} files")

    # C-FIND verification (sample up to 5)
    for uid in list(dict.fromkeys(sent_uids))[:5]:
        verify_study_arrived(cfind_client, uid, perf_config)


# ============================================================================
# Example 3: Parametrized Test Across Modalities
# ============================================================================

@pytest.mark.integration
@pytest.mark.parametrize("modality", ["CT", "MR", "CR", "US"])
def test_send_by_modality(
    dicom_sender,
    dicom_by_modality: dict,
    metrics: PerfMetrics,
    modality: str,
    cfind_client,
    perf_config,
):
    """
    Test sending files of specific modality.

    Parametrized to run for CT, MR, CR, and US.
    Gracefully skips if a particular modality is not available.
    """
    from data_loader import load_dataset
    from tests.conftest import get_files_by_modality

    # This will skip if modality not available
    files = get_files_by_modality(dicom_by_modality, modality, count=3)

    print(f"Testing {modality} modality with {len(files)} files")

    sent_uids = []
    for file in files:
        ds = load_dataset(file)
        dicom_sender._send_single_dataset(ds, metrics)
        if hasattr(ds, 'StudyInstanceUID'):
            sent_uids.append(str(ds.StudyInstanceUID))

    assert metrics.successes == len(files), f"{modality}: Some sends failed"
    assert metrics.error_rate == 0, f"{modality}: Error rate too high"

    print(f"{modality}: All {len(files)} files sent successfully")

    # C-FIND verification (sample up to 3)
    for uid in list(dict.fromkeys(sent_uids))[:3]:
        verify_study_arrived(cfind_client, uid, perf_config)


# ============================================================================
# Example 4: Testing with Different File Counts
# ============================================================================

@pytest.mark.integration
@pytest.mark.parametrize("dicom_file_subset", [1, 5, 10], indirect=True)
def test_send_variable_batch_sizes(
    dicom_sender,
    dicom_file_subset: List[Path],
    metrics: PerfMetrics
):
    """
    Test sending different batch sizes (1, 5, 10 files).
    
    Uses indirect parametrization to pass count to fixture.
    Automatically skips if not enough files available.
    """
    from data_loader import load_dataset
    
    batch_size = len(dicom_file_subset)
    print(f"Testing batch size: {batch_size}")
    
    for file in dicom_file_subset:
        ds = load_dataset(file)
        dicom_sender._send_single_dataset(ds, metrics)
    
    assert metrics.total == batch_size
    assert metrics.error_rate == 0
    
    avg_latency = metrics.avg_latency_ms
    print(f"Batch of {batch_size}: avg latency {avg_latency:.2f}ms")


# ============================================================================
# Example 5: Testing with Size Categories
# ============================================================================

@pytest.mark.integration
@pytest.mark.parametrize("size_category", ["small", "medium", "large"])
def test_send_by_size_category(
    dicom_sender,
    dicom_by_size_category: dict,
    metrics: PerfMetrics,
    size_category: str
):
    """
    Test sending files from different size categories.
    
    Categories: small (<1MB), medium (1-10MB), large (>10MB)
    Gracefully skips if category has no files.
    """
    from data_loader import load_dataset
    
    files = dicom_by_size_category.get(size_category, [])
    
    if not files:
        pytest.skip(f"No {size_category} files available")
    
    # Test with up to 3 files from this category
    test_files = files[:3]
    print(f"Testing {size_category} category with {len(test_files)} files")
    
    for file in test_files:
        ds = load_dataset(file)
        dicom_sender._send_single_dataset(ds, metrics)
    
    assert metrics.successes == len(test_files)
    
    # Different latency expectations by size
    latency_thresholds = {
        'small': 1000,   # 1 second
        'medium': 3000,  # 3 seconds
        'large': 10000   # 10 seconds
    }
    
    max_latency = latency_thresholds[size_category]
    assert metrics.avg_latency_ms < max_latency, \
        f"{size_category} files exceeded latency threshold"


# ============================================================================
# Example 6: Simple Single File Test
# ============================================================================

@pytest.mark.integration
def test_single_file_basic(dicom_sender, single_dicom_file: Path, metrics: PerfMetrics):
    """
    Basic test with a single file - simplest case.
    
    Uses single_dicom_file fixture which just picks any available file.
    Good for smoke tests or basic connectivity checks.
    """
    from data_loader import load_dataset
    
    print(f"Testing with file: {single_dicom_file.name}")
    
    ds = load_dataset(single_dicom_file)
    dicom_sender._send_single_dataset(ds, metrics)
    
    assert metrics.successes == 1, "Basic send failed"
    assert metrics.error_rate == 0, "Error occurred"
    
    print("Basic send test passed")


# ============================================================================
# Example 7: Conditional Test Based on Available Data
# ============================================================================

@pytest.mark.integration
def test_all_available_modalities(dicom_sender, dicom_by_modality: dict, metrics: PerfMetrics):
    """
    Test all modalities that are available in the dataset.
    
    Dynamically adapts to whatever modalities are present.
    Won't skip - will test whatever is available.
    """
    from data_loader import load_dataset
    
    if not dicom_by_modality:
        pytest.skip("No DICOM files with readable modality available")
    
    results = {}
    
    for modality, files in dicom_by_modality.items():
        modality_metrics = PerfMetrics()  # Separate metrics per modality
        
        # Test first 2 files of each modality
        test_files = files[:2]
        
        for file in test_files:
            ds = load_dataset(file)
            dicom_sender._send_single_dataset(ds, modality_metrics)
        
        results[modality] = {
            'count': len(test_files),
            'successes': modality_metrics.successes,
            'failures': modality_metrics.failures,
            'avg_latency': modality_metrics.avg_latency_ms
        }
    
    print("\nResults by modality:")
    for modality, result in results.items():
        print(f"  {modality}: {result['successes']}/{result['count']} succeeded, "
              f"avg latency {result['avg_latency']:.2f}ms")
    
    # Overall assertion
    total_successes = sum(r['successes'] for r in results.values())
    total_count = sum(r['count'] for r in results.values())
    
    assert total_successes == total_count, "Some sends failed across modalities"

