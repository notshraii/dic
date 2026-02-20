# tests/conftest.py

"""
Global pytest fixtures for DICOM testing with automatic configuration and dataset loading.
"""

import os
import platform
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pytest
from dotenv import load_dotenv

# Add project root to Python path to ensure modules can be imported
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import from root-level modules (compass_perf contents moved to root)
from config import TestConfig
from compass_cfind_client import CompassCFindClient, CompassCFindConfig
from data_loader import find_dicom_files, load_dataset
from dicom_sender import DicomSender
from metrics import PerfMetrics
from report import ReportData, TestResult, generate_html_report

# Load .env file from project root
dotenv_path = project_root / ".env"

if dotenv_path.exists():
    load_dotenv(dotenv_path)
else:
    print(f"WARNING: .env file not found at {dotenv_path}")

# ---------------------------------------------------------------------------
# Report collection globals
# ---------------------------------------------------------------------------
_report_test_results: List[TestResult] = []
_report_session_start: float = 0.0
_report_config: Optional[TestConfig] = None


@pytest.fixture(scope="session")
def perf_config() -> TestConfig:
    """Performance configuration from environment variables."""
    global _report_config
    cfg = TestConfig.from_env()
    _report_config = cfg
    return cfg


@pytest.fixture(scope="session")
def dicom_files(perf_config: TestConfig) -> List[Path]:
    """List of DICOM files for testing."""
    return find_dicom_files(
        perf_config.dataset.dicom_root_dir,
        recursive=perf_config.dataset.recursive,
    )


@pytest.fixture(scope="session")
def dicom_datasets(dicom_files: List[Path]):
    """Loaded DICOM datasets."""
    return [load_dataset(p) for p in dicom_files]


@pytest.fixture
def metrics(request) -> PerfMetrics:
    """Metrics collector for tracking performance."""
    m = PerfMetrics()
    request.node._perf_metrics = m
    return m


@pytest.fixture(scope="session")
def dicom_sender(perf_config: TestConfig) -> DicomSender:
    """DICOM sender for C-STORE operations."""
    return DicomSender(
        endpoint=perf_config.endpoint,
        load_profile=perf_config.load_profile,
    )


# Legacy fixtures for backward compatibility
@pytest.fixture(scope="session")
def compass_config(perf_config):
    """Configuration for Compass server connection (legacy compatibility)."""
    return {
        'host': perf_config.endpoint.host,
        'port': perf_config.endpoint.port,
        'ae_title': perf_config.endpoint.remote_ae_title,
        'local_ae_title': perf_config.endpoint.local_ae_title
    }


@pytest.fixture(scope="session")
def cfind_client(perf_config) -> Optional[CompassCFindClient]:
    """Session-scoped C-FIND client for verifying studies arrived in Compass."""
    if not perf_config.integration.cfind_verify:
        return None
    config = CompassCFindConfig.from_env()
    return CompassCFindClient(config)


def verify_study_arrived(
    cfind_client: Optional[CompassCFindClient],
    study_uid: str,
    perf_config: TestConfig,
) -> Optional[dict]:
    """
    Poll C-FIND to confirm a study arrived in Compass.

    Args:
        cfind_client: CompassCFindClient instance (None means verification disabled).
        study_uid: StudyInstanceUID to look for.
        perf_config: TestConfig for timeout / poll-interval settings.

    Returns:
        Dict of study attributes on success.

    Raises:
        AssertionError if the study is not found within the timeout.
    """
    if cfind_client is None:
        print("  [CFIND VERIFY] Skipped (CFIND_VERIFY=false)")
        return None

    timeout = perf_config.integration.cfind_timeout
    interval = perf_config.integration.cfind_poll_interval
    cfg = cfind_client.config
    print(f"  [CFIND VERIFY] C-FIND enabled. Using C-FIND server: {cfg.host}:{cfg.port}")
    print(f"  [CFIND VERIFY] Called AE: {cfg.remote_ae_title}, Calling AE: {cfg.local_ae_title}")
    print(f"  [CFIND VERIFY] Polling for StudyInstanceUID: {study_uid}")
    print(f"  [CFIND VERIFY] Timeout: {timeout}s, poll interval: {interval}s")

    start = time.time()
    attempts = 0

    while True:
        attempts += 1
        print(f"  [CFIND VERIFY] Attempt {attempts}: sending C-FIND query...")
        try:
            result = cfind_client.find_study_by_uid(study_uid)
        except socket.gaierror as e:
            raise AssertionError(
                f"C-FIND host could not be resolved: '{cfg.host}' (getaddrinfo failed). "
                f"Check .env: set CFIND_HOST or COMPASS_HOST to a valid hostname or IP. "
                f"If using a separate C-FIND server, ensure CFIND_HOST is correct."
            ) from e
        if result is not None:
            study_dict = cfind_client.dataset_to_dict(result)
            elapsed = time.time() - start
            print(f"  [CFIND VERIFY] Study found after {elapsed:.1f}s ({attempts} attempt(s))")
            for key, val in study_dict.items():
                print(f"    {key}: {val}")
            return study_dict

        elapsed = time.time() - start
        if elapsed >= timeout:
            print(f"  [CFIND VERIFY] Study not found after {attempts} attempt(s) in {timeout}s (timeout)")
            break
        remaining = timeout - elapsed
        sleep_time = min(interval, remaining)
        print(f"  [CFIND VERIFY] Attempt {attempts}: no match, retrying in {sleep_time:.1f}s...")
        if sleep_time > 0:
            time.sleep(sleep_time)

    raise AssertionError(
        f"C-FIND verification failed: study {study_uid} not found "
        f"after {timeout}s ({attempts} attempts)"
    )


