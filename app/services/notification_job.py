import logging
from datetime import datetime, timezone
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.base import AsyncSessionLocal
from app.db.models import Notification, User
from app.services.push_notification_service import send_push_notification

logger = logging.getLogger("plantguard.notifications")

# Initialize the scheduler
scheduler = AsyncIOScheduler()

async def check_and_send_due_notifications():
    """
    Runs periodically (e.g., every 5 minutes) to find pending notifications
    that are due to be sent, sends them via FCM, and marks them as sent.
    """
    now = datetime.now(timezone.utc)
    
    async with AsyncSessionLocal() as db:
        try:
            # Find notifications that are:
            # 1. Active (is_active == True)
            # 2. Not yet sent (sent_at IS NULL)
            # 3. Due now or in the past (scheduled_at <= now)
            result = await db.execute(
                select(Notification)
                .where(Notification.is_active == True)
                .where(Notification.sent_at == None)
                .where(Notification.scheduled_at <= now)
            )
            due_notifications = result.scalars().all()
            
            if not due_notifications:
                return
                
            logger.info(f"Found {len(due_notifications)} due notifications to process.")
            
            for notif in due_notifications:
                # Fetch user to get FCM token
                user_result = await db.execute(
                    select(User).where(User.id == notif.user_id)
                )
                user = user_result.scalars().first()
                
                if not user or not user.fcm_token:
                    logger.warning(f"User {notif.user_id} has no FCM token. Skipping notification {notif.id}.")
                    # Mark as sent to avoid infinite retry loop
                    notif.sent_at = datetime.now(timezone.utc)
                    continue
                
                # Determine language for the message
                lang = user.language_pref if user.language_pref else "en"
                title = notif.title_ne if lang == "ne" else notif.title_en
                message = notif.message_ne if lang == "ne" else notif.message_en
                
                # Send the push notification
                success = await send_push_notification(
                    user_id=str(notif.user_id),
                    title=title,
                    message=message,
                    db_session=db
                )
                
                if success:
                    notif.sent_at = datetime.now(timezone.utc)
                    notif.is_delivered = True
                    logger.info(f"Notification {notif.id} sent successfully to user {notif.user_id}")
                else:
                    logger.warning(f"Failed to send notification {notif.id} to user {notif.user_id}")
                    # Mark as attempted to prevent infinite spam loops
                    notif.sent_at = datetime.now(timezone.utc)
            
            await db.commit()
            logger.info("Successfully processed due notifications.")
            
        except Exception as e:
            logger.error(f"Error processing due notifications: {e}")
            await db.rollback()

def start_notification_scheduler():
    """
    Starts the APScheduler to check for due notifications every 5 minutes.
    """
    scheduler.add_job(
        check_and_send_due_notifications,
        'interval',
        minutes=5,
        id='check_due_notifications',
        replace_existing=True
    )
    scheduler.start()
    logger.info("✅ Notification scheduler started (checks every 5 minutes)")