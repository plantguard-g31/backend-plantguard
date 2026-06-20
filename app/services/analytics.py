from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import DiagnosisHistory
from datetime import datetime, timedelta

async def get_diagnosis_analytics(user_id: str, db: AsyncSession, crop_type: str = None) -> dict:
    """
    30-Day Disease Frequency Analytics.
    """
    # Calculate cutoff date (30 days ago)
    cutoff = datetime.utcnow() - timedelta(days=30)
    
    # Base query: all diagnoses for this user in the last 30 days
    query = select(DiagnosisHistory).where(
        and_(
            DiagnosisHistory.user_id == user_id,
            DiagnosisHistory.diagnosed_at >= cutoff
        )
    )
    
    # Apply crop filter if provided (FR-18b: Per-Crop Analytics)
    if crop_type:
        query = query.where(DiagnosisHistory.crop_type == crop_type)
        
    result = await db.execute(query)
    records = result.scalars().all()
    
    # 1. Calculate basic counts
    total_diagnoses = len(records)
    healthy_count = sum(1 for r in records if "Healthy" in r.disease_label)
    diseased_count = total_diagnoses - healthy_count
    
    # 2. Calculate disease frequency (excluding healthy plants)
    freq_map = {}
    for r in records:
        if "Healthy" not in r.disease_label:
            freq_map[r.disease_label] = freq_map.get(r.disease_label, 0) + 1
            
    # 3. Format for API response: list of dicts sorted by count descending
    disease_frequency = [
        {"disease_label": k, "count": v} 
        for k, v in sorted(freq_map.items(), key=lambda item: item[1], reverse=True)
    ]
    
    # 4. Most common disease
    most_common_disease = disease_frequency[0]["disease_label"] if disease_frequency else None
    
    # 5. Spreading-Disease Urgency Alert
    # Fires when any single disease_label appears >= 3 times within the 30-day window
    spreading_alert = {"triggered": False, "disease_label": None, "count": 0}
    for item in disease_frequency:
        if item["count"] >= 3:
            spreading_alert = {
                "triggered": True, 
                "disease_label": item["disease_label"], 
                "count": item["count"]
            }
            break # Only report the most frequent spreading disease
            
    return {
        "total_diagnoses": total_diagnoses,
        "healthy_count": healthy_count,
        "diseased_count": diseased_count,
        "disease_frequency": disease_frequency,
        "disease_frequency_dict": freq_map, # Kept for internal use by diagnosis.py severity logic
        "most_common_disease": most_common_disease,
        "spreading_alert": spreading_alert
    }