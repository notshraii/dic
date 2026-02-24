# DICOM Automation Suite

DICOM performance and load testing framework for Laurel Bridge Compass built on pytest, pynetdicom, and pydicom.

---


## Overview

A pytest-based test suite sends DICOM images to a Laurel Bridge Compass router via C-STORE, measures performance (throughput, latency, error rate), and verifies delivery via C-FIND. Tests cover load/stress scenarios, routing transformations, failure modes, data validation, and AE title routing.


---

## Project Structure

```
dicomAuto/
|-- config.py                    # Centralized configuration (env vars + dataclasses)
|-- data_loader.py               # DICOM file discovery and loading with auto-decompression
|-- dicom_sender.py              # C-STORE client with concurrent sending
|-- metrics.py                   # Thread-safe performance metrics collection
|-- dcmutl.py                    # Low-level DICOM tag manipulation utilities
|-- compass_cfind_client.py      # C-FIND query client for verifying delivery
|-- report.py                    # HTML test report generator
|-- update_dicom_tags.py         # DICOM tag updater
|
|-- tests/
|   |-- conftest.py              # Shared fixtures, report hooks, data selection helpers
|   |-- test_load_stability.py   # Load/stress tests
|   |-- test_routing_throughput.py# Throughput tests at target images/sec
|   |-- test_routing_transformations.py  # Tag transformation verification
|   |-- test_data_validation.py  # Compass data handling edge cases
|   |-- test_failure_modes.py    # Delays, duplicates, interruptions
|   |-- test_calling_aet_routing.py     # AE title routing tests
|   |-- test_anonymize_and_send.py      # PHI removal and send
|   |-- test_update_dicom_tags.py       # Tag updater tool tests
|   |-- test_data_selection_examples.py # Fixture usage examples
|
|-- env_template.txt             # Template for .env
|-- requirements.txt             # Python dependencies
|-- pytest.ini                   # Pytest configuration and markers
```

---

## Setup

### Prerequisites

- Python 3.9+
- Network access to a Laurel Bridge Compass server (for integration/load tests). IP address as well as DNS name both work

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd dicomAuto

# Install dependencies
pip install -r requirements.txt

# Copy the environment template and configure
cp env_template.txt .env
# Edit .env with your Compass server details
```

### Test Data

Place DICOM files in the `dicom_samples/` directory (or set `DICOM_ROOT_DIR` in `.env`). Files are discovered recursively by validating the DICM magic string, so any valid DICOM file will be found regardless of extension.


## Configuration

All settings are managed through environment variables, typically set in a `.env` file. See `env_template.txt` for the full template.

### DICOM Connection (C-STORE)

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPASS_HOST` | `127.0.0.1` | Compass server hostname |
| `COMPASS_PORT` | `11112` | DICOM port |
| `COMPASS_ROUTE` | _(none)_ | Active route: `HTM_GI`, `HTM_OPH`, or `HTM_ORTHO` |

### Route-Specific AE Titles

Each route has its own Called AE (the one we are calling) and Calling AE (the one that makes the call):

| Route | Remote AE Variable | Local AE Variable |
|-------|--------------------|--------------------|
| HTM_GI | `REMOTE_AE_HTM_GI` | `LOCAL_AE_HTM_GI` |
| HTM_OPH | `REMOTE_AE_HTM_OPH` | `LOCAL_AE_HTM_OPH` |
| HTM_ORTHO | `REMOTE_AE_HTM_ORTHO` | `LOCAL_AE_HTM_ORTHO` |

When `COMPASS_ROUTE` is unset, `COMPASS_AE_TITLE` and `LOCAL_AE_TITLE` are used as fallbacks.

### C-FIND Verification

| Variable | Default | Description |
|----------|---------|-------------|
| `CFIND_HOST` | _(uses COMPASS_HOST)_ | C-FIND server |
| `CFIND_PORT` | _(uses COMPASS_PORT)_ | C-FIND port |
| `CFIND_AE_TITLE` | _(uses COMPASS_AE_TITLE)_ | Called AE for queries |
| `CFIND_VERIFY` | `true` | Enable/disable C-FIND verification after sends |
| `CFIND_INITIAL_DELAY` | `5.0` | Seconds to wait before first C-FIND attempt |
| `CFIND_TIMEOUT` | `60` | Total polling timeout in seconds |
| `CFIND_POLL_INTERVAL` | `5.0` | Seconds between C-FIND retries |

