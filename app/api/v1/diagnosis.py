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
from app.services.localization import get_translated_treatment


logger = logging.getLogger("plantguard.diagnosis")
router = APIRouter(prefix="/diagnose", tags=["Diagnosis Pipeline"])

@router.post("/")
async def run_diagnosis(
    file: UploadFile = File(...),
    lang: str = Query(default="en", pattern="^(en|ne)$"),
    minimal: bool = Query(False),
    crop_type: str = Query(default="tomato", pattern="^(tomato|potato|bell_pepper)$"),  
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        # 1. SECURITY VALIDATION (Size + Magic Bytes)
        await validate_upload_file(file)
        
        # 2. QUALITY PRE-SCREENING (5 Checks - now returns scores)
        quality_result = await run_quality_checks(file)
        image_bytes = quality_result["content"]
        blur_score = quality_result["blur_score"]
        brightness = quality_result["brightness"]
        
        # 3. AI INFERENCE (DeiT-Tiny)
        ai_result = await predict_disease(image_bytes=image_bytes, filename=file.filename)
        if ai_result is None:
            raise HTTPException(status_code=503, detail="AI model unavailable. Please try again later.")
        
        disease_name = ai_result["disease"]
        confidence = float(ai_result["confidence"])
        is_healthy = ai_result.get("is_healthy", False)
        low_confidence_flag = ai_result.get("low_confidence", False)
        top3_predictions = ai_result.get("top3", [])
        expert_warning = ai_result.get("warning")
        
        # 4. ANALYTICS (30-day history)
        analytics = await get_diagnosis_analytics(user_id=str(current_user.id), db=db, crop_type=crop_type)
        # Use the dictionary for frequency lookup
        current_disease_freq = analytics.get("disease_frequency_dict", {}).get(disease_name, 0)

        # 5. SEVERITY CLASSIFICATION (Confidence x Frequency Matrix)
        if low_confidence_flag: # Confidence < 0.60
            severity = None
            treatment_severity = "moderate" # Fallback for DB lookup
        else:
            severity = classify_severity(confidence, current_disease_freq)
            treatment_severity = severity
       
        # 6. TREATMENT LOOKUP (Deterministic SQL)
        treatment = await get_treatment(
            disease_name=disease_name, 
            crop_type=crop_type, 
            severity=treatment_severity, 
            db=db
        )
        
        if "error" in treatment:
            raise HTTPException(status_code=404, detail=treatment["error"])
        
        # Fetch treatment_id for history (nullable per normalized schema)
        treatment_record = await db.execute(
            select(TreatmentRecord.id)
            .where(TreatmentRecord.disease_name == disease_name)
            .where(TreatmentRecord.crop_type == crop_type)
            .where(TreatmentRecord.severity_level == treatment_severity)
            .limit(1)
        )
        treatment_id = treatment_record.scalar()

        # Localization: Fetch nepali version if user choose 'ne' language)     
        translated = await get_translated_treatment(str(treatment_id), lang, db) if treatment_id else None

        # 7. SAVE TO HISTORY (ACID Transaction, SRS FR-16)
        new_diag = DiagnosisHistory(
            user_id=current_user.id,
            disease_label=disease_name,
            crop_type=crop_type,
            treatment_id=treatment_id,
            confidence=confidence,
            severity=severity, # Will be NULL if low confidence
            image_blur_score=blur_score,
            image_brightness=brightness,
            quality_passed=True,
            low_confidence_warning=low_confidence_flag
        )
        db.add(new_diag)
        await db.commit()

        translated = await get_translated_treatment(str(treatment_id), lang, db) if treatment_id else None
        
        # 8. BUILD RESPONSE
        response = {
            "disease": translated["disease_name"] if translated else disease_name,
            "confidence": round(confidence, 4),
            "is_healthy": is_healthy,
            "top3": top3_predictions,  # SRS FR-13: Top-3 predictions
            "severity": severity,
            "pesticide": treatment.get("pesticide"),
            "dosage": treatment.get("dosage"),
            "application_timing": translated["application_timing"] if translated else treatment.get("application_timing"),
            "safety_instructions": translated["safety_instructions"] if translated else treatment.get("safety_instructions"),
            "pre_harvest_interval_days": treatment.get("pre_harvest_interval_days"),
            "source_reference": treatment.get("source_reference"),
            "low_confidence_warning": expert_warning,
            "spreading_alert": analytics.get("spreading_alert")
        }
        
        # 9. MINIMAL MODE (SRS FR-19: Exactly 4 fields for 2G/3G)
        if minimal:
            treatment_summary = treatment.get("dosage", "No treatment required.") if not is_healthy else "Plant is healthy. Maintain current care."
            return {
                "disease": disease_name,
                "confidence": round(confidence, 4),
                "is_healthy": is_healthy,
                "treatment_summary": treatment_summary
            }
            
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Diagnosis pipeline error: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="server_error")