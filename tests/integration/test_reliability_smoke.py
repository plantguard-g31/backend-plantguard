"""
Reliability Smoke Test -- Group O: NFR-12 (Scaled Proxy)
Maps to Master Test Plan Section 3.3.3, Test Case TC-RB-065.

HONESTY NOTE: NFR-12 requires zero unplanned crashes over a REAL 2-HOUR
continuous load window against a deployed instance. That full-duration test
cannot run inside a normal CI/pytest cycle and has NOT been executed here --
it remains genuinely Not Executed in the Test Execution Report and must be
run separately against a deployed environment (see Master Test Plan Section
3.3.1, Reliability risk note).

What THIS test provides instead is a scaled-down smoke proxy: 60 sequential
requests against the real in-process app (no real network/deployment
needed), confirming no unhandled exception / crash / connection leak occurs
across a sustained short burst. A Pass here is evidence the code path is
stable, NOT evidence the full 2-hour NFR-12 target has been met.
"""
import io
import pytest
from unittest.mock import AsyncMock
from app.db.models import TreatmentRecord
from tests.integration.test_diagnosis_pipeline import register_and_login, make_good_leaf_jpeg

MOCK_AI_RESULT = {
    "disease": "Tomato Early Blight", "confidence": 0.88, "is_healthy": False,
    "low_confidence": False, "warning": None,
    "top3": [{"rank": 1, "disease": "Tomato Early Blight", "confidence": 0.88}],
}


@pytest.mark.asyncio
async def test_IT31_TC_RB_065_scaled_smoke_no_crash_over_60_sequential_requests(client, db_session, monkeypatch):
    """Scaled proxy for TC-RB-065 / NFR-12. See module docstring: this is
    NOT a substitute for the full 2-hour soak test, which remains a
    separate, Not-Executed item pending a deployed environment."""
    monkeypatch.setattr(
        "app.api.v1.diagnosis.predict_disease",
        AsyncMock(return_value=MOCK_AI_RESULT)
    )
    db_session.add(TreatmentRecord(
        disease_name="Tomato Early Blight", crop_type="tomato", severity_level="moderate",
        pesticide_name="Chlorothalonil", dosage_mild="1.5g/L", dosage_moderate="2.5g/L",
        dosage_severe="4.0g/L", application_timing="Morning", safety_instructions="Wear gloves",
        pre_harvest_interval_days=7, source_reference="FAO 2023", is_active=True,
    ))
    await db_session.commit()

    errors = []
    for i in range(60):
        try:
            token = await register_and_login(client)
            headers = {"Authorization": f"Bearer {token}"}
            files = {"file": ("leaf.jpg", io.BytesIO(make_good_leaf_jpeg()), "image/jpeg")}
            resp = await client.post("/api/v1/diagnose/", files=files, headers=headers)
            assert resp.status_code in (200, 429)
        except Exception as e:  # noqa: BLE001 -- intentionally broad, this IS the crash detector
            errors.append((i, str(e)))

    assert not errors, f"{len(errors)} unhandled exceptions during the 60-request smoke run: {errors[:5]}"
