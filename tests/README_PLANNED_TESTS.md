# PlantGuard Backend — Planned Automated Test Suite (File 1)

**56 tests. All 56 currently PASS against the real backend code and a real PostgreSQL database.**
No mocked pass/fail results — every test in this folder was actually executed.

This is the "planned" test set: it covers the Functional and Non-Functional Requirements
documented in the Master Test Plan (`PlantGuard_Master_v6.2.docx`, Section 3.3.3), run as
real, automated pytest code instead of only being described on paper.

## How to run it yourself (for your report screenshot)

```bash
# 1. PostgreSQL running locally, with an empty test database
createdb plantguard_test

# 2. Python deps (heavy ML deps are NOT needed -- conftest.py stubs torch/timm/
#    huggingface_hub/supabase, since AI accuracy and photo storage are explicitly
#    out of scope for backend testing per the Master Test Plan, Section 2.2)
pip install fastapi==0.111.0 uvicorn "sqlalchemy==2.0.30" asyncpg pydantic \
    pydantic-settings PyJWT passlib bcrypt pytest pytest-asyncio httpx \
    python-multipart Pillow email-validator alembic opencv-python-headless numpy

# 3. Environment variables (a real .env also works; these are the minimum for tests)
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/plantguard_test"
export SYNC_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/plantguard_test"
export JWT_SECRET="any_random_32_byte_string_for_testing_only"
export SMTP_EMAIL="test@example.com"
export SMTP_APP_PASSWORD="testpass"
export SUPABASE_URL="https://fake.supabase.co"
export SUPABASE_KEY="fake_key"

# 4. Run everything
pytest tests/ -v
```

Expected result: `56 passed`.

## Coverage map (Test Case Plan / Master Test Plan traceability)

| Area | Test file | Real TC ID(s) covered | Status |
|---|---|---|---|
| Password hashing, JWT issue/expiry/tamper | `unit/test_auth_crypto.py` (UT01–05) | FR-03, NFR-04/05 (pre-existing) | 5 pass |
| Magic-byte / size / quality-gate validation | `unit/test_file_validation.py` (UT11–15) | FR-06, FR-07, FR-09 (pre-existing) | 5 pass |
| Severity matrix (confidence × frequency) | `unit/test_severity.py` (UT06–10) | FR-13 (pre-existing) | 5 pass |
| Admin hierarchy (Super Admin gate) | `integration/test_admin_hierarchy.py` (IT13–15) | FR-20, FR-22 (pre-existing) | 3 pass |
| Register/login/refresh/logout | `integration/test_auth_flow.py` (IT01–05) | FR-01–FR-04 (pre-existing) | 5 pass |
| DB cascade / SET NULL integrity | `integration/test_db_integrity.py` (IT16–17) | FR-14 (pre-existing) | 2 pass |
| Full diagnosis pipeline, gates 1–4 | `integration/test_diagnosis_pipeline.py` (IT06–10) | FR-05–FR-12 (pre-existing) | 5 pass |
| History IDOR protection | `integration/test_history_idor.py` (IT11–12) | FR-15 (pre-existing) | 3 pass |
| Rate limit (11th request blocked) | `integration/test_rate_limiting.py` (IT08) | NFR-06 (pre-existing) | 1 pass |
| **Change Password** | `integration/test_change_password.py` | **TC-RB-058, 059, 071** | 4 pass |
| **Forgot Password / OTP** | `integration/test_forgot_password_otp.py` | **TC-RB-061, 062, 072** | 5 pass |
| **Profile Photo upload/retrieval** | `integration/test_profile_photo.py` | **TC-RB-056, 057** | 3 pass |
| **Rate-limit window reset** | `unit/test_rate_limit_reset.py` | **TC-RB-073** | 2 pass |
| **Exact 5MB boundary (system-level)** | `unit/test_file_size_boundary.py` | **TC-RB-074** | 2 pass |
| **Pinned dependency versions** | `unit/test_dependency_pins.py` | **TC-RB-069** | 2 pass |
| **Quality-gate speed <200ms (genuine)** | `integration/test_performance_timing.py` | **TC-RB-064** | 1 pass |
| **Backend timing w/ AI mocked (partial)** | `integration/test_performance_timing.py` | **TC-RB-063** (partial, see caveat below) | 1 pass |
| **10 concurrent requests (partial)** | `integration/test_performance_timing.py` | **TC-RB-070** (partial, see caveat below) | 1 pass |
| **60-request reliability smoke (scaled)** | `integration/test_reliability_smoke.py` | **TC-RB-065** (scaled proxy, see caveat below) | 1 pass |
| **Total** | | | **56 pass** |

## What this suite deliberately does NOT claim (read before screenshotting into your report)

- **TC-RB-063 (NFR-02) and TC-RB-070 (NFR-03)** use a **mocked AI call** (per `conftest.py`'s
  documented design decision — real model inference is out of scope for backend testing).
  A Pass here proves the backend itself adds no bottleneck; it does **not** prove the full
  system meets the 3-second target with the real DeiT-Tiny model running. That claim still
  needs a timing run against a deployed instance.
- **TC-RB-065 (NFR-12)** here is a **60-request smoke proxy**, not the real 2-hour soak test.
  The full-duration test remains genuinely **Not Executed** in the TER until run against a
  deployed environment.
- **TC-ALL-008 (NFR-13, UAT timing with 5 human users)** is **not included** in this pytest
  suite at all — it cannot be automated; it requires real people using the Flutter app.
- Frontend-only planned cases (e.g. TC-JN-036–040 admin panel screens, i18n rendering checks)
  are **not included** here since they test the Flutter app, not this backend repository.

## Real findings surfaced while writing these tests (not assumptions)

1. **OTP validity is 15 minutes** (`OTP_EXPIRE_MINUTES=15` in `app/core/config.py`), not the
   5 minutes originally reported — corrected in the test assertions and should be corrected
   in the Master Test Plan / SRS wording too.
2. **Super Admin Hierarchy (F47/F48) is actually implemented** (`POST /admin/create-admin`,
   migration `b37425e57c90`) — the Sprint Backlog's "Not Implemented" label was wrong. The
   Master Test Plan's out-of-scope table needs correcting to bring this back into scope.
3. **`password_must_be_different` has no bilingual translation entry** in
   `error_handler.py`'s `ERROR_MESSAGES` dict — a real NFR-14 (bilingual errors) gap.
4. **A real-looking Resend API key is committed in `.env.example`** — recommend rotating it
   before submission regardless of test status.