### Load Testing

| Variable | Default | Description |
|----------|---------|-------------|
| `PEAK_IMAGES_PER_SECOND` | `50` | Baseline performance rate |
| `LOAD_MULTIPLIER` | `3.0` | Multiplier applied to peak rate for stress tests |
| `LOAD_CONCURRENCY` | `8` | Thread pool size for concurrent sends |
| `TEST_DURATION_SECONDS` | `300` | Default load test duration |

### Performance Thresholds

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_ERROR_RATE` | `0.02` | Maximum acceptable error rate (2%) |
| `MAX_P95_LATENCY_MS` | `2000` | P95 latency threshold for stability tests |
| `MAX_P95_LATENCY_MS_SHORT` | `1500` | P95 latency threshold for throughput tests |

### Dataset

| Variable | Default | Description |
|----------|---------|-------------|
| `DICOM_ROOT_DIR` | `./dicom_samples` | Root directory for test DICOM files |

### Runtime Overrides

Any variable can be overridden at runtime like this:

```bash
TEST_DURATION_SECONDS=10 LOAD_CONCURRENCY=4 python3 -m pytest tests/test_load_stability.py -vv
```

---

## Running Tests

```bash
# Run all tests
python3 -m pytest -vv

# Run load/performance tests only
python3 -m pytest -m load -vv

# Run integration tests only
python3 -m pytest -m integration -vv

# Exclude load tests (faster iteration)
python3 -m pytest -m "not load" -vv

# Run a specific test file
python3 -m pytest tests/test_routing_transformations.py -vv

# Run a single test function with full output
python3 -m pytest tests/test_load_stability.py::test_load_stability_3x_peak -vv -s
```

An HTML report (`test_report.html`) is automatically generated after each test session.

---

## Test Suite

### Load and Performance Tests

**`test_load_stability.py`** -- Drives sustained load at the configured multiplier (default 3x peak) for a configurable duration. Asserts error rate and P95 latency stay within thresholds. After the load run, samples unique StudyInstanceUIDs and verifies they arrived via C-FIND.

**`test_routing_throughput.py`** -- Measures throughput at target images/sec and validates that the system sustains the expected rate without excessive latency.

### Functional and Integration Tests

**`test_routing_transformations.py`** -- Verifies that Compass applies DICOM tag transformations correctly. Parametrized test cases send images with specific modality/series attributes and check that the routed study has the expected StudyDescription (e.g., OPV + GPA -> "Visual Fields (VF) GPA").

**`test_calling_aet_routing.py`** -- Tests routing behavior across different Called AE titles (`LB-HTM-GI`, `LB-HTM-OPH`, `LB-HTM-ORTHO`). Validates that each route correctly accepts and processes images.

**`test_data_validation.py`** -- Edge cases for Compass data handling: blank study dates, accession number formats, study date validation rules.

**`test_failure_modes.py`** -- Validates Compass behavior under adverse conditions:
- Long pauses (2 minutes) between sends
- Duplicate image submission
- Send interruptions and recovery

**`test_anonymize_and_send.py`** -- Strips PHI from DICOM files and sends anonymized data via C-STORE, then verifies arrival.

**`test_update_dicom_tags.py`** -- Unit and integration tests for the DICOM Tag Updater tool.

### Test Fixtures

Tests use shared fixtures defined in `tests/conftest.py`:

| Fixture | Scope | Description |
|---------|-------|-------------|
| `perf_config` | session | `TestConfig` loaded from environment |
| `dicom_files` | session | Discovered DICOM file paths |
| `dicom_datasets` | session | Loaded pydicom Dataset objects |
| `dicom_sender` | session | `DicomSender` instance |
| `cfind_client` | session | `CompassCFindClient` for C-FIND verification |
| `metrics` | function | Fresh `PerfMetrics` per test |
| `single_dicom_file` | session | Any single DICOM file |
| `large_dicom_file` | session | A file >10MB (skips if unavailable) |
| `small_dicom_files` | session | Up to 10 files <1MB |
| `medium_dicom_files` | session | Files between 1-10MB |
| `dicom_by_modality` | session | Files organized by modality (CT, MR, etc.) |
| `dicom_by_size_category` | session | Files grouped as small/medium/large |
| `test_dicom_with_attributes` | function | Factory for creating DICOM files with custom attributes |

---

## DICOM Tag Updater

A standalone CLI tool for batch-updating DICOM tags in a folder.


```bash
python3 update_dicom_tags.py /path/to/dicom/folder --verbose --dry-run
```

| Flag | Description |
|------|-------------|
| `--verbose` | Print detailed output for each file processed |
| `--dry-run` | Show what would be changed without modifying files |

---

## C-FIND Query Client

The `compass_cfind_client.py` module provides a DICOM C-FIND client for querying studies on the Compass server (or a separate Image Manager/Query server).

### Standalone Usage

```bash
# Test connection
python3 compass_cfind_client.py

