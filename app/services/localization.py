from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import TreatmentTranslation

async def get_translated_treatment(treatment_record_id: str, lang: str, db: AsyncSession) -> dict | None:
    """Returns Nepali-translated fields for a treatment, or None if English or no translation exists."""
    if lang == "en" or not treatment_record_id:
        return None

    result = await db.execute(
        select(TreatmentTranslation)
        .where(TreatmentTranslation.treatment_record_id == treatment_record_id)
        .where(TreatmentTranslation.language_code == lang)
    )
    t = result.scalars().first()
    if not t:
        return None

    return {
        "disease_name": t.disease_name_translated,
        "application_timing": t.treatment_instructions_translated,
        "safety_instructions": t.safety_warnings_translated,
    }