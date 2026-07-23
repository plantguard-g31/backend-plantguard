"""
Integration Tests -- Group F: Notification System
Maps to the new Notification Feature (Sprint 6).
Tests the API endpoints for FCM tokens, fetching notifications, and preferences.
"""
import pytest
from sqlalchemy import select
from app.db.models import User, Notification, UserNotificationPreference
from tests.conftest import unique_email

# Helper to get an auth header
def get_auth_header(token):
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_save_fcm_token(client, db_session):
    """Test that a user can successfully save their FCM device token."""
    # 1. Register and login
    email = unique_email()
    await client.post("/api/v1/auth/register", json={
        "name": "Test Farmer", "email": email,
        "password": "Farmer@2026", "confirm_password": "Farmer@2026"
    })
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": email, "password": "Farmer@2026"
    })
    token = login_resp.json()["access_token"]
    
    # 2. Save FCM token
    resp = await client.post(
        "/api/v1/notifications/fcm-token",
        json={"fcm_token": "test_device_token_123"},
        headers=get_auth_header(token)
    )
    
    assert resp.status_code == 200
    assert resp.json()["message"] == "FCM token updated successfully"
    
    # 3. Verify it was saved in the database
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    assert user.fcm_token == "test_device_token_123"

@pytest.mark.asyncio
async def test_get_notifications_empty(client, db_session):
    """Test fetching notifications when the user has none."""
    email = unique_email()
    await client.post("/api/v1/auth/register", json={
        "name": "Test Farmer", "email": email,
        "password": "Farmer@2026", "confirm_password": "Farmer@2026"
    })
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": email, "password": "Farmer@2026"
    })
    token = login_resp.json()["access_token"]
    
    resp = await client.get(
        "/api/v1/notifications/",
        headers=get_auth_header(token)
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []

@pytest.mark.asyncio
async def test_update_preferences(client, db_session):
    """Test updating notification preferences."""
    email = unique_email()
    await client.post("/api/v1/auth/register", json={
        "name": "Test Farmer", "email": email,
        "password": "Farmer@2026", "confirm_password": "Farmer@2026"
    })
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": email, "password": "Farmer@2026"
    })
    token = login_resp.json()["access_token"]
    
    # Update preferences
    resp = await client.put(
        "/api/v1/notifications/preferences",
        json={
            "treatment_reminders_enabled": False,
            "preferred_notification_hour": 9
        },
        headers=get_auth_header(token)
    )
    
    assert resp.status_code == 200
    
    # Verify in DB
    result = await db_session.execute(
        select(UserNotificationPreference).where(UserNotificationPreference.user_id == login_resp.json().get("user_id")) # Note: login doesn't return user_id, so we fetch by email below
    )
    # Actually, let's fetch by user_id properly
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    
    result = await db_session.execute(
        select(UserNotificationPreference).where(UserNotificationPreference.user_id == user.id)
    )
    prefs = result.scalars().first()
    
    assert prefs is not None
    assert prefs.treatment_reminders_enabled is False
    assert prefs.preferred_notification_hour == 9