# ============================================================================
# Test Data Selection Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def large_dicom_file(dicom_files: List[Path]):
    """
    Select a large DICOM file (>10MB) for testing.
    Gracefully skips if no large file is available.
    """
    large_threshold_bytes = 10 * 1024 * 1024  # 10MB
    
    for file in dicom_files:
        if file.stat().st_size > large_threshold_bytes:
            file_size_mb = file.stat().st_size / (1024 * 1024)
            print(f"\n[INFO] Selected large file: {file.name} ({file_size_mb:.2f}MB)")
            return file
    
    pytest.skip(f"No large DICOM file (>10MB) found in dataset. "
                f"Available files: {len(dicom_files)}")


@pytest.fixture(scope="session")
def small_dicom_files(dicom_files: List[Path]):
    """
    Select up to 10 small DICOM files (<1MB) for batch testing.
    Gracefully skips if fewer than 3 small files available.
    """
    small_threshold_bytes = 1 * 1024 * 1024  # 1MB
    min_required = 3
    max_returned = 10
    
    small_files = [f for f in dicom_files if f.stat().st_size < small_threshold_bytes]
    
    if len(small_files) < min_required:
        pytest.skip(f"Need at least {min_required} small files (<1MB), "
                    f"only found {len(small_files)}")
    
    selected = small_files[:max_returned]
    total_size_mb = sum(f.stat().st_size for f in selected) / (1024 * 1024)
    print(f"\n[INFO] Selected {len(selected)} small files (total: {total_size_mb:.2f}MB)")
    return selected


@pytest.fixture(scope="session")
def medium_dicom_files(dicom_files: List[Path]):
    """
    Select medium-sized DICOM files (1MB - 10MB) for testing.
    Gracefully skips if no medium files available.
    """
    min_size = 1 * 1024 * 1024  # 1MB
    max_size = 10 * 1024 * 1024  # 10MB
    
    medium_files = [f for f in dicom_files 
                    if min_size <= f.stat().st_size <= max_size]
    
    if not medium_files:
        pytest.skip(f"No medium-sized DICOM files (1-10MB) found. "
                    f"Total files available: {len(dicom_files)}")
    
    print(f"\n[INFO] Found {len(medium_files)} medium-sized files")
    return medium_files


@pytest.fixture(scope="session")
def dicom_by_modality(dicom_files: List[Path]):
    """
    Organize DICOM files by modality (CT, MR, CR, etc.).
    Returns dict: {modality: [files]}
    
    Usage with parametrize:
        @pytest.mark.parametrize("modality", ["CT", "MR", "CR"])
        def test_by_modality(dicom_by_modality, modality):
            if modality not in dicom_by_modality:
                pytest.skip(f"No {modality} files available")
            files = dicom_by_modality[modality]
    """
    by_modality = {}
    skipped_files = 0
    
    for file in dicom_files:
        try:
            ds = load_dataset(file)
            modality = ds.Modality if hasattr(ds, 'Modality') else 'UNKNOWN'
            
            if modality not in by_modality:
                by_modality[modality] = []
            by_modality[modality].append(file)
        except Exception as e:
            skipped_files += 1
            print(f"\n[WARNING] Could not read modality from {file.name}: {e}")
    
    if not by_modality:
        pytest.skip("Could not determine modality for any files")
    
    print(f"\n[INFO] Files organized by modality:")
    for modality, files in sorted(by_modality.items()):
        print(f"  - {modality}: {len(files)} files")
    
    if skipped_files > 0:
        print(f"  - Skipped: {skipped_files} files (read errors)")
    
    return by_modality


