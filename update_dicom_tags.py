#!/usr/bin/env python3
"""
Standalone script to update DICOM tags in all files within a specified folder.

This script processes DICOM files and updates critical tags with unique timestamp-based
values, including StudyInstanceUID, AccessionNumber, and SeriesInstanceUID. It also
updates other test tags as specified and verifies all changes are valid.

Usage:
    python update_dicom_tags.py <folder_path> [--verbose] [--dry-run]
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


def get_original_values(ds) -> Dict[str, Optional[str]]:
    """
    Extract original values from DICOM dataset.
    
    Args:
        ds: pydicom Dataset object
        
    Returns:
        Dictionary with original values for StudyInstanceUID, AccessionNumber, SeriesInstanceUID
    """
    originals = {
        'StudyInstanceUID': None,
        'AccessionNumber': None,
        'SeriesInstanceUID': None
    }
    
    try:
        if hasattr(ds, 'StudyInstanceUID'):
            originals['StudyInstanceUID'] = str(ds.StudyInstanceUID)
    except (AttributeError, KeyError):
        pass
    
    try:
        if hasattr(ds, 'AccessionNumber'):
            originals['AccessionNumber'] = str(ds.AccessionNumber)
    except (AttributeError, KeyError):
        pass
    
    try:
        if hasattr(ds, 'SeriesInstanceUID'):
            originals['SeriesInstanceUID'] = str(ds.SeriesInstanceUID)
    except (AttributeError, KeyError):
        pass
    
    return originals


def update_dicom_file(
    file_path: str,
    dry_run: bool = False,
    verbose: bool = False
) -> Tuple[bool, str, Dict[str, Optional[str]], Dict[str, Optional[str]]]:
    """
    Update DICOM tags in a single file.
    
    Args:
        file_path: Path to DICOM file
        dry_run: If True, don't actually modify the file
        verbose: If True, print detailed information
        
    Returns:
        Tuple of (success, message, original_values, new_values)
    """
    try:
        # Read DICOM file
        print("  Step 0: Reading DICOM file...")
        ds = dcmread(file_path)
        print("    File read successfully")
        
        # Get original values (stored but not displayed for security)
        original_values = get_original_values(ds)
        
        # Generate unique values
        print("  Step 1: Generating unique timestamp-based values...")
        new_study_uid = generate_uid()
        new_accession_number = generate_accession_number()
        new_series_uid = generate_uid()
        
        new_values = {
            'StudyInstanceUID': new_study_uid,
            'AccessionNumber': new_accession_number,
            'SeriesInstanceUID': new_series_uid
        }
        
        # Log new values (security: only show new values, not originals)
        print("  Step 2: Updating tags with new values:")
        print(f"    StudyInstanceUID: {new_study_uid}")
        print(f"    AccessionNumber: {new_accession_number}")
        print(f"    SeriesInstanceUID: {new_series_uid}")
        
        if verbose:
            print(f"  Original StudyInstanceUID: {original_values['StudyInstanceUID']}")
            print(f"  Original AccessionNumber: {original_values['AccessionNumber']}")
            print(f"  Original SeriesInstanceUID: {original_values['SeriesInstanceUID']}")
        
        if not dry_run:
            # Update unique tags
            print("  Step 3: Updating unique identifier tags...")
            update_tags_ds(ds, "StudyInstanceUID", new_study_uid)
            update_tags_ds(ds, "AccessionNumber", new_accession_number)
            update_tags_ds(ds, "SeriesInstanceUID", new_series_uid)
            print("    Unique identifier tags updated")
            
            # Update other test tags using direct hex tag assignment
            print("  Step 4: Updating test data tags (using hex tag values)...")
            
            # PatientID - (0010,0020) LO (Long String)
            old_patient_id = None
            if (0x0010, 0x0020) in ds:
                old_patient_id = str(ds[0x0010, 0x0020].value)
            if (0x0010, 0x0020) not in ds:
                ds.add_new((0x0010, 0x0020), 'LO', "11043207")
            else:
                ds[0x0010, 0x0020].value = "11043207"
            print(f"    PatientID (0010,0020) updated: {old_patient_id} to 11043207")
            
            # PatientName - (0010,0010) PN (Person Name)
            old_patient_name = None
            if (0x0010, 0x0010) in ds:
                old_patient_name = str(ds[0x0010, 0x0010].value)
            if (0x0010, 0x0010) not in ds:
                ds.add_new((0x0010, 0x0010), 'PN', "ZZTESTPATIENT^MIDIA THREE")
            else:
                ds[0x0010, 0x0010].value = "ZZTESTPATIENT^MIDIA THREE"
            print(f"    PatientName (0010,0010) updated: {old_patient_name} to ZZTESTPATIENT^MIDIA THREE")
            
            # PatientBirthDate - (0010,0030) DA (Date)
            old_birth_date = None
            if (0x0010, 0x0030) in ds:
                old_birth_date = str(ds[0x0010, 0x0030].value)
            if (0x0010, 0x0030) not in ds:
                ds.add_new((0x0010, 0x0030), 'DA', "19010101")
            else:
                ds[0x0010, 0x0030].value = "19010101"
            print(f"    PatientBirthDate (0010,0030) updated: {old_birth_date} to 19010101")
            
            # InstitutionName - (0008,0080) LO (Long String)
            old_institution = None
            if (0x0008, 0x0080) in ds:
                old_institution = str(ds[0x0008, 0x0080].value)
            if (0x0008, 0x0080) not in ds:
                ds.add_new((0x0008, 0x0080), 'LO', "TEST FACILITY")
            else:
                ds[0x0008, 0x0080].value = "TEST FACILITY"
            print(f"    InstitutionName (0008,0080) updated: {old_institution} to TEST FACILITY")
            
            # ReferringPhysicianName - Try (0008,0090) first, fallback to (0808,0090)
            old_referring_physician = None
            referring_physician_set = False
            
            # Try standard tag (0008,0090) first
            try:
                if (0x0008, 0x0090) in ds:
                    old_referring_physician = str(ds[0x0008, 0x0090].value)
                    ds[0x0008, 0x0090].value = "TEST PROVIDER"
                    referring_physician_set = True
                    print(f"    ReferringPhysicianName (0008,0090) updated: {old_referring_physician} to TEST PROVIDER")
                else:
                    ds.add_new((0x0008, 0x0090), 'PN', "TEST PROVIDER")
                    referring_physician_set = True
                    print("    ReferringPhysicianName (0008,0090) added: TEST PROVIDER")
            except Exception as e:
                print(f"    Warning: Could not set ReferringPhysicianName (0008,0090): {e}")
            
            # Fallback to private tag (0808,0090) if standard tag failed
            if not referring_physician_set:
                try:
                    if (0x0808, 0x0090) in ds:
                        old_referring_physician = str(ds[0x0808, 0x0090].value)
                        ds[0x0808, 0x0090].value = "TEST PROVIDER"
                        referring_physician_set = True
                        print(f"    ReferringPhysicianName (0808,0090) updated: {old_referring_physician} to TEST PROVIDER")
                    else:
                        ds.add_new((0x0808, 0x0090), 'PN', "TEST PROVIDER")
                        referring_physician_set = True
                        print("    ReferringPhysicianName (0808,0090) added: TEST PROVIDER")
                except Exception as e:
                    print(f"    Warning: Could not set ReferringPhysicianName (0808,0090): {e}")
            
            # Save the file
            print("  Step 5: Saving updated DICOM file...")
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
    new_values: Dict[str, Optional[str]]
) -> Tuple[bool, str]:
    """
    Verify that the changes were applied correctly and values are valid.
    
    Args:
        file_path: Path to DICOM file
        original_values: Dictionary of original values
        new_values: Dictionary of new values
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Re-read the file
        ds = dcmread(file_path)
        
        verification_errors = []
        
        # Verify StudyInstanceUID
        print("    Verifying StudyInstanceUID...")
        if hasattr(ds, 'StudyInstanceUID'):
            current_uid = str(ds.StudyInstanceUID)
            if current_uid == original_values.get('StudyInstanceUID'):
                verification_errors.append("StudyInstanceUID did not change")
            elif not is_valid_uid(current_uid):
                verification_errors.append(f"StudyInstanceUID is not valid: {current_uid}")
            elif current_uid != new_values.get('StudyInstanceUID'):
                verification_errors.append(f"StudyInstanceUID mismatch: expected {new_values.get('StudyInstanceUID')}, got {current_uid}")
            else:
                print("      StudyInstanceUID verified")
        else:
            verification_errors.append("StudyInstanceUID tag missing after update")
        
        # Verify AccessionNumber
        print("    Verifying AccessionNumber...")
        if hasattr(ds, 'AccessionNumber'):
            current_acc = str(ds.AccessionNumber)
            if current_acc == original_values.get('AccessionNumber'):
                verification_errors.append("AccessionNumber did not change")
            elif current_acc != new_values.get('AccessionNumber'):
                verification_errors.append(f"AccessionNumber mismatch: expected {new_values.get('AccessionNumber')}, got {current_acc}")
            else:
                print(f"      AccessionNumber verified: {current_acc}")
        else:
            verification_errors.append("AccessionNumber tag missing after update")
        
        # Verify SeriesInstanceUID
        print("    Verifying SeriesInstanceUID...")
        if hasattr(ds, 'SeriesInstanceUID'):
            current_series_uid = str(ds.SeriesInstanceUID)
            if current_series_uid == original_values.get('SeriesInstanceUID'):
                verification_errors.append("SeriesInstanceUID did not change")
            elif not is_valid_uid(current_series_uid):
                verification_errors.append(f"SeriesInstanceUID is not valid: {current_series_uid}")
            elif current_series_uid != new_values.get('SeriesInstanceUID'):
                verification_errors.append(f"SeriesInstanceUID mismatch: expected {new_values.get('SeriesInstanceUID')}, got {current_series_uid}")
            else:
                print("      SeriesInstanceUID verified")
        else:
            verification_errors.append("SeriesInstanceUID tag missing after update")
        
        # Verify other test tags using hex tag values directly
        print("    Verifying test data tags (using hex tag values)...")
        
        # PatientID - (0010,0020)
        if (0x0010, 0x0020) in ds:
            current_value = str(ds[0x0010, 0x0020].value)
            if current_value != '11043207':
                verification_errors.append(f"PatientID (0010,0020) mismatch: expected '11043207', got '{current_value}'")
            else:
                print(f"      PatientID (0010,0020) verified: {current_value}")
        else:
            verification_errors.append("PatientID (0010,0020) tag missing after update")
        
        # PatientName - (0010,0010)
        if (0x0010, 0x0010) in ds:
            current_value = str(ds[0x0010, 0x0010].value)
            if current_value != 'ZZTESTPATIENT^MIDIA THREE':
                verification_errors.append(f"PatientName (0010,0010) mismatch: expected 'ZZTESTPATIENT^MIDIA THREE', got '{current_value}'")
            else:
                print(f"      PatientName (0010,0010) verified: {current_value}")
        else:
            verification_errors.append("PatientName (0010,0010) tag missing after update")
        
        # PatientBirthDate - (0010,0030)
        if (0x0010, 0x0030) in ds:
            current_value = str(ds[0x0010, 0x0030].value)
            if current_value != '19010101':
                verification_errors.append(f"PatientBirthDate (0010,0030) mismatch: expected '19010101', got '{current_value}'")
            else:
                print(f"      PatientBirthDate (0010,0030) verified: {current_value}")
        else:
            verification_errors.append("PatientBirthDate (0010,0030) tag missing after update")
        
        # InstitutionName - (0008,0080)
        if (0x0008, 0x0080) in ds:
            current_value = str(ds[0x0008, 0x0080].value)
            if current_value != 'TEST FACILITY':
                verification_errors.append(f"InstitutionName (0008,0080) mismatch: expected 'TEST FACILITY', got '{current_value}'")
            else:
                print(f"      InstitutionName (0008,0080) verified: {current_value}")
        else:
            verification_errors.append("InstitutionName (0008,0080) tag missing after update")
        
        # ReferringPhysicianName - Try (0008,0090) first, then (0808,0090)
        referring_physician_verified = False
        if (0x0008, 0x0090) in ds:
            current_value = str(ds[0x0008, 0x0090].value)
            if current_value != 'TEST PROVIDER':
                verification_errors.append(f"ReferringPhysicianName (0008,0090) mismatch: expected 'TEST PROVIDER', got '{current_value}'")
            else:
                print(f"      ReferringPhysicianName (0008,0090) verified: {current_value}")
                referring_physician_verified = True
        elif (0x0808, 0x0090) in ds:
            current_value = str(ds[0x0808, 0x0090].value)
            if current_value != 'TEST PROVIDER':
                verification_errors.append(f"ReferringPhysicianName (0808,0090) mismatch: expected 'TEST PROVIDER', got '{current_value}'")
            else:
                print(f"      ReferringPhysicianName (0808,0090) verified: {current_value}")
                referring_physician_verified = True
        else:
            verification_errors.append("ReferringPhysicianName (0008,0090 or 0808,0090) tag missing after update")
        
        if verification_errors:
            return False, "; ".join(verification_errors)
        
        return True, "All verifications passed"
        
    except Exception as e:
        return False, f"Verification error: {e}"


