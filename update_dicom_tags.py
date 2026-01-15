#!/usr/bin/env python3
"""
Standalone script to update DICOM tags in all files within a specified folder.

This script processes DICOM files and updates critical tags with unique timestamp-based
values, including StudyInstanceUID, AccessionNumber, and SeriesInstanceUID. It also
updates other test tags as specified and verifies all changes are valid.

The script supports updating any DICOM tag by specifying tag updates via command-line
arguments or a JSON configuration file.

Usage:
    # Update specific tags via command-line
    python update_dicom_tags.py <folder_path> --tag PatientID=TEST123 --tag PatientName="TEST^PATIENT"
    
    # Update tags from JSON file
    python update_dicom_tags.py <folder_path> --tags-file tags.json
    
    # Use default test tag updates (backward compatible)
    python update_dicom_tags.py <folder_path>
    
    # Specify hex tag format
    python update_dicom_tags.py <folder_path> --tag "(0010,0020)=TEST123"
    
    # Specify VR for new tags
    python update_dicom_tags.py <folder_path> --tag "PatientID:LO=TEST123"
"""

import argparse
import json
import os
import re
import sys
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from pydicom import dcmread
from pydicom import datadict
from pydicom.uid import generate_uid
from pydicom.errors import InvalidDicomError

# Add project root to path to allow importing dcmutl
script_dir = Path(__file__).parent.absolute()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

try:
    from dcmutl import get_dcm_files, update_tags_ds
except ImportError as e:
    print(f"Error: Could not import dcmutl module: {e}", file=sys.stderr)
    print("Make sure you're running this script from the project root directory.", file=sys.stderr)
    sys.exit(1)


def parse_tag_specification(tag_spec: str) -> Tuple[str, str, Optional[str]]:
    """
    Parse a tag specification string into tag identifier, value, and optional VR.
    
    Supports multiple formats:
    - "PatientID=TEST123" (standard keyword)
    - "PatientID:LO=TEST123" (keyword with VR)
    - "(0010,0020)=TEST123" (hex tag format)
    - "(0010,0020):LO=TEST123" (hex tag with VR)
    - "00100020=TEST123" (8-char hex string)
    - "00100020:LO=TEST123" (8-char hex with VR)
    
    Args:
        tag_spec: Tag specification string
        
    Returns:
        Tuple of (tag_identifier, value, vr)
        tag_identifier can be keyword, hex tuple string, or 8-char hex string
    """
    # Pattern: tag[:VR]=value
    match = re.match(r'^(.+?)(?::([A-Z]{2}))?=(.+)$', tag_spec)
    if not match:
        raise ValueError(f"Invalid tag specification format: {tag_spec}. Expected 'TAG=VALUE' or 'TAG:VR=VALUE'")
    
    tag_part, vr, value = match.groups()
    
    # Normalize tag identifier
    tag_identifier = tag_part.strip()
    
    # Handle hex format (0010,0020) or 00100020
    if tag_identifier.startswith('(') and tag_identifier.endswith(')'):
        # Format: (0010,0020)
        hex_match = re.match(r'^\(([0-9A-Fa-f]{4}),([0-9A-Fa-f]{4})\)$', tag_identifier)
        if hex_match:
            group, element = hex_match.groups()
            tag_identifier = f"{group}{element}"
        else:
            raise ValueError(f"Invalid hex tag format: {tag_identifier}")
    elif len(tag_identifier) == 8 and all(c in '0123456789ABCDEFabcdef' for c in tag_identifier):
        # Format: 00100020 (already correct)
        pass
    else:
        # Standard keyword - validate it exists in DICOM dictionary
        try:
            tag_tuple = datadict.tag_for_keyword(tag_identifier)
            if tag_tuple is None:
                # Not a standard keyword, but might be a private tag or custom
                # We'll allow it and let pydicom handle it
                pass
        except Exception:
            # Not a standard keyword, but we'll try to use it anyway
            pass
    
    return tag_identifier, value, vr


def get_tag_tuple(tag_identifier: str) -> Optional[Tuple[int, int]]:
    """
    Convert tag identifier to (group, element) tuple.
    
    Args:
        tag_identifier: Tag as keyword, hex tuple string, or 8-char hex string
        
    Returns:
        (group, element) tuple or None if invalid
    """
    # Check if it's an 8-character hex string
    if len(tag_identifier) == 8 and all(c in '0123456789ABCDEFabcdef' for c in tag_identifier):
        try:
            group = int(tag_identifier[0:4], 16)
            element = int(tag_identifier[4:8], 16)
            return (group, element)
        except ValueError:
            return None
    
    # Check if it's a standard keyword
    try:
        tag_tuple = datadict.tag_for_keyword(tag_identifier)
        return tag_tuple
    except Exception:
        return None


def get_tag_vr(tag_identifier: str, dataset=None) -> Optional[str]:
    """
    Get the VR (Value Representation) for a tag.
    
    Args:
        tag_identifier: Tag as keyword, hex tuple string, or 8-char hex string
        dataset: Optional dataset to check existing tag VR
        
    Returns:
        VR string or None if cannot determine
    """
    tag_tuple = get_tag_tuple(tag_identifier)
    if tag_tuple:
        try:
            vr = datadict.dictionary_VR(tag_tuple)
            return vr
        except Exception:
            pass
    
    # If tag exists in dataset, use its VR
    if dataset:
        tag_tuple = get_tag_tuple(tag_identifier)
        if tag_tuple and tag_tuple in dataset:
            return dataset[tag_tuple].VR
    
    return None


