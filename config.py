# config.py

"""
Configuration management for all Compass DICOM tests using environment variables and dataclasses.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Tuple


# ============================================================================
# Helper Functions
# ============================================================================

def _env_str(name: str, default: Optional[str] = None) -> Optional[str]:
    """Safely read string environment variable."""
    value = os.getenv(name)
    return value if value is not None else default


def _env_int(name: str, default: int) -> int:
    """Safely read integer environment variable with fallback."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    """Safely read float environment variable with fallback."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


# ============================================================================
# Configuration Classes
# ============================================================================


def _routes_from_env() -> Dict[str, Tuple[str, str]]:
    """Build dict of named routes from env: HTM_GI, HTM_OPH, HTM_ORTHO."""
    routes: Dict[str, Tuple[str, str]] = {}
    for name, remote_key, local_key in (
        ("HTM_GI", "REMOTE_AE_HTM_GI", "LOCAL_AE_HTM_GI"),
        ("HTM_OPH", "REMOTE_AE_HTM_OPH", "LOCAL_AE_HTM_OPH"),
        ("HTM_ORTHO", "REMOTE_AE_HTM_ORTHO", "LOCAL_AE_HTM_ORTHO"),
    ):
        remote = _env_str(remote_key)
        local = _env_str(local_key)
        if remote and local:
            routes[name] = (remote, local)
    return routes


@dataclass
class DicomEndpointConfig:
    """
    DICOM connection configuration - WHERE to send data.
    
    Supports three named routes (HTM_GI, HTM_OPH, HTM_ORTHO). Set COMPASS_ROUTE
    to choose the active one; each route has REMOTE_AE_* and LOCAL_AE_*.
    If COMPASS_ROUTE is unset, falls back to COMPASS_AE_TITLE + LOCAL_AE_TITLE.
    
    Used by: All tests
    """
    host: str
    port: int
    remote_ae_title: str  # Compass's AE Title (called AET)
    local_ae_title: str   # Default calling AE Title (can be overridden per test)
    routes: Dict[str, Tuple[str, str]] = field(default_factory=dict)  # name -> (remote_ae, local_ae)

    @classmethod
    def from_env(cls) -> "DicomEndpointConfig":
        host = _env_str("COMPASS_HOST", "127.0.0.1")
        port = _env_int("COMPASS_PORT", 11112)
        routes = _routes_from_env()
        active_route = _env_str("COMPASS_ROUTE")
        if active_route and active_route in routes:
            remote_ae_title, local_ae_title = routes[active_route]
        else:
            remote_ae_title = _env_str("COMPASS_AE_TITLE", "COMPASS")
            local_ae_title = _env_str("LOCAL_AE_TITLE", "PERF_SENDER") or "PERF_SENDER"
        return cls(
            host=host,
            port=port,
            remote_ae_title=remote_ae_title,
            local_ae_title=local_ae_title,
            routes=routes,
        )


@dataclass
class LoadProfileConfig:
    """
    Load testing configuration - HOW HARD to stress test.
    
    Used by: Load tests (test_load_stability, test_routing_throughput)
    """
    peak_images_per_second: int
    load_multiplier: float
    test_duration_seconds: int
    concurrency: int

    @classmethod
    def from_env(cls) -> "LoadProfileConfig":
        return cls(
            peak_images_per_second=_env_int("PEAK_IMAGES_PER_SECOND", 50),
            load_multiplier=_env_float("LOAD_MULTIPLIER", 3.0),
            test_duration_seconds=_env_int("TEST_DURATION_SECONDS", 300),
            concurrency=_env_int("LOAD_CONCURRENCY", 8),
        )


@dataclass
class DatasetConfig:
    """
    Test data location configuration - WHAT to send.
    
    Used by: All tests
    """
    dicom_root_dir: Path
    recursive: bool = True

    @classmethod
    def from_env(cls) -> "DatasetConfig":
        dicom_root = _env_str("DICOM_ROOT_DIR", "./dicom_samples")
        return cls(
            dicom_root_dir=Path(dicom_root).resolve(),
            recursive=True,
        )


@dataclass
class PerformanceThresholdsConfig:
    """
    Performance acceptance criteria - WHAT defines success.
    
    Used by: Load tests for pass/fail criteria
    """
    max_error_rate: float  # Maximum acceptable error rate (e.g., 0.02 = 2%)
    max_p95_latency_ms: float  # Maximum p95 latency for stability tests
    max_p95_latency_ms_short: float  # Maximum p95 latency for throughput tests

    @classmethod
    def from_env(cls) -> "PerformanceThresholdsConfig":
        return cls(
            max_error_rate=_env_float("MAX_ERROR_RATE", 0.02),
            max_p95_latency_ms=_env_float("MAX_P95_LATENCY_MS", 2000.0),
            max_p95_latency_ms_short=_env_float("MAX_P95_LATENCY_MS_SHORT", 1500.0),
        )


@dataclass
class IntegrationTestConfig:
    """
    Configuration specific to integration/functional tests.

    Used by: Integration tests (test_anonymize_and_send, etc.)
    """
    test_dicom_file: Optional[str] = None  # Specific file for anonymize test
    cfind_verify: bool = True              # Enable C-FIND verification after sends
    cfind_initial_delay: float = 5.0      # Seconds to wait before first C-FIND attempt
    cfind_timeout: int = 60               # Poll timeout in seconds
    cfind_poll_interval: float = 5.0      # Poll interval in seconds

    @classmethod
    def from_env(cls) -> "IntegrationTestConfig":
        cfind_verify_str = _env_str("CFIND_VERIFY", "true")
        return cls(
            test_dicom_file=_env_str("TEST_DICOM_FILE", None),
            cfind_verify=cfind_verify_str.lower() not in ("false", "0", "no"),
            cfind_initial_delay=_env_float("CFIND_INITIAL_DELAY", 5.0),
            cfind_timeout=_env_int("CFIND_TIMEOUT", 60),
            cfind_poll_interval=_env_float("CFIND_POLL_INTERVAL", 5.0),
        )


# ============================================================================
# Master Configuration
# ============================================================================

@dataclass
class TestConfig:
    """
    Master configuration object for ALL tests.
    
    This is the single source of truth for configuration.
    Use TestConfig.from_env() to load all settings at once.
    
    Structure:
    - endpoint: Connection to Compass (WHERE)
    - load_profile: Stress testing parameters (HOW HARD)
    - dataset: Test data location (WHAT)
    - thresholds: Performance acceptance criteria (SUCCESS CRITERIA)
    - integration: Integration test specific settings
    """
    endpoint: DicomEndpointConfig
    load_profile: LoadProfileConfig
    dataset: DatasetConfig
    thresholds: PerformanceThresholdsConfig
    integration: IntegrationTestConfig

    @classmethod
    def from_env(cls) -> "TestConfig":
        """Load complete configuration from environment variables."""
        return cls(
            endpoint=DicomEndpointConfig.from_env(),
            load_profile=LoadProfileConfig.from_env(),
            dataset=DatasetConfig.from_env(),
            thresholds=PerformanceThresholdsConfig.from_env(),
            integration=IntegrationTestConfig.from_env(),
        )
