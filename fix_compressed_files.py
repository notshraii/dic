"""
Decompresses JPEG-compressed DICOM files to uncompressed format for compatibility.
"""

import argparse
import sys
from pathlib import Path

import pydicom
from pydicom.uid import ImplicitVRLittleEndian


# Uncompressed transfer syntax UIDs
UNCOMPRESSED_SYNTAXES = [
    '1.2.840.10008.1.2',      # Implicit VR Little Endian
    '1.2.840.10008.1.2.1',    # Explicit VR Little Endian
    '1.2.840.10008.1.2.2',    # Explicit VR Big Endian
]

# Known compressed transfer syntaxes
COMPRESSED_SYNTAXES = {
    '1.2.840.10008.1.2.4.50': 'JPEG Baseline (Process 1)',
    '1.2.840.10008.1.2.4.51': 'JPEG Extended (Process 2 & 4)',
    '1.2.840.10008.1.2.4.57': 'JPEG Lossless, Non-Hierarchical (Process 14)',
    '1.2.840.10008.1.2.4.70': 'JPEG Lossless, Non-Hierarchical, First-Order Prediction',
    '1.2.840.10008.1.2.4.80': 'JPEG-LS Lossless',
    '1.2.840.10008.1.2.4.81': 'JPEG-LS Lossy',
    '1.2.840.10008.1.2.4.90': 'JPEG 2000 Lossless',
    '1.2.840.10008.1.2.4.91': 'JPEG 2000',
    '1.2.840.10008.1.2.5': 'RLE Lossless',
}


def get_transfer_syntax_name(uid: str) -> str:
    """Get human-readable name for transfer syntax UID."""
    if uid in UNCOMPRESSED_SYNTAXES:
        names = {
            '1.2.840.10008.1.2': 'Implicit VR Little Endian (uncompressed)',
            '1.2.840.10008.1.2.1': 'Explicit VR Little Endian (uncompressed)',
            '1.2.840.10008.1.2.2': 'Explicit VR Big Endian (uncompressed)',
        }
        return names.get(uid, f'Uncompressed ({uid})')
    elif uid in COMPRESSED_SYNTAXES:
        return COMPRESSED_SYNTAXES[uid]
    else:
        return f'Unknown ({uid})'


def decompress_dicom_file(input_path: Path, output_path: Path = None, backup: bool = True) -> bool:
    """
    Decompress a DICOM file to Implicit VR Little Endian (uncompressed).
    
    Args:
        input_path: Path to compressed DICOM file
        output_path: Path to save decompressed file (defaults to overwriting input)
        backup: If True, create .bak backup before overwriting
    
    Returns:
        True if file was decompressed, False if already uncompressed or error
    """
    if output_path is None:
        output_path = input_path
    
    try:
        # Read the file
        ds = pydicom.dcmread(input_path)
        
        # Check if it has transfer syntax info
        if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
            print(f"  {input_path.name}: No transfer syntax info, skipping")
            return False
        
        transfer_syntax = ds.file_meta.TransferSyntaxUID
        
        # Check if already uncompressed
        if transfer_syntax in UNCOMPRESSED_SYNTAXES:
            print(f"  {input_path.name}: Already uncompressed - {get_transfer_syntax_name(transfer_syntax)}")
            return False
        
        print(f"  {input_path.name}: Found compressed format")
        print(f"    Current: {get_transfer_syntax_name(transfer_syntax)}")
        
        # Create backup if requested and overwriting
        if backup and output_path == input_path:
            backup_path = input_path.with_suffix('.dcm.bak')
            if not backup_path.exists():
                import shutil
                shutil.copy2(input_path, backup_path)
                print(f"    Backup: {backup_path.name}")
        
        # Decompress pixel data
        print(f"    Decompressing pixel data...")
        ds.decompress()
        
        # Set uncompressed transfer syntax
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        
        # Save
        ds.save_as(output_path, write_like_original=False)
        print(f"    Saved as: {get_transfer_syntax_name(ImplicitVRLittleEndian)}")
        
        return True
        
    except Exception as e:
        print(f"  ERROR processing {input_path.name}: {e}")
        return False


