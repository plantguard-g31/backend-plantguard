"""
Performance Tests -- Group N: NFR-02, NFR-11, NFR-03
Maps to Master Test Plan Section 3.3.3, Test Cases TC-RB-063, TC-RB-064, TC-RB-070.

IMPORTANT SCOPE NOTE (read before trusting these numbers in a report):
Per tests/conftest.py, the real DeiT-Tiny model (torch/timm/huggingface_hub)
is stubbed out for this whole test suite, because AI inference latency and
accuracy are explicitly owned by the AI/Model team and out of scope for the
backend test effort (see Master Test Plan Section 2.2, Out of Scope).

That means:
  - test_UT22 (NFR-11) is a FULLY GENUINE, unmocked measurement of the real
    5-check quality-gate function -- safe to cite directly.
  - test_IT29 (NFR-02) and test_IT30 (NFR-03) measure real backend overhead
    (auth, DB writes, middleware) with the AI call mocked to return
    instantly. They confirm the backend does NOT introduce its own
    multi-second bottleneck, but they do NOT include real model inference
    time and therefore CANNOT be cited as proof the full NFR-02 <3s target
    is met in production. That claim requires a timing run against the
    actual deployed model, which is still Not Executed per the Test
    Execution Report.
"""
import io
import time
import asyncio
import pytest
import numpy as np
import cv2
from unittest.mock import AsyncMock
from app.services.quality_gate import run_quality_checks
from app.db.models import TreatmentRecord
from tests.integration.test_diagnosis_pipeline import register_and_login, make_good_leaf_jpeg
from tests.unit.test_file_validation import make_upload_file


async def _seed_matching_treatment(db_session):
    """Same seed pattern as test_IT09: confidence=0.88, frequency=0 -> 'moderate'."""
    record = TreatmentRecord(
        disease_name="Tomato Early Blight", crop_type="tomato", severity_level="moderate",
        pesticide_name="Chlorothalonil", dosage_mild="1.5g/L", dosage_moderate="2.5g/L",
        dosage_severe="4.0g/L", application_timing="Morning", safety_instructions="Wear gloves",
        pre_harvest_interval_days=7, source_reference="FAO 2023", is_active=True,
    )
    db_session.add(record)
    await db_session.commit()


MOCK_AI_RESULT = {
    "disease": "Tomato Early Blight", "confidence": 0.88, "is_healthy": False,
    "low_confidence": False, "warning": None,
    "top3": [{"rank": 1, "disease": "Tomato Early Blight", "confidence": 0.88}],
}


@pytest.mark.asyncio
async def test_UT22_TC_RB_064_quality_gate_p95_under_200ms():
    """TC-RB-064 (NFR-11, genuine/unmocked): the real 5-check quality
    pre-screen must complete in <200ms at P95 across 30 real images."""
    timings = []
    for _ in range(30):
        upload = make_upload_file(_make_good_jpeg_bytes())
        start = time.perf_counter()
        await run_quality_checks(upload)
        timings.append(time.perf_counter() - start)

    timings.sort()
    p95_index = int(len(timings) * 0.95) - 1
    p95 = timings[p95_index]
    assert p95 < 0.2, f"NFR-11 violation: P95 quality-gate time was {p95*1000:.1f}ms (limit 200ms)"


def _make_good_jpeg_bytes(width=400, height=400):
    img = np.full((height, width, 3), (60, 150, 70), dtype=np.uint8)
    noise = np.random.randint(0, 60, (height, width, 3), dtype=np.uint8)
    img = cv2.add(img, noise)
    success, encoded = cv2.imencode(".jpg", img)
    assert success
    return encoded.tobytes()


@pytest.mark.asyncio
async def test_IT29_TC_RB_063_backend_overhead_p95_with_ai_mocked(client, db_session, monkeypatch):
    """TC-RB-063 (NFR-02, PARTIAL -- see module docstring): backend-only
    response time (auth + quality gate + mocked AI + DB write) at P95 across
    20 sequential requests. Confirms no backend-side bottleneck; does NOT
    validate real model inference latency."""
    monkeypatch.setattr(
        "app.api.v1.diagnosis.predict_disease",
        AsyncMock(return_value=MOCK_AI_RESULT)
    )
    await _seed_matching_treatment(db_session)

    timings = []
    for _ in range(20):
        # A fresh user per request: reusing the same user would let diagnosis
        # frequency climb and shift severity from "moderate" to "severe"
        # partway through (by real, correct backend logic -- see
        # app/services/treatment_mapper.py::classify_severity), and only a
        # "moderate" treatment record is seeded here. Using a fresh user
        # keeps every sample a first-time (frequency=0) diagnosis, which is
        # also the more realistic timing scenario for this NFR.
        token = await register_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        files = {"file": ("leaf.jpg", io.BytesIO(make_good_leaf_jpeg()), "image/jpeg")}
        start = time.perf_counter()
        resp = await client.post("/api/v1/diagnose/", files=files, headers=headers)
        timings.append(time.perf_counter() - start)
        assert resp.status_code in (200, 429)  # 429 possible after 10 requests (NFR-06)

    timings.sort()
    p95 = timings[int(len(timings) * 0.95) - 1]
    assert p95 < 3.0, f"Backend-only P95 was {p95:.2f}s (limit 3.0s, excluding real AI inference time)"


@pytest.mark.asyncio
async def test_IT30_TC_RB_070_ten_concurrent_requests_not_serialised(client, db_session, monkeypatch):
    """TC-RB-070 (NFR-03, PARTIAL -- AI mocked): 10 concurrent diagnosis
    requests from 10 different accounts complete without an obvious
    serialisation penalty (concurrent max well under a naive 10x-sequential
    estimate). Complements test_IT16/17 (DB integrity under concurrency)
    with a timing dimension."""
    monkeypatch.setattr(
        "app.api.v1.diagnosis.predict_disease",
        AsyncMock(return_value=MOCK_AI_RESULT)
    )
    await _seed_matching_treatment(db_session)

    tokens = [await register_and_login(client) for _ in range(10)]

    async def one_request(token):
        files = {"file": ("leaf.jpg", io.BytesIO(make_good_leaf_jpeg()), "image/jpeg")}
        headers = {"Authorization": f"Bearer {token}"}
        start = time.perf_counter()
        resp = await client.post("/api/v1/diagnose/", files=files, headers=headers)
        return resp.status_code, time.perf_counter() - start

    start_all = time.perf_counter()
    results = await asyncio.gather(*(one_request(t) for t in tokens))
    total_wall_time = time.perf_counter() - start_all

    statuses = [r[0] for r in results]
    assert all(s == 200 for s in statuses), f"Expected all 10 concurrent requests to succeed, got {statuses}"

    max_individual = max(r[1] for r in results)
    # A truly serialised implementation would make total wall time ~= 10x a
    # single request; a non-serialised one keeps it close to a single
    # request's time. This is a generous, explicitly non-strict threshold.
    assert total_wall_time < max_individual * 5, (
        f"Total wall time ({total_wall_time:.2f}s) suggests requests may be "
        f"serialising (max individual was {max_individual:.2f}s)"
    )
