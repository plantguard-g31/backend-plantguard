from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.db.models import User
from app.core.dependencies import get_current_user
from app.services.analytics import get_diagnosis_analytics

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/")
async def get_analytics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """FR-18: 30-day analytics + spreading alert for all crops."""
    return await get_diagnosis_analytics(user_id=str(current_user.id), db=db, crop_type=None)

@router.get("/crop/{crop_type}")
async def get_crop_analytics(
    crop_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """FR-18b: Per-crop analytics (tomato, potato, bell_pepper)."""
    # Validate crop type strictly per SRS v3.1
    if crop_type not in ["tomato", "potato", "bell_pepper"]:
        raise HTTPException(status_code=422, detail="Invalid crop type. Must be tomato, potato, or bell_pepper.")
    
    return await get_diagnosis_analytics(user_id=str(current_user.id), db=db, crop_type=crop_type)