def scan_directory(directory: Path, fix: bool = False, backup: bool = True):
    """
    Scan directory for compressed DICOM files.
    
    Args:
        directory: Directory to scan
        fix: If True, decompress compressed files
        backup: If True, create backups before modifying files
    """
    print(f"\nScanning directory: {directory.absolute()}")
    print(f"{'='*70}\n")
    
    dcm_files = list(directory.glob("*.dcm"))
    
    if not dcm_files:
        print(f"No DICOM files found in {directory}")
        return
    
    print(f"Found {len(dcm_files)} DICOM files\n")
    
    compressed_files = []
    uncompressed_files = []
    error_files = []
    decompressed_files = []
    
    for dcm_file in sorted(dcm_files):
        try:
            ds = pydicom.dcmread(dcm_file)
            
            if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
                error_files.append((dcm_file.name, "No transfer syntax info"))
                continue
            
            transfer_syntax = ds.file_meta.TransferSyntaxUID
            
            if transfer_syntax in UNCOMPRESSED_SYNTAXES:
                uncompressed_files.append((dcm_file.name, transfer_syntax))
            else:
                compressed_files.append((dcm_file.name, transfer_syntax))
                
                if fix:
                    if decompress_dicom_file(dcm_file, backup=backup):
                        decompressed_files.append(dcm_file.name)
        
        except Exception as e:
            error_files.append((dcm_file.name, str(e)))
    
    # Print summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}\n")
    
    print(f"Total files scanned: {len(dcm_files)}")
    print(f"Already uncompressed: {len(uncompressed_files)}")
    print(f"Compressed files found: {len(compressed_files)}")
    
    if fix:
        print(f"Successfully decompressed: {len(decompressed_files)}")
        print(f"Failed/Skipped: {len(compressed_files) - len(decompressed_files)}")
    
    if error_files:
        print(f"Errors: {len(error_files)}")
    
    if compressed_files and not fix:
        print(f"\n{'='*70}")
        print("COMPRESSED FILES FOUND:")
        print(f"{'='*70}")
        for filename, ts in compressed_files:
            print(f"  - {filename}")
            print(f"    Transfer Syntax: {get_transfer_syntax_name(ts)}")
        print(f"\nRun with --fix flag to decompress these files.")
    
    if fix and decompressed_files:
        print(f"\n{'='*70}")
        print("FILES SUCCESSFULLY DECOMPRESSED:")
        print(f"{'='*70}")
        for filename in decompressed_files:
            print(f"  {filename}")
    
    if error_files:
        print(f"\n{'='*70}")
        print("ERRORS:")
        print(f"{'='*70}")
        for filename, error in error_files:
            print(f"  ! {filename}: {error}")


def main():
    parser = argparse.ArgumentParser(
        description='Scan and fix compressed DICOM files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan for compressed files (no changes)
  python fix_compressed_files.py
  
  # Decompress all compressed files
  python fix_compressed_files.py --fix
  
  # Decompress without creating backups
  python fix_compressed_files.py --fix --no-backup
  
  # Specify different directory
  python fix_compressed_files.py --directory /path/to/dicom/files --fix
        """
    )
    
    parser.add_argument(
        '--directory', '-d',
        type=Path,
        default=Path('dicom_samples'),
        help='Directory containing DICOM files (default: dicom_samples)'
    )
    
    parser.add_argument(
        '--fix', '-f',
        action='store_true',
        help='Fix compressed files by decompressing them'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not create .bak backup files'
    )
    
    args = parser.parse_args()
    
    if not args.directory.exists():
        print(f"ERROR: Directory does not exist: {args.directory}")
        sys.exit(1)
    
    if not args.directory.is_dir():
        print(f"ERROR: Not a directory: {args.directory}")
        sys.exit(1)
    
    scan_directory(args.directory, fix=args.fix, backup=not args.no_backup)
    
    print()


if __name__ == "__main__":
    main()

