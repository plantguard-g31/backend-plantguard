"""
Unit Test -- Group K: Rate Limit Window Reset Behaviour (NFR-06)
Maps to Master Test Plan Section 3.3.3, Test Case TC-RB-073.

Tests app/middleware/security.py::check_rate_limit directly (whitebox) with
a controlled clock, rather than making a real integration test sleep for a
real 61 seconds. This exercises exactly the same function the live
rate_limit_middleware calls (see test_IT08_eleventh_request_within_60s_is_blocked
for the integration-level version of the "blocked at 11" half of this
behaviour); this test adds the previously-uncovered "resets after the window
elapses" half.
"""
import time
import uuid
from app.middleware import security as security_module
from app.middleware.security import check_rate_limit


def test_UT16_TC_RB_073_rate_limit_resets_after_window_elapses(monkeypatch):
    user_id = f"test-user-{uuid.uuid4()}"

    fake_now = [1_000_000.0]
    monkeypatch.setattr(time, "time", lambda: fake_now[0])

    # Exhaust all 10 tokens (RATE_LIMIT_TOKENS=10 per .env)
    for _ in range(10):
        assert check_rate_limit(user_id) is True

    # 11th request at the same instant must be blocked
    assert check_rate_limit(user_id) is False

    # Advance the clock by 61 seconds (past RATE_LIMIT_WINDOW=60)
    fake_now[0] += 61

    # The window has elapsed -> the very next request must succeed again
    assert check_rate_limit(user_id) is True, (
        "Expected the rate limit to reset once the 60-second window elapsed, "
        "but the account remained blocked."
    )

    # Cleanup: don't leak state into other tests sharing the module-level dict
    security_module._rate_limits.pop(user_id, None)


def test_UT17_rate_limit_independent_per_account(monkeypatch):
    """Sanity companion check: exhausting one account's limit does not
    affect a different account (NFR-06's 'independent per account' clause)."""
    user_a = f"test-user-a-{uuid.uuid4()}"
    user_b = f"test-user-b-{uuid.uuid4()}"

    for _ in range(10):
        assert check_rate_limit(user_a) is True
    assert check_rate_limit(user_a) is False

    # A fresh account should still have its full allowance
    assert check_rate_limit(user_b) is True

    security_module._rate_limits.pop(user_a, None)
    security_module._rate_limits.pop(user_b, None)