@pytest.fixture(scope="session")
def dicom_by_size_category(dicom_files: List[Path]):
    """
    Organize DICOM files into size categories.
    Returns dict: {'small': [files], 'medium': [files], 'large': [files]}
    """
    categories = {
        'small': [],   # <1MB
        'medium': [],  # 1-10MB
        'large': []    # >10MB
    }
    
    for file in dicom_files:
        size_mb = file.stat().st_size / (1024 * 1024)
        
        if size_mb < 1:
            categories['small'].append(file)
        elif size_mb <= 10:
            categories['medium'].append(file)
        else:
            categories['large'].append(file)
    
    print(f"\n[INFO] Files by size category:")
    for category, files in categories.items():
        if files:
            total_mb = sum(f.stat().st_size for f in files) / (1024 * 1024)
            print(f"  - {category}: {len(files)} files ({total_mb:.2f}MB total)")
    
    return categories


@pytest.fixture(scope="session")
def single_dicom_file(dicom_files: List[Path]):
    """
    Select a single representative DICOM file.
    Gracefully skips if no files available.
    
    Useful for simple integration tests that just need any valid file.
    """
    if not dicom_files:
        pytest.skip("No DICOM files available for testing")
    
    file = dicom_files[0]
    size_mb = file.stat().st_size / (1024 * 1024)
    print(f"\n[INFO] Using single file: {file.name} ({size_mb:.2f}MB)")
    return file


@pytest.fixture
def dicom_file_subset(dicom_files: List[Path], request):
    """
    Parametrizable fixture for selecting N files.
    
    Usage:
        @pytest.mark.parametrize("dicom_file_subset", [5, 10, 20], indirect=True)
        def test_batch(dicom_file_subset):
            assert len(dicom_file_subset) == expected_count
    """
    count = request.param if hasattr(request, 'param') else 5
    
    if len(dicom_files) < count:
        pytest.skip(f"Need {count} files, only {len(dicom_files)} available")
    
    subset = dicom_files[:count]
    print(f"\n[INFO] Selected subset of {len(subset)} files")
    return subset


# ============================================================================
# Utility Functions for Tests
# ============================================================================

def get_files_by_modality(dicom_by_modality: dict, modality: str, count: int = None):
    """
    Helper to get files for a specific modality with graceful fallback.
    
    Args:
        dicom_by_modality: Dict from dicom_by_modality fixture
        modality: Modality code (e.g., 'CT', 'MR')
        count: Number of files to return (None = all)
    
    Returns:
        List of files, or skips test if modality not available
    """
    if modality not in dicom_by_modality:
        available = ", ".join(dicom_by_modality.keys())
        pytest.skip(f"Modality '{modality}' not available. "
                    f"Available: {available}")
    
    files = dicom_by_modality[modality]
    
    if count and len(files) < count:
        pytest.skip(f"Need {count} {modality} files, only {len(files)} available")
    
    return files[:count] if count else files


@pytest.fixture
def test_dicom_with_attributes(single_dicom_file):
    """
    Factory fixture to create test DICOM files with specific attributes.
    
    This fixture returns a function that creates DICOM files with custom
    attributes for transformation testing.
    
    Usage:
        test_file_path, dataset = test_dicom_with_attributes(
            modality='OPV',
            series_description='GPA',
            patient_id='TEST123'
        )
    
    Returns:
        Function that takes **kwargs and returns (file_path, dataset) tuple
    """
    import tempfile
    from pydicom.uid import generate_uid
    
    def _create_test_file(**attributes):
        """
        Create a DICOM file with specified attributes.
        
        Args:
            **attributes: DICOM attributes in snake_case or PascalCase
                         (e.g., modality='CT' or Modality='CT')
        
        Returns:
            Tuple of (file_path, dataset)
        """
        ds = load_dataset(single_dicom_file)
        
        # Apply custom attributes
        for attr, value in attributes.items():
            # Support both snake_case and PascalCase
            if '_' in attr:
                # Convert snake_case to PascalCase
                dicom_attr = ''.join(word.capitalize() for word in attr.split('_'))
            else:
                dicom_attr = attr
            
            setattr(ds, dicom_attr, value)
        
        # Generate unique UIDs to ensure each test is independent
        ds.StudyInstanceUID = generate_uid()
        ds.SeriesInstanceUID = generate_uid()
        ds.SOPInstanceUID = generate_uid()
        
        # Save to temp file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.dcm', prefix='test_transform_')
        os.close(temp_fd)
        
        # Ensure encoding consistency before saving
        # Import the helper function to ensure proper encoding
        from data_loader import ensure_encoding_consistency
        ds = ensure_encoding_consistency(ds)
        
        # Get the transfer syntax to determine encoding parameters
        transfer_syntax = str(ds.file_meta.TransferSyntaxUID) if hasattr(ds, 'file_meta') and hasattr(ds.file_meta, 'TransferSyntaxUID') else '1.2.840.10008.1.2.1'
        
        # Save with proper encoding parameters based on transfer syntax
        # Use the recommended implicit_vr and little_endian arguments
        # instead of deprecated is_implicit_VR and is_little_endian attributes
        if transfer_syntax == '1.2.840.10008.1.2':  # Implicit VR Little Endian
            ds.save_as(temp_path, implicit_vr=True, little_endian=True)
        elif transfer_syntax == '1.2.840.10008.1.2.2':  # Explicit VR Big Endian
            ds.save_as(temp_path, implicit_vr=False, little_endian=False)
        else:  # Explicit VR Little Endian (default for most transfer syntaxes)
            ds.save_as(temp_path, implicit_vr=False, little_endian=True)
        
        return temp_path, ds
    
    return _create_test_file


