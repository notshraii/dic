# tests/test_load_stability.py

"""
Load stability tests that stress-test Compass at 3x peak load to verify system resilience.
"""

from __future__ import annotations

import pytest

from metrics import PerfMetrics
from tests.conftest import verify_study_arrived


@pytest.mark.load
def test_load_stability_3x_peak(
    dicom_sender,
    dicom_datasets,
    metrics: PerfMetrics,
    perf_config,
    cfind_client,
):
    """
    Drives approximate 3x-peak load for a configurable time window.
    """
    duration = perf_config.load_profile.test_duration_seconds

    total_sent = dicom_sender.load_test_for_duration(
        datasets=dicom_datasets,
        metrics=metrics,
        duration_seconds=duration,
        concurrency=perf_config.load_profile.concurrency,
        rate_limit_images_per_second=None,
    )

    snapshot = metrics.snapshot()
    print("Load stability snapshot:", snapshot)

    assert total_sent > 0, "No messages were sent during load test"
    assert metrics.total == total_sent, "Mismatch total_sent vs metrics.total"

    # Use thresholds from config
    max_error_rate = perf_config.thresholds.max_error_rate
    max_p95_latency = perf_config.thresholds.max_p95_latency_ms

    assert (
        metrics.error_rate <= max_error_rate
    ), f"Error rate too high: {metrics.error_rate:.3f} > {max_error_rate:.3f}"

    p95 = metrics.p95_latency_ms
    assert (
        p95 is not None and p95 <= max_p95_latency
    ), f"p95 latency too high: {p95} ms > {max_p95_latency} ms"

    # Sample-based C-FIND verification (up to 5 unique StudyInstanceUIDs)
    unique_uids = list({
        str(ds.StudyInstanceUID)
        for ds in dicom_datasets
        if hasattr(ds, 'StudyInstanceUID')
    })[:5]
    if unique_uids:
        print(f"\n[C-FIND VERIFICATION] Verifying sample of {len(unique_uids)} study UIDs")
        for uid in unique_uids:
            verify_study_arrived(cfind_client, uid, perf_config)

