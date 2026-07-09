"""
Integration Test -- IT-08: Rate Limiting (Gate 4)
Maps to STP Section 3.3.2, Test Case IT-08.

NOTE ON DESIGN: rate_limit_middleware (app/middleware/security.py) is a
GLOBAL middleware applied to every route (except register/login/health/docs),
keyed by user_id extracted from the JWT -- not path-specific. This test uses
GET /api/v1/history/ rather than POST /api/v1/diagnose/ to isolate the rate
limiter itself from the diagnosis pipeline's other gates (file validation,
AI mocking), since the rate limit decision happens in middleware before the
route body is ever inspected. This still exercises the exact same shared
rate-limiting component the diagnosis endpoint uses.
"""
import pytest
from tests.integration.test_diagnosis_pipeline import register_and_login


@pytest.mark.asyncio
async def test_IT08_eleventh_request_within_60s_is_blocked(client):
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    statuses = []
    for _ in range(11):
        resp = await client.get("/api/v1/history/", headers=headers)
        statuses.append(resp.status_code)

    assert statuses[:10] == [200] * 10, f"Expected first 10 requests to succeed, got {statuses[:10]}"
    assert statuses[10] == 429, f"Expected the 11th request to be rate-limited, got {statuses[10]}"
