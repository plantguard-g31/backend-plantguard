"""
Unit Tests -- Group C: File & Image Validation
(middleware/security.py, services/quality_gate.py)
Maps to STP Section 3.3.1, Test Cases UT-11 through UT-15.

Synthetic test images are generated in-memory with PIL/numpy/cv2 so these
tests need no external fixture files and are fully reproducible.
"""
import io
import numpy as np
import cv2
import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers


def make_upload_file(content: bytes, filename="test.jpg", content_type="image/jpeg") -> UploadFile:
    return UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


def make_jpeg_bytes(width=300, height=300, color=(80, 160, 60), blur=False, brightness_add=0):
    """Builds a real, valid JPEG in memory with controllable properties."""
    img = np.full((height, width, 3), color, dtype=np.uint8)
    # add a bit of texture so it isn't perfectly flat (perfectly flat images
    # have zero variance and would always look "blurry" to the Laplacian test)
    noise = np.random.randint(0, 40, (height, width, 3), dtype=np.uint8)
    img = cv2.add(img, noise)
    if brightness_add:
        img = cv2.add(img, np.full_like(img, brightness_add))
    if blur:
        img = cv2.GaussianBlur(img, (25, 25), 15)
    success, encoded = cv2.imencode(".jpg", img)
    assert success
    return encoded.tobytes()


# ---- UT-11 / UT-12 / UT-13: middleware/security.py ----

@pytest.mark.asyncio
async def test_UT11_genuine_jpeg_passes_magic_byte_check():
    """UT-11: a real JPEG with correct header bytes passes validation."""
    from app.middleware.security import validate_upload_file
    content = make_jpeg_bytes()
    upload = make_upload_file(content)
    result = await validate_upload_file(upload)
    assert result["valid"] is True


@pytest.mark.asyncio
async def test_UT12_disguised_executable_is_rejected():
    """UT-12: a file whose bytes don't match JPEG/PNG signatures is rejected
    with 415, regardless of its .jpg filename/extension."""
    from app.middleware.security import validate_upload_file
    fake_exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100  # PE header magic bytes
    upload = make_upload_file(fake_exe_bytes, filename="photo.jpg")
    with pytest.raises(HTTPException) as exc_info:
        await validate_upload_file(upload)
    assert exc_info.value.status_code == 415


@pytest.mark.asyncio
async def test_UT13_oversized_file_is_rejected():
    """UT-13: a valid JPEG sized over the 5MB limit is rejected with 413."""
    from app.middleware.security import validate_upload_file
    # 6MB of dummy bytes prefixed with a real JPEG magic-byte header
    oversized_content = b"\xff\xd8\xff" + (b"\x00" * (6 * 1024 * 1024))
    upload = make_upload_file(oversized_content)
    with pytest.raises(HTTPException) as exc_info:
        await validate_upload_file(upload)
    assert exc_info.value.status_code == 413


# ---- UT-14 / UT-15: services/quality_gate.py ----

@pytest.mark.asyncio
async def test_UT14_blurry_image_fails_quality_gate():
    """UT-14: a heavily blurred image is rejected with reason 'blurry_image'."""
    from app.services.quality_gate import run_quality_checks
    blurry_bytes = make_jpeg_bytes(width=300, height=300, blur=True)
    upload = make_upload_file(blurry_bytes)
    with pytest.raises(HTTPException) as exc_info:
        await run_quality_checks(upload)
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "blurry_image"


@pytest.mark.asyncio
async def test_UT15_non_leaf_image_fails_vegetation_check():
    """UT-15: a plain grey (non-vegetation-colored) image is rejected with
    reason 'no_leaf_detected'."""
    from app.services.quality_gate import run_quality_checks
    # Flat mid-grey image: sharp enough to pass the blur check, but contains
    # no green/yellow hue at all, so it must fail the vegetation-ratio check.
    grey_bytes = make_jpeg_bytes(width=300, height=300, color=(128, 128, 128))
    upload = make_upload_file(grey_bytes)
    with pytest.raises(HTTPException) as exc_info:
        await run_quality_checks(upload)
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "no_leaf_detected"