def update_tag_in_dataset(
    ds,
    tag_identifier: str,
    value: str,
    vr: Optional[str] = None,
    verbose: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Update a tag in a DICOM dataset.
    
    Args:
        ds: pydicom Dataset object
        tag_identifier: Tag as keyword, hex tuple string, or 8-char hex string
        value: Value to set
        vr: Optional VR to use when creating new tags
        verbose: If True, print detailed information
        
    Returns:
        Tuple of (success, old_value)
    """
    old_value = None
    
    try:
        tag_tuple = get_tag_tuple(tag_identifier)
        
        if tag_tuple:
            # Use hex tuple format
            group, element = tag_tuple
            
            if (group, element) in ds:
                old_value = str(ds[group, element].value)
                ds[group, element].value = value
                if verbose:
                    print(f"    Tag ({group:04X},{element:04X}) updated: {old_value} -> {value}")
            else:
                # Tag doesn't exist, need to add it
                if vr is None:
                    vr = get_tag_vr(tag_identifier, ds) or 'LO'  # Default to LO if unknown
                
                ds.add_new((group, element), vr, value)
                if verbose:
                    print(f"    Tag ({group:04X},{element:04X}) added with VR {vr}: {value}")
        else:
            # Try as standard keyword
            if hasattr(ds, tag_identifier):
                old_value = str(getattr(ds, tag_identifier))
                setattr(ds, tag_identifier, value)
                if verbose:
                    print(f"    Tag {tag_identifier} updated: {old_value} -> {value}")
            else:
                # Try to add using setattr (pydicom will determine VR)
                try:
                    setattr(ds, tag_identifier, value)
                    if verbose:
                        print(f"    Tag {tag_identifier} added: {value}")
                except Exception as e:
                    if verbose:
                        print(f"    Warning: Could not set tag {tag_identifier}: {e}")
                    return False, None
        
        return True, old_value
        
    except Exception as e:
        if verbose:
            print(f"    Error updating tag {tag_identifier}: {e}")
        return False, None


def load_tags_from_json(json_file: str) -> Dict[str, Dict[str, str]]:
    """
    Load tag updates from a JSON file.
    
    JSON format:
    {
        "PatientID": {
            "value": "TEST123",
            "vr": "LO"  // optional
        },
        "(0010,0020)": {
            "value": "TEST456"
        }
    }
    
    Or simpler format:
    {
        "PatientID": "TEST123",
        "(0010,0020)": "TEST456"
    }
    
    Args:
        json_file: Path to JSON file
        
    Returns:
        Dictionary mapping tag identifiers to update info
    """
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        tags = {}
        for tag_key, tag_data in data.items():
            if isinstance(tag_data, dict):
                tags[tag_key] = {
                    'value': tag_data.get('value', ''),
                    'vr': tag_data.get('vr')
                }
            else:
                # Simple format: just value
                tags[tag_key] = {
                    'value': str(tag_data),
                    'vr': None
                }
        
        return tags
        
    except FileNotFoundError:
        raise FileNotFoundError(f"Tags file not found: {json_file}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in tags file: {e}")
    except Exception as e:
        raise ValueError(f"Error loading tags file: {e}")


def generate_accession_number() -> str:
    """
    Generate a unique accession number based on current timestamp.
    
    Returns:
        Accession number in format: YYYYMMDD-HHMMSS-{microseconds}
    """
    now = datetime.now()
    microseconds = now.microsecond
    return f"{now.strftime('%Y%m%d-%H%M%S')}-{microseconds:06d}"


def is_valid_uid(uid: str) -> bool:
    """
    Validate that a UID follows DICOM format requirements.
    
    DICOM UIDs must:
    - Contain only numeric characters and dots
    - Each component must not start with 0 (unless it's a single 0)
    - Maximum length of 64 characters
    - Components separated by dots
    
    Args:
        uid: UID string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not uid or not isinstance(uid, str):
        return False
    
    if len(uid) > 64:
        return False
    
    # Split by dots and validate each component
    components = uid.split('.')
    if not components:
        return False
    
    for component in components:
        if not component:
            return False
        # Component must be numeric
        if not component.isdigit():
            return False
        # Component must not start with 0 unless it's just "0"
        if len(component) > 1 and component.startswith('0'):
            return False
    
    return True


def get_original_values(ds, tag_identifiers: Optional[List[str]] = None) -> Dict[str, Optional[str]]:
    """
    Extract original values from DICOM dataset.
    
    Args:
        ds: pydicom Dataset object
        tag_identifiers: Optional list of tag identifiers to extract
        
    Returns:
        Dictionary with original values for specified tags
    """
    if tag_identifiers is None:
        # Default tags for backward compatibility
        tag_identifiers = ['StudyInstanceUID', 'AccessionNumber', 'SeriesInstanceUID']
    
    originals = {}
    
    for tag_id in tag_identifiers:
        originals[tag_id] = None
        try:
            tag_tuple = get_tag_tuple(tag_id)
            if tag_tuple:
                group, element = tag_tuple
                if (group, element) in ds:
                    originals[tag_id] = str(ds[group, element].value)
            elif hasattr(ds, tag_id):
                originals[tag_id] = str(getattr(ds, tag_id))
        except (AttributeError, KeyError, Exception):
            pass
    
    return originals


def update_dicom_file(
    file_path: str,
    dry_run: bool = False,
    verbose: bool = False,
    custom_tags: Optional[Dict[str, Dict[str, str]]] = None,
    use_default_test_tags: bool = True,
    generate_unique_ids: bool = True
) -> Tuple[bool, str, Dict[str, Optional[str]], Dict[str, Optional[str]]]:
    """
    Update DICOM tags in a single file.
    
    Args:
        file_path: Path to DICOM file
        dry_run: If True, don't actually modify the file
        verbose: If True, print detailed information
        custom_tags: Optional dictionary of custom tag updates {tag_id: {value: str, vr: Optional[str]}}
        use_default_test_tags: If True, apply default test tag updates (backward compatibility)
        generate_unique_ids: If True, generate unique IDs for StudyInstanceUID, AccessionNumber, SeriesInstanceUID
        
    Returns:
        Tuple of (success, message, original_values, new_values)
    """
    try:
        # Read DICOM file
        print("  Step 0: Reading DICOM file...")
        ds = dcmread(file_path)
        print("    File read successfully")
        
        # Collect all tags to update
        tags_to_update = {}
        tag_identifiers = []
        
        # Add unique ID tags if requested
        if generate_unique_ids:
            new_study_uid = generate_uid()
            new_accession_number = generate_accession_number()
            new_series_uid = generate_uid()
            
            tags_to_update['StudyInstanceUID'] = {'value': new_study_uid, 'vr': None}
            tags_to_update['AccessionNumber'] = {'value': new_accession_number, 'vr': None}
            tags_to_update['SeriesInstanceUID'] = {'value': new_series_uid, 'vr': None}
            tag_identifiers.extend(['StudyInstanceUID', 'AccessionNumber', 'SeriesInstanceUID'])
        
        # Add default test tags if requested
        if use_default_test_tags:
            default_tags = {
                'PatientID': {'value': '11043207', 'vr': 'LO'},
                'PatientName': {'value': 'ZZTESTPATIENT^MIDIA THREE', 'vr': 'PN'},
                'PatientBirthDate': {'value': '19010101', 'vr': 'DA'},
                'InstitutionName': {'value': 'TEST FACILITY', 'vr': 'LO'},
                'ReferringPhysicianName': {'value': 'TEST PROVIDER', 'vr': 'PN'}
            }
            for tag_id, tag_info in default_tags.items():
                if tag_id not in tags_to_update:  # Don't override custom tags
                    tags_to_update[tag_id] = tag_info
                    tag_identifiers.append(tag_id)
        
        # Add custom tags (these override defaults)
        if custom_tags:
            for tag_id, tag_info in custom_tags.items():
                tags_to_update[tag_id] = tag_info
                if tag_id not in tag_identifiers:
                    tag_identifiers.append(tag_id)
        
        # Get original values
        original_values = get_original_values(ds, tag_identifiers)
        
        # Prepare new values dictionary
        new_values = {tag_id: tags_to_update[tag_id]['value'] for tag_id in tags_to_update}
        
        # Log updates
        print("  Step 1: Preparing tag updates...")
        if generate_unique_ids:
            print(f"    StudyInstanceUID: {new_study_uid}")
            print(f"    AccessionNumber: {new_accession_number}")
            print(f"    SeriesInstanceUID: {new_series_uid}")
        
        if verbose:
            for tag_id in tag_identifiers:
                if tag_id in original_values:
                    print(f"  Original {tag_id}: {original_values[tag_id]}")
        
        if not dry_run:
            # Update all tags
            print("  Step 2: Updating tags...")
            
            for tag_id, tag_info in tags_to_update.items():
                value = tag_info['value']
                vr = tag_info.get('vr')
                
                # Special handling for ReferringPhysicianName (try multiple tags)
                if tag_id == 'ReferringPhysicianName':
                    referring_physician_set = False
                    # Try standard tag (0008,0090) first
                    try:
                        if (0x0008, 0x0090) in ds:
                            old_val = str(ds[0x0008, 0x0090].value)
                            ds[0x0008, 0x0090].value = value
                            referring_physician_set = True
                            print(f"    ReferringPhysicianName (0008,0090) updated: {old_val} -> {value}")
                        else:
                            ds.add_new((0x0008, 0x0090), vr or 'PN', value)
                            referring_physician_set = True
                            print(f"    ReferringPhysicianName (0008,0090) added: {value}")
                    except Exception as e:
                        if verbose:
                            print(f"    Warning: Could not set ReferringPhysicianName (0008,0090): {e}")
                    
                    # Fallback to private tag (0808,0090) if standard tag failed
                    if not referring_physician_set:
                        try:
                            if (0x0808, 0x0090) in ds:
                                old_val = str(ds[0x0808, 0x0090].value)
                                ds[0x0808, 0x0090].value = value
                                referring_physician_set = True
                                print(f"    ReferringPhysicianName (0808,0090) updated: {old_val} -> {value}")
                            else:
                                ds.add_new((0x0808, 0x0090), vr or 'PN', value)
                                referring_physician_set = True
                                print(f"    ReferringPhysicianName (0808,0090) added: {value}")
                        except Exception as e:
                            if verbose:
                                print(f"    Warning: Could not set ReferringPhysicianName (0808,0090): {e}")
                else:
                    # Regular tag update
                    success, old_val = update_tag_in_dataset(ds, tag_id, value, vr, verbose)
                    if not success and verbose:
                        print(f"    Warning: Failed to update tag {tag_id}")
            
            # Save the file
            print("  Step 3: Saving updated DICOM file...")
            ds.save_as(file_path, write_like_original=False)
            print("    File saved successfully")
        
        return True, "Success", original_values, new_values
        
    except InvalidDicomError as e:
        return False, f"Invalid DICOM file: {e}", {}, {}
    except Exception as e:
        return False, f"Error processing file: {e}", {}, {}


def verify_changes(
    file_path: str,
    original_values: Dict[str, Optional[str]],
    new_values: Dict[str, Optional[str]],
    verify_unique_ids: bool = True,
    verify_test_tags: bool = True
) -> Tuple[bool, str]:
    """
    Verify that the changes were applied correctly and values are valid.
    
    Args:
        file_path: Path to DICOM file
        original_values: Dictionary of original values
        new_values: Dictionary of new values
        verify_unique_ids: If True, verify unique ID tags (StudyInstanceUID, etc.)
        verify_test_tags: If True, verify default test tags
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Re-read the file
        ds = dcmread(file_path)
        
        verification_errors = []
        
        # Verify all tags in new_values
        print("    Verifying updated tags...")
        
        for tag_id, expected_value in new_values.items():
            if tag_id is None or expected_value is None:
                continue
            
            print(f"    Verifying {tag_id}...")
            
            # Get current value
            current_value = None
            tag_tuple = get_tag_tuple(tag_id)
            
            if tag_tuple:
                group, element = tag_tuple
                if (group, element) in ds:
                    current_value = str(ds[group, element].value)
            elif hasattr(ds, tag_id):
                current_value = str(getattr(ds, tag_id))
            
            if current_value is None:
                verification_errors.append(f"{tag_id} tag missing after update")
            else:
                # Special validation for UIDs
                if tag_id in ['StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID']:
                    if not is_valid_uid(current_value):
                        verification_errors.append(f"{tag_id} is not valid: {current_value}")
                    elif current_value != expected_value:
                        verification_errors.append(f"{tag_id} mismatch: expected {expected_value}, got {current_value}")
                    else:
                        print(f"      {tag_id} verified")
                else:
                    # Regular value comparison
                    if current_value != expected_value:
                        verification_errors.append(f"{tag_id} mismatch: expected '{expected_value}', got '{current_value}'")
                    else:
                        print(f"      {tag_id} verified: {current_value}")
        
        if verification_errors:
            return False, "; ".join(verification_errors)
        
        return True, "All verifications passed"
        
    except Exception as e:
        return False, f"Verification error: {e}"


def process_folder(
    folder_path: str,
    dry_run: bool = False,
    verbose: bool = False,
    custom_tags: Optional[Dict[str, Dict[str, str]]] = None,
    use_default_test_tags: bool = True,
    generate_unique_ids: bool = True
) -> Dict[str, int]:
    """
    Process all DICOM files in a folder.
    
    Args:
        folder_path: Path to folder containing DICOM files
        dry_run: If True, don't actually modify files
        verbose: If True, print detailed information
        custom_tags: Optional dictionary of custom tag updates
        use_default_test_tags: If True, apply default test tag updates
        generate_unique_ids: If True, generate unique IDs for UIDs
        
    Returns:
        Dictionary with statistics about processing
    """
    stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'verification_failed': 0
    }
    
    # Normalize path for Windows (handle both forward and backslashes)
    folder_path = os.path.normpath(folder_path)
    
    # Validate folder exists
    if not os.path.exists(folder_path):
        print(f"Error: Folder does not exist: {folder_path}", file=sys.stderr)
        print(f"  Resolved path: {os.path.abspath(folder_path)}", file=sys.stderr)
        return stats
    
    if not os.path.isdir(folder_path):
        print(f"Error: Path is not a directory: {folder_path}", file=sys.stderr)
        return stats
    
    print("=" * 60)
    print("DICOM TAG UPDATER")
    print("=" * 60)
    print(f"Processing folder: {folder_path}")
    if verbose:
        print(f"Absolute path: {os.path.abspath(folder_path)}")
    print()
    
    # Get all DICOM files
    print("Searching for DICOM files...")
    dcm_files = get_dcm_files(folder_path)
    
    if not dcm_files:
        print(f"Warning: No DICOM files found in folder: {folder_path}", file=sys.stderr)
        if verbose:
            # List what files are actually in the directory
            try:
                files_in_dir = os.listdir(folder_path)
                print(f"  Files in directory: {len(files_in_dir)} items")
                if files_in_dir:
                    print(f"  Sample files: {files_in_dir[:5]}")
            except Exception as e:
                print(f"  Could not list directory contents: {e}")
        return stats
    
    stats['total'] = len(dcm_files)
    
    print("=" * 60)
    print(f"Found {stats['total']} DICOM file(s) to process")
    if dry_run:
        print("DRY RUN MODE: Files will not be modified")
    print("=" * 60)
    print()
    
    # Process each file
    for idx, dcm_file in enumerate(dcm_files, 1):
        print(f"[{idx}/{stats['total']}] Processing: {os.path.basename(dcm_file)}")
        
        if verbose:
            print(f"  Full path: {dcm_file}")
        
        success, message, original_values, new_values = update_dicom_file(
            dcm_file,
            dry_run=dry_run,
            verbose=verbose,
            custom_tags=custom_tags,
            use_default_test_tags=use_default_test_tags,
            generate_unique_ids=generate_unique_ids
        )
        
        if not success:
            print(f"  ERROR: {message}")
            stats['failed'] += 1
            print()
            continue
        
        stats['success'] += 1
        
        if not dry_run:
            # Verify changes
            print("  Step 6: Verifying changes...")
            verify_success, verify_message = verify_changes(
                dcm_file,
                original_values,
                new_values
            )
            
            if not verify_success:
                print(f"  VERIFICATION FAILED: {verify_message}")
                stats['verification_failed'] += 1
            else:
                print("  Verification passed: All tags updated correctly")
        else:
            print("  Skipping verification in dry-run mode")
        
        print(f"  File {idx}/{stats['total']} completed successfully")
        print()
    
    return stats


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Update DICOM tags in all files within a specified folder.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update specific tags via command-line
  %(prog)s folder --tag PatientID=TEST123 --tag PatientName="TEST^PATIENT"
  
  # Update tags from JSON file
  %(prog)s folder --tags-file tags.json
  
  # Use default test tag updates (backward compatible)
  %(prog)s folder
  
  # Specify hex tag format
  %(prog)s folder --tag "(0010,0020)=TEST123"
  
  # Specify VR for new tags
  %(prog)s folder --tag "PatientID:LO=TEST123"
  
  # Disable default test tags and only use custom tags
  %(prog)s folder --tag PatientID=TEST123 --no-default-tags
  
  # Disable unique ID generation
  %(prog)s folder --tag PatientID=TEST123 --no-unique-ids
        """
    )
    
    parser.add_argument(
        'folder',
        type=str,
        help='Path to folder containing DICOM files'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )
    
    parser.add_argument(
        '--tag',
        action='append',
        dest='tags',
        metavar='TAG_SPEC',
        help='Tag to update in format TAG=VALUE or TAG:VR=VALUE. Can be specified multiple times. '
             'Supports standard keywords (e.g., PatientID), hex format (e.g., "(0010,0020)"), '
             'or 8-char hex string (e.g., "00100020").'
    )
    
    parser.add_argument(
        '--tags-file',
        type=str,
        metavar='JSON_FILE',
        help='JSON file containing tag updates. Format: {"TagID": "value"} or '
             '{"TagID": {"value": "value", "vr": "LO"}}'
    )
    
    parser.add_argument(
        '--no-default-tags',
        action='store_true',
        help='Disable default test tag updates (PatientID, PatientName, etc.)'
    )
    
    parser.add_argument(
        '--no-unique-ids',
        action='store_true',
        help='Disable automatic generation of unique IDs for StudyInstanceUID, '
             'AccessionNumber, and SeriesInstanceUID'
    )
    
    args = parser.parse_args()
    
    # Parse custom tags
    custom_tags = None
    
    if args.tags_file:
        try:
            custom_tags = load_tags_from_json(args.tags_file)
            if args.verbose:
                print(f"Loaded {len(custom_tags)} tags from {args.tags_file}")
        except Exception as e:
            print(f"Error loading tags file: {e}", file=sys.stderr)
            sys.exit(1)
    
    if args.tags:
        if custom_tags is None:
            custom_tags = {}
        
        for tag_spec in args.tags:
            try:
                tag_id, value, vr = parse_tag_specification(tag_spec)
                custom_tags[tag_id] = {'value': value, 'vr': vr}
            except Exception as e:
                print(f"Error parsing tag specification '{tag_spec}': {e}", file=sys.stderr)
                sys.exit(1)
    
    # Process the folder
    stats = process_folder(
        args.folder,
        dry_run=args.dry_run,
        verbose=args.verbose,
        custom_tags=custom_tags,
        use_default_test_tags=not args.no_default_tags,
        generate_unique_ids=not args.no_unique_ids
    )
    
    # Print summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total files processed: {stats['total']}")
    print(f"Successfully updated: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    if not args.dry_run:
        print(f"Verification failed: {stats['verification_failed']}")
    print("=" * 60)
    
    # Exit with appropriate code
    if stats['failed'] > 0 or stats['verification_failed'] > 0:
        sys.exit(1)
    elif stats['total'] == 0:
        sys.exit(2)
    else:
        sys.exit(0)


class DICOMTagUpdaterGUI:
    """GUI application for updating DICOM tags."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("DICOM Tag Updater")
        self.root.geometry("800x700")
        
        # Default tag values
        self.default_tags = {
            'PatientID': {'title': 'Patient ID', 'hex': '(0010,0020)', 'value': '11043207'},
            'PatientName': {'title': 'Patient Name', 'hex': '(0010,0010)', 'value': 'ZZTESTPATIENT^MIDIA THREE'},
            'PatientBirthDate': {'title': 'Patient Birth Date', 'hex': '(0010,0030)', 'value': '19010101'},
            'InstitutionName': {'title': 'Institution Name', 'hex': '(0008,0080)', 'value': 'TEST FACILITY'},
            'ReferringPhysicianName': {'title': 'Referring Physician Name', 'hex': '(0008,0090)', 'value': 'TEST PROVIDER'}
        }
        
        # Custom tags (dynamically added)
        self.custom_tags = []
        
        # Path variable
        self.path_var = tk.StringVar()
        
        # Status variable
        self.status_var = tk.StringVar(value="Ready")
        
        # Cache of available DICOM tags
        self.available_tags = self._get_available_dicom_tags()
        
        self.setup_ui()
    
    def _get_available_dicom_tags(self):
        """Get a sorted list of all available DICOM tag keywords."""
        tags = set()
        try:
            # Get all keywords from keyword_dict (most efficient method)
            if hasattr(datadict, 'keyword_dict') and datadict.keyword_dict:
                tags.update(datadict.keyword_dict.keys())
            
            # Also check private dictionary keywords if available
            if hasattr(datadict, 'private_dictionary') and datadict.private_dictionary:
                # Private dictionary structure may vary, try to extract keywords
                try:
                    for entry in datadict.private_dictionary.values():
                        if isinstance(entry, tuple) and len(entry) > 2:
                            keyword = entry[2] if len(entry) > 2 else None
                            if keyword and keyword != '':
                                tags.add(keyword)
                except Exception:
                    pass
            
            # Filter out empty, None, or 'Unknown' keywords
            tags = {tag for tag in tags if tag and tag != '' and tag != 'Unknown'}
            
            # Convert to sorted list
            tags_list = sorted(list(tags))
            
            # If we got a reasonable number of tags, return them
            if len(tags_list) > 50:
                return tags_list
            else:
                # Fallback if we didn't get many tags
                raise Exception("Not enough tags found")
                
        except Exception as e:
            # Comprehensive fallback list of common DICOM tags
            tags_list = [
                'AccessionNumber', 'AcquisitionDate', 'AcquisitionDateTime', 'AcquisitionTime',
                'BitsAllocated', 'BitsStored', 'BodyPartExamined', 'Columns', 'ContentDate',
                'ContentTime', 'DeviceSerialNumber', 'HighBit', 'ImageOrientationPatient',
                'ImagePositionPatient', 'ImageType', 'InstitutionAddress', 'InstitutionName',
                'InstitutionalDepartmentName', 'InstanceNumber', 'Manufacturer',
                'ManufacturerModelName', 'Modality', 'NumberOfFrames', 'OperatorName',
                'PatientAge', 'PatientBirthDate', 'PatientID', 'PatientName', 'PatientPosition',
                'PatientSex', 'PatientSize', 'PatientWeight', 'PerformingPhysicianName',
                'PhotometricInterpretation', 'PixelAspectRatio', 'PixelSpacing',
                'ReferringPhysicianName', 'Rows', 'SamplesPerPixel', 'SeriesDate',
                'SeriesDescription', 'SeriesInstanceUID', 'SeriesNumber', 'SeriesTime',
                'SliceLocation', 'SliceThickness', 'SoftwareVersions', 'SOPInstanceUID',
                'StationName', 'StudyDate', 'StudyDescription', 'StudyID', 'StudyInstanceUID',
                'StudyTime', 'TransferSyntaxUID', 'WindowCenter', 'WindowWidth'
            ]
            return tags_list
    
    def setup_ui(self):
        """Set up the user interface."""
        # Title
        title_label = tk.Label(self.root, text="DICOM Tag Updater", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # File/Folder selection section
        file_frame = ttk.LabelFrame(self.root, text="Select DICOM File or Folder", padding=10)
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        path_frame = tk.Frame(file_frame)
        path_frame.pack(fill=tk.X)
        
        tk.Label(path_frame, text="Path:").pack(side=tk.LEFT, padx=(0, 5))
        path_entry = tk.Entry(path_frame, textvariable=self.path_var, width=50)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        browse_file_btn = tk.Button(path_frame, text="Browse File...", command=self.browse_file)
        browse_file_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        browse_folder_btn = tk.Button(path_frame, text="Browse Folder...", command=self.browse_folder)
        browse_folder_btn.pack(side=tk.LEFT)
        
        # Tag values section
        tags_frame = ttk.LabelFrame(self.root, text="Tag Values", padding=10)
        tags_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Scrollable frame for tags
        self.tags_canvas = tk.Canvas(tags_frame)
        scrollbar = ttk.Scrollbar(tags_frame, orient="vertical", command=self.tags_canvas.yview)
        self.scrollable_frame = tk.Frame(self.tags_canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.tags_canvas.configure(scrollregion=self.tags_canvas.bbox("all"))
        )
        
        self.tags_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.tags_canvas.configure(yscrollcommand=scrollbar.set)
        
        # Default tags
        self.tag_widgets = {}
        for tag_key, tag_info in self.default_tags.items():
            self.create_tag_row(self.scrollable_frame, tag_key, tag_info['title'], tag_info['hex'], tag_info['value'], is_default=True)
        
        self.tags_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add tag button
        add_tag_btn = tk.Button(tags_frame, text="Add tag", command=self.add_custom_tag)
        add_tag_btn.pack(pady=5)
        
        # Note
        note_label = tk.Label(tags_frame, text="Note: StudyInstanceUID, AccessionNumber, and SeriesInstanceUID will be automatically generated with unique timestamp-based values.", 
                             font=("Arial", 9), fg="gray")
        note_label.pack(pady=5)
        
        # Action buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        process_btn = tk.Button(button_frame, text="Process DICOM Files", command=self.process_files, 
                               bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), width=20)
        process_btn.pack(side=tk.LEFT, padx=5)
        
        reset_btn = tk.Button(button_frame, text="Reset to Defaults", command=self.reset_defaults, width=20)
        reset_btn.pack(side=tk.LEFT, padx=5)
        
        # Status
        status_label = tk.Label(self.root, textvariable=self.status_var, font=("Arial", 10))
        status_label.pack(pady=5)
        
        # Output area
        output_frame = ttk.LabelFrame(self.root, text="Output", padding=10)
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.output_text = scrolledtext.ScrolledText(output_frame, height=10, width=80)
        self.output_text.pack(fill=tk.BOTH, expand=True)
    
    def create_tag_row(self, parent, tag_key, tag_title, hex_value, tag_value, is_default=False):
        """Create a row for a tag with title, hex, and value fields."""
        row_frame = tk.Frame(parent)
        row_frame.pack(fill=tk.X, pady=2)
        
        # Tag title and hex label
        label_text = f"{tag_title} {hex_value}:"
        label = tk.Label(row_frame, text=label_text, width=35, anchor="w")
        label.pack(side=tk.LEFT, padx=(0, 5))
        
        # Value entry
        value_var = tk.StringVar(value=tag_value)
        value_entry = tk.Entry(row_frame, textvariable=value_var, width=40)
        value_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Remove button for custom tags
        if not is_default:
            remove_btn = tk.Button(row_frame, text="Remove", command=lambda: self.remove_tag(tag_key), 
                                   bg="#f44336", fg="white", width=8)
            remove_btn.pack(side=tk.LEFT)
        
        # Store widget references
        self.tag_widgets[tag_key] = {
            'frame': row_frame,
            'title': tag_title,
            'hex': hex_value,
            'value_var': value_var,
            'is_default': is_default,
            'keyword': None  # Will be set for custom tags
        }
    
    def add_custom_tag(self):
        """Add a new custom tag row."""
        # Generate unique key for custom tag
        custom_index = len(self.custom_tags) + 1
        tag_key = f"CustomTag_{custom_index}"
        
        # Create dialog to get tag info
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Tag")
        dialog.geometry("500x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Tag selection dropdown
        tk.Label(dialog, text="Select DICOM Tag:").pack(pady=5)
        
        # Create combobox with searchable dropdown
        tag_var = tk.StringVar()
        tag_combo = ttk.Combobox(dialog, textvariable=tag_var, width=50, state="normal")
        tag_combo['values'] = self.available_tags
        tag_combo.pack(pady=5)
        
        # Enable search/filter functionality
        def filter_tags(event=None):
            value = tag_var.get().lower()
            if value:
                filtered = [tag for tag in self.available_tags if value in tag.lower()]
                tag_combo['values'] = filtered[:100]  # Limit to 100 results for performance
            else:
                tag_combo['values'] = self.available_tags[:100]
            tag_combo.event_generate('<Down>')
        
        tag_combo.bind('<KeyRelease>', filter_tags)
        
        # Hex value display (read-only, auto-populated)
        hex_var = tk.StringVar()
        hex_label_frame = tk.Frame(dialog)
        hex_label_frame.pack(pady=5)
        tk.Label(hex_label_frame, text="Hex Value:").pack(side=tk.LEFT, padx=5)
        hex_display = tk.Entry(hex_label_frame, textvariable=hex_var, width=20, state="readonly")
        hex_display.pack(side=tk.LEFT)
        
        # Update hex value when tag is selected
        def update_hex_value(event=None):
            selected_tag = tag_var.get()
            if selected_tag:
                try:
                    tag_tuple = datadict.tag_for_keyword(selected_tag)
                    if tag_tuple:
                        group, element = tag_tuple
                        hex_val = f"({group:04X},{element:04X})"
                        hex_var.set(hex_val)
                    else:
                        hex_var.set("")
                except Exception:
                    hex_var.set("")
        
        tag_combo.bind('<<ComboboxSelected>>', update_hex_value)
        tag_combo.bind('<Return>', update_hex_value)
        
        # Tag value entry
        tk.Label(dialog, text="Tag Value:").pack(pady=5)
        value_entry = tk.Entry(dialog, width=50)
        value_entry.pack(pady=5)
        value_entry.focus_set()
        
        def add_tag():
            selected_tag = tag_var.get().strip()
            hex_val = hex_var.get().strip()
            value = value_entry.get().strip()
            
            if not selected_tag:
                messagebox.showwarning("Warning", "Please select a DICOM tag.")
                return
            
            if not value:
                messagebox.showwarning("Warning", "Please enter a tag value.")
                return
            
            # Get display name for the tag
            try:
                tag_tuple = datadict.tag_for_keyword(selected_tag)
                if tag_tuple:
                    group, element = tag_tuple
                    if not hex_val:
                        hex_val = f"({group:04X},{element:04X})"
                    # Format display name nicely
                    display_name = selected_tag.replace('_', ' ').title()
                else:
                    display_name = selected_tag
                    if not hex_val:
                        messagebox.showerror("Error", f"Could not find hex value for tag: {selected_tag}")
                        return
            except Exception as e:
                display_name = selected_tag
                if not hex_val:
                    messagebox.showerror("Error", f"Error processing tag: {e}")
                    return
            
            # Create the tag row
            self.create_tag_row(self.scrollable_frame, tag_key, display_name, hex_val, value, is_default=False)
            # Store the actual keyword for processing
            self.tag_widgets[tag_key]['keyword'] = selected_tag
            self.custom_tags.append(tag_key)
            
            # Update canvas scroll region
            self.tags_canvas.update_idletasks()
            self.tags_canvas.configure(scrollregion=self.tags_canvas.bbox("all"))
            dialog.destroy()
        
        # Button frame
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)
        
        add_btn = tk.Button(button_frame, text="Add", command=add_tag, bg="#4CAF50", fg="white", width=10)
        add_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(button_frame, text="Cancel", command=dialog.destroy, width=10)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key to add button
        dialog.bind('<Return>', lambda e: add_tag())
    
    def remove_tag(self, tag_key):
        """Remove a custom tag."""
        if tag_key in self.tag_widgets:
            widget_info = self.tag_widgets[tag_key]
            widget_info['frame'].destroy()
            del self.tag_widgets[tag_key]
            if tag_key in self.custom_tags:
                self.custom_tags.remove(tag_key)
            # Update canvas scroll region
            self.tags_canvas.update_idletasks()
            self.tags_canvas.configure(scrollregion=self.tags_canvas.bbox("all"))
    
    def browse_file(self):
        """Browse for a DICOM file."""
        filename = filedialog.askopenfilename(
            title="Select DICOM File",
            filetypes=[("DICOM files", "*.dcm"), ("All files", "*.*")]
        )
        if filename:
            self.path_var.set(filename)
    
    def browse_folder(self):
        """Browse for a folder containing DICOM files."""
        folder = filedialog.askdirectory(title="Select Folder with DICOM Files")
        if folder:
            self.path_var.set(folder)
    
    def reset_defaults(self):
        """Reset all tags to default values."""
        for tag_key, tag_info in self.default_tags.items():
            if tag_key in self.tag_widgets:
                self.tag_widgets[tag_key]['value_var'].set(tag_info['value'])
        
        # Remove all custom tags
        for tag_key in list(self.custom_tags):
            self.remove_tag(tag_key)
        self.custom_tags.clear()
        
        self.status_var.set("Reset to defaults")
        self.log_output("Reset all tags to default values.\n")
    
    def log_output(self, message):
        """Add message to output text area."""
        self.output_text.insert(tk.END, message)
        self.output_text.see(tk.END)
        self.root.update_idletasks()
    
    def process_files(self):
        """Process DICOM files with the specified tags."""
        path = self.path_var.get().strip()
        
        if not path:
            messagebox.showerror("Error", "Please select a DICOM file or folder.")
            return
        
        if not os.path.exists(path):
            messagebox.showerror("Error", f"Path does not exist: {path}")
            return
        
        # Collect all tag values
        custom_tags = {}
        
        # Add default tags (use keyword format)
        for tag_key, widget_info in self.tag_widgets.items():
            if widget_info['is_default']:
                # Use the tag keyword (PatientID, PatientName, etc.)
                tag_keyword = tag_key
                value = widget_info['value_var'].get().strip()
                
                if value:
                    # Determine VR based on tag type
                    vr = None
                    if tag_keyword == 'PatientName' or tag_keyword == 'ReferringPhysicianName':
                        vr = 'PN'
                    elif tag_keyword == 'PatientBirthDate':
                        vr = 'DA'
                    elif tag_keyword == 'PatientID' or tag_keyword == 'InstitutionName':
                        vr = 'LO'
                    
                    custom_tags[tag_keyword] = {'value': value, 'vr': vr}
        
        # Add custom tags (use keyword if available, otherwise hex format)
        for tag_key in self.custom_tags:
            if tag_key in self.tag_widgets:
                widget_info = self.tag_widgets[tag_key]
                value = widget_info['value_var'].get().strip()
                
                if value:
                    # Prefer keyword if available (from dropdown selection)
                    if widget_info.get('keyword'):
                        tag_identifier = widget_info['keyword']
                        # Determine VR based on tag type
                        vr = None
                        try:
                            tag_tuple = datadict.tag_for_keyword(tag_identifier)
                            if tag_tuple:
                                vr = datadict.dictionary_VR(tag_tuple)
                        except Exception:
                            pass
                        custom_tags[tag_identifier] = {'value': value, 'vr': vr}
                    else:
                        # Fallback to hex format
                        hex_val = widget_info['hex']
                        # Parse hex value to 8-char format
                        hex_clean = hex_val.strip('()').replace(',', '').replace(' ', '')
                        if len(hex_clean) == 8 and all(c in '0123456789ABCDEFabcdef' for c in hex_clean):
                            # Use hex format as tag identifier
                            custom_tags[hex_clean] = {'value': value, 'vr': None}
                        else:
                            # Try to use hex format with parentheses
                            if hex_val.startswith('(') and hex_val.endswith(')'):
                                custom_tags[hex_val] = {'value': value, 'vr': None}
                            else:
                                # Fallback: try as keyword
                                custom_tags[hex_val] = {'value': value, 'vr': None}
        
        # Clear output
        self.output_text.delete(1.0, tk.END)
        self.status_var.set("Processing...")
        
        # Redirect stdout to capture output
        import io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        try:
            # Process the folder/file
            if os.path.isfile(path):
                # Single file - process just this file
                try:
                    # Process single file
                    success, message, original_values, new_values = update_dicom_file(
                        path,
                        dry_run=False,
                        verbose=True,
                        custom_tags=custom_tags,
                        use_default_test_tags=False,
                        generate_unique_ids=True
                    )
                    
                    # Create stats dict for single file
                    stats = {
                        'total': 1,
                        'success': 1 if success else 0,
                        'failed': 0 if success else 1,
                        'verification_failed': 0
                    }
                    
                    if not success:
                        self.log_output(f"Error: {message}\n")
                    else:
                        # Verify changes
                        verify_success, verify_message = verify_changes(
                            path,
                            original_values,
                            new_values
                        )
                        if not verify_success:
                            stats['verification_failed'] = 1
                            self.log_output(f"Verification failed: {verify_message}\n")
                except InvalidDicomError:
                    messagebox.showerror("Error", "Selected file is not a valid DICOM file.")
                    self.status_var.set("Error: Not a DICOM file")
                    sys.stdout = old_stdout
                    return
            else:
                folder_path = path
                stats = process_folder(
                    folder_path,
                    dry_run=False,
                    verbose=True,
                    custom_tags=custom_tags,
                    use_default_test_tags=False,  # We're using custom tags from GUI
                    generate_unique_ids=True
                )
            
            # Get captured output
            output = sys.stdout.getvalue()
            self.log_output(output)
            
            # Show summary
            summary = f"\n{'='*60}\nSUMMARY\n{'='*60}\n"
            summary += f"Total files processed: {stats['total']}\n"
            summary += f"Successfully updated: {stats['success']}\n"
            summary += f"Failed: {stats['failed']}\n"
            if stats.get('verification_failed', 0) > 0:
                summary += f"Verification failed: {stats['verification_failed']}\n"
            summary += f"{'='*60}\n"
            
            self.log_output(summary)
            
            if stats['failed'] == 0 and stats.get('verification_failed', 0) == 0:
                self.status_var.set("Processing completed successfully")
                messagebox.showinfo("Success", f"Successfully processed {stats['success']} file(s).")
            else:
                self.status_var.set("Processing completed with errors")
                messagebox.showwarning("Warning", f"Processed with {stats['failed']} failure(s).")
        
        except Exception as e:
            error_msg = f"Error processing files: {str(e)}\n"
            self.log_output(error_msg)
            self.status_var.set("Error occurred")
            messagebox.showerror("Error", f"Error processing files: {str(e)}")
        
        finally:
            # Restore stdout
            sys.stdout = old_stdout


def main():
    """Main entry point for the script."""
    # Check if running with GUI (no command-line arguments beyond script name)
    # When run as executable or with no args, launch GUI
    if len(sys.argv) == 1:
        # No arguments - launch GUI
        try:
            root = tk.Tk()
            app = DICOMTagUpdaterGUI(root)
            root.mainloop()
            return
        except Exception as e:
            # If GUI fails, show error and exit
            print(f"Error launching GUI: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Otherwise, use command-line interface
    parser = argparse.ArgumentParser(
        description='Update DICOM tags in all files within a specified folder.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update specific tags via command-line
  %(prog)s folder --tag PatientID=TEST123 --tag PatientName="TEST^PATIENT"
  
  # Update tags from JSON file
  %(prog)s folder --tags-file tags.json
  
  # Use default test tag updates (backward compatible)
  %(prog)s folder
  
  # Specify hex tag format
  %(prog)s folder --tag "(0010,0020)=TEST123"
  
  # Specify VR for new tags
  %(prog)s folder --tag "PatientID:LO=TEST123"
  
  # Disable default test tags and only use custom tags
  %(prog)s folder --tag PatientID=TEST123 --no-default-tags
  
  # Disable unique ID generation
  %(prog)s folder --tag PatientID=TEST123 --no-unique-ids
        """
    )
    
    parser.add_argument(
        'folder',
        type=str,
        help='Path to folder containing DICOM files'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )
    
    parser.add_argument(
        '--tag',
        action='append',
        dest='tags',
        metavar='TAG_SPEC',
        help='Tag to update in format TAG=VALUE or TAG:VR=VALUE. Can be specified multiple times. '
             'Supports standard keywords (e.g., PatientID), hex format (e.g., "(0010,0020)"), '
             'or 8-char hex string (e.g., "00100020").'
    )
    
    parser.add_argument(
        '--tags-file',
        type=str,
        metavar='JSON_FILE',
        help='JSON file containing tag updates. Format: {"TagID": "value"} or '
             '{"TagID": {"value": "value", "vr": "LO"}}'
    )
    
    parser.add_argument(
        '--no-default-tags',
        action='store_true',
        help='Disable default test tag updates (PatientID, PatientName, etc.)'
    )
    
    parser.add_argument(
        '--no-unique-ids',
        action='store_true',
        help='Disable automatic generation of unique IDs for StudyInstanceUID, '
             'AccessionNumber, and SeriesInstanceUID'
    )
    
    args = parser.parse_args()
    
    # Parse custom tags
    custom_tags = None
    
    if args.tags_file:
        try:
            custom_tags = load_tags_from_json(args.tags_file)
            if args.verbose:
                print(f"Loaded {len(custom_tags)} tags from {args.tags_file}")
        except Exception as e:
            print(f"Error loading tags file: {e}", file=sys.stderr)
            sys.exit(1)
    
    if args.tags:
        if custom_tags is None:
            custom_tags = {}
        
        for tag_spec in args.tags:
            try:
                tag_id, value, vr = parse_tag_specification(tag_spec)
                custom_tags[tag_id] = {'value': value, 'vr': vr}
            except Exception as e:
                print(f"Error parsing tag specification '{tag_spec}': {e}", file=sys.stderr)
                sys.exit(1)
    
    # Process the folder
    stats = process_folder(
        args.folder,
        dry_run=args.dry_run,
        verbose=args.verbose,
        custom_tags=custom_tags,
        use_default_test_tags=not args.no_default_tags,
        generate_unique_ids=not args.no_unique_ids
    )
    
    # Print summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total files processed: {stats['total']}")
    print(f"Successfully updated: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    if not args.dry_run:
        print(f"Verification failed: {stats['verification_failed']}")
    print("=" * 60)
    
    # Exit with appropriate code
    if stats['failed'] > 0 or stats['verification_failed'] > 0:
        sys.exit(1)
    elif stats['total'] == 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
