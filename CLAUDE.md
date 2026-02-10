# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running Tests
```bash
# Run all load tests
python3 -m pytest -m load -vv

# Run all tests (default path is tests/)
python3 -m pytest -vv

# Run specific test files
python3 -m pytest tests/test_load_stability.py -vv
python3 -m pytest tests/test_routing_throughput.py -vv

# Run a single test function
python3 -m pytest tests/test_load_stability.py::test_function_name -vv -s

# Run by marker
python3 -m pytest -m integration -vv
python3 -m pytest -m "not load" -vv
```

### Development Environment
```bash
pip install -r requirements.txt

# Generate sample DICOM files for testing
python3 create_diverse_dicom_samples.py
```

### DICOM Tag Updater (GUI + CLI)
```bash
# Launch GUI (no arguments)
python3 update_dicom_tags.py

# CLI mode
python3 update_dicom_tags.py <folder_path> [--verbose] [--dry-run]
```

### Building Executable
```bash
pip install pyinstaller
pyinstaller build_exe.spec            # Uses spec file (recommended)
# Output: dist/DICOMTagUpdater
```

## Configuration

All settings via `.env` file or environment variables (see `env_template.txt`). Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `COMPASS_HOST` | `127.0.0.1` | Compass server hostname |
| `COMPASS_PORT` | `11112` | DICOM port |
| `COMPASS_AE_TITLE` | `COMPASS` | Remote AE Title |
| `LOCAL_AE_TITLE` | `PERF_SENDER` | Local AE Title |
| `DICOM_ROOT_DIR` | `./dicom_samples` | Test data directory |
| `PEAK_IMAGES_PER_SECOND` | `50` | Baseline performance rate |
| `LOAD_MULTIPLIER` | `3.0` | Load scaling factor |
| `LOAD_CONCURRENCY` | `8` | Thread pool size |
| `TEST_DURATION_SECONDS` | `300` | Default test duration |
| `MAX_ERROR_RATE` | `0.02` | Acceptable error rate (2%) |
| `MAX_P95_LATENCY_MS` | `2000` | P95 latency threshold (stability) |
| `MAX_P95_LATENCY_MS_SHORT` | `1500` | P95 latency threshold (throughput) |

Override at runtime: `TEST_DURATION_SECONDS=10 python3 -m pytest tests/test_load_stability.py -vv`

## Project Architecture

**DICOM performance/load testing suite + tag updater GUI** for Laurel Bridge Compass, built on pytest and pynetdicom.

### Core Modules (project root, flat structure)

- **`config.py`** — Centralized configuration via dataclasses + env vars. `TestConfig.from_env()` is the single entry point that composes `DicomEndpointConfig`, `LoadProfileConfig`, `DatasetConfig`, `PerformanceThresholdsConfig`, and `IntegrationTestConfig`.
- **`data_loader.py`** — DICOM file discovery (validates `DICM` magic string) and loading with automatic decompression (JPEG/JPEG2000/RLE via pylibjpeg).
- **`dicom_sender.py`** — `DicomSender` class: pynetdicom C-STORE client with `ThreadPoolExecutor`-based concurrent sending. Key methods: `ping()` (C-ECHO), `_send_single_dataset()`, `load_test_for_duration()`.
- **`metrics.py`** — Thread-safe `PerfMetrics` class collecting `Sample` objects (latency, success/failure, error). Properties: `total`, `error_rate`, `p95_latency_ms`.
- **`dcmutl.py`** — Low-level DICOM utilities: `get_dcm_files()` (recursive file discovery by extension), `update_tags_ds()` (tag manipulation by keyword or hex).

### Compass Query Clients

Three approaches to verify data arrived at Compass:
- **`compass_cfind_client.py`** — C-FIND queries via DICOM protocol (preferred, no special credentials needed)
- **`compass_db_query.py`** — Direct SQL Server queries to Compass ODM database (requires pyodbc + credentials)
- **`compass_api_client.py`** — REST API client for Compass web interface

### GUI Tool

- **`update_dicom_tags.py`** — Tkinter GUI + CLI for updating DICOM tags. Generates unique StudyInstanceUID/AccessionNumber/SeriesInstanceUID per run. Supports default tags (PatientID, PatientName, etc.) and dynamically added custom tags. Depends on `dcmutl.py`.

### Test Structure

Tests live in `tests/` and use pytest markers (`@pytest.mark.load`, `@pytest.mark.integration`) defined in `pytest.ini`.

**Key fixtures** (from `tests/conftest.py`, session-scoped):
- `perf_config` → `TestConfig` from env
- `dicom_files` → discovered DICOM file paths
- `dicom_datasets` → loaded pydicom Dataset objects
- `dicom_sender` → `DicomSender` instance
- `metrics` → fresh `PerfMetrics` per test (function-scoped)
- `test_dicom_with_attributes` → factory fixture to create DICOM files with custom attributes
- `single_dicom_file`, `large_dicom_file`, `small_dicom_files`, `dicom_by_modality`, `dicom_by_size_category` — data selection fixtures

### Test Data Flow

1. `find_dicom_files()` discovers files by DICM magic string validation
2. `load_dataset()` loads + auto-decompresses
3. `DicomSender.load_test_for_duration()` sends via ThreadPoolExecutor
4. `PerfMetrics` collects thread-safe timing samples
5. Tests assert against configurable thresholds (error rate, p95 latency)

### Key Dependencies

- **pynetdicom** — DICOM networking (C-STORE, C-ECHO, C-FIND)
- **pydicom** — DICOM file parsing and manipulation
- **pylibjpeg + pillow** — Automatic DICOM decompression
- **pyodbc** — SQL Server database access (optional, for Compass DB queries)
- **requests** — REST API client (optional, for Compass API)
