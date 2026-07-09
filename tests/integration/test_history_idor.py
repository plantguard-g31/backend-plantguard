"""
Integration Tests -- Group C: History Access & IDOR Protection
Maps to STP Section 3.3.2, Test Cases IT-11 and IT-12.
"""
import pytest
import uuid
from app.db.models import DiagnosisHistory
from tests.conftest import unique_email
from tests.integration.test_diagnosis_pipeline import register_and_login


async def create_diagnosis_for_user(db_session, user_id):
    record = DiagnosisHistory(
        user_id=user_id,
        disease_label="Tomato Early Blight",
        crop_type="tomato",
        confidence=0.88,
        severity="moderate",
        image_blur_score=120.0,
        image_brightness=110.0,
        quality_passed=True,
        low_confidence_warning=False,
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    return record


@pytest.mark.asyncio
async def test_IT11_farmer_can_only_view_own_history(client, db_session):
    """IT-11: Farmer B must not be able to view Farmer A's diagnosis record."""
    from app.db.models import User
    from sqlalchemy import select

    email_a = unique_email()
    await register_and_login(client, email_a)
    result = await db_session.execute(select(User).where(User.email == email_a))
    farmer_a = result.scalars().first()
    diag_a = await create_diagnosis_for_user(db_session, farmer_a.id)

    token_b = await register_and_login(client)

    resp = await client.get(
        f"/api/v1/history/{diag_a.id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code in (403, 404), (
        f"Expected 403/404 blocking cross-user access, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.asyncio
async def test_IT11b_farmer_can_view_own_history_item_happy_path(client, db_session):
    """IT-11b (supplementary): a farmer viewing their OWN existing diagnosis
    record should succeed with a full response body. Added because IT-11's
    cross-user case returns 404 before reaching the response-building code
    path, so it doesn't actually exercise the same code as a successful view."""
    from app.db.models import User
    from sqlalchemy import select

    email = unique_email()
    token = await register_and_login(client, email)
    result = await db_session.execute(select(User).where(User.email == email))
    farmer = result.scalars().first()
    diag = await create_diagnosis_for_user(db_session, farmer.id)

    resp = await client.get(
        f"/api/v1/history/{diag.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_IT12_farmer_cannot_delete_others_record(client, db_session):
    """IT-12: Farmer B must not be able to delete Farmer A's diagnosis record."""
    from app.db.models import User
    from sqlalchemy import select

    email_a = unique_email()
    await register_and_login(client, email_a)
    result = await db_session.execute(select(User).where(User.email == email_a))
    farmer_a = result.scalars().first()
    diag_a = await create_diagnosis_for_user(db_session, farmer_a.id)

    token_b = await register_and_login(client)

    resp = await client.delete(
        f"/api/v1/history/{diag_a.id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    # Confirm the record still exists afterward
    result = await db_session.execute(select(DiagnosisHistory).where(DiagnosisHistory.id == diag_a.id))
    still_there = result.scalars().first()
    assert still_there is not None
