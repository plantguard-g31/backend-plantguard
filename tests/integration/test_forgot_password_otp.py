"""
Integration Tests -- Group I: Forgot Password / OTP Reset (FR-30)
Maps to Master Test Plan Section 3.3.3, Test Cases TC-RB-061, TC-RB-062, TC-RB-072.

FR-30 was completely undocumented in the SRS and Sprint Backlog and was
reverse-verified directly against app/api/v1/auth.py::forgot_password /
reset_password and app/schemas/auth.py for this test file. Confirmed ground
truth used below (CORRECTING an earlier assumption from the team of 5
minutes):
  - Endpoints: POST /api/v1/auth/forgot-password, POST /api/v1/auth/reset-password
  - OTP is a 6-digit code, valid for OTP_EXPIRE_MINUTES = 15 minutes (app/core/config.py),
    NOT 5 minutes as originally reported to the test team -- corrected here.
  - The forgot-password response is IDENTICAL whether or not the email exists
    (anti-enumeration design) -- verified below.
  - The OTP is marked is_used=True on a successful reset (single-use enforcement).
  - A successful reset clears refresh_token on the user (forces re-login everywhere).

Since the real email delivery path (Resend) is not reachable/desired in an
automated test run, these tests read the OTP directly from the
password_reset_tokens table via db_session, exactly as the real email would
have contained it -- this is a legitimate whitebox technique for verifying
server-side OTP behaviour without depending on an external email provider.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import select
from app.db.models import PasswordResetToken, User
from tests.conftest import unique_email


async def register_user(client, email=None, password="Farmer@2026"):
    email = email or unique_email()
    await client.post("/api/v1/auth/register", json={
        "name": "Test Farmer", "email": email,
        "password": password, "confirm_password": password
    })
    return email


async def get_latest_otp(db_session, email):
    result = await db_session.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.email == email)
        .order_by(PasswordResetToken.created_at.desc())
    )
    return result.scalars().first()


@pytest.mark.asyncio
async def test_IT22_TC_RB_061_forgot_password_generates_otp_for_registered_email(client, db_session, monkeypatch):
    """TC-RB-061: requesting a reset for a registered email creates a
    PasswordResetToken row with a 6-digit OTP, expiring 15 minutes out."""
    sent_calls = []
    monkeypatch.setattr(
        "app.api.v1.auth.send_otp_email",
        lambda email, otp: sent_calls.append((email, otp)) or True
    )

    email = await register_user(client)
    resp = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200

    token_row = await get_latest_otp(db_session, email)
    assert token_row is not None
    assert len(token_row.otp_code) == 6 and token_row.otp_code.isdigit()
    assert token_row.is_used is False

    remaining = token_row.expires_at - datetime.utcnow()
    assert timedelta(minutes=14) < remaining <= timedelta(minutes=15), (
        f"Expected ~15 minute validity per OTP_EXPIRE_MINUTES, got {remaining}"
    )
    # Confirm the email service was actually invoked with the same OTP stored in the DB
    assert sent_calls and sent_calls[0][1] == token_row.otp_code


@pytest.mark.asyncio
async def test_IT22b_forgot_password_same_response_for_unregistered_email(client, monkeypatch):
    """Anti-enumeration check: an unregistered email gets the exact same
    response shape/message as a registered one, so an attacker cannot use
    this endpoint to discover which emails have accounts."""
    monkeypatch.setattr("app.api.v1.auth.send_otp_email", lambda email, otp: True)

    registered_email = await register_user(client)
    resp_registered = await client.post("/api/v1/auth/forgot-password", json={"email": registered_email})
    resp_unregistered = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody_here@test.com"})

    assert resp_registered.status_code == resp_unregistered.status_code == 200
    assert resp_registered.json()["message"] == resp_unregistered.json()["message"]


@pytest.mark.asyncio
async def test_IT23_TC_RB_061b_reset_password_with_valid_otp_succeeds_and_invalidates_sessions(client, db_session, monkeypatch):
    """Full happy path: request OTP, use it to reset, confirm old password
    fails, new password works, and prior refresh token is cleared."""
    monkeypatch.setattr("app.api.v1.auth.send_otp_email", lambda email, otp: True)

    email = await register_user(client)
    login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Farmer@2026"})
    old_refresh_token = login_resp.json()["refresh_token"]

    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    token_row = await get_latest_otp(db_session, email)

    reset_resp = await client.post("/api/v1/auth/reset-password", json={
        "email": email, "otp_code": token_row.otp_code,
        "new_password": "NewSecure@9012", "confirm_new_password": "NewSecure@9012",
    })
    assert reset_resp.status_code == 200, reset_resp.text

    old_login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Farmer@2026"})
    assert old_login.status_code == 401

    new_login = await client.post("/api/v1/auth/login", json={"email": email, "password": "NewSecure@9012"})
    assert new_login.status_code == 200

    refresh_after_reset = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh_token})
    assert refresh_after_reset.status_code == 401


@pytest.mark.asyncio
async def test_IT24_TC_RB_062_reset_rejected_after_otp_expiry(client, db_session, monkeypatch):
    """TC-RB-062: an OTP whose expires_at is in the past is rejected, even
    though it is otherwise a correct/unused code."""
    monkeypatch.setattr("app.api.v1.auth.send_otp_email", lambda email, otp: True)

    email = await register_user(client)
    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    token_row = await get_latest_otp(db_session, email)

    # Simulate the 15-minute window having already elapsed
    token_row.expires_at = datetime.utcnow() - timedelta(minutes=1)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/reset-password", json={
        "email": email, "otp_code": token_row.otp_code,
        "new_password": "NewSecure@9012", "confirm_new_password": "NewSecure@9012",
    })
    assert resp.status_code == 400

    still_original = await client.post("/api/v1/auth/login", json={"email": email, "password": "Farmer@2026"})
    assert still_original.status_code == 200


@pytest.mark.asyncio
async def test_IT25_TC_RB_072_otp_cannot_be_reused_after_first_successful_reset(client, db_session, monkeypatch):
    """TC-RB-072: once an OTP has been used successfully, it cannot be used
    a second time, even though it has not expired yet (is_used enforcement)."""
    monkeypatch.setattr("app.api.v1.auth.send_otp_email", lambda email, otp: True)

    email = await register_user(client)
    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    token_row = await get_latest_otp(db_session, email)
    otp_code = token_row.otp_code

    first = await client.post("/api/v1/auth/reset-password", json={
        "email": email, "otp_code": otp_code,
        "new_password": "NewSecure@9012", "confirm_new_password": "NewSecure@9012",
    })
    assert first.status_code == 200

    second = await client.post("/api/v1/auth/reset-password", json={
        "email": email, "otp_code": otp_code,
        "new_password": "AnotherNew@3456", "confirm_new_password": "AnotherNew@3456",
    })
    assert second.status_code == 400, (
        f"Expected the reused OTP to be rejected, got {second.status_code}: {second.text}"
    )

    still_first_reset = await client.post("/api/v1/auth/login", json={"email": email, "password": "NewSecure@9012"})
    assert still_first_reset.status_code == 200
