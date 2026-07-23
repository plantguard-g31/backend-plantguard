"""
Integration Tests -- Group H: Change Password (FR-29)
Maps to Master Test Plan Section 3.3.3, Test Cases TC-RB-058, TC-RB-059, TC-RB-071.

FR-29 was undocumented in the original SRS/Sprint Backlog and was reverse-verified
directly against app/api/v1/user.py::change_password and app/schemas/auth.py::
ChangePasswordRequest for this test file. Confirmed ground truth used below:
  - Endpoint: PUT /api/v1/user/change-password
  - Body: current_password, new_password, confirm_new_password (all min 8 chars)
  - Wrong current_password -> 401 "invalid_current_password"
  - new_password == current_password -> 400 "password_must_be_different"
  - On success: refresh_token is invalidated (forces re-login on other sessions)
  - An audit_logs row (event_type="password_change") is written
"""
import pytest
from sqlalchemy import select
from app.db.models import User, AuditLog
from tests.conftest import unique_email


async def register_login_full(client, email=None, password="Farmer@2026"):
    """Like register_and_login, but also returns the refresh_token so tests
    can verify session-invalidation behaviour."""
    email = email or unique_email()
    await client.post("/api/v1/auth/register", json={
        "name": "Test Farmer", "email": email,
        "password": password, "confirm_password": password
    })
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    body = resp.json()
    return {"email": email, "access_token": body["access_token"], "refresh_token": body["refresh_token"]}


@pytest.mark.asyncio
async def test_IT18_TC_RB_058_change_password_success_then_old_password_fails(client, db_session):
    """TC-RB-058: correct current_password -> 200; old password no longer logs in;
    new password does."""
    session = await register_login_full(client)
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    resp = await client.put("/api/v1/user/change-password", headers=headers, json={
        "current_password": "Farmer@2026",
        "new_password": "NewSecure@5678",
        "confirm_new_password": "NewSecure@5678",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["requires_relogin"] is True

    old_login = await client.post("/api/v1/auth/login", json={
        "email": session["email"], "password": "Farmer@2026"
    })
    assert old_login.status_code == 401

    new_login = await client.post("/api/v1/auth/login", json={
        "email": session["email"], "password": "NewSecure@5678"
    })
    assert new_login.status_code == 200

    # Confirm the audit trail (FR-21 cross-check)
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.event_type == "password_change")
    )
    assert result.scalars().first() is not None


@pytest.mark.asyncio
async def test_IT19_TC_RB_059_change_password_wrong_current_password_rejected(client):
    """TC-RB-059: incorrect current_password -> 401, no change made, original
    password still works."""
    session = await register_login_full(client)
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    resp = await client.put("/api/v1/user/change-password", headers=headers, json={
        "current_password": "WrongPass@0000",
        "new_password": "NewSecure@5678",
        "confirm_new_password": "NewSecure@5678",
    })
    assert resp.status_code == 401
    # Real response shape (app/middleware/error_handler.py): {"error_code","message_en","message_ne"}
    # -- NOT a raw {"detail": ...} FastAPI default, since the app converts every
    # HTTPException into this bilingual farmer-friendly format.
    body = resp.json()
    assert body["error_code"] == "401"
    assert body["message_en"] == "Current password is incorrect."

    still_works = await client.post("/api/v1/auth/login", json={
        "email": session["email"], "password": "Farmer@2026"
    })
    assert still_works.status_code == 200


@pytest.mark.asyncio
async def test_IT20_TC_RB_059b_new_password_same_as_current_rejected(client):
    """Real business rule discovered in app/api/v1/user.py: the new password
    must differ from the current one -> 400 'password_must_be_different'."""
    session = await register_login_full(client)
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    resp = await client.put("/api/v1/user/change-password", headers=headers, json={
        "current_password": "Farmer@2026",
        "new_password": "Farmer@2026",
        "confirm_new_password": "Farmer@2026",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_IT21_TC_RB_071_refresh_token_invalidated_after_password_change(client, db_session):
    """TC-RB-071: after a successful password change, the refresh_token issued
    before the change can no longer be used to obtain a new access token."""
    session = await register_login_full(client)
    old_refresh_token = session["refresh_token"]
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    resp = await client.put("/api/v1/user/change-password", headers=headers, json={
        "current_password": "Farmer@2026",
        "new_password": "NewSecure@5678",
        "confirm_new_password": "NewSecure@5678",
    })
    assert resp.status_code == 200

    refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh_token})
    assert refresh_resp.status_code == 401, (
        "Expected the pre-change refresh token to be invalidated, but it still worked. "
        f"Got {refresh_resp.status_code}: {refresh_resp.text}"
    )
