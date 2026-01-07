# tests/test_routing_transformations.py

"""
Tests that verify Compass applies DICOM tag transformations correctly using C-STORE and C-FIND.
"""

from __future__ import annotations

import os
from datetime import datetime

import pytest

from data_loader import load_dataset
from metrics import PerfMetrics


# ============================================================================
# Test Case Definitions
# ============================================================================

# Define transformation test cases here
# Each test case specifies input attributes and expected output
TRANSFORMATION_TEST_CASES = [
    {
        'name': 'OPV_GPA_VisualFields',
        'description': 'OPV modality with GPA series description should set Visual Fields study description',
        'aet': 'ULTRA_MCR_FORUM',
        'input': {
            'modality': 'OPV',
            'series_description': 'GPA',
        },
        'expected': {
            'study_description': 'Visual Fields (VF) GPA',
        }
    },
    {
        'name': 'OPV_SFA_VisualFields',
        'description': 'OPV modality with SFA series description should set Visual Fields study description',
        'aet': 'ULTRA_MCR_FORUM',
        'input': {
            'modality': 'OPV',
            'series_description': 'SFA',
        },
        'expected': {
            'study_description': 'Visual Fields (VF) SFA',
        }
    },
    {
        'name': 'OPV_Mixed_VisualFields',
        'description': 'OPV modality with mixed series description (GPA or SFA) should set Visual Fields',
        'aet': 'ULTRA_MCR_FORUM',
        'input': {
            'modality': 'OPV',
            'series_description': 'Mixed Analysis',
        },
        'expected': {
            'study_description': 'Visual Fields (VF)',
        }
    },
    {
        'name': 'OPT_OCT',
        'description': 'OPT modality for Optical Coherence Tomography',
        'aet': 'ULTRA_MCR_FORUM',
        'input': {
            'modality': 'OPT',
        },
        'expected': {
            'study_description': 'Optical Coherence Tomography (OCT)',
        }
    },
    {
        'name': 'OT_IOLMaster',
        'description': 'OT modality for IOL Master measurements',
        'aet': 'ULTRA_MCR_FORUM',
        'input': {
            'modality': 'OT',
        },
        'expected': {
            'study_description': 'IOL Master (OT)',
        }
    },
    {
        'name': 'DOC_Combined',
        'description': 'DOC modality for combined OCT and VF report',
        'aet': 'ULTRA_MCR_FORUM',
        'input': {
            'modality': 'DOC',
        },
        'expected': {
            'study_description': 'OCT and VF Combined Report',
        }
    },
    # Add more test cases here following the same pattern:
    # {
    #     'name': 'TestCaseName',
    #     'description': 'Human-readable description',
    #     'aet': 'SOURCE_AE_TITLE',
    #     'input': {
    #         'modality': 'CT',
    #         'series_description': 'BRAIN',
    #         # Add any other DICOM attributes in snake_case
    #     },
    #     'expected': {
    #         'study_description': 'Expected Study Description',
    #         # Add other expected transformations
    #     }
    # },
]


# ============================================================================
# Test Implementation
# ============================================================================

