from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.db.models import DiagnosisHistory, TreatmentRecord, TreatmentTranslation, User
from app.core.dependencies import get_current_user
from fastapi import status

router = APIRouter(prefix="/history", tags=["History"])

@router.get("/")
async def get_user_history(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve paginated diagnosis history for authenticated user."""
    try:
        # Get user's preferred language
        lang = current_user.language_pref

        result = await db.execute(
            select(
                DiagnosisHistory,
                TreatmentRecord.disease_name,
                TreatmentRecord.crop_type,
                TreatmentRecord.id  # Need ID to fetch translation
            )
            .join(TreatmentRecord, DiagnosisHistory.treatment_id == TreatmentRecord.id, isouter=True)
            .where(DiagnosisHistory.user_id == current_user.id)
            .order_by(DiagnosisHistory.diagnosed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        records = result.all()
        
        # Fetch translations if user prefers Nepali
        translation_map = {}
        if lang == "ne":
            treatment_ids = [r[2] for r in records if r[2] is not None] # r[2] is TreatmentRecord.id
            if treatment_ids:
                trans_result = await db.execute(
                    select(TreatmentTranslation).where(
                        TreatmentTranslation.treatment_record_id.in_(treatment_ids),
                        TreatmentTranslation.language_code == "ne"
                    )
                )
                for t in trans_result.scalars().all():
                    translation_map[str(t.treatment_record_id)] = t

        return {
            "total": len(records),
            "limit": limit,
            "offset": offset,
            "has_more": len(records) == limit,
            "items": [
                {
                    "id": str(h.id),
                    # If Nepali and translation exists, use translated disease name, else fallback to English
                    "disease": translation_map[str(t_id)].disease_name_translated if (lang == "ne" and t_id and str(t_id) in translation_map) else (d_name or "Unknown"),
                    "crop": d_crop or "Unknown",
                    "confidence": h.confidence,
                    "severity": h.severity,
                    "low_confidence_warning": h.low_confidence_warning,
                    "diagnosed_at": h.diagnosed_at.isoformat() if h.diagnosed_at else None
                }
                for h, d_name, d_crop, t_id in records
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")

@router.get("/{history_id}")
async def get_history_item(
    history_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a single diagnosis history record by ID."""
    try:
        # 1. Get the user's preferred language
        lang = current_user.language_pref

        # 2. Fetch the base diagnosis and treatment record
        result = await db.execute(
            select(DiagnosisHistory, TreatmentRecord)
            .join(TreatmentRecord, DiagnosisHistory.treatment_id == TreatmentRecord.id, isouter=True)
            .where(DiagnosisHistory.id == history_id)
            .where(DiagnosisHistory.user_id == current_user.id)
        )
        
        row = result.first()
        if not row:
            raise HTTPException(status_code=404, detail="Diagnosis history not found")
        
        h, treatment_record = row
        
        if not treatment_record:
            # No treatment record linked (e.g., healthy plant or missing data)
            return {
                "id": str(h.id),
                "disease": h.disease_label,
                "crop": h.crop_type,
                "confidence": h.confidence,
                "severity": h.severity,
                "low_confidence_warning": h.low_confidence_warning,
                "diagnosed_at": h.diagnosed_at.isoformat() if h.diagnosed_at else None,
                "pesticide_name": "N/A",
                "dosage": "N/A",
                "application_timing": "N/A",
                "safety_instructions": "N/A",
                "pre_harvest_interval_days": 0,
            }

        # 3. Default to English values
        pesticide_name = treatment_record.pesticide_name
        app_timing = treatment_record.application_timing
        safety = treatment_record.safety_instructions
        disease_display = treatment_record.disease_name

        # 4. If user prefers Nepali, fetch translations
        if lang == "ne":
            trans_result = await db.execute(
                select(TreatmentTranslation).where(
                    TreatmentTranslation.treatment_record_id == treatment_record.id,
                    TreatmentTranslation.language_code == "ne"
                )
            )
            trans = trans_result.scalars().first()
            
            if trans:
                disease_display = trans.disease_name_translated
                app_timing = trans.treatment_instructions_translated
                safety = trans.safety_warnings_translated
                # Note: Chemical names (pesticide_name) are usually kept in English 
                # as they are specific chemical compounds, but you can add a 
                # pesticide_name_translated column later if needed.

        # 5. Smart Dosage Logic: Pick the right dosage based on the historical severity
        if h.severity == "mild":
            final_dosage = treatment_record.dosage_mild
        elif h.severity == "severe":
            final_dosage = treatment_record.dosage_severe
        else:
            final_dosage = treatment_record.dosage_moderate
            
        # 6. Return the Full Dictionary (Now Language-Aware!)
        return {
            "id": str(h.id),
            "disease": disease_display,
            "crop": treatment_record.crop_type,
            "confidence": h.confidence,
            "severity": h.severity,
            "low_confidence_warning": h.low_confidence_warning,
            "diagnosed_at": h.diagnosed_at.isoformat() if h.diagnosed_at else None,
            "pesticide_name": pesticide_name,
            "dosage": final_dosage,
            "application_timing": app_timing,
            "safety_instructions": safety,
            "pre_harvest_interval_days": treatment_record.pre_harvest_interval_days,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history item: {str(e)}")

@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_item(
    history_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """FR-17: Delete a diagnosis record. Scoped to authenticated user only."""
    result = await db.execute(
        select(DiagnosisHistory).where(DiagnosisHistory.id == history_id)
    )
    record = result.scalars().first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Diagnosis history not found")
        
    if str(record.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="You do not have permission to delete this record.")
        
    await db.delete(record)
    await db.commit()
    
    return None