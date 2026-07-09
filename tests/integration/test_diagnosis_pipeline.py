"""
Integration Tests -- Group B: Diagnosis Pipeline (full gate chain)
Maps to STP Section 3.3.2, Test Cases IT-06 through IT-10.
"""
import io
import pytest
import numpy as np
import cv2
from unittest.mock import AsyncMock
from sqlalchemy import select
from app.db.models import TreatmentRecord, DiagnosisHistory
from tests.conftest import unique_email


def make_good_leaf_jpeg(width=400, height=400):
    """A sharp, well-lit, green image that passes the quality gate."""
    img = np.full((height, width, 3), (60, 150, 70), dtype=np.uint8)
    noise = np.random.randint(0, 60, (height, width, 3), dtype=np.uint8)
    img = cv2.add(img, noise)
    success, encoded = cv2.imencode(".jpg", img)
    assert success
    return encoded.tobytes()


async def register_and_login(client, email=None):
    email = email or unique_email()
    await client.post("/api/v1/auth/register", json={
        "name": "Test Farmer", "email": email,
        "password": "Farmer@2026", "confirm_password": "Farmer@2026"
    })
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Farmer@2026"})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_IT06_unauthenticated_request_blocked_at_gate1(client, monkeypatch):
    """IT-06 (corrected): no Authorization header at all -> 403, not 401.

    FINDING: FastAPI's HTTPBearer() security scheme returns 403 Forbidden
    when the Authorization header is missing entirely, and reserves 401
    Unauthorized for the case where a header IS present but the token is
    invalid/expired (see UT-04/UT-05, and IT-06b below). This is FastAPI's
    documented default behaviour, not a bug, but it is a REST-semantics
    inconsistency worth a deliberate team decision (see Execution Report
    finding log) -- strictly, "no credentials provided" is usually modeled
    as 401, with 403 reserved for "authenticated but not permitted".
    The important security property -- that the quality gate is never
    reached without valid auth -- still holds either way, which is what
    this test actually verifies.
    """
    called = {"quality_gate": False}

    async def spy_quality_checks(file):
        called["quality_gate"] = True
        return {}

    monkeypatch.setattr("app.api.v1.diagnosis.run_quality_checks", spy_quality_checks)

    files = {"file": ("leaf.jpg", io.BytesIO(make_good_leaf_jpeg()), "image/jpeg")}
    resp = await client.post("/api/v1/diagnose/", files=files)
    assert resp.status_code == 403
    assert called["quality_gate"] is False


@pytest.mark.asyncio
async def test_IT06b_invalid_token_present_is_401(client, monkeypatch):
    """IT-06b (supplementary): an Authorization header WITH an invalid token
    correctly returns 401, confirming decode_token()'s own error path."""
    called = {"quality_gate": False}

    async def spy_quality_checks(file):
        called["quality_gate"] = True
        return {}

    monkeypatch.setattr("app.api.v1.diagnosis.run_quality_checks", spy_quality_checks)

    files = {"file": ("leaf.jpg", io.BytesIO(make_good_leaf_jpeg()), "image/jpeg")}
    resp = await client.post(
        "/api/v1/diagnose/", files=files,
        headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401
    assert called["quality_gate"] is False


@pytest.mark.asyncio
async def test_IT07_disguised_file_blocked_at_gate2_after_gate1_passes(client):
    """IT-07: valid auth, but a disguised .exe file -> 415 (auth passed, file validation caught it)."""
    token = await register_and_login(client)
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100
    files = {"file": ("photo.jpg", io.BytesIO(fake_exe), "image/jpeg")}
    resp = await client.post(
        "/api/v1/diagnose/", files=files,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_IT09_full_happy_path_writes_complete_history_record(client, db_session, monkeypatch):
    """IT-09: mocked AI + seeded treatment -> 200 with diagnosis+treatment,
    and a real diagnosis_history row is written linking to the right treatment."""
    mock_ai_result = {
        "disease": "Tomato Early Blight", "confidence": 0.88, "is_healthy": False,
        "low_confidence": False, "warning": None,
        "top3": [{"rank": 1, "disease": "Tomato Early Blight", "confidence": 0.88}],
    }
    monkeypatch.setattr(
        "app.api.v1.diagnosis.predict_disease",
        AsyncMock(return_value=mock_ai_result)
    )

    # Seed a matching treatment record (confidence 0.88, frequency 0 -> "moderate")
    record = TreatmentRecord(
        disease_name="Tomato Early Blight", crop_type="tomato", severity_level="moderate",
        pesticide_name="Chlorothalonil", dosage_mild="1.5g/L", dosage_moderate="2.5g/L",
        dosage_severe="4.0g/L", application_timing="Morning", safety_instructions="Wear gloves",
        pre_harvest_interval_days=7, source_reference="FAO 2023", is_active=True,
    )
    db_session.add(record)
    await db_session.commit()

    email = unique_email()
    token = await register_and_login(client, email)
    files = {"file": ("leaf.jpg", io.BytesIO(make_good_leaf_jpeg()), "image/jpeg")}
    resp = await client.post(
        "/api/v1/diagnose/", files=files,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["disease"] == "Tomato Early Blight"
    assert body["severity"] == "moderate"
    assert body["dosage"] == "2.5g/L"

    result = await db_session.execute(select(DiagnosisHistory).where(DiagnosisHistory.disease_label == "Tomato Early Blight"))
    history_row = result.scalars().first()
    assert history_row is not None
    assert history_row.treatment_id == record.id


@pytest.mark.asyncio
async def test_IT10_low_confidence_result_still_returns_200_with_warning(client, db_session, monkeypatch):
    """IT-10: AI mocked with confidence=0.45 -> 200, low_confidence_warning set, severity is None.
    Note: the low-confidence path still performs a treatment lookup using a
    'moderate' fallback severity (see diagnosis.py), so a matching treatment
    record must exist or the route 404s before we can observe this behaviour."""
    mock_ai_result = {
        "disease": "Tomato Early Blight", "confidence": 0.45, "is_healthy": False,
        "low_confidence": True, "warning": "Low confidence -- consider retaking the photo.",
        "top3": [{"rank": 1, "disease": "Tomato Early Blight", "confidence": 0.45}],
    }
    monkeypatch.setattr(
        "app.api.v1.diagnosis.predict_disease",
        AsyncMock(return_value=mock_ai_result)
    )
    record = TreatmentRecord(
        disease_name="Tomato Early Blight", crop_type="tomato", severity_level="moderate",
        pesticide_name="Chlorothalonil", dosage_mild="1.5g/L", dosage_moderate="2.5g/L",
        dosage_severe="4.0g/L", application_timing="Morning", safety_instructions="Wear gloves",
        pre_harvest_interval_days=7, source_reference="FAO 2023", is_active=True,
    )
    db_session.add(record)
    await db_session.commit()

    token = await register_and_login(client)
    files = {"file": ("leaf.jpg", io.BytesIO(make_good_leaf_jpeg()), "image/jpeg")}
    resp = await client.post(
        "/api/v1/diagnose/", files=files,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["severity"] is None
    assert body["low_confidence_warning"] is not None
