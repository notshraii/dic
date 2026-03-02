# DICOM Automation Framework - How to Run

## Prerequisites

- Python 3.8+
- Network access to the Compass server
- DICOM test files (`.dcm`)
- For C-FIND verification: your device must be whitelisted and added to the appropriate pools that match the values in the `.env` file

## Setup

```bash
git clone https://github.com/notshraii/dic.git
cd dic
pip install -r requirements.txt
```

Copy `env_template.txt` to `.env` and configure your environment:

```bash
cp env_template.txt .env
```

At minimum, set these values in `.env`:

| Variable | Description |
|---|---|
| `COMPASS_HOST` | Compass server hostname |
| `COMPASS_PORT` | DICOM port (default `11112`) |
| `COMPASS_ROUTE` | Active route: `HTM_GI`, `HTM_OPH`, or `HTM_ORTHO` |
| `REMOTE_AE_HTM_*` / `LOCAL_AE_HTM_*` | Called/Calling AE titles for the chosen route |
| `DICOM_ROOT_DIR` | Path to folder containing `.dcm` test files |

If you don't have test DICOM files, generate samples:

```bash
python3 create_diverse_dicom_samples.py
```

## Running Tests

**All tests:**
```bash
python3 -m pytest -vv
```

**By category (marker):**
```bash
python3 -m pytest -m integration -vv    # Integration tests (requires live Compass)
python3 -m pytest -m load -vv           # Load/performance tests
python3 -m pytest -m "not load" -vv     # Everything except load tests
```

**Specific test file:**
```bash
python3 -m pytest tests/test_load_stability.py -vv
python3 -m pytest tests/test_failure_modes.py -vv
python3 -m pytest tests/test_calling_aet_routing.py -vv
```

**Single test function:**
```bash
python3 -m pytest tests/test_failure_modes.py::test_slow_send_one_at_a_time -vv -s
```

**Override settings at runtime:**
```bash
TEST_DURATION_SECONDS=10 LOAD_CONCURRENCY=4 python3 -m pytest tests/test_load_stability.py -vv
```

## DICOM Tag Updater Tool

A standalone GUI/CLI for modifying DICOM tags before sending:

```bash
python3 update_dicom_tags.py              # Launch GUI
python3 update_dicom_tags.py /path/to/dcm --dry-run   # CLI preview
python3 update_dicom_tags.py /path/to/dcm --verbose    # CLI execute
```

## Test Markers Reference

| Marker | Meaning |
|---|---|
| `integration` | Requires a live Compass server |
| `load` | Performance/stress tests (long-running) |
| `manual_verify` | May require manual verification on failure |

## Available Test Suites

| File | Purpose |
|---|---|
| `test_load_stability.py` | Sustained load over time, error rate and P95 latency thresholds |
| `test_routing_throughput.py` | Throughput measurement under concurrent sends |
| `test_failure_modes.py` | Delays, duplicates, network resilience |
| `test_calling_aet_routing.py` | AE title routing verification |
| `test_data_validation.py` | DICOM tag and data integrity checks |
| `test_routing_transformations.py` | Tag transformation during routing |
| `test_anonymize_and_send.py` | Anonymization workflow |
| `test_data_selection_examples.py` | Data selection fixture examples |
| `test_update_dicom_tags.py` | Tag updater unit tests |
