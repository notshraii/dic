# tests/test_routing_throughput.py

"""
Throughput tests that verify Compass routing performance at target images-per-second rates.
"""

from __future__ import annotations

import itertools
import tempfile
import shutil
import threading
from datetime import datetime
from typing import Tuple

import pytest
from pydicom import dcmread
from pydicom.uid import generate_uid

from metrics import PerfMetrics
from tests.conftest import verify_study_arrived


def generate_accession_number() -> str:
    """Generate a unique accession number based on current timestamp."""
    now = datetime.now()
    microseconds = now.microsecond
    return f"{now.strftime('%Y%m%d-%H%M%S')}-{microseconds:06d}"


def update_tag_recursively(ds, tag_tuple: Tuple, value, vr: str = None) -> int:
    """Recursively update a tag in the dataset and all nested sequences."""
    count = 0
    
    if tag_tuple in ds:
        ds[tag_tuple].value = value
        count += 1
    
    for elem in ds:
        if elem.VR == "SQ" and elem.value:
            for seq_item in elem.value:
                count += update_tag_recursively(seq_item, tag_tuple, value, vr)
    
    return count


def create_anonymized_variant(ds):
    """
    Create an anonymized copy of a dataset with unique UIDs.
    Returns a new dataset object (doesn't modify original).
    """
    # Create a deep copy by re-reading if possible, otherwise use as-is
    if hasattr(ds, 'filename') and ds.filename:
        ds_copy = dcmread(ds.filename)
    else:
        # If no filename, work with the dataset directly (it's already loaded)
        # We'll need to work with it as-is since we can't deep copy easily
        ds_copy = ds
    
    # Generate new unique identifiers
    new_study_uid = generate_uid()
    new_accession_number = generate_accession_number()
    new_series_uid = generate_uid()
    new_sop_instance_uid = generate_uid()
    
    # Update UIDs
    if (0x0020, 0x000d) not in ds_copy:
        ds_copy.add_new((0x0020, 0x000d), 'UI', new_study_uid)
    update_tag_recursively(ds_copy, (0x0020, 0x000d), new_study_uid, 'UI')
    
    if (0x0008, 0x0050) not in ds_copy:
        ds_copy.add_new((0x0008, 0x0050), 'SH', new_accession_number)
    update_tag_recursively(ds_copy, (0x0008, 0x0050), new_accession_number, 'SH')
    
    if (0x0020, 0x000e) not in ds_copy:
        ds_copy.add_new((0x0020, 0x000e), 'UI', new_series_uid)
    update_tag_recursively(ds_copy, (0x0020, 0x000e), new_series_uid, 'UI')
    
    if (0x0008, 0x0018) not in ds_copy:
        ds_copy.add_new((0x0008, 0x0018), 'UI', new_sop_instance_uid)
    update_tag_recursively(ds_copy, (0x0008, 0x0018), new_sop_instance_uid, 'UI')
    
    return ds_copy


@pytest.mark.load
@pytest.mark.parametrize("multiplier", [1.5, 2.0])
def test_routing_throughput_under_peak_plus(
    dicom_sender,
    dicom_datasets,
    metrics: PerfMetrics,
    perf_config,
    multiplier,
    cfind_client,
):
    """
    Push Compass to 150 percent and 200 percent of configured peak_images_per_second.
    Now with anonymization - each send gets unique UIDs even from a single file.
    """
    assert dicom_sender.ping(), "Compass did not respond to C-ECHO ping"

    target_peak = perf_config.load_profile.peak_images_per_second * multiplier
    duration = perf_config.load_profile.test_duration_seconds

    # Thread-safe collection of sample UIDs for verification
    _sampled_uids = []
    _sample_lock = threading.Lock()
    _max_samples = 20

    # Create anonymized variants generator
    # This will continuously create new anonymized copies with unique UIDs
    def anonymized_dataset_generator():
        for ds in itertools.cycle(dicom_datasets):
            variant = create_anonymized_variant(ds)
            # Collect a sample of UIDs for post-test verification
            if len(_sampled_uids) < _max_samples:
                with _sample_lock:
                    if len(_sampled_uids) < _max_samples:
                        _sampled_uids.append(str(variant.StudyInstanceUID))
            yield variant

    print(f"\n[INFO] Starting throughput test with {multiplier}x multiplier")
    print(f"[INFO] Each file will be anonymized with unique UIDs before sending")
    print(f"[INFO] Source files: {len(dicom_datasets)}")
    
    total_sent = dicom_sender.load_test_for_duration(
        datasets=anonymized_dataset_generator(),
        metrics=metrics,
        duration_seconds=duration,
        concurrency=perf_config.load_profile.concurrency,
        rate_limit_images_per_second=target_peak,
    )

    snapshot = metrics.snapshot()
    actual_rate = metrics.throughput_per_second()

    assert total_sent > 0, "No messages were sent during throughput test"

    assert (
        actual_rate >= 0.95 * target_peak
    ), f"Effective throughput {actual_rate:.2f}/s is below 95 percent of target {target_peak:.2f}/s"

    # Use thresholds from config
    max_error_rate = perf_config.thresholds.max_error_rate
    max_p95_latency = perf_config.thresholds.max_p95_latency_ms_short

    assert (
        metrics.error_rate <= max_error_rate
    ), f"Error rate too high: {metrics.error_rate:.3f} > {max_error_rate:.3f}"

    p95 = metrics.p95_latency_ms
    assert (
        p95 is not None and p95 <= max_p95_latency
    ), f"p95 latency too high: {p95} ms > {max_p95_latency} ms"

    print(f"\n[SUCCESS] Sent {total_sent} anonymized files with unique IDs")
    print("Throughput snapshot:", snapshot)

    # Sample-based C-FIND verification (up to 5 from collected UIDs)
    sample_uids = _sampled_uids[:5]
    if sample_uids:
        print(f"\n[C-FIND VERIFICATION] Verifying sample of {len(sample_uids)} study UIDs")
        for uid in sample_uids:
            verify_study_arrived(cfind_client, uid, perf_config)

