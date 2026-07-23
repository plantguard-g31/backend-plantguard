from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional

from app.db.base import get_db
from app.db.models import User, Notification, UserNotificationPreference
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])

class FcmTokenRequest(BaseModel):
    fcm_token: str

class NotificationPreferenceUpdate(BaseModel):
    treatment_reminders_enabled: Optional[bool] = None
    follow_ups_enabled: Optional[bool] = None
    crop_recommendations_enabled: Optional[bool] = None
    preferred_notification_hour: Optional[int] = None

@router.post("/fcm-token", status_code=status.HTTP_200_OK)
async def update_fcm_token(
    request_data: FcmTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Save or update the user's Firebase Cloud Messaging token."""
    current_user.fcm_token = request_data.fcm_token
    await db.commit()
    return {"message": "FCM token updated successfully"}

@router.get("/", status_code=status.HTTP_200_OK)
async def get_user_notifications(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a list of notifications for the current user."""
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.scheduled_at.desc())
        .limit(limit)
        .offset(offset)
    )
    notifications = result.scalars().all()
    
    return {
        "total": len(notifications),
        "items": [
            {
                "id": str(n.id),
                "type": n.notification_type,
                "title": n.title_en, # Can be localized based on user pref later
                "message": n.message_en,
                "scheduled_at": n.scheduled_at.isoformat() if n.scheduled_at else None,
                "is_read": n.read_at is not None
            }
            for n in notifications
        ]
    }

@router.post("/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_notification_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a specific notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    notif = result.scalars().first()
    
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    notif.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Notification marked as read"}

@router.put("/preferences", status_code=status.HTTP_200_OK)
async def update_notification_preferences(
    preferences: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user's notification preferences."""
    result = await db.execute(
        select(UserNotificationPreference).where(UserNotificationPreference.user_id == current_user.id)
    )
    user_prefs = result.scalars().first()
    
    if not user_prefs:
        # Create default preferences if they don't exist
        user_prefs = UserNotificationPreference(user_id=current_user.id)
        db.add(user_prefs)
        
    # Update only provided fields
    update_data = preferences.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user_prefs, key, value)
        
    await db.commit()
    return {"message": "Notification preferences updated successfully"}