"""
Unit Tests -- Group B: Severity Classification (services/treatment_mapper.py)
Maps to STP Section 3.3.1, Test Cases UT-06 through UT-10.

NOTE ON CORRECTIONS: While writing these tests against the real
classify_severity() implementation, the actual thresholds turned out to
differ from what the STP originally assumed (the STP was drafted before
this file was read line-by-line). This is exactly the kind of discrepancy
real testing is supposed to catch:

  - STP originally assumed the "severe" threshold for confidence >= 0.80
    was disease_frequency == 3. The real code's threshold is
    disease_frequency >= 2. Tests below assert the REAL behaviour and this
    correction is logged as a finding in the Execution Report.
  - STP originally assumed confidence == 0.60 with frequency 0 returns
    "moderate". The real code returns "mild" at exactly 0.60 (the
    0.60-0.79 band), not "moderate" (which starts at 0.80). Corrected below.
"""
import pytest
from app.services.treatment_mapper import classify_severity


def test_UT06_first_time_diagnosis_can_never_be_severe():
    """UT-06: high confidence (0.95) on a first-time diagnosis (frequency=0)
    returns 'moderate', never 'severe'."""
    result = classify_severity(confidence=0.95, disease_frequency=0)
    assert result == "moderate"
    assert result != "severe"


def test_UT07_confidence_just_below_low_confidence_threshold():
    """UT-07: confidence=0.59 with frequency=0 falls into the function's own
    'low_confidence' category (below the 0.60 cutoff)."""
    result = classify_severity(confidence=0.59, disease_frequency=0)
    assert result == "low_confidence"


def test_UT08_confidence_exactly_at_threshold_first_time():
    """UT-08 (corrected): confidence=0.60 exactly, frequency=0, lands in the
    0.60-0.79 band -> 'mild', not 'moderate' (moderate requires >= 0.80)."""
    result = classify_severity(confidence=0.60, disease_frequency=0)
    assert result == "mild"


def test_UT09_severe_threshold_boundary_corrected():
    """UT-09 (corrected): for confidence >= 0.80, the real 'severe' threshold
    is disease_frequency >= 2, not >= 3 as originally assumed in the STP.
    frequency=1 -> 'moderate'; frequency=2 -> 'severe'."""
    result_freq1 = classify_severity(confidence=0.85, disease_frequency=1)
    result_freq2 = classify_severity(confidence=0.85, disease_frequency=2)
    assert result_freq1 == "moderate"
    assert result_freq2 == "severe"


@pytest.mark.asyncio
async def test_UT10_get_treatment_selects_correct_dosage_column(db_session):
    """UT-10: get_treatment() returns the dosage_moderate value when severity
    is 'moderate', for a real seeded treatment record."""
    from app.services.treatment_mapper import get_treatment
    from app.db.models import TreatmentRecord

    record = TreatmentRecord(
        disease_name="Tomato Early Blight",
        crop_type="tomato",
        severity_level="moderate",
        pesticide_name="Chlorothalonil",
        dosage_mild="1.5g/L",
        dosage_moderate="2.5g/L",
        dosage_severe="4.0g/L",
        application_timing="Early morning or late evening",
        safety_instructions="Wear gloves and mask",
        pre_harvest_interval_days=7,
        source_reference="FAO Plant Protection Manual 2023",
        is_active=True,
    )
    db_session.add(record)
    await db_session.commit()

    result = await get_treatment("Tomato Early Blight", "tomato", "moderate", db_session)
    assert result["dosage"] == "2.5g/L"
