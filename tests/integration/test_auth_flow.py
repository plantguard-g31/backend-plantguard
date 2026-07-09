"""
Integration Tests -- Group A: Authentication Flow
Maps to STP Section 3.3.2, Test Cases IT-01 through IT-05.
These hit the real FastAPI routes via httpx.AsyncClient, backed by a real
PostgreSQL test schema (created fresh per test by the db_engine fixture).
"""
import pytest
from sqlalchemy import select
from app.db.models import User
from tests.conftest import unique_email


@pytest.mark.asyncio
async def test_IT01_registration_creates_real_db_row(client, db_session):
    email = unique_email()
    resp = await client.post("/api/v1/auth/register", json={
        "name": "Sita Gurung", "email": email,
        "password": "Farmer@2026", "confirm_password": "Farmer@2026"
    })
    assert resp.status_code == 201, resp.text

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    assert user is not None
    assert user.role == "farmer"
    assert user.password_hash != "Farmer@2026"   # never store plaintext


@pytest.mark.asyncio
async def test_IT02_duplicate_email_registration_rejected(client):
    email = unique_email()
    payload = {"name": "Sita Gurung", "email": email, "password": "Farmer@2026", "confirm_password": "Farmer@2026"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_IT03_login_issues_tokens_and_stores_refresh_in_db(client, db_session):
    email = unique_email()
    await client.post("/api/v1/auth/register", json={
        "name": "Sita Gurung", "email": email,
        "password": "Farmer@2026", "confirm_password": "Farmer@2026"
    })
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Farmer@2026"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    assert user.refresh_token == body["refresh_token"]


@pytest.mark.asyncio
async def test_IT04_refresh_issues_new_access_token(client):
    email = unique_email()
    await client.post("/api/v1/auth/register", json={
        "name": "Sita Gurung", "email": email,
        "password": "Farmer@2026", "confirm_password": "Farmer@2026"
    })
    login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Farmer@2026"})
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_IT05_logout_revokes_refresh_token(client, db_session):
    email = unique_email()
    await client.post("/api/v1/auth/register", json={
        "name": "Sita Gurung", "email": email,
        "password": "Farmer@2026", "confirm_password": "Farmer@2026"
    })
    login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Farmer@2026"})
    access_token = login_resp.json()["access_token"]
    refresh_token = login_resp.json()["refresh_token"]

    logout_resp = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert logout_resp.status_code == 200, logout_resp.text

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    assert user.refresh_token is None

    retry = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert retry.status_code == 401
