# compass_perf/data_loader.py

"""
DICOM file discovery and loading with automatic decompression for performance testing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List

import pydicom
from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian

logger = logging.getLogger(__name__)


def is_dicom_file(path: Path) -> bool:
    """Check if file is a valid DICOM file by verifying magic string."""
    try:
        with open(path, 'rb') as f:
            f.seek(128)
            magic = f.read(4)
            if magic != b'DICM':
                logger.debug(
                    "Not DICOM: %s (bytes 128-131: %r, file size: %d)",
                    path.name, magic, path.stat().st_size,
                )
                return False
            return True
    except (IOError, OSError) as exc:
        logger.warning("Cannot read %s: %s", path.name, exc)
        return False


def find_dicom_files(root: Path, recursive: bool = True) -> List[Path]:
    """Find DICOM files in directory by validating magic string."""
    if not root.exists():
        raise FileNotFoundError(f"DICOM root directory does not exist: {root}")

    pattern = "**/*" if recursive else "*"
    files: List[Path] = []
    skipped: List[str] = []
    for path in root.glob(pattern):
        if not path.is_file():
            continue

        if path.name.startswith("."):
            continue

        if not is_dicom_file(path):
            size_mb = path.stat().st_size / (1024 * 1024)
            skipped.append(f"{path.name} ({size_mb:.1f} MB)")
            continue

        files.append(path)

    if skipped:
        logger.info("Skipped %d non-DICOM file(s): %s", len(skipped), ", ".join(skipped))

    if not files:
        raise RuntimeError(f"No DICOM files found under: {root}")

    return sorted(files)


def load_dataset(path: Path):
    """Load DICOM dataset and automatically decompress if needed."""
    # Uncompressed transfer syntax UIDs
    UNCOMPRESSED_SYNTAXES = {
        '1.2.840.10008.1.2',      # Implicit VR Little Endian
        '1.2.840.10008.1.2.1',    # Explicit VR Little Endian
        '1.2.840.10008.1.2.2',    # Explicit VR Big Endian
    }
    
    # Load the dataset
    ds = pydicom.dcmread(path, force=True)
    
    # Ensure encoding consistency
    ds = ensure_encoding_consistency(ds)
    
    # Check if decompression is needed
    if hasattr(ds, 'file_meta') and hasattr(ds.file_meta, 'TransferSyntaxUID'):
        transfer_syntax = ds.file_meta.TransferSyntaxUID
        
        # If compressed, decompress automatically
        if transfer_syntax not in UNCOMPRESSED_SYNTAXES:
            logger.info(f"Auto-decompressing {path.name} (transfer syntax: {transfer_syntax})")
            
            try:
                # Decompress pixel data
                ds.decompress()
                
                # After decompression, the dataset is in Explicit VR Little Endian format
                # (not Implicit VR as previously assumed)
                # This is because decompress() keeps the dataset structure but uncompresses pixel data
                ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
                
                # IMPORTANT: Set the dataset encoding to match the transfer syntax
                # Decompressed datasets are Explicit VR Little Endian
                ds.is_implicit_VR = False
                ds.is_little_endian = True
                
                logger.info(f"  -> Successfully decompressed to Explicit VR Little Endian")
            except Exception as e:
                logger.warning(f"  -> Could not decompress {path.name}: {e}")
                logger.warning(f"  -> Continuing with original compressed format (may cause send errors)")
    
    return ds


def ensure_encoding_consistency(ds):
    """Ensure dataset encoding flags match transfer syntax UID."""
    if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
        return ds
    
    transfer_syntax = str(ds.file_meta.TransferSyntaxUID)
    
    # For datasets that have been decompressed, we need to ensure the encoding
    # flags match the transfer syntax. This will trigger deprecation warnings
    # but is necessary until pydicom v4.0 provides an alternative approach.
    
    # Check if flags are already correct to minimize unnecessary assignments
    if transfer_syntax == '1.2.840.10008.1.2':  # Implicit VR Little Endian
        if not (getattr(ds, 'is_implicit_VR', None) == True and 
                getattr(ds, 'is_little_endian', None) == True):
            ds.is_implicit_VR = True
            ds.is_little_endian = True
    elif transfer_syntax == '1.2.840.10008.1.2.1':  # Explicit VR Little Endian
        if not (getattr(ds, 'is_implicit_VR', None) == False and 
                getattr(ds, 'is_little_endian', None) == True):
            ds.is_implicit_VR = False
            ds.is_little_endian = True
    elif transfer_syntax == '1.2.840.10008.1.2.2':  # Explicit VR Big Endian
        if not (getattr(ds, 'is_implicit_VR', None) == False and 
                getattr(ds, 'is_little_endian', None) == False):
            ds.is_implicit_VR = False
            ds.is_little_endian = False
    # All other transfer syntaxes (compressed) default to Explicit VR Little Endian
    else:
        if not (getattr(ds, 'is_implicit_VR', None) == False and 
                getattr(ds, 'is_little_endian', None) == True):
            ds.is_implicit_VR = False
            ds.is_little_endian = True
    
    return ds


def iter_datasets(paths: Iterable[Path]):
    """Generator that yields (path, dataset) pairs for iteration."""
    for path in paths:
        ds = load_dataset(path)
        yield path, ds
