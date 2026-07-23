"""
Unit Test -- Group L: File Size Limit, Exact Boundary (FR-07)
Maps to Master Test Plan Section 3.3.3, Test Case TC-RB-074.

Complements test_UT13_oversized_file_is_rejected (which only tests a file
well over the limit, 6MB) with the precise boundary values either side of
exactly 5,242,880 bytes (5.0 MB), through the same real
app/middleware/security.py::validate_upload_file function.
"""
import pytest
from fastapi import HTTPException
from tests.unit.test_file_validation import make_upload_file


FIVE_MB = 5 * 1024 * 1024


@pytest.mark.asyncio
async def test_UT18_TC_RB_074_file_exactly_5mb_is_accepted():
    """A JPEG-signed payload of exactly 5,242,880 bytes must be ACCEPTED
    (FR-07 states a '5 MB' limit, which this project treats as inclusive)."""
    from app.middleware.security import validate_upload_file
    content = b"\xff\xd8\xff" + (b"\x00" * (FIVE_MB - 3))
    assert len(content) == FIVE_MB
    upload = make_upload_file(content)
    result = await validate_upload_file(upload)
    assert result["valid"] is True
    assert result["size_bytes"] == FIVE_MB


@pytest.mark.asyncio
async def test_UT19_TC_RB_074b_file_one_byte_over_5mb_is_rejected():
    """A payload of 5,242,881 bytes (one byte over the limit) must be
    REJECTED with 413, confirming the boundary is not off-by-one in either
    direction."""
    from app.middleware.security import validate_upload_file
    content = b"\xff\xd8\xff" + (b"\x00" * (FIVE_MB - 2))
    assert len(content) == FIVE_MB + 1
    upload = make_upload_file(content)
    with pytest.raises(HTTPException) as exc_info:
        await validate_upload_file(upload)
    assert exc_info.value.status_code == 413