# Find a study by UID
python3 compass_cfind_client.py study <study_instance_uid>

# Find studies by patient ID
python3 compass_cfind_client.py patient <patient_id>

# Find today's studies
python3 compass_cfind_client.py today
```

### Programmatic Usage

```python
from compass_cfind_client import CompassCFindClient, CompassCFindConfig

config = CompassCFindConfig.from_env()
client = CompassCFindClient(config)

# Test connectivity
client.test_connection()

# Query by study UID
result = client.find_study_by_uid("1.2.3.4.5.6.7.8.9")

# Query by patient
studies = client.find_studies_by_patient_id("PATIENT001")

# Query by date range
studies = client.find_studies_by_date_range("20240101", "20240131")

# Query by modality
studies = client.find_studies_by_modality("CT")
```

---

## HTML Test Reports

Every pytest session automatically generates `test_report.html` in the project root. The report includes:

- Summary dashboard with pass/fail/skip counts
- Donut chart of test outcomes and duration bar chart
- Configuration summary (endpoint, load profile, thresholds)
- Filterable results table with per-test performance metrics
- Performance detail panels for load tests: latency histogram, throughput timeline, latency-over-time scatter plot
- Collapsible failure details with full tracebacks

---

## Architecture

### Data Flow

```
DICOM Files (dicom_samples/)
        |
        v
  data_loader.py          -- discover files (DICM magic), load + decompress
        |
        v
  dicom_sender.py         -- C-STORE via pynetdicom, ThreadPoolExecutor concurrency
        |
        v
  Laurel Bridge Compass   -- routes images based on AE title and transformation rules
        |
        v
  compass_cfind_client.py -- C-FIND verification: poll until study appears
        |
        v
  metrics.py              -- thread-safe latency/error collection
        |
        v
  report.py               -- generate HTML report with charts
```

### Core Modules

- **`config.py`** -- Single entry point `TestConfig.from_env()` composes all configuration from environment variables into typed dataclasses: `DicomEndpointConfig`, `LoadProfileConfig`, `DatasetConfig`, `PerformanceThresholdsConfig`, `IntegrationTestConfig`.

- **`data_loader.py`** -- `find_dicom_files()` recursively discovers files by DICM magic string validation. `load_dataset()` loads files and automatically decompresses JPEG, JPEG2000, and RLE transfer syntaxes via pylibjpeg.

- **`dicom_sender.py`** -- `DicomSender` wraps pynetdicom for C-STORE operations. `ping()` sends C-ECHO to verify connectivity. `load_test_for_duration()` drives sustained load using a thread pool with configurable concurrency and optional rate limiting.

- **`metrics.py`** -- `PerfMetrics` collects `Sample` objects (start/end time, latency, success/failure, error message) in a thread-safe manner. Exposes `error_rate`, `p95_latency_ms`, and `snapshot()` for reporting.

- **`dcmutl.py`** -- Low-level DICOM utilities: `get_dcm_files()` for recursive file discovery by extension, `update_tags_ds()` for tag manipulation by keyword or hex notation.

- **`compass_cfind_client.py`** -- `CompassCFindClient` supports Study Root and Patient Root query models, with automatic fallback strategies. Used by tests to verify that sent studies arrived at the destination.

- **`report.py`** -- Generates self-contained HTML reports with Chart.js visualizations, integrated via pytest session hooks in `conftest.py`.

### Key Dependencies

| Package | Purpose |
|---------|---------|
| pynetdicom | DICOM networking (C-STORE, C-ECHO, C-FIND) |
| pydicom | DICOM file parsing and tag manipulation |
| pylibjpeg, pylibjpeg-libjpeg, pylibjpeg-openjpeg | Automatic DICOM decompression |
| pillow | Image processing support |
| pytest | Test framework with markers and fixtures |
| python-dotenv | Environment variable loading from `.env` |