@pytest.mark.integration
@pytest.mark.parametrize("test_case", TRANSFORMATION_TEST_CASES, ids=lambda tc: tc['name'])
def test_routing_transformation(
    test_case: dict,
    test_dicom_with_attributes,
    dicom_sender,
    metrics: PerfMetrics
):
    """
    Test Compass routing transformations based on input attributes.
    
    This test:
    1. Creates a DICOM file with specified input attributes
    2. Sends it to Compass using the specified AE Title
    3. Verifies the send was successful
    4. Automatically verifies transformations using C-FIND
    
    To add new test cases:
    - Add entries to TRANSFORMATION_TEST_CASES list above
    - Run: pytest tests/test_routing_transformations.py -v
    
    Automated verification:
    - Uses C-FIND to query Compass for the study
    - Verifies expected transformations were applied
    - Test fails if transformations don't match expected values
    """
    test_name = test_case['name']
    test_desc = test_case['description']
    
    print(f"\n{'='*70}")
    print(f"TEST CASE: {test_name}")
    print(f"{'='*70}")
    print(f"Description: {test_desc}")
    
    # Create test file with input attributes
    test_file_path, test_dataset = test_dicom_with_attributes(**test_case['input'])
    
    try:
        # Display test configuration
        print(f"\n[CONFIGURATION]")
        print(f"  Source AE Title: {test_case['aet']}")
        print(f"\n[INPUT ATTRIBUTES]")
        for attr_name, attr_value in test_case['input'].items():
            display_name = ''.join(word.capitalize() for word in attr_name.split('_'))
            print(f"  {display_name}: {attr_value}")
        
        print(f"\n[EXPECTED TRANSFORMATIONS]")
        for attr_name, attr_value in test_case['expected'].items():
            display_name = ''.join(word.capitalize() for word in attr_name.split('_'))
            print(f"  {display_name}: '{attr_value}'")
        
        print(f"\n[TEST IDENTIFIERS]")
        print(f"  StudyInstanceUID: {test_dataset.StudyInstanceUID}")
        print(f"  SeriesInstanceUID: {test_dataset.SeriesInstanceUID}")
        print(f"  SOPInstanceUID: {test_dataset.SOPInstanceUID}")
        
        # Override AE title for this test
        original_ae_title = dicom_sender.endpoint.local_ae_title
        dicom_sender.endpoint.local_ae_title = test_case['aet']
        
        try:
            # Send to Compass
            print(f"\n[STEP 1: SENDING TO COMPASS]")
            print(f"  Compass Host: {dicom_sender.endpoint.host}")
            print(f"  Compass Port: {dicom_sender.endpoint.port}")
            
            ds = load_dataset(test_file_path)
            dicom_sender._send_single_dataset(ds, metrics)
            
            # Verify send was successful
            assert metrics.successes == 1, \
                f"Send failed: {metrics.failures} failures, error rate: {metrics.error_rate:.1%}"
            
            print(f"  Status: SUCCESS")
            print(f"  Latency: {metrics.avg_latency_ms:.2f}ms")
            
            # Automated verification via C-FIND
            print(f"\n[STEP 2: AUTOMATED VERIFICATION]")
            query_and_verify(dicom_sender, test_dataset.StudyInstanceUID, test_case['expected'])
            
            print(f"\n[RESULT: TEST COMPLETE]")
            
        finally:
            # Restore original AE title
            dicom_sender.endpoint.local_ae_title = original_ae_title
    
    finally:
        # Cleanup temp file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)


# ============================================================================
# Automated Verification via C-FIND
# ============================================================================

def query_and_verify(dicom_sender, study_uid: str, expected_attributes: dict,
                     calling_aet: str = None,
                     timeout_seconds: int = 30, poll_interval: float = 2.0):
    """
    Query Compass database and verify transformations were applied.
    
    Uses database queries to find studies and DICOM tags.
    Polls Compass database for up to timeout_seconds waiting for study to appear.
    
    Args:
        dicom_sender: DicomSender instance
        study_uid: StudyInstanceUID to query
        expected_attributes: Dict of expected attribute values (snake_case keys)
        calling_aet: Not used for database queries (kept for compatibility)
        timeout_seconds: Maximum seconds to wait for study to appear (default: 30)
        poll_interval: Seconds between polls (default: 2.0)
    """
    import time
    
    print(f"\n  [AUTOMATED VERIFICATION VIA DATABASE QUERY]")
    print(f"  Querying Compass database for study: {study_uid}")
    print(f"  Timeout: {timeout_seconds}s")
    
    try:
        from compass_db_query import CompassDatabaseClient, CompassDatabaseConfig
    except ImportError:
        print(f"  ERROR: compass_db_query not available")
        print(f"  Cannot perform automated verification")
        raise AssertionError(
            "compass_db_query module not available. "
            "Automated verification cannot run."
        )
    
    try:
        # Load database config from environment
        config = CompassDatabaseConfig.from_env()
        
        print(f"  Database: {config.database} on {config.server}")
        
        # Poll for the study with timeout
        start_time = time.time()
        study_data = None
        attempts = 0
        
        while time.time() - start_time < timeout_seconds:
            attempts += 1
            
            with CompassDatabaseClient(config) as client:
                study_data = client.get_job_by_study_uid(study_uid)
            
            if study_data:
                elapsed = time.time() - start_time
                print(f"  SUCCESS: Study found in Compass after {elapsed:.1f}s ({attempts} attempts)")
                break
            
            if attempts == 1:
                print(f"  Waiting for study to appear in Compass database...")
            
            time.sleep(poll_interval)
        
        if not study_data:
            elapsed = time.time() - start_time
            print(f"  ERROR: Study not found in Compass after {elapsed:.1f}s ({attempts} attempts)")
            print(f"  StudyInstanceUID: {study_uid}")
            print(f"  Possible reasons:")
            print(f"    - Study not yet processed by Compass (waited {timeout_seconds}s)")
            print(f"    - Compass routing without storing locally")
            print(f"    - Database connection/permissions issue")
            print(f"    - Study was rejected/filtered")
            raise AssertionError(
                f"Study not found in Compass after {timeout_seconds}s: {study_uid}\n"
                f"Database query returned no results after {attempts} attempts. "
                f"Study may not have been received or stored."
            )
        
        # Verify each expected attribute
        print(f"\n  Verifying expected transformations:")
        all_matched = True
        
        for attr_name, expected_value in expected_attributes.items():
            # Convert snake_case to PascalCase DICOM attribute name
            dicom_attr = ''.join(word.capitalize() for word in attr_name.split('_'))
            
            # Get actual value from study
            actual_value = study_data.get(dicom_attr, None)
            
            if actual_value is None:
                print(f"    {dicom_attr}: NOT FOUND in database")
                all_matched = False
            elif str(actual_value).strip() == str(expected_value).strip():
                print(f"    {dicom_attr}: '{actual_value}' ✓ MATCH")
            else:
                print(f"    {dicom_attr}: '{actual_value}' ✗ MISMATCH")
                print(f"      Expected: '{expected_value}'")
                all_matched = False
                # Raise assertion error for test failure
                raise AssertionError(
                    f"{dicom_attr} mismatch: expected '{expected_value}', got '{actual_value}'"
                )
        
        if all_matched:
            print(f"\n  ✓ DATABASE VERIFICATION PASSED - All transformations correct!")
        else:
            print(f"\n  ✗ DATABASE VERIFICATION FAILED - See mismatches above")
    
    except ConnectionError as e:
        print(f"  ERROR: Database connection failed: {e}")
        print(f"  Cannot connect to Compass database for verification")
        raise AssertionError(
            f"Database connection failed: {e}\n"
            f"Cannot verify study was received by Compass."
        )
    
    except AssertionError:
        # Re-raise assertion errors for test failure
        raise
    
    except Exception as e:
        print(f"  ERROR: Database query failed: {e}")
        print(f"  Unexpected error during verification")
        raise AssertionError(
            f"Database query failed: {e}\n"
            f"Cannot verify study was received by Compass."
        )


