import firebase_admin
from firebase_admin import credentials, messaging
import logging
from sqlalchemy import select
from app.core.config import get_settings
from app.db.models import User

logger = logging.getLogger("plantguard.notifications")
settings = get_settings()

# Initialize Firebase Admin SDK (only once per application lifecycle)
if not firebase_admin._apps:
    try:
        # This reads the JSON key file you downloaded from Firebase
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        logger.info("✅ Firebase Admin SDK initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Firebase Admin SDK: {e}")
        # We don't crash the app here, but notifications will fail until fixed


async def send_push_notification(user_id: str, title: str, message: str, db_session) -> bool:
    """
    Sends a push notification to a specific user via Firebase Cloud Messaging (FCM).
    
    Args:
        user_id: The UUID of the user to notify
        title: The notification title (e.g., "🌱 Spray Reminder")
        message: The notification body (e.g., "Time to spray your tomatoes!")
        db_session: The active SQLAlchemy database session
    
    Returns:
        True if sent successfully, False otherwise.
    """
    try:
        # 1. Fetch the user's FCM token from the database
        result = await db_session.execute(
            select(User.fcm_token).where(User.id == user_id)
        )
        fcm_token = result.scalar_one_or_none()

        # 2. If no FCM token, skip sending (user hasn't logged in on a device or denied permissions)
        if not fcm_token:
            logger.warning(f"User {user_id} has no FCM token. Skipping notification.")
            return False

        # 3. Construct the FCM message payload
        msg = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=message,
            ),
            token=fcm_token,
            # Optional: Add data payload for deep linking in Flutter (e.g., opening the History screen)
            data={
                "type": "treatment_reminder",
                "user_id": str(user_id)
            },
        )

        # 4. Send the message via Firebase
        response = messaging.send(msg)
        logger.info(f"✅ Push notification sent successfully to user {user_id}. Response: {response}")
        return True

    except messaging.UnregisteredError:
        # This happens if the user uninstalled the app or revoked notification permissions
        logger.warning(f"FCM token for user {user_id} is invalid/revoked.")
        return False
        
    except Exception as e:
        logger.error(f"❌ Failed to send push notification to user {user_id}: {e}")
        return False