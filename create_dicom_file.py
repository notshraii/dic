#!/usr/bin/env python3
"""
Generate synthetic DICOM files of a specified size for performance testing.

Creates valid multi-frame CT DICOM files that pass DICM magic-string validation
and can be loaded by pydicom / sent via pynetdicom.

Usage:
    python3 create_large_dicom.py 500          # 500 MB file
    python3 create_large_dicom.py 1024         # 1 GB file
    python3 create_large_dicom.py 50 100 500   # three files: 50, 100, 500 MB

Options:
    --output-dir DIR      Output directory (default: ./dicom_samples)
    --modality MOD        DICOM modality: CT, MR, MG, CR, DX (default: CT)
    --patient-id ID       Patient ID tag value (default: PERF-SYNTH-001)
    --patient-name NAME   Patient name tag value (default: SYNTHETIC^TEST)
    --prefix PREFIX       Output filename prefix (default: SYNTH)

Examples:
    python3 create_large_dicom.py 256 --modality MR --patient-id MR-TEST-001
    python3 create_large_dicom.py 1024 --output-dir /tmp/dicom_test
    python3 create_large_dicom.py 50 200 1024 --prefix LOAD_TEST
"""

import argparse
import struct
import sys
import time
from pathlib import Path

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

MODALITY_SOP_CLASSES = {
    "CT": "1.2.840.10008.5.1.4.1.1.2",
    "MR": "1.2.840.10008.5.1.4.1.1.4",
    "CR": "1.2.840.10008.5.1.4.1.1.1",
    "DX": "1.2.840.10008.5.1.4.1.1.1.1",
    "MG": "1.2.840.10008.5.1.4.1.1.1.2",
}


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / (1024 ** 3):.2f} GB"
    return f"{size_bytes / (1024 ** 2):.1f} MB"


