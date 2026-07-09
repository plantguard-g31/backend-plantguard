from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from app.db.base import get_db
from app.db.models import User, TreatmentRecord, TreatmentTranslation
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/treatments", tags=["Treatments (Farmer)"])

@router.get("/library")
async def get_treatment_library(
    crop_type: Optional[str] = Query(None, pattern="^(tomato|potato|bell_pepper)$"),
    search: Optional[str] = Query(None, min_length=2),
    lang: str = Query("en", pattern="^(en|ne)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Browse the FAO Treatment Library.
    Accessible to all logged-in users (Farmers & Admins).
    Supports filtering by crop and searching by disease name.
    """
    try:
        # 1. Base Query: Fetch only ACTIVE treatments
        query = select(TreatmentRecord).where(TreatmentRecord.is_active == True)

        # 2. Apply Filters
        if crop_type:
            query = query.where(TreatmentRecord.crop_type == crop_type)
        
        if search:
            # Case-insensitive search
            query = query.where(func.lower(TreatmentRecord.disease_name).contains(search.lower()))

        # 3. Execute Query
        result = await db.execute(query)
        treatments = result.scalars().all()

        if not treatments:
            return {"total": 0, "items": []}

        # 4. Localization Logic (Optimized)
        # If user wants Nepali, fetch translations for ONLY the treatments we found
        translation_map = {}
        if lang == "ne":
            treatment_ids = [str(t.id) for t in treatments]
            trans_query = select(TreatmentTranslation).where(
                TreatmentTranslation.treatment_record_id.in_(treatment_ids),
                TreatmentTranslation.language_code == "ne"
            )
            trans_result = await db.execute(trans_query)
            translations = trans_result.scalars().all()
            
            # Create a map: { treatment_id: translation_object }
            for t in translations:
                translation_map[str(t.treatment_record_id)] = t

        # 5. Build Response
        items = []
        for t in treatments:
            trans = translation_map.get(str(t.id))
            
            # Use Nepali if available and requested, else fallback to English
            disease_display = trans.disease_name_translated if trans else t.disease_name
            timing_display = trans.treatment_instructions_translated if trans else t.application_timing
            safety_display = trans.safety_warnings_translated if trans else t.safety_instructions

            items.append({
                "id": str(t.id),
                "disease_name": disease_display,
                "original_disease_name": t.disease_name, # Keep English for search context
                "crop_type": t.crop_type,
                "severity_level": t.severity_level,
                "pesticide_name": t.pesticide_name,
                "dosage": {
                    "mild": t.dosage_mild,
                    "moderate": t.dosage_moderate,
                    "severe": t.dosage_severe
                },
                "application_timing": timing_display,
                "safety_instructions": safety_display,
                "pre_harvest_interval_days": t.pre_harvest_interval_days,
                "source_reference": t.source_reference
            })

        return {
            "total": len(items),
            "language": lang,
            "items": items
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch treatments: {str(e)}")