# ============================================================================
# HTML Report Hooks
# ============================================================================

def pytest_sessionstart(session):
    """Record session start time for report duration calculation."""
    global _report_session_start, _report_test_results
    _report_session_start = time.time()
    _report_test_results = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture per-test results for the HTML report."""
    outcome = yield
    report = outcome.get_result()

    # Only process the "call" phase (the actual test), or "setup" if it failed
    if report.when == "call" or (report.when == "setup" and report.failed):
        if report.when == "setup" and report.failed:
            test_outcome = "error"
        elif report.skipped:
            test_outcome = "skipped"
        elif report.passed:
            test_outcome = "passed"
        else:
            test_outcome = "failed"

        # Extract perf metrics if the test used the metrics fixture
        perf_snapshot = None
        perf_samples = None
        thresholds = None
        perf_metrics = getattr(item, "_perf_metrics", None)
        if perf_metrics is not None and perf_metrics.total > 0:
            perf_snapshot = perf_metrics.snapshot()
            perf_samples = [
                {
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "latency_ms": s.latency_ms,
                    "success": s.success,
                    "error": s.error,
                }
                for s in perf_metrics.samples
            ]

            # Extract thresholds from config if available
            if _report_config is not None:
                th = _report_config.thresholds
                lp = _report_config.load_profile
                thresholds = {
                    "max_error_rate": th.max_error_rate,
                    "max_p95_latency_ms": th.max_p95_latency_ms,
                    "target_rate": lp.peak_images_per_second * lp.load_multiplier,
                }

        # Collect markers
        markers = [m.name for m in item.iter_markers()
                    if m.name not in ("parametrize", "usefixtures", "filterwarnings")]

        # Error message
        error_message = None
        if test_outcome in ("failed", "error"):
            error_message = report.longreprtext

        _report_test_results.append(TestResult(
            node_id=item.nodeid,
            outcome=test_outcome,
            duration=report.duration,
            perf_snapshot=perf_snapshot,
            perf_samples=perf_samples,
            thresholds=thresholds,
            markers=markers,
            error_message=error_message,
        ))


def pytest_sessionfinish(session, exitstatus):
    """Generate HTML report at session end."""
    duration = time.time() - _report_session_start

    config_summary = None
    if _report_config is not None:
        cfg = _report_config
        config_summary = {
            "endpoint": {
                "host": cfg.endpoint.host,
                "port": cfg.endpoint.port,
                "remote_ae_title": cfg.endpoint.remote_ae_title,
                "local_ae_title": cfg.endpoint.local_ae_title,
            },
            "load_profile": {
                "peak_images_per_second": cfg.load_profile.peak_images_per_second,
                "load_multiplier": cfg.load_profile.load_multiplier,
                "test_duration_seconds": cfg.load_profile.test_duration_seconds,
                "concurrency": cfg.load_profile.concurrency,
            },
            "thresholds": {
                "max_error_rate": f"{cfg.thresholds.max_error_rate:.1%}",
                "max_p95_latency_ms": f"{cfg.thresholds.max_p95_latency_ms:.0f} ms",
                "max_p95_latency_ms_short": f"{cfg.thresholds.max_p95_latency_ms_short:.0f} ms",
            },
            "dataset": {
                "dicom_root_dir": str(cfg.dataset.dicom_root_dir),
                "recursive": cfg.dataset.recursive,
            },
        }

    report_data = ReportData(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        duration=duration,
        platform_info=f"Python {sys.version.split()[0]} on {platform.system()} {platform.release()}",
        test_results=_report_test_results,
        config_summary=config_summary,
    )

    html_content = generate_html_report(report_data)
    report_path = project_root / "test_report.html"
    report_path.write_text(html_content, encoding="utf-8")
    file_url = report_path.as_uri()
    tw = session.config.get_terminal_writer()
    tw.line()
    tw.sep("=", "Test Execution Report")
    tw.line(f" {file_url}")
    tw.sep("=")