def process_folder(
    folder_path: str,
    dry_run: bool = False,
    verbose: bool = False
) -> Dict[str, int]:
    """
    Process all DICOM files in a folder.
    
    Args:
        folder_path: Path to folder containing DICOM files
        dry_run: If True, don't actually modify files
        verbose: If True, print detailed information
        
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
            verbose=verbose
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
        
        self.setup_ui()
    
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
        tags_frame = ttk.LabelFrame(self.root, text="Tag Values (Editable)", padding=10)
        tags_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Default tags - create rows for each tag
        self.tag_widgets = {}
        for tag_key, tag_info in self.default_tags.items():
            self.create_tag_row(tags_frame, tag_key, tag_info['title'], tag_info['hex'], tag_info['value'])
        
        # Add tag button - positioned between Referring Physician Name and Note
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
    
    def create_tag_row(self, parent, tag_key, tag_title, hex_value, tag_value):
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
        value_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Store widget references
        self.tag_widgets[tag_key] = {
            'frame': row_frame,
            'title': tag_title,
            'hex': hex_value,
            'value_var': value_var
        }
    
    def add_custom_tag(self):
        """Add a new custom tag row."""
        # Generate unique key for custom tag
        custom_index = len(self.custom_tags) + 1
        tag_key = f"CustomTag_{custom_index}"
        
        # Create dialog to get tag info
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Tag")
        dialog.geometry("500x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Tag selection dropdown
        tk.Label(dialog, text="Select DICOM Tag:").pack(pady=5)
        
        # Create combobox with searchable dropdown
        tag_var = tk.StringVar()
        tag_combo = ttk.Combobox(dialog, textvariable=tag_var, width=50, state="normal")
        
        # Get available tags
        try:
            if hasattr(datadict, 'keyword_dict') and datadict.keyword_dict:
                available_tags = sorted([tag for tag in datadict.keyword_dict.keys() if tag and tag != '' and tag != 'Unknown'])
            else:
                available_tags = [
                    'AccessionNumber', 'AcquisitionDate', 'AcquisitionTime', 'BitsAllocated', 'BitsStored',
                    'BodyPartExamined', 'Columns', 'ContentDate', 'ContentTime', 'DeviceSerialNumber',
                    'HighBit', 'ImageType', 'InstitutionAddress', 'InstitutionName', 'InstitutionalDepartmentName',
                    'InstanceNumber', 'Manufacturer', 'ManufacturerModelName', 'Modality', 'NumberOfFrames',
                    'OperatorName', 'PatientAge', 'PatientBirthDate', 'PatientID', 'PatientName',
                    'PatientPosition', 'PatientSex', 'PatientSize', 'PatientWeight', 'PerformingPhysicianName',
                    'PhotometricInterpretation', 'PixelSpacing', 'ReferringPhysicianName', 'Rows',
                    'SamplesPerPixel', 'SeriesDate', 'SeriesDescription', 'SeriesInstanceUID', 'SeriesNumber',
                    'SeriesTime', 'SliceThickness', 'SoftwareVersions', 'SOPInstanceUID', 'StationName',
                    'StudyDate', 'StudyDescription', 'StudyID', 'StudyInstanceUID', 'StudyTime'
                ]
        except Exception:
            available_tags = ['PatientID', 'PatientName', 'StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID']
        
        tag_combo['values'] = available_tags[:500]  # Limit for performance
        tag_combo.pack(pady=5)
        
        # Tag value entry
        tk.Label(dialog, text="Tag Value:").pack(pady=5)
        value_entry = tk.Entry(dialog, width=50)
        value_entry.pack(pady=5)
        value_entry.focus_set()
        
        def add_tag():
            selected_tag = tag_var.get().strip()
            value = value_entry.get().strip()
            
            if not selected_tag:
                messagebox.showwarning("Warning", "Please select a DICOM tag.")
                return
            
            if not value:
                messagebox.showwarning("Warning", "Please enter a tag value.")
                return
            
            # Get hex value and display name for the tag
            hex_val = None
            display_name = selected_tag.replace('_', ' ').title()
            
            try:
                tag_tuple = datadict.tag_for_keyword(selected_tag)
                if tag_tuple and isinstance(tag_tuple, tuple) and len(tag_tuple) == 2:
                    group, element = tag_tuple
                    hex_val = f"({group:04X},{element:04X})"
                else:
                    # Tag not found in standard dictionary, use tag name as identifier
                    # Hex value will be None, we'll use the keyword directly
                    hex_val = None
            except (ValueError, TypeError, Exception):
                # If we can't get the hex value, that's okay - we'll use the keyword
                hex_val = None
            
            # If we couldn't determine hex value, use the tag keyword directly
            if not hex_val:
                hex_val = selected_tag
            
            # Find tags_frame to add the new tag
            tags_frame = None
            for widget in self.root.winfo_children():
                if isinstance(widget, ttk.LabelFrame) and widget.cget("text") == "Tag Values (Editable)":
                    tags_frame = widget
                    break
            
            if tags_frame:
                # Create the tag row before the "Add tag" button
                # We need to find the Add tag button and insert before it
                add_tag_btn = None
                for widget in tags_frame.winfo_children():
                    if isinstance(widget, tk.Button) and widget.cget("text") == "Add tag":
                        add_tag_btn = widget
                        break
                
                # Create new tag row
                row_frame = tk.Frame(tags_frame)
                
                # Insert before Add tag button if found
                if add_tag_btn:
                    row_frame.pack(fill=tk.X, pady=2, before=add_tag_btn)
                else:
                    row_frame.pack(fill=tk.X, pady=2)
                
                # Format label - include hex value if available, otherwise just tag name
                if hex_val and hex_val != selected_tag and hex_val.startswith('('):
                    label_text = f"{display_name} {hex_val}:"
                else:
                    label_text = f"{display_name}:"
                label = tk.Label(row_frame, text=label_text, width=35, anchor="w")
                label.pack(side=tk.LEFT, padx=(0, 5))
                
                value_var = tk.StringVar(value=value)
                value_entry_new = tk.Entry(row_frame, textvariable=value_var, width=40)
                value_entry_new.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
                
                # Remove button for custom tags
                remove_btn = tk.Button(row_frame, text="Remove", command=lambda: self.remove_tag(tag_key), 
                                     bg="#f44336", fg="white", width=8)
                remove_btn.pack(side=tk.LEFT)
                
                # Store widget references
                # Use hex_val if available, otherwise use selected_tag as identifier
                hex_display = hex_val if (hex_val and hex_val.startswith('(')) else selected_tag
                self.tag_widgets[tag_key] = {
                    'frame': row_frame,
                    'title': display_name,
                    'hex': hex_display,
                    'value_var': value_var,
                    'keyword': selected_tag
                }
                self.custom_tags.append(tag_key)
            
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
        
        # Clear output
        self.output_text.delete(1.0, tk.END)
        self.status_var.set("Processing...")
        
        # Redirect stdout to capture output
        import io
        old_stdout = sys.stdout
        output_buffer = io.StringIO()
        sys.stdout = output_buffer
        
        try:
            # Process the folder/file
            if os.path.isfile(path):
                # Single file - process just this file
                try:
                    # Log file being processed
                    self.log_output(f"Processing file: {os.path.basename(path)}\n")
                    self.log_output(f"Full path: {path}\n\n")
                    
                    success, message, original_values, new_values = update_dicom_file(
                        path,
                        dry_run=False,
                        verbose=True
                    )
                    
                    # Get captured output
                    output = output_buffer.getvalue()
                    if output:
                        self.log_output(output)
                    # Clear buffer for next operation
                    output_buffer.seek(0)
                    output_buffer.truncate(0)
                    
                    if not success:
                        self.log_output(f"ERROR: {message}\n")
                        self.status_var.set("Error occurred")
                        messagebox.showerror("Error", f"Error processing file: {message}")
                    else:
                        # Verify changes
                        verify_success, verify_message = verify_changes(
                            path,
                            original_values,
                            new_values
                        )
                        if not verify_success:
                            self.log_output(f"VERIFICATION FAILED: {verify_message}\n")
                            self.status_var.set("Verification failed")
                        else:
                            self.log_output("Verification passed: All tags updated correctly\n")
                            self.status_var.set("Processing completed successfully")
                            messagebox.showinfo("Success", "File processed successfully.")
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
                    verbose=True
                )
                
                # Get captured output
                output = output_buffer.getvalue()
                if output:
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
    # Check if running with GUI (no command-line arguments)
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
  python update_dicom_tags.py /path/to/dicom/folder
  python update_dicom_tags.py /path/to/dicom/folder --verbose
  python update_dicom_tags.py /path/to/dicom/folder --dry-run
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
    
    args = parser.parse_args()
    
    # Process the folder
    stats = process_folder(
        args.folder,
        dry_run=args.dry_run,
        verbose=args.verbose
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