def create_dicom_file(
    output_dir: Path,
    target_size_mb: int,
    modality: str = "CT",
    patient_id: str = "PERF-SYNTH-001",
    patient_name: str = "SYNTHETIC^TEST",
    prefix: str = "SYNTH",
) -> Path:
    target_bytes = target_size_mb * 1024 * 1024

    rows = 512
    cols = 512
    bits_allocated = 16
    bytes_per_pixel = bits_allocated // 8
    frame_size = rows * cols * bytes_per_pixel

    if target_bytes <= frame_size:
        num_frames = 1
    else:
        num_frames = (target_bytes // frame_size) + 1

    expected_pixel_bytes = num_frames * frame_size
    size_label = f"{target_size_mb}MB"

    sop_class = MODALITY_SOP_CLASSES.get(modality.upper())
    if not sop_class:
        supported = ", ".join(sorted(MODALITY_SOP_CLASSES))
        print(f"ERROR: Unsupported modality '{modality}'. Supported: {supported}")
        sys.exit(1)

    filename = f"{prefix}_{modality}_{rows}x{cols}_{bits_allocated}bit_{num_frames}f_{size_label}.dcm"
    output_path = output_dir / filename

    print(f"\n--- Generating {size_label} {modality} DICOM ---")
    print(f"  Target:     {_format_size(target_bytes)}")
    print(f"  Frame size: {_format_size(frame_size)}")
    print(f"  Frames:     {num_frames}")
    print(f"  Pixel data: {_format_size(expected_pixel_bytes)}")
    print(f"  Output:     {output_path.name}")

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = sop_class
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(
        str(output_path),
        {},
        file_meta=file_meta,
        preamble=b"\x00" * 128,
    )

    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.FrameOfReferenceUID = generate_uid()

    ds.Modality = modality.upper()
    ds.Manufacturer = "SYNTHETIC"
    ds.InstitutionName = "Performance Testing"
    ds.PatientName = patient_name
    ds.PatientID = patient_id
    ds.StudyDescription = f"Synthetic {size_label} Performance Test"
    ds.SeriesDescription = f"Synthetic {num_frames}-frame {modality}"
    ds.StudyDate = time.strftime("%Y%m%d")
    ds.StudyTime = time.strftime("%H%M%S")

    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = bits_allocated
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 1
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.NumberOfFrames = str(num_frames)
    ds.ImageType = ["DERIVED", "PRIMARY"]

    ds.RescaleIntercept = "-1024"
    ds.RescaleSlope = "1"
    ds.WindowCenter = "40"
    ds.WindowWidth = "400"
    ds.SliceThickness = "1.0"
    ds.PixelSpacing = [0.5, 0.5]

    ds.is_implicit_VR = False
    ds.is_little_endian = True

    max_explicit_length = 0xFFFFFFFE
    if expected_pixel_bytes > max_explicit_length:
        print(f"ERROR: Pixel data ({_format_size(expected_pixel_bytes)}) exceeds "
              f"DICOM explicit length limit (~4 GB)")
        sys.exit(1)

    print(f"  Writing metadata header...")
    ds.save_as(str(output_path))

    print(f"  Streaming pixel data to file...")
    rng = np.random.default_rng(seed=42)
    batch_size = 50

    with open(output_path, 'ab') as f:
        # Pixel Data tag (7FE0,0010), VR "OW", 2 reserved bytes, uint32 length
        f.write(struct.pack('<HH', 0x7FE0, 0x0010))
        f.write(b'OW\x00\x00')
        f.write(struct.pack('<I', expected_pixel_bytes))

        for start in range(0, num_frames, batch_size):
            end = min(start + batch_size, num_frames)
            count = end - start
            batch = rng.integers(-1024, 3072, size=(count, rows, cols), dtype=np.int16)
            f.write(batch.tobytes())
            del batch

            pct = end / num_frames * 100
            size_so_far = end * frame_size
            print(f"  Streaming: {end}/{num_frames} frames "
                  f"({pct:.0f}%) - {_format_size(size_so_far)}", end="\r")

        print()

    actual_size = output_path.stat().st_size
    print(f"  Done: {output_path.name} ({_format_size(actual_size)})")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic DICOM files of a specified size for testing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s 500                          Generate a 500 MB file
  %(prog)s 1024                         Generate a 1 GB file
  %(prog)s 50 100 500                   Generate 50, 100, and 500 MB files
  %(prog)s 256 --modality MR            Generate a 256 MB MR file
  %(prog)s 1024 --output-dir /tmp/dcm   Save to a custom directory
        """,
    )
    parser.add_argument(
        "sizes_mb",
        type=int,
        nargs="+",
        metavar="SIZE_MB",
        help="Target file size(s) in megabytes (e.g. 50, 256, 1024)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./dicom_samples"),
        help="Output directory (default: ./dicom_samples)",
    )
    parser.add_argument(
        "--modality",
        type=str,
        default="CT",
        choices=sorted(MODALITY_SOP_CLASSES),
        help="DICOM modality (default: CT)",
    )
    parser.add_argument(
        "--patient-id",
        type=str,
        default="PERF-SYNTH-001",
        help="Patient ID tag value (default: PERF-SYNTH-001)",
    )
    parser.add_argument(
        "--patient-name",
        type=str,
        default="SYNTHETIC^TEST",
        help="Patient name (default: SYNTHETIC^TEST)",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="SYNTH",
        help="Output filename prefix (default: SYNTH)",
    )
    args = parser.parse_args()

    if not args.output_dir.exists():
        args.output_dir.mkdir(parents=True)
        print(f"Created output directory: {args.output_dir}")

    for size_mb in args.sizes_mb:
        if size_mb <= 0:
            print(f"ERROR: Size must be positive, got {size_mb}")
            sys.exit(1)

    created = []
    for size_mb in args.sizes_mb:
        path = create_dicom_file(
            output_dir=args.output_dir,
            target_size_mb=size_mb,
            modality=args.modality,
            patient_id=args.patient_id,
            patient_name=args.patient_name,
            prefix=args.prefix,
        )
        created.append(path)

    print(f"\n{'='*60}")
    print(f"Generated {len(created)} file(s):")
    for p in created:
        size = p.stat().st_size
        print(f"  {p.name}  ({_format_size(size)})")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
