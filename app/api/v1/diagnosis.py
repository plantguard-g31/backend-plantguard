from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.db.base import get_db
from app.db.models import User, DiagnosisHistory, TreatmentRecord
from app.core.dependencies import get_current_user
from app.middleware.security import validate_upload_file
from app.services.quality_gate import run_quality_checks
from app.services.analytics import get_diagnosis_analytics
from app.services.treatment_mapper import classify_severity, get_treatment
from app.services.ai_client import predict_disease

logger = logging.getLogger("plantguard.diagnosis")
router = APIRouter(prefix="/diagnose", tags=["Diagnosis Pipeline"])

@router.post("/")
async def run_diagnosis(
    file: UploadFile = File(...),
    lang: str = Query(default="en", regex="^(en|ne)$"),
    minimal: bool = Query(False),
    crop_type: str = Query(default="tomato", regex="^(tomato|potato|bell_pepper)$"),  
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    
    try:
        # 1. SECURITY VALIDATION
        await validate_upload_file(file)
        
        # 2. QUALITY PRE-SCREENING
        await run_quality_checks(file)
        
        # 3. AI INFERENCE
        await file.seek(0)
        image_bytes = await file.read()
        
        ai_result = await predict_disease(image_bytes=image_bytes, filename=file.filename)
        if ai_result is None:
            raise HTTPException(status_code=503, detail="AI model unavailable. Please try again later.")
        
        disease_name = ai_result["disease"]
        confidence = float(ai_result["confidence"])
        
        # 4. ANALYTICS
        analytics = await get_diagnosis_analytics(user_id=str(current_user.id), db=db)
        
        # 5. SEVERITY CLASSIFICATION
        disease_count = len(analytics.get("disease_frequency", {}))
        severity = classify_severity(confidence, disease_count)
        
        # 6. TREATMENT LOOKUP
        treatment = await get_treatment(
            disease_name=disease_name, 
            crop_type=crop_type, 
            severity=severity, 
            db=db
        )
        
        if "error" in treatment:
            raise HTTPException(status_code=404, detail=treatment["error"])
        
        # Fetch treatment_id for history (nullable per normalized schema)
        treatment_record = await db.execute(
            select(TreatmentRecord.id)
            .where(TreatmentRecord.disease_name == disease_name)
            .where(TreatmentRecord.crop_type == crop_type)
            .limit(1)
        )
        treatment_id = treatment_record.scalar()  # Returns None if not found (safe)

        # 7. SAVE TO HISTORY
        new_diag = DiagnosisHistory(
            user_id=current_user.id,
            treatment_id=treatment_id,
            confidence_score=confidence,
            severity_level=severity,
            is_confidence_flag=confidence < 0.60
        )
        db.add(new_diag)
        await db.commit()
        
        # 8. BUILD RESPONSE
        response = {
            "disease": disease_name,
            "confidence": round(confidence, 2),
            "severity": severity,
            "pesticide": treatment.get("pesticide"),
            "dosage": treatment.get("dosage"),
            "application": treatment.get("application"),
            "safety_notes": treatment.get("safety_notes"),
            "source": treatment.get("source"),
            "low_confidence_warning": None if confidence >= 0.60 else "Confidence below 60%. Verify with an expert.",
            "analytics_warning": analytics.get("spreading_warning")
        }
        
        # 9. MINIMAL MODE
        if minimal:
            return {
                "disease": response["disease"],
                "confidence": response["confidence"],
                "severity": response["severity"],
                "pesticide": response["pesticide"]
            }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Diagnosis pipeline error: {type(e).__name__}: {e}", exc_info=True)
        raise