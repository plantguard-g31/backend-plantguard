from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import TreatmentTranslation

async def get_translated_treatment(treatment_id: str, lang: str, db: AsyncSession) -> dict:
    """
    Fetches Nepali translations if available, else falls back to English.
    """
    if lang == "en":
        return None  # Already in base record
    
    result = await db.execute(
        select(TreatmentTranslation)
        .where(TreatmentTranslation.treatment_id == treatment_id)
        .where(TreatmentTranslation.language_code == lang)
    )
    translations = result.scalars().all()
    
    translated = {}
    for t in translations:
        translated[t.field_name] = t.translated_text
    
    return translated if translated else None