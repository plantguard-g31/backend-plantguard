from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.db.models import DiagnosisHistory, TreatmentRecord, User
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
        result = await db.execute(
            select(
                DiagnosisHistory,
                TreatmentRecord.disease_name,
                TreatmentRecord.crop_type
            )
            .join(TreatmentRecord, DiagnosisHistory.treatment_id == TreatmentRecord.id, isouter=True)
            .where(DiagnosisHistory.user_id == current_user.id)
            .order_by(DiagnosisHistory.diagnosed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        records = result.all()
        
        return {
            "total": len(records),
            "limit": limit,
            "offset": offset,
            "has_more": len(records) == limit,
            "items": [
                {
                    "id": str(h.id),
                    "disease": d_name or "Unknown",  # Handle NULL treatment_id
                    "crop": d_crop or "Unknown",
                    "confidence": h.confidence,
                    "severity": h.severity,
                    "low_confidence_warning": h.low_confidence_warning,
                    "diagnosed_at": h.diagnosed_at.isoformat() if h.diagnosed_at else None
                }
                for h, d_name, d_crop in records
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
        # 1. UPDATE THE QUERY: Fetch all necessary treatment columns
        result = await db.execute(
            select(
                DiagnosisHistory,
                TreatmentRecord.disease_name,
                TreatmentRecord.crop_type,
                TreatmentRecord.pesticide_name,
                TreatmentRecord.dosage_mild,
                TreatmentRecord.dosage_moderate,
                TreatmentRecord.dosage_severe,
                TreatmentRecord.application_timing,
                TreatmentRecord.safety_instructions,
                TreatmentRecord.pre_harvest_interval_days,
            )
            .join(TreatmentRecord, DiagnosisHistory.treatment_id == TreatmentRecord.id, isouter=True)
            .where(DiagnosisHistory.id == history_id)
            .where(DiagnosisHistory.user_id == current_user.id)
        )
        
        row = result.first()
        if not row:
            raise HTTPException(status_code=404, detail="Diagnosis history not found")
        
        # 2. UNPACK THE ROW: Assign all the new variables
        h, d_name, d_crop, pesticide, dose_mild, dose_mod, dose_sev, app_timing, safety, phi = row
        
        # 3. SMART DOSAGE LOGIC: Pick the right dosage based on the historical severity
        if h.severity == "mild":
            final_dosage = dose_mild
        elif h.severity == "severe":
            final_dosage = dose_sev
        else:
            final_dosage = dose_mod  # Default to moderate if null or moderate
            
        # 4. RETURN THE FULL DICTIONARY
        return {
            "id": str(h.id),
            "disease": d_name or "Unknown",
            "crop": d_crop or "Unknown",
            "confidence": h.confidence,
            "severity": h.severity,
            "is_confidence_flag": h.low_confidence_warning,
            "diagnosed_at": h.diagnosed_at.isoformat() if h.diagnosed_at else None,
            # --- NEW REMEDY FIELDS ---
            "pesticide_name": pesticide,
            "dosage": final_dosage,
            "application_timing": app_timing,
            "safety_instructions": safety,
            "pre_harvest_interval_days": phi,
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
    # 1. Find the record
    result = await db.execute(
        select(DiagnosisHistory).where(DiagnosisHistory.id == history_id)
    )
    record = result.scalars().first()
    
    # 2. Check if it exists
    if not record:
        raise HTTPException(status_code=404, detail="Diagnosis history not found")
        
    # 3. Security Check: Ensure user owns this record (Prevents IDOR vulnerability)
    if str(record.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="You do not have permission to delete this record.")
        
    # 4. Delete and commit
    await db.delete(record)
    await db.commit()
    
    # 204 No Content means success, but returns empty body (saves bandwidth for 2G/3G)
    return None 