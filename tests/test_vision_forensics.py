"""Unit tests for vision forensics and image hash analysis."""

import hashlib
from pathlib import Path
from PIL import Image, ImageDraw
import pytest

from src.vision_forensics import (
    compute_image_hashes,
    compute_sha256,
    extract_exif_metadata,
    hamming_distance,
    inspect_stage_photo,
)


@pytest.fixture
def temp_images(tmp_path):
    """Creates temporary images: two identical, one slightly modified, one distinct."""
    # 1. Base image (500x500 white with blue rectangle)
    img1 = Image.new("RGB", (500, 500), color=(255, 255, 255))
    draw1 = ImageDraw.Draw(img1)
    draw1.rectangle([50, 50, 250, 250], fill=(0, 100, 200))
    p1 = tmp_path / "stage1.jpg"
    img1.save(p1)

    # 2. Exact duplicate
    p2 = tmp_path / "stage2_dup.jpg"
    img1.save(p2)

    # 3. Near-duplicate (same with tiny 5px dot in corner)
    img3 = img1.copy()
    draw3 = ImageDraw.Draw(img3)
    draw3.point((10, 10), fill=(0, 0, 0))
    p3 = tmp_path / "stage3_near.jpg"
    img3.save(p3)

    # 4. Completely distinct image (black and red circle)
    img4 = Image.new("RGB", (500, 500), color=(0, 0, 0))
    draw4 = ImageDraw.Draw(img4)
    draw4.ellipse([100, 100, 400, 400], fill=(220, 20, 60))
    p4 = tmp_path / "stage4_diff.jpg"
    img4.save(p4)

    return {"base": p1, "exact": p2, "near": p3, "distinct": p4}


def test_sha256_exact_match(temp_images):
    sha1 = compute_sha256(temp_images["base"])
    sha2 = compute_sha256(temp_images["exact"])
    sha3 = compute_sha256(temp_images["near"])
    sha4 = compute_sha256(temp_images["distinct"])

    assert sha1 == sha2
    assert sha1 != sha3
    assert sha1 != sha4


def test_invalid_perceptual_hash_returns_no_distance():
    assert hamming_distance("not-hex", "ffffffffffffffff") is None


def test_perceptual_hash_hamming_distance(temp_images):
    with Image.open(temp_images["base"]) as i1, Image.open(temp_images["near"]) as i3, Image.open(temp_images["distinct"]) as i4:
        ph1, dh1 = compute_image_hashes(i1)
        ph3, dh3 = compute_image_hashes(i3)
        ph4, dh4 = compute_image_hashes(i4)

    # Base vs Near duplicate should have very low Hamming distance (<= 4)
    dist_near_p = hamming_distance(ph1, ph3)
    dist_near_d = hamming_distance(dh1, dh3)
    assert dist_near_p is not None and dist_near_p <= 4
    assert dist_near_d is not None and dist_near_d <= 4

    # Base vs Distinct should have high Hamming distance
    dist_diff_p = hamming_distance(ph1, ph4)
    assert dist_diff_p is not None and dist_diff_p > 10


def test_exif_metadata_safety(temp_images):
    # Image without EXIF should return warnings rather than raising an exception
    with Image.open(temp_images["base"]) as img:
        dt, lat, lon, warnings = extract_exif_metadata(img)
        assert dt is None
        assert lat is None
        assert lon is None
        assert len(warnings) > 0


def test_inspect_stage_photo(temp_images):
    photo_ev = inspect_stage_photo(
        file_path=temp_images["base"],
        stage_label="Stage 1: Foundation",
        declared_order=1,
        synthetic=True,
    )
    assert photo_ev.image_width == 500
    assert photo_ev.image_height == 500
    assert photo_ev.sha256 is not None
    assert photo_ev.phash is not None
    assert photo_ev.declared_stage_label == "Stage 1: Foundation"
    assert photo_ev.evidence_reference.synthetic is True
