from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import TreatmentRecord

def classify_severity(confidence: float, disease_frequency: int) -> str:
   
    # First-Time Diagnosis (frequency = 0)
    if disease_frequency == 0:
        if confidence < 0.60:
            return "low_confidence" # Handled separately in diagnosis.py
        elif 0.60 <= confidence <= 0.79:
            return "mild"
        elif confidence >= 0.80:
            return "moderate" # First-time cannot be severe
            
    # Returning Diagnosis (frequency >= 1)
    else:
        # Severe conditions
        if (confidence >= 0.80 and disease_frequency >= 2) or \
           (confidence >= 0.60 and disease_frequency >= 4):
            return "severe"
            
        # Moderate conditions
        if (confidence >= 0.80 and disease_frequency == 1) or \
           (0.60 <= confidence <= 0.79 and 2 <= disease_frequency <= 3):
            return "moderate"
            
        # Mild conditions
        if 0.60 <= confidence <= 0.79 and disease_frequency == 1:
            return "mild"

    # Fallback
    return "moderate"

async def get_treatment(disease_name: str, crop_type: str, severity: str, db: AsyncSession) -> dict:

    result = await db.execute(
        select(TreatmentRecord)
        .where(TreatmentRecord.disease_name == disease_name)
        .where(TreatmentRecord.crop_type == crop_type)
        .where(TreatmentRecord.severity_level == severity)
        .where(TreatmentRecord.is_active == True)
    )
    record = result.scalars().first()
    
    if not record:
        return {"error": "Treatment not found in database for this severity level."}
        
    # Dynamically select the correct dosage column based on severity
    dosage_column = f"dosage_{severity}"
    selected_dosage = getattr(record, dosage_column, record.dosage_moderate)
    
    return {
        "disease": record.disease_name,
        "crop": record.crop_type,
        "severity": severity,
        "pesticide": record.pesticide_name,
        "dosage": selected_dosage,
        "application_timing": record.application_timing,
        "safety_instructions": record.safety_instructions,
        "pre_harvest_interval_days": record.pre_harvest_interval_days,
        "source_reference": record.source_reference
    }