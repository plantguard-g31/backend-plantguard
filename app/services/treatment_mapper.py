from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import TreatmentRecord

def classify_severity(confidence: float, disease_count_30d: int) -> str:
    """
    Maps confidence + history to severity tier.
    """
    if confidence < 0.75 or disease_count_30d >= 3:
        return "severe"
    elif confidence >= 0.90:
        return "mild"
    else:
        return "moderate"

async def get_treatment(disease_name: str, crop_type: str, severity: str, db: AsyncSession) -> dict:
    """
    Fetches expert-verified treatment matching disease + crop.
    Selects dosage based on severity tier (mild/moderate/severe).
    """
    # Query by disease + crop (composite unique key)
    result = await db.execute(
        select(TreatmentRecord)
        .where(TreatmentRecord.disease_name == disease_name)
        .where(TreatmentRecord.crop_type == crop_type)
    )
    record = result.scalars().first()
    
    if not record:
        return {"error": "Treatment not found in database"}
    
    # Select dosage based on severity column
    dosage_map = {
        "mild": record.dosage_mild,
        "moderate": record.dosage_moderate,
        "severe": record.dosage_severe
    }
    selected_dosage = dosage_map.get(severity, record.dosage_moderate)  # Fallback to moderate
    
    return {
        "disease": record.disease_name,
        "crop": record.crop_type,
        "severity": severity,
        "pesticide": record.pesticide_name,
        "dosage": selected_dosage,
        "application": record.application_method,
        "safety_notes": record.safety_warning,
        "source": record.source
    }