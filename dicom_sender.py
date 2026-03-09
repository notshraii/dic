# compass_perf/dicom_sender.py

"""
DICOM C-STORE client for load testing with multi-threaded transmission and metrics collection.
"""

from __future__ import annotations

import itertools
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, Optional

from pynetdicom import AE, AllStoragePresentationContexts
from pynetdicom.sop_class import Verification

from config import DicomEndpointConfig, LoadProfileConfig
from metrics import PerfMetrics, Sample

logger = logging.getLogger(__name__)


class DicomSender:
    """High-level C-STORE sender with simple concurrency support."""

    def __init__(
        self,
        endpoint: DicomEndpointConfig,
        load_profile: LoadProfileConfig,
        accession_number: Optional[str] = None,
    ) -> None:
        self.endpoint = endpoint
        self.load_profile = load_profile
        self.accession_number = accession_number

    def _build_ae(self) -> AE:
        ae = AE(ae_title=self.endpoint.local_ae_title.encode("ascii", "ignore"))
        # Add storage presentation contexts (limit to 127 to leave room for Verification)
        storage_contexts = list(AllStoragePresentationContexts)[:127]
        for context in storage_contexts:
            ae.requested_contexts.append(context)
        # Add Verification context for C-ECHO (total = 128 max)
        ae.add_requested_context(Verification)
        return ae

    def _send_single_dataset(
        self,
        ds,
        metrics: PerfMetrics,
        stamp_accession: bool = True,
    ) -> None:
        """Send single dataset using fresh association.

        Args:
            ds: pydicom Dataset to send.
            metrics: PerfMetrics collector.
            stamp_accession: When True (default) and self.accession_number is
                configured, overwrite ds.AccessionNumber before sending.
                Pass False to skip (used by the IIMS blank-accession test).
        """
        if stamp_accession and self.accession_number:
            ds.AccessionNumber = self.accession_number

        start = time.perf_counter()
        ae = self._build_ae()
        try:
            from data_loader import ensure_encoding_consistency
            ds = ensure_encoding_consistency(ds)
            
            assoc = ae.associate(
                self.endpoint.host,
                self.endpoint.port,
                ae_title=self.endpoint.remote_ae_title.encode("ascii", "ignore"),
            )
            if not assoc.is_established:
                end = time.perf_counter()
                metrics.record(
                    Sample(
                        start_time=start,
                        end_time=end,
                        success=False,
                        error="Association failed",
                    )
                )
                return

            status = assoc.send_c_store(ds)
            assoc.release()

            end = time.perf_counter()
            success = status and status.Status in (0x0000,)
            metrics.record(
                Sample(
                    start_time=start,
                    end_time=end,
                    success=success,
                    status_code=getattr(status, "Status", None),
                    error=None if success else f"Non-success status: {status!r}",
                )
            )
        except Exception as exc:
            end = time.perf_counter()
            logger.exception("Error while sending dataset")
            metrics.record(
                Sample(
                    start_time=start,
                    end_time=end,
                    success=False,
                    error=str(exc),
                )
            )
        finally:
            ae.shutdown()

    def load_test_for_duration(
        self,
        datasets: Iterable,
        metrics: PerfMetrics,
        duration_seconds: int,
        concurrency: Optional[int] = None,
        rate_limit_images_per_second: Optional[float] = None,
    ) -> int:
        """Run load test for specified duration with rate limiting."""
        if concurrency is None:
            concurrency = self.load_profile.concurrency

        target_rate = rate_limit_images_per_second
        if target_rate is None:
            target_rate = (
                self.load_profile.peak_images_per_second
                * self.load_profile.load_multiplier
            )

        period = 1.0 / target_rate if target_rate > 0 else 0.0

        stop_at = time.perf_counter() + duration_seconds
        total_sent = 0

        if hasattr(datasets, '__len__'):
            ds_iter = itertools.cycle(datasets)
        else:
            ds_iter = iter(datasets)
        executor = ThreadPoolExecutor(max_workers=concurrency)
        futures = []

        lock = threading.Lock()
        next_send_time = time.perf_counter()

        try:
            while time.perf_counter() < stop_at:
                now = time.perf_counter()
                if period > 0 and now < next_send_time:
                    time.sleep(max(next_send_time - now, 0.0))
                next_send_time = time.perf_counter() + period

                ds = next(ds_iter)
                future = executor.submit(self._send_single_dataset, ds, metrics)
                futures.append(future)
                with lock:
                    total_sent += 1

            for f in as_completed(futures):
                _ = f.result()
        finally:
            executor.shutdown(wait=True)

        return total_sent

    def ping(self, timeout_seconds: int = 5) -> bool:
        """Ping Compass using C-ECHO to check reachability."""
        ae = self._build_ae()
        # Verification is already included in _build_ae(), no need to append again
        try:
            # Note: associate() doesn't take timeout parameter in some pynetdicom versions
            # Use acse_timeout network option instead
            assoc = ae.associate(
                self.endpoint.host,
                self.endpoint.port,
                ae_title=self.endpoint.remote_ae_title.encode("ascii", "ignore"),
            )
            if not assoc.is_established:
                return False
            status = assoc.send_c_echo()
            assoc.release()
            return bool(status) and status.Status == 0x0000
        finally:
            ae.shutdown()
