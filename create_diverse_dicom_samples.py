"""
Generates diverse DICOM test files with different modalities, bit depths, and image dimensions.
"""

import pydicom
from pydicom.dataset import FileDataset
from pydicom.uid import generate_uid
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

# DICOM Modality configurations
MODALITY_CONFIGS = {
    "CR": {
        "modality": "CR",
        "sop_class": "1.2.840.10008.5.1.4.1.1.1",  # CR Image Storage
        "sizes": [(256, 256), (512, 512), (1024, 1024), (2048, 2048)],
        "bit_depths": [12, 16],
    },
    "CT": {
        "modality": "CT",
        "sop_class": "1.2.840.10008.5.1.4.1.1.2",  # CT Image Storage
        "sizes": [(512, 512)],
        "bit_depths": [16],
    },
    "MR": {
        "modality": "MR",
        "sop_class": "1.2.840.10008.5.1.4.1.1.4",  # MR Image Storage
        "sizes": [(256, 256), (512, 512)],
        "bit_depths": [16],
    },
    "US": {
        "modality": "US",
        "sop_class": "1.2.840.10008.5.1.4.1.1.6",  # US Image Storage
        "sizes": [(256, 256), (512, 512)],
        "bit_depths": [8, 16],
    },
    "PET": {
        "modality": "PT",  # PET modality code
        "sop_class": "1.2.840.10008.5.1.4.1.1.128",  # PET Image Storage
        "sizes": [(128, 128), (256, 256)],
        "bit_depths": [16],
    },
    "MG": {
        "modality": "MG",
        "sop_class": "1.2.840.10008.5.1.4.1.1.1.1.1",  # Digital Mammography
        "sizes": [(2048, 2560), (4608, 5200)],
        "bit_depths": [14, 16],
    },
    "NM": {
        "modality": "NM",
        "sop_class": "1.2.840.10008.5.1.4.1.1.20",  # Nuclear Medicine Image Storage
        "sizes": [(128, 128), (256, 256), (512, 512)],
        "bit_depths": [16],
    },
}

PHOTOMETRIC_OPTIONS = ["MONOCHROME1", "MONOCHROME2"]


def create_dicom_file(
    output_path: Path,
    modality: str,
    sop_class_uid: str,
    rows: int,
    cols: int,
    bits_allocated: int,
    bits_stored: int,
    photometric: str = "MONOCHROME2",
    pixel_representation: int = 0,
    patient_id: str = "TEST001",
    patient_name: str = "Test^Patient",
) -> Path:
    """Create a DICOM file with specified parameters."""
    
    ds = FileDataset("sample.dcm", {}, file_meta=None, preamble=b"\x00" * 128)
    
    # Required DICOM tags
    ds.PatientName = patient_name
    ds.PatientID = patient_id
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.SOPClassUID = sop_class_uid
    ds.Modality = modality
    ds.StudyDate = datetime.now().strftime("%Y%m%d")
    ds.StudyTime = datetime.now().strftime("%H%M%S")
    ds.SeriesDate = datetime.now().strftime("%Y%m%d")
    ds.SeriesTime = datetime.now().strftime("%H%M%S")
    
    # Image characteristics
    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = bits_allocated
    ds.BitsStored = bits_stored
    ds.HighBit = bits_stored - 1
    ds.PixelRepresentation = pixel_representation
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = photometric
    ds.PixelSpacing = [1.0, 1.0]
    
    # Generate pixel data based on bit depth
    max_val = (2 ** bits_stored) - 1
    if bits_allocated == 8:
        pixel_data = np.random.randint(0, 256, (rows, cols), dtype=np.uint8).tobytes()
    else:
        pixel_data = np.random.randint(0, max_val + 1, (rows, cols), dtype=np.uint16).tobytes()
    
    ds.PixelData = pixel_data
    
    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ds.save_as(str(output_path), write_like_original=False)
    return output_path


def generate_all_samples(output_dir: Path = Path("dicom_samples")):
    """Generate diverse DICOM samples with descriptive filenames."""
    
    files_created = []
    
    for modality_code, config in MODALITY_CONFIGS.items():
        modality = config["modality"]
        sop_class = config["sop_class"]
        
        for rows, cols in config["sizes"]:
            for bits_stored in config["bit_depths"]:
                bits_allocated = 16 if bits_stored > 8 else 8
                
                # Generate with MONOCHROME2 (standard)
                filename = f"{modality_code}_{rows}x{cols}_{bits_stored}bit_MONO2.dcm"
                filepath = output_dir / filename
                create_dicom_file(
                    filepath, modality, sop_class, rows, cols,
                    bits_allocated, bits_stored, "MONOCHROME2"
                )
                files_created.append(filepath)
                print(f"Created: {filename}")
                
                # For some modalities, also create MONOCHROME1 variant
                if modality_code in ["CR", "CT", "MR"]:
                    filename = f"{modality_code}_{rows}x{cols}_{bits_stored}bit_MONO1.dcm"
                    filepath = output_dir / filename
                    create_dicom_file(
                        filepath, modality, sop_class, rows, cols,
                        bits_allocated, bits_stored, "MONOCHROME1"
                    )
                    files_created.append(filepath)
                    print(f"Created: {filename}")
    
    # Create some special cases
    # Small file
    small_file = output_dir / "CR_128x128_8bit_MONO2_small.dcm"
    create_dicom_file(
        small_file, "CR", MODALITY_CONFIGS["CR"]["sop_class"],
        128, 128, 8, 8, "MONOCHROME2"
    )
    files_created.append(small_file)
    print(f"Created: {small_file.name}")
    
    # Large file
    large_file = output_dir / "CR_4096x4096_16bit_MONO2_large.dcm"
    create_dicom_file(
        large_file, "CR", MODALITY_CONFIGS["CR"]["sop_class"],
        4096, 4096, 16, 16, "MONOCHROME2"
    )
    files_created.append(large_file)
    print(f"Created: {large_file.name}")
    
    # Different patient IDs for routing tests
    for i, patient_id in enumerate(["PAT001", "PAT002", "PAT003"], 1):
        patient_file = output_dir / f"CT_512x512_16bit_MONO2_PAT{patient_id}.dcm"
        create_dicom_file(
            patient_file, "CT", MODALITY_CONFIGS["CT"]["sop_class"],
            512, 512, 16, 16, "MONOCHROME2",
            patient_id=patient_id,
            patient_name=f"Patient^{i:03d}"
        )
        files_created.append(patient_file)
        print(f"Created: {patient_file.name}")
    
    print(f"\nCreated {len(files_created)} DICOM sample files in {output_dir.absolute()}")
    return files_created


if __name__ == "__main__":
    generate_all_samples()

