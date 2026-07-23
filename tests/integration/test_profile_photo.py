"""
Integration Tests -- Group J: Profile Picture Upload + Retrieval (FR-28)
Maps to Master Test Plan Section 3.3.3, Test Cases TC-RB-056, TC-RB-057.

Ground truth verified against app/api/v1/user.py::upload_profile_photo_endpoint.
The real Supabase Storage client is stubbed in tests/conftest.py, so
app/services/storage.py::upload_profile_photo is monkeypatched here to avoid
depending on it directly while still exercising the real endpoint's
validation logic (MIME check, size check, extension check, real-image
verification via PIL).
"""
import io
import pytest
import numpy as np
import cv2
from tests.integration.test_diagnosis_pipeline import register_and_login


def make_jpeg(width=200, height=200):
    img = np.full((height, width, 3), (100, 120, 90), dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", img)
    assert success
    return encoded.tobytes()


@pytest.mark.asyncio
async def test_IT26_TC_RB_056_profile_photo_upload_success(client, monkeypatch):
    """TC-RB-056: a genuine JPEG upload succeeds and returns a URL."""
    async def _fake_upload(file_bytes, user_id, file_extension):
        return f"https://storage.test/{user_id}.{file_extension}"
    monkeypatch.setattr("app.api.v1.user.upload_profile_photo", _fake_upload)
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("photo.jpg", io.BytesIO(make_jpeg()), "image/jpeg")}

    resp = await client.post("/api/v1/user/profile-photo", headers=headers, files=files)
    assert resp.status_code == 200, resp.text
    assert resp.json()["profile_picture_url"].startswith("https://storage.test/")


@pytest.mark.asyncio
async def test_IT27_TC_RB_057_get_me_returns_uploaded_profile_picture_url(client, monkeypatch):
    """TC-RB-057: after a successful upload, GET /user/me reflects the new
    profile_picture_url."""
    async def _fake_upload(file_bytes, user_id, file_extension):
        return f"https://storage.test/{user_id}.{file_extension}"
    monkeypatch.setattr("app.api.v1.user.upload_profile_photo", _fake_upload)
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("photo.jpg", io.BytesIO(make_jpeg()), "image/jpeg")}
    await client.post("/api/v1/user/profile-photo", headers=headers, files=files)

    me = await client.get("/api/v1/user/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["profile_picture_url"] is not None
    assert me.json()["profile_picture_url"].startswith("https://storage.test/")


@pytest.mark.asyncio
async def test_IT28_profile_photo_disguised_file_rejected(client):
    """Negative case: a non-image disguised as a .jpg is rejected with 415,
    same magic-byte-style defence pattern as the diagnosis upload path."""
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 50
    files = {"file": ("photo.jpg", io.BytesIO(fake_exe), "image/jpeg")}

    resp = await client.post("/api/v1/user/profile-photo", headers=headers, files=files)
    assert resp.status_code == 415
