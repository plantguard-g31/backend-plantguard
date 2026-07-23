import re
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Notification, UserNotificationPreference

logger = logging.getLogger("plantguard.notifications")

def extract_spray_interval(dosage_string: str) -> int:
    """Extract the number of days between sprays from the dosage string."""
    if not dosage_string:
        return 7
    match = re.search(r'every\s+(\d+)\s+days?', dosage_string, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 7

def extract_notification_hour(timing_string: str) -> int:
    """Extract the hour (0-23) to send the notification based on timing string."""
    if not timing_string:
        return 7
    timing_lower = timing_string.lower()
    if "early morning" in timing_lower:
        return 7
    elif "late evening" in timing_lower:
        return 18
    elif "morning" in timing_lower:
        return 8
    elif "evening" in timing_lower:
        return 17
    return 7

def calculate_treatment_end_date(diagnosis_date: datetime, phi_days: int) -> datetime:
    """Calculate the last day the farmer should spray (based on Pre-Harvest Interval)."""
    if phi_days <= 0:
        return diagnosis_date
    return diagnosis_date + timedelta(days=phi_days)

async def get_user_notification_preferences(
    user_id: str, 
    db: AsyncSession
) -> Optional[UserNotificationPreference]:
    """Fetch user's notification preferences."""
    result = await db.execute(
        select(UserNotificationPreference)
        .where(UserNotificationPreference.user_id == user_id)
    )
    return result.scalars().first()

async def create_treatment_notification_schedule(
    user_id: str,
    diagnosis_id: str,
    disease_name: str,
    dosage_string: str,
    timing_string: str,
    phi_days: int,
    pesticide_name: str,
    db: AsyncSession
) -> List[Notification]:
    """Generate and save notification schedule for a treatment."""
    
    # 1. Check if user has disabled treatment reminders
    prefs = await get_user_notification_preferences(user_id, db)
    if prefs and not prefs.treatment_reminders_enabled:
        logger.info(f"User {user_id} has disabled treatment reminders. Skipping.")
        return []
    
    # 2. Parse treatment parameters
    spray_interval = extract_spray_interval(dosage_string)
    notify_hour = extract_notification_hour(timing_string)
    
    if prefs and prefs.preferred_notification_hour:
        notify_hour = prefs.preferred_notification_hour
    
    diagnosis_date = datetime.utcnow()
    end_date = calculate_treatment_end_date(diagnosis_date, phi_days)
    
    if phi_days <= 0:
        logger.info(f"No treatment needed for {disease_name} (PHI={phi_days}). Skipping.")
        return []
    
    # 3. Generate spray reminder notifications
    notifications = []
    current_date = diagnosis_date
    spray_number = 1
    
    while current_date <= end_date:
        notify_time = current_date.replace(hour=notify_hour, minute=0, second=0, microsecond=0)
        
        if notify_time > datetime.utcnow():
            notification = Notification(
                user_id=user_id,
                diagnosis_id=diagnosis_id,
                notification_type="treatment_reminder",
                title_en=f"🌱 Spray #{spray_number} — {disease_name}",
                title_ne=f"🌱 छर्कनुहोस् #{spray_number} — {disease_name}",
                message_en=f"Time to spray! {dosage_string} of {pesticide_name}. Best time: {timing_string}.",
                message_ne=f"छर्कने समय भयो! {pesticide_name} को {dosage_string}। उत्तम समय: {timing_string}।",
                scheduled_at=notify_time,
                is_active=True,
                is_delivered=False
            )
            notifications.append(notification)
            db.add(notification)
        
        current_date += timedelta(days=spray_interval)
        spray_number += 1
    
    # 4. Generate PHI warning notification (stop spraying)
    phi_warning_time = end_date.replace(hour=notify_hour, minute=0, second=0, microsecond=0)
    
    if phi_warning_time > datetime.utcnow():
        phi_notification = Notification(
            user_id=user_id,
            diagnosis_id=diagnosis_id,
            notification_type="phi_warning",
            title_en=f"⚠️ Stop Spraying — {disease_name}",
            title_ne=f"⚠️ छर्कन बन्द गर्नुहोस् — {disease_name}",
            message_en=f"Pre-harvest interval reached ({phi_days} days). STOP applying {pesticide_name}. Safe to harvest after today.",
            message_ne=f"बाली काट्नु अघिको अवधि पूरा भयो ({phi_days} दिन)। {pesticide_name} छर्कन बन्द गर्नुहोस्।",
            scheduled_at=phi_warning_time,
            is_active=True,
            is_delivered=False
        )
        notifications.append(phi_notification)
        db.add(phi_notification)
    
    # 5. Commit all notifications
    await db.commit()
    
    logger.info(f"Created {len(notifications)} notifications for user {user_id}, diagnosis {diagnosis_id}")
    return notifications