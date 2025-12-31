# DICOM Testing Framework - Engineering Guide

This guide helps new engineers understand, use, and extend the Compass DICOM testing framework.

## Table of Contents

1. [Framework Overview](#framework-overview)
2. [Architecture](#architecture)
3. [Setup and Getting Started](#setup-and-getting-started)
4. [How to Add a New Test](#how-to-add-a-new-test)
5. [Test Types and Patterns](#test-types-and-patterns)
6. [Configuration Management](#configuration-management)
7. [Data Management](#data-management)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

## Framework Overview

This is a pytest-based DICOM performance and validation testing framework for Laurel Bridge Compass. It provides:

- **Load testing** at various traffic levels
- **Routing validation** for different AE titles
- **Tag transformation verification**
- **Failure mode simulation**
- **Data validation testing**
- **Anonymization workflow testing**

### Key Features

- Environment-driven configuration
- Automatic DICOM decompression
- Thread-safe metrics collection
- Intelligent test data selection
- Comprehensive fixture ecosystem

## Architecture

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   config.py     │    │  data_loader.py │    │ dicom_sender.py │
│ Configuration   │    │ File Discovery  │    │ Network Client  │
│ Management      │    │ & Loading       │    │ & Transmission  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   metrics.py    │
                    │ Performance     │
                    │ Tracking        │
                    └─────────────────┘
```

#### 1. Configuration System (`config.py`)

Manages all test settings through environment variables and dataclasses:

- **DicomEndpointConfig**: Connection details (host, port, AE titles)
- **LoadProfileConfig**: Performance test parameters
- **DatasetConfig**: Test data locations
- **PerformanceThresholdsConfig**: Pass/fail criteria

#### 2. Data Layer (`data_loader.py`)

Handles DICOM file operations:

- Discovers DICOM files by magic string validation
- Automatically decompresses JPEG/JPEG2000/RLE files
- Ensures encoding consistency for transmission

#### 3. Network Layer (`dicom_sender.py`)

Manages DICOM communications:

- Multi-threaded C-STORE transmission
- C-ECHO connectivity checks
- Rate limiting and load control

#### 4. Metrics Collection (`metrics.py`)

Thread-safe performance tracking:

- Latency measurements (min/avg/p95)
- Success/failure rates
- Error categorization

### Test Structure

```
tests/
├── conftest.py              # Global fixtures and configuration
├── test_load_stability.py   # Stress tests at 3x peak load
├── test_routing_throughput.py # Rate-limited performance tests
├── test_routing_transformations.py # Tag modification validation
├── test_calling_aet_routing.py # AE Title routing tests
├── test_data_validation.py # Data handling and edge cases
├── test_failure_modes.py   # Resilience and error scenarios
└── test_anonymize_and_send.py # Privacy workflow tests
```

## Setup and Getting Started

### 1. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd dicomAuto

# Install dependencies
pip install -r requirements.txt

# Generate test data
python3 create_diverse_dicom_samples.py
```

### 2. Configuration

Create a `.env` file in the project root:

```env
# Compass Connection
COMPASS_HOST=your-compass-server.com
COMPASS_PORT=11112
COMPASS_AE_TITLE=COMPASS
LOCAL_AE_TITLE=TEST_SENDER

# Test Data
DICOM_ROOT_DIR=./dicom_samples

# Load Testing Parameters
PEAK_IMAGES_PER_SECOND=50
LOAD_MULTIPLIER=3.0
LOAD_CONCURRENCY=8
TEST_DURATION_SECONDS=60

# Performance Thresholds
MAX_ERROR_RATE=0.02
MAX_P95_LATENCY_MS_SHORT=1500
MAX_P95_LATENCY_MS=2000
```

### 3. Run Tests

```bash
# Run all load tests
python3 run_tests.py

# Quick test (10 seconds)
python3 run_tests.py --quick

# Specific test types
python3 run_tests.py --stability
python3 run_tests.py --throughput

# Using pytest directly
python3 -m pytest -m load -vv
python3 -m pytest tests/test_load_stability.py -vv
```

## How to Add a New Test

### Step 1: Choose Test Type and Location

Determine what type of test you're adding:

- **Load/Performance**: `test_load_stability.py` or `test_routing_throughput.py`
- **Routing/Transformation**: `test_routing_transformations.py` 
- **AE Title Routing**: `test_calling_aet_routing.py`
- **Data Validation**: `test_data_validation.py`
- **Failure Scenarios**: `test_failure_modes.py`
- **New Category**: Create new file `test_your_category.py`

### Step 2: Basic Test Structure

```python
# tests/test_your_feature.py

"""
Brief description of what this test module validates.
"""

from __future__ import annotations

import pytest
from metrics import PerfMetrics

# Mark for test categorization
@pytest.mark.load  # or @pytest.mark.integration
def test_your_feature_name(
    dicom_sender,      # Network client
    dicom_datasets,    # Loaded DICOM files
    metrics: PerfMetrics,  # Performance tracking
    perf_config,       # Configuration object
):
    """Test description - what this validates."""
    
    # 1. Setup test conditions
    duration = 30  # seconds
    
    # 2. Execute test
    total_sent = dicom_sender.load_test_for_duration(
        datasets=dicom_datasets,
        metrics=metrics,
        duration_seconds=duration,
    )
    
    # 3. Validate results
    assert total_sent > 0, "Should send at least one file"
    
    # Check performance metrics
    error_rate = metrics.error_rate
    assert error_rate <= perf_config.thresholds.max_error_rate, \
        f"Error rate {error_rate:.1%} exceeds threshold"
    
    p95_latency = metrics.p95_latency_ms
    assert p95_latency <= perf_config.thresholds.max_p95_latency_ms_short, \
        f"P95 latency {p95_latency:.1f}ms exceeds threshold"
```

### Step 3: Advanced Test Patterns

#### Using Specific Test Data

```python
def test_with_specific_modality(dicom_by_modality, dicom_sender, metrics):
    """Test with specific DICOM modality."""
    
    # Get CT files specifically
    from tests.conftest import get_files_by_modality
    ct_files = get_files_by_modality(dicom_by_modality, "CT", count=5)
    
    # Load datasets
    from data_loader import load_dataset
    datasets = [load_dataset(f) for f in ct_files]
    
    # Run test with CT data only
    result = dicom_sender.load_test_for_duration(
        datasets=datasets,
        metrics=metrics,
        duration_seconds=30,
    )
    
    assert result > 0
```

#### Parametrized Tests

```python
@pytest.mark.parametrize("calling_aet", ["DEVICE_A", "DEVICE_B", "DEVICE_C"])
def test_multiple_calling_aets(calling_aet, single_dicom_file, perf_config, metrics):
    """Test routing with different calling AE titles."""
    
    # Create custom sender with specific AE title
    custom_config = perf_config.endpoint
    custom_config.local_ae_title = calling_aet
    
    sender = DicomSender(custom_config, perf_config.load_profile)
    
    # Load and send single file
    from data_loader import load_dataset
    dataset = load_dataset(single_dicom_file)
    
    sender._send_single_dataset(dataset, metrics)
    
    # Verify success
    assert metrics.total_sent > 0
    assert metrics.error_rate == 0
```

#### Custom Test Data Creation

```python
def test_with_custom_attributes(test_dicom_with_attributes, dicom_sender, metrics):
    """Test with DICOM files having specific attributes."""
    
    # Create test file with custom attributes
    test_file, dataset = test_dicom_with_attributes(
        modality='OPV',
        series_description='GPA',
        patient_id='TEST123'
    )
    
    # Send the custom file
    dicom_sender._send_single_dataset(dataset, metrics)
    
    # Cleanup
    import os
    os.unlink(test_file)
    
    assert metrics.total_sent == 1
```

### Step 4: Add Test Markers

Use pytest markers to categorize your tests:

```python
@pytest.mark.load          # Load/performance tests
@pytest.mark.integration   # Integration tests
@pytest.mark.slow         # Long-running tests
@pytest.mark.parametrize   # Parametrized tests
```

### Step 5: Configuration for New Tests

If your test needs new configuration parameters:

1. Add to appropriate config class in `config.py`:

```python
@dataclass
class YourTestConfig:
    your_setting: str
    your_threshold: float
    
    @classmethod
    def from_env(cls) -> "YourTestConfig":
        return cls(
            your_setting=_env_str("YOUR_SETTING", "default_value"),
            your_threshold=_env_float("YOUR_THRESHOLD", 1.0),
        )
```

2. Add to master `TestConfig`:

```python
@dataclass
class TestConfig:
    # ... existing configs ...
    your_config: YourTestConfig
    
    @classmethod
    def from_env(cls) -> "TestConfig":
        return cls(
            # ... existing configs ...
            your_config=YourTestConfig.from_env(),
        )
```

3. Update your `.env` file:

```env
YOUR_SETTING=custom_value
YOUR_THRESHOLD=2.5
```

## Test Types and Patterns

### 1. Load Tests

Test system performance under various loads:

```python
@pytest.mark.load
def test_sustained_load(dicom_sender, dicom_datasets, metrics, perf_config):
    """Verify system handles sustained load without degradation."""
    
    duration = perf_config.load_profile.test_duration_seconds
    
    total_sent = dicom_sender.load_test_for_duration(
        datasets=dicom_datasets,
        metrics=metrics,
        duration_seconds=duration,
        rate_limit_images_per_second=100,  # Custom rate
    )
    
    # Validate performance stays within bounds
    assert metrics.error_rate <= 0.01  # Max 1% errors
    assert metrics.p95_latency_ms <= 2000  # Max 2s latency
```

### 2. Routing Tests

Validate DICOM routing behavior:

```python
def test_routing_by_modality(test_dicom_with_attributes, dicom_sender, metrics):
    """Test that different modalities route correctly."""
    
    modalities = ['CT', 'MR', 'CR', 'US']
    
    for modality in modalities:
        # Create file with specific modality
        file_path, dataset = test_dicom_with_attributes(modality=modality)
        
        # Send and track
        dicom_sender._send_single_dataset(dataset, metrics)
        
        # Verify routing (would need C-FIND verification in real test)
        
        # Cleanup
        import os
        os.unlink(file_path)
```

### 3. Transformation Tests

Verify DICOM tag modifications:

```python
def test_tag_transformation(test_dicom_with_attributes, perf_config):
    """Test that Compass transforms tags correctly."""
    
    # Create file with specific attributes to trigger transformation
    file_path, original_dataset = test_dicom_with_attributes(
        modality='OPV',
        series_description='GPA'  # Should trigger transformation
    )
    
    # Send to Compass
    sender = DicomSender(perf_config.endpoint, perf_config.load_profile)
    metrics = PerfMetrics()
    sender._send_single_dataset(original_dataset, metrics)
    
    # Verify transformation occurred (using C-FIND)
    # This would query Compass to verify the tag was changed
    
    assert metrics.error_rate == 0
```

### 4. Failure Mode Tests

Simulate various failure conditions:

```python
def test_slow_transmission(dicom_datasets, dicom_sender, metrics):
    """Test behavior during slow transmission."""
    
    import time
    
    # Send files with delays between each
    for dataset in dicom_datasets[:3]:  # Limit to 3 files
        dicom_sender._send_single_dataset(dataset, metrics)
        time.sleep(2)  # 2 second delay between sends
    
    # System should handle delays gracefully
    assert metrics.error_rate <= 0.1  # Allow some tolerance for timeouts
```

## Configuration Management

### Environment Variables

All configuration is managed through environment variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `COMPASS_HOST` | Compass server hostname | `127.0.0.1` |
| `COMPASS_PORT` | DICOM port | `11112` |
| `DICOM_ROOT_DIR` | Test data directory | `./dicom_samples` |
| `PEAK_IMAGES_PER_SECOND` | Baseline performance rate | `50` |
| `TEST_DURATION_SECONDS` | Default test duration | `300` |
| `MAX_ERROR_RATE` | Acceptable error rate | `0.02` |

### Runtime Configuration Override

You can override settings for specific test runs:

```bash
# Quick test with custom settings
export TEST_DURATION_SECONDS=10
export LOAD_CONCURRENCY=4
python3 -m pytest tests/test_load_stability.py -vv

# High-intensity test
export LOAD_MULTIPLIER=5.0
export PEAK_IMAGES_PER_SECOND=100
python3 run_tests.py
```

### Configuration in Tests

Access configuration in your tests:

```python
def test_with_config_access(perf_config):
    """Test that uses configuration values."""
    
    # Access endpoint configuration
    host = perf_config.endpoint.host
    port = perf_config.endpoint.port
    
    # Access load testing parameters
    peak_rate = perf_config.load_profile.peak_images_per_second
    multiplier = perf_config.load_profile.load_multiplier
    target_rate = peak_rate * multiplier
    
    # Access thresholds
    max_error_rate = perf_config.thresholds.max_error_rate
    
    # Use in test logic
    assert target_rate > 0
```

## Data Management

### Test Data Sources

1. **Generated Samples**: `create_diverse_dicom_samples.py` creates test files
2. **Custom Data**: Place DICOM files in directory specified by `DICOM_ROOT_DIR`
3. **Runtime Generation**: Use `test_dicom_with_attributes` fixture

### Data Selection Fixtures

Use built-in fixtures for intelligent data selection:

```python
def test_with_large_files(large_dicom_file):
    """Test with files >10MB."""
    # large_dicom_file automatically selects a large file
    # or skips test if none available

def test_with_small_batch(small_dicom_files):
    """Test with small files <1MB.""" 
    # Returns up to 10 small files or skips if <3 available

def test_by_modality(dicom_by_modality):
    """Test organized by DICOM modality."""
    ct_files = dicom_by_modality.get('CT', [])
    if ct_files:
        # Use CT files specifically
        pass

def test_size_categories(dicom_by_size_category):
    """Test with files grouped by size."""
    small_files = dicom_by_size_category['small']
    medium_files = dicom_by_size_category['medium']
    large_files = dicom_by_size_category['large']
```

### Creating Custom Test Data

```python
def test_with_custom_data(test_dicom_with_attributes):
    """Create DICOM files with specific attributes."""
    
    # Create file with custom attributes
    file_path, dataset = test_dicom_with_attributes(
        patient_id='TEST001',
        modality='CT',
        study_description='Test Study',
        series_description='Test Series',
        institution_name='Test Hospital'
    )
    
    # Use the file in your test
    # ...
    
    # Cleanup happens automatically
```

## Best Practices

### 1. Test Design

- **Single Responsibility**: Each test should verify one specific behavior
- **Descriptive Names**: Use clear, descriptive test function names
- **Proper Markers**: Add appropriate pytest markers for categorization
- **Error Handling**: Include proper assertions with clear failure messages

### 2. Performance Testing

```python
def test_performance_example(dicom_sender, dicom_datasets, metrics, perf_config):
    """Example of proper performance test structure."""
    
    # 1. Pre-test validation
    assert len(dicom_datasets) > 0, "Need test data to run performance test"
    
    # 2. Pre-test connectivity check
    assert dicom_sender.ping(), "Compass must be reachable for performance test"
    
    # 3. Run test
    duration = perf_config.load_profile.test_duration_seconds
    total_sent = dicom_sender.load_test_for_duration(
        datasets=dicom_datasets,
        metrics=metrics,
        duration_seconds=duration,
    )
    
    # 4. Comprehensive validation
    assert total_sent > 0, "Should successfully send at least one file"
    
    error_rate = metrics.error_rate
    assert error_rate <= perf_config.thresholds.max_error_rate, \
        f"Error rate {error_rate:.1%} exceeds {perf_config.thresholds.max_error_rate:.1%}"
    
    p95_latency = metrics.p95_latency_ms
    max_latency = perf_config.thresholds.max_p95_latency_ms
    assert p95_latency <= max_latency, \
        f"P95 latency {p95_latency:.1f}ms exceeds {max_latency}ms threshold"
    
    # 5. Log results for debugging
    print(f"Performance Test Results:")
    print(f"  Files sent: {total_sent}")
    print(f"  Duration: {duration}s") 
    print(f"  Rate: {total_sent/duration:.1f} files/sec")
    print(f"  Error rate: {error_rate:.1%}")
    print(f"  P95 latency: {p95_latency:.1f}ms")
```

### 3. Resource Management

```python
def test_with_cleanup():
    """Example of proper resource cleanup."""
    
    temp_files = []
    try:
        # Create temporary resources
        for i in range(3):
            file_path, dataset = test_dicom_with_attributes(patient_id=f'TEST{i:03d}')
            temp_files.append(file_path)
            
        # Use resources in test
        # ...
        
    finally:
        # Cleanup
        import os
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
```

### 4. Configuration Best Practices

- Use environment variables for all configurable values
- Provide sensible defaults in config classes
- Document all configuration options
- Validate configuration values where possible

### 5. Error Handling

```python
def test_with_proper_error_handling(dicom_sender, single_dicom_file):
    """Example of proper error handling in tests."""
    
    try:
        # Test operation
        from data_loader import load_dataset
        dataset = load_dataset(single_dicom_file)
        
        metrics = PerfMetrics()
        dicom_sender._send_single_dataset(dataset, metrics)
        
        # Validate success
        assert metrics.total_sent == 1
        
    except Exception as e:
        # Provide helpful context for debugging
        pytest.fail(f"Test failed with error: {e}. "
                   f"Check Compass connectivity and configuration.")
```

## Troubleshooting

### Common Issues

#### 1. Connection Errors

**Problem**: Tests fail with connection refused or timeout errors.

**Solution**:
```bash
# Check Compass connectivity
telnet your-compass-server.com 11112

# Verify configuration
echo $COMPASS_HOST
echo $COMPASS_PORT

# Test C-ECHO connectivity
python3 -c "
from config import TestConfig
from dicom_sender import DicomSender
config = TestConfig.from_env()
sender = DicomSender(config.endpoint, config.load_profile)
print('Ping result:', sender.ping())
"
```

#### 2. No Test Data

**Problem**: Tests skip due to missing DICOM files.

**Solution**:
```bash
# Generate test data
python3 create_diverse_dicom_samples.py

# Check data location
ls -la $DICOM_ROOT_DIR

# Verify DICOM files are valid
python3 -c "
from data_loader import find_dicom_files
from pathlib import Path
files = find_dicom_files(Path('./dicom_samples'))
print(f'Found {len(files)} DICOM files')
"
```

#### 3. Performance Test Failures

**Problem**: Tests fail performance thresholds.

**Solution**:
```bash
# Reduce test intensity temporarily
export TEST_DURATION_SECONDS=10
export LOAD_CONCURRENCY=2
export LOAD_MULTIPLIER=1.0

# Or adjust thresholds for your environment
export MAX_ERROR_RATE=0.05
export MAX_P95_LATENCY_MS=5000
```

#### 4. Import Errors

**Problem**: `ImportError: No module named 'config'`

**Solution**:
```bash
# Run tests from project root
cd /path/to/dicomAuto
python3 -m pytest tests/

# Or use the test runner
python3 run_tests.py
```

### Debugging Test Failures

#### Enable Verbose Output

```bash
# Run with maximum verbosity
python3 -m pytest tests/test_your_test.py -vv -s

# Add pytest debugging
python3 -m pytest tests/test_your_test.py -vv -s --tb=long

# Run single test with full output
python3 -m pytest tests/test_your_test.py::test_function_name -vv -s
```

#### Add Debug Logging

```python
def test_with_debugging(dicom_sender, metrics):
    """Test with debug output."""
    
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Your test code here
    # Debug output will show detailed information
```

### Getting Help

1. **Check logs**: Look at pytest output and any error messages
2. **Verify configuration**: Ensure `.env` file settings are correct
3. **Test connectivity**: Use ping() method to verify Compass reachability  
4. **Check data**: Ensure test data exists and is valid
5. **Review documentation**: Check README.md and existing test examples

This guide provides the foundation for working with the DICOM testing framework. As you become more familiar with the codebase, you can explore advanced patterns and contribute improvements to the framework itself.