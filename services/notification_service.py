from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from core.firebase_push import send_push_notification
from core.utils.core_enums import NotificationType, NotificationRecipientType
from config.db_config import notification_collection , user_collection , admin_collection
from services.translation import translate_message

async def send_notification(
    *,
    recipient_id: str,
    recipient_type: NotificationRecipientType,
    notification_type: NotificationType,
    title: str,
    message: str,
    reference: Optional[dict] = None,
    sender_user_id: Optional[str] = None,
    send_push: bool = False,
    push_data: Optional[dict] = None
):
    """
    Common notification handler:
    - Stores notification in DB
    - Optionally sends Firebase push
    """

    # ------------------ RESOLVE LANGUAGE ------------------
    lang = "en"

    if recipient_type == NotificationRecipientType.USER:
        user = await user_collection.find_one(
            {"_id": ObjectId(recipient_id)},
            {"lang": 1}
        )
        if user:
            lang = user.get("lang", "en")

    elif recipient_type == NotificationRecipientType.ADMIN:
        admin = await admin_collection.find_one(
            {"_id": ObjectId(recipient_id)},
            {"lang": 1}
        )
        if admin:
            lang = admin.get("lang", "en")

    # ------------------ TRANSLATE ------------------
    translated_title = translate_message(title, lang)
    translated_message = translate_message(message, lang)

    notification_doc = {
        "recipient_id": recipient_id,
        "recipient_type": recipient_type.value,
        "type": notification_type.value,
        "title": title,
        "message": message,
        "reference": reference,
        "sender_user_id": sender_user_id,
        "is_read": False,
        "read_at": None,
        "created_at": datetime.now(timezone.utc)
    }

    # Store in DB
    await notification_collection.insert_one(notification_doc)

    # Send push notification (if required)
    if send_push:
        try:
            await send_push_notification(
                user_id=recipient_id,
                title=translated_title,
                body=translated_message,
                data=push_data or {}
            )
        except Exception as e:
            # Do NOT fail main flow if push fails
            print(f"[Notification Push Failed] {e}")

    return True
