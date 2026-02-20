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
from tests.conftest import verify_study_arrived


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
    metrics: PerfMetrics,
    cfind_client,
    perf_config,
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
            print(f"\n[STEP 2: AUTOMATED VERIFICATION VIA C-FIND]")
            patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else None
            query_and_verify(
                cfind_client, perf_config,
                str(test_dataset.StudyInstanceUID), test_case['expected'],
                patient_id=patient_id,
            )
            
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

def query_and_verify(cfind_client, perf_config, study_uid: str, expected_attributes: dict, patient_id: str = None):
    """
    Query Compass via C-FIND and verify transformations were applied.

    Args:
        cfind_client: CompassCFindClient instance (or None).
        perf_config: TestConfig with timeout / poll settings.
        study_uid: StudyInstanceUID to query.
        expected_attributes: Dict of expected attribute values (snake_case keys).
        patient_id: Optional PatientID for fallback PATIENT-level C-FIND query.
    """
    print(f"\n  [AUTOMATED VERIFICATION VIA C-FIND]")

    study_data = verify_study_arrived(cfind_client, study_uid, perf_config, patient_id=patient_id)

    if study_data is None:
        # verify_study_arrived returned None (CFIND_VERIFY=false)
        print(f"  Skipped (C-FIND verification disabled)")
        return

    # Verify each expected attribute
    print(f"\n  Verifying expected transformations:")

    for attr_name, expected_value in expected_attributes.items():
        # Convert snake_case to PascalCase DICOM attribute name
        dicom_attr = ''.join(word.capitalize() for word in attr_name.split('_'))

        actual_value = study_data.get(dicom_attr, None)

        if actual_value is None:
            print(f"    {dicom_attr}: NOT FOUND in C-FIND response")
            raise AssertionError(
                f"{dicom_attr} not found in C-FIND response for study {study_uid}"
            )
        elif str(actual_value).strip() == str(expected_value).strip():
            print(f"    {dicom_attr}: '{actual_value}' - MATCH")
        else:
            print(f"    {dicom_attr}: '{actual_value}' - MISMATCH")
            print(f"      Expected: '{expected_value}'")
            raise AssertionError(
                f"{dicom_attr} mismatch: expected '{expected_value}', got '{actual_value}'"
            )

    print(f"\n  C-FIND VERIFICATION PASSED - All transformations correct!")


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

