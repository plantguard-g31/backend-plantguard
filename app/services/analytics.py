from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import DiagnosisHistory, TreatmentRecord
from datetime import datetime, timedelta

async def get_diagnosis_analytics(user_id: str, db: AsyncSession) -> dict:
    """
    Analyzes user's diagnosis history for the last 30 days.
    Returns disease frequency and spreading warnings.
    
    NOTE: DiagnosisHistory no longer stores disease_name directly.
    We JOIN with TreatmentRecord to get disease info via FK.
    """
    # Calculate cutoff date (30 days ago)
    cutoff = datetime.utcnow() - timedelta(days=30)
    
    # Query diagnoses for this user in last 30 days
    # JOIN with TreatmentRecord to get disease_name via FK
    result = await db.execute(
        select(
            TreatmentRecord.disease_name,  #  Get disease_name from TreatmentRecord
            func.count(DiagnosisHistory.id).label('count')
        )
        .join(
            TreatmentRecord,
            DiagnosisHistory.treatment_id == TreatmentRecord.id  #  Join via FK
        )
        .where(
            and_(
                DiagnosisHistory.user_id == user_id,
                DiagnosisHistory.diagnosed_at >= cutoff  #  Use diagnosed_at (not created_at)
            )
        )
        .group_by(TreatmentRecord.disease_name)  # Group by disease_name from TreatmentRecord
    )
    
    rows = result.all()
    disease_frequency = {row[0]: row[1] for row in rows}
    
    # Check for spreading disease warning (same disease ≥3 times)
    spreading_warning = None
    for disease, count in disease_frequency.items():
        if count >= 3:
            spreading_warning = f"{disease} detected {count} times in 30 days. Consider consulting an expert."
            break  # Report first warning only
    
    return {
        "period_days": 30,
        "total_diagnoses": sum(disease_frequency.values()),
        "disease_frequency": disease_frequency,
        "spreading_warning": spreading_warning
    }