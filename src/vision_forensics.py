"""Image forensics and perceptual hash analysis for JanataLens AI.

Computes SHA-256, perceptual hashes (pHash, dHash), image dimensions,
and extracts EXIF timestamps / GPS metadata safely.
Does not perform worker recognition or face identification.
"""

from __future__ import annotations

import hashlib
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import ExifTags, Image
import imagehash

from src.schemas import EvidenceCategory, EvidenceReference, StagePhotoEvidence


def compute_sha256(file_path: Path | str) -> str:
    """Calculates SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_image_hashes(image: Image.Image) -> Tuple[str, str]:
    """Computes pHash and dHash hex strings for a PIL Image."""
    # Ensure RGB conversion
    rgb_img = image.convert("RGB")
    ph = str(imagehash.phash(rgb_img))
    dh = str(imagehash.dhash(rgb_img))
    return ph, dh


def hamming_distance(hex_hash1: Optional[str], hex_hash2: Optional[str]) -> Optional[int]:
    """Computes Hamming distance between two hex hash strings."""
    if not hex_hash1 or not hex_hash2:
        return None
    if not re.fullmatch(r"[0-9a-fA-F]{16}", hex_hash1):
        return None
    if not re.fullmatch(r"[0-9a-fA-F]{16}", hex_hash2):
        return None
    try:
        val1 = int(hex_hash1, 16)
        val2 = int(hex_hash2, 16)
        return bin(val1 ^ val2).count("1")
    except Exception:
        return None


def extract_exif_metadata(image: Image.Image) -> Tuple[Optional[datetime], Optional[float], Optional[float], List[str]]:
    """Safely extracts capture timestamp, GPS latitude/longitude, and metadata warnings."""
    warnings: List[str] = []
    capture_time: Optional[datetime] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

    try:
        raw_exif = image.getexif()
        if not raw_exif:
            warnings.append("No EXIF metadata present in image (standard in synthetic or stripped uploads).")
            return None, None, None, warnings

        # Map EXIF tags
        exif_dict: Dict[str, Any] = {}
        for tag_id, val in raw_exif.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            exif_dict[tag_name] = val

        # Extract DateTimeOriginal or DateTime
        dt_str = exif_dict.get("DateTimeOriginal") or exif_dict.get("DateTime")
        if dt_str:
            try:
                # Format typically 'YYYY:MM:DD HH:MM:SS'
                capture_time = datetime.strptime(str(dt_str), "%Y:%m:%d %H:%M:%S")
            except Exception:
                warnings.append(f"Unparseable EXIF datetime string: '{dt_str}'")

        # Extract GPS Info if present in IFD
        # In modern Pillow, GPSInfo is often an IFD
        gps_ifd = raw_exif.get_ifd(ExifTags.IFD.GPSInfo)
        if gps_ifd:
            gps_tags: Dict[str, Any] = {}
            for t_id, t_val in gps_ifd.items():
                t_name = ExifTags.GPSTAGS.get(t_id, str(t_id))
                gps_tags[t_name] = t_val

            lat = _convert_gps_coords(gps_tags.get("GPSLatitude"), gps_tags.get("GPSLatitudeRef"))
            lon = _convert_gps_coords(gps_tags.get("GPSLongitude"), gps_tags.get("GPSLongitudeRef"))
        else:
            warnings.append("No GPS coordinates in image metadata.")

    except Exception as e:
        warnings.append(f"Could not parse EXIF metadata: {str(e)}")

    return capture_time, lat, lon, warnings


def _convert_gps_coords(coord_tuple: Any, ref: Optional[str]) -> Optional[float]:
    """Converts EXIF degrees/minutes/seconds rational tuple to decimal degrees."""
    if not coord_tuple or len(coord_tuple) < 3:
        return None
    try:
        deg = float(coord_tuple[0])
        minute = float(coord_tuple[1])
        sec = float(coord_tuple[2])
        dec = deg + (minute / 60.0) + (sec / 3600.0)
        if ref and ref.upper() in ("S", "W"):
            dec = -dec
        return round(dec, 6)
    except Exception:
        return None


def inspect_stage_photo(
    file_path: Path | str,
    stage_label: str,
    declared_order: int,
    synthetic: bool = False,
) -> StagePhotoEvidence:
    """Inspects a stage photo on disk, calculating SHA-256, pHash, dHash, dimensions, and EXIF."""
    path = Path(file_path)
    file_bytes = path.stat().st_size
    file_sha256 = compute_sha256(path)

    with Image.open(path) as img:
        width, height = img.size
        phash_val, dhash_val = compute_image_hashes(img)
        dt_val, lat_val, lon_val, exif_warnings = extract_exif_metadata(img)

    ev_ref = EvidenceReference(
        evidence_id=f"EV-PHOTO-{path.stem}",
        filename=path.name,
        evidence_type=EvidenceCategory.STAGE_PHOTO,
        sha256=file_sha256,
        file_size_bytes=file_bytes,
        synthetic=synthetic,
    )

    return StagePhotoEvidence(
        photo_id=f"PHOTO-{path.stem}",
        evidence_reference=ev_ref,
        declared_stage_label=stage_label,
        declared_order=declared_order,
        capture_timestamp=dt_val,
        gps_latitude=lat_val,
        gps_longitude=lon_val,
        image_width=width,
        image_height=height,
        sha256=file_sha256,
        phash=phash_val,
        dhash=dhash_val,
        metadata_warnings=exif_warnings,
    )


def inspect_stage_photo_bytes(
    file_bytes: bytes,
    filename: str,
    stage_label: str,
    declared_order: int,
    synthetic: bool = False,
) -> StagePhotoEvidence:
    """Inspects an uploaded stage photograph entirely in memory."""
    file_sha256 = hashlib.sha256(file_bytes).hexdigest()
    with Image.open(io.BytesIO(file_bytes)) as img:
        width, height = img.size
        phash_val, dhash_val = compute_image_hashes(img)
        dt_val, lat_val, lon_val, exif_warnings = extract_exif_metadata(img)

    stem = Path(filename).stem or "uploaded-stage"
    ev_ref = EvidenceReference(
        evidence_id=f"EV-PHOTO-{file_sha256[:8]}",
        filename=filename,
        evidence_type=EvidenceCategory.STAGE_PHOTO,
        sha256=file_sha256,
        file_size_bytes=len(file_bytes),
        synthetic=synthetic,
    )
    return StagePhotoEvidence(
        photo_id=f"PHOTO-{stem}",
        evidence_reference=ev_ref,
        declared_stage_label=stage_label,
        declared_order=declared_order,
        capture_timestamp=dt_val,
        gps_latitude=lat_val,
        gps_longitude=lon_val,
        image_width=width,
        image_height=height,
        sha256=file_sha256,
        phash=phash_val,
        dhash=dhash_val,
        metadata_warnings=exif_warnings,
    )