# ============================================================================
# Summary Test - Run All Transformation Tests
# ============================================================================

@pytest.mark.integration
def test_all_transformations_summary(
    test_dicom_with_attributes,
    dicom_sender,
):
    """
    Summary test that displays all configured transformation test cases.
    
    This test doesn't send anything - it just documents what will be tested.
    Run this first to see what transformation rules are being validated.
    """
    print(f"\n{'='*70}")
    print(f"COMPASS ROUTING TRANSFORMATION TEST SUITE")
    print(f"{'='*70}")
    print(f"\nTotal test cases configured: {len(TRANSFORMATION_TEST_CASES)}")
    print(f"\nTest cases:")
    
    for i, test_case in enumerate(TRANSFORMATION_TEST_CASES, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   Description: {test_case['description']}")
        print(f"   AE Title: {test_case['aet']}")
        print(f"   Input: {', '.join(f'{k}={v}' for k, v in test_case['input'].items())}")
        print(f"   Expected: {', '.join(f'{k}={v}' for k, v in test_case['expected'].items())}")
    
    print(f"\n{'='*70}")
    print(f"To run all transformation tests:")
    print(f"  pytest tests/test_routing_transformations.py::test_routing_transformation -v")
    print(f"\nTo run a specific test case:")
    print(f"  pytest tests/test_routing_transformations.py::test_routing_transformation[OPV_GPA_VisualFields] -v")
    print(f"{'='*70}\n")


# ============================================================================
# Helper: Add New Test Case Interactively
# ============================================================================

def add_test_case_template():
    """
    Template for adding new test cases.
    
    Copy this structure and add to TRANSFORMATION_TEST_CASES list:
    """
    new_test_case = {
        'name': 'YourTestCaseName',  # Short identifier (no spaces)
        'description': 'Human-readable description of what this tests',
        'aet': 'SOURCE_AE_TITLE',  # The sending AE title
        'input': {
            # Input DICOM attributes (snake_case)
            'modality': 'XX',
            'series_description': 'Description',
            'institution_name': 'Hospital Name',
            # Add more attributes as needed
        },
        'expected': {
            # Expected output after Compass transformation (snake_case)
            'study_description': 'Expected Study Description',
            # Add more expected transformations
        }
    }
    return new_test_case

