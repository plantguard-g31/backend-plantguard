"""
Integration Tests -- Group D: Admin Hierarchy Enforcement
Maps to STP Section 3.3.2, Test Cases IT-13, IT-14, IT-15.
This is the highest-risk area identified in the STP (Section 2.2.1) --
privilege escalation from Regular Admin to Super Admin capability.
"""
import pytest
from sqlalchemy import select
from app.db.models import User
from app.core.security import hash_password
from tests.conftest import unique_email


async def create_user_directly(db_session, email, password, role="farmer", is_super_admin=False):
    """Bypasses the API entirely, mirroring how the real create_admin.py
    bootstrap script works -- direct DB insertion, not an API call."""
    user = User(
        name="Test Admin", email=email, password_hash=hash_password(password),
        role=role, is_super_admin=is_super_admin, is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def login(client, email, password="AdminPass@2026"):
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_IT13_super_admin_can_create_regular_admin(client, db_session):
    """IT-13: the seeded Super Admin can successfully create a new Regular Admin."""
    email = unique_email()
    await create_user_directly(db_session, email, "AdminPass@2026", role="admin", is_super_admin=True)
    token = await login(client, email)

    new_admin_email = unique_email()
    resp = await client.post(
        "/api/v1/admin/create-admin",
        json={"name": "New Admin", "email": new_admin_email, "password": "NewAdminPass@2026"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201, resp.text

    result = await db_session.execute(select(User).where(User.email == new_admin_email))
    created = result.scalars().first()
    assert created is not None
    assert created.role == "admin"
    assert created.is_super_admin is False


@pytest.mark.asyncio
async def test_IT14_regular_admin_blocked_from_creating_admin(client, db_session):
    """IT-14: a Regular Admin (is_super_admin=False) must be blocked with 403
    when attempting to create another admin. This is the single most
    important security test in the whole suite."""
    email = unique_email()
    await create_user_directly(db_session, email, "AdminPass@2026", role="admin", is_super_admin=False)
    token = await login(client, email)

    target_email = unique_email()
    resp = await client.post(
        "/api/v1/admin/create-admin",
        json={"name": "Escalation Attempt", "email": target_email, "password": "Whatever@2026"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403, f"CRITICAL: Regular Admin was NOT blocked! Got {resp.status_code}: {resp.text}"

    result = await db_session.execute(select(User).where(User.email == target_email))
    assert result.scalars().first() is None, "CRITICAL: privilege escalation succeeded -- new admin row was created!"


@pytest.mark.asyncio
async def test_IT15_regular_admin_can_still_manage_treatments(client, db_session):
    """IT-15 (positive control): confirms IT-14's block is specific to admin
    creation, not an over-broad permission failure -- the same Regular Admin
    must still be able to perform their legitimate duties."""
    email = unique_email()
    await create_user_directly(db_session, email, "AdminPass@2026", role="admin", is_super_admin=False)
    token = await login(client, email)

    resp = await client.post(
        "/api/v1/admin/treatments",
        json={
            "disease_name": "Potato Late Blight", "crop_type": "potato", "severity_level": "mild",
            "pesticide_name": "Copper Fungicide", "dosage_mild": "1.0g/L",
            "dosage_moderate": "2.0g/L", "dosage_severe": "3.5g/L",
            "application_timing": "Evening", "safety_instructions": "Wear gloves and mask",
            "pre_harvest_interval_days": 5, "source_reference": "NARC Guidelines 2024"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201, resp.text
