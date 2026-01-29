from config.models.user_models import find_expiring_subscriptions
from core.utils.core_enums import NotificationRecipientType, NotificationType
from services.notification_service import send_notification


async def notify_expiring_subscriptions(days_before: int):
    subs = await find_expiring_subscriptions(days_before)

    for sub in subs:
        await send_notification(
            recipient_id=str(sub['_id']),
            recipient_type=NotificationRecipientType.USER.value,
            notification_type=NotificationType.SUBSCRIPTION_EXPIRY.value,
            title="PUSH_TITLE_SUBSCRIPTION_EXPIRING_SOON",
            message="PUSH_MESSAGE_SUBSCRIPTION_EXPIRING_SOON",
        )
