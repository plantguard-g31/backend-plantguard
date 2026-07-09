from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import TreatmentTranslation
import logging

logger = logging.getLogger("plantguard.localization")

async def get_translated_treatment(treatment_record_id: str, lang: str, db: AsyncSession) -> dict | None:
    """
    Returns Nepali-translated fields for a treatment.
    Returns None if lang is 'en' or if no translation exists (fallback to English).
    """
    # 1. Short-circuit for English or missing ID
    if lang == "en" or not treatment_record_id:
        return None

    # 2. Query the database using the CORRECT column names from models.py
    result = await db.execute(
        select(TreatmentTranslation)
        .where(TreatmentTranslation.treatment_record_id == treatment_record_id) # FIX 1: Correct FK name
        .where(TreatmentTranslation.language_code == lang)
    )
    
    # FIX 2: Use .first() because UNIQUE constraint guarantees only 1 row per language
    t = result.scalars().first()

    if not t:
        logger.warning(f"No '{lang}' translation found for treatment {treatment_record_id}. Falling back to English.")
        return None

    # FIX 3: Map the actual database columns to standard dictionary keys
    return {
        "disease_name": t.disease_name_translated,
        "application_timing": t.treatment_instructions_translated,
        "safety_instructions": t.safety_warnings_translated,
    }