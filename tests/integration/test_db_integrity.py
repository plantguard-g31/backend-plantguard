"""
Integration Tests -- Group E: Database Relationship Integrity
Maps to STP Section 3.3.2, Test Cases IT-16, IT-17.
Verifies the CASCADE / SET NULL foreign-key behaviour documented in the
Software Design Document, Section 6.3, against a real PostgreSQL database.
"""
import pytest
from sqlalchemy import select
from app.db.models import User, TreatmentRecord, DiagnosisHistory
from app.core.security import hash_password
from tests.conftest import unique_email


@pytest.mark.asyncio
async def test_IT16_deleting_treatment_preserves_history_via_set_null(db_session):
    """IT-16: deleting a treatment_records row must not delete the
    diagnosis_history rows that reference it -- treatment_id should become
    NULL (SET NULL), not cascade-delete the farmer's history."""
    treatment = TreatmentRecord(
        disease_name="Bell Pepper Bacterial Spot", crop_type="bell_pepper", severity_level="mild",
        pesticide_name="Copper Hydroxide", dosage_mild="1.2g/L", dosage_moderate="2.2g/L",
        dosage_severe="3.8g/L", application_timing="Morning", safety_instructions="Wear gloves",
        pre_harvest_interval_days=6, source_reference="FAO 2023", is_active=True,
    )
    db_session.add(treatment)
    await db_session.commit()
    await db_session.refresh(treatment)

    farmer = User(name="Test Farmer", email=unique_email(), password_hash=hash_password("x"), role="farmer")
    db_session.add(farmer)
    await db_session.commit()
    await db_session.refresh(farmer)

    diagnosis = DiagnosisHistory(
        user_id=farmer.id, disease_label="Bell Pepper Bacterial Spot", crop_type="bell_pepper",
        treatment_id=treatment.id, confidence=0.80, severity="mild",
        image_blur_score=100.0, image_brightness=100.0, quality_passed=True, low_confidence_warning=False,
    )
    db_session.add(diagnosis)
    await db_session.commit()
    diagnosis_id = diagnosis.id

    await db_session.delete(treatment)
    await db_session.commit()

    result = await db_session.execute(select(DiagnosisHistory).where(DiagnosisHistory.id == diagnosis_id))
    surviving_diagnosis = result.scalars().first()
    assert surviving_diagnosis is not None, "History row was deleted -- expected SET NULL, not CASCADE"
    assert surviving_diagnosis.treatment_id is None


@pytest.mark.asyncio
async def test_IT17_deleting_user_cascades_to_diagnosis_history(db_session):
    """IT-17: deleting a users row must CASCADE delete their diagnosis_history rows."""
    farmer = User(name="Test Farmer", email=unique_email(), password_hash=hash_password("x"), role="farmer")
    db_session.add(farmer)
    await db_session.commit()
    await db_session.refresh(farmer)

    for i in range(2):
        diagnosis = DiagnosisHistory(
            user_id=farmer.id, disease_label=f"Disease {i}", crop_type="tomato",
            confidence=0.80, severity="mild",
            image_blur_score=100.0, image_brightness=100.0, quality_passed=True, low_confidence_warning=False,
        )
        db_session.add(diagnosis)
    await db_session.commit()

    farmer_id = farmer.id
    await db_session.delete(farmer)
    await db_session.commit()

    result = await db_session.execute(select(DiagnosisHistory).where(DiagnosisHistory.user_id == farmer_id))
    remaining = result.scalars().all()
    assert len(remaining) == 0, f"Expected CASCADE delete, but {len(remaining)} history rows survived"
