from datetime import datetime, timezone
from bson import ObjectId
from datetime import datetime, timezone
from config.db_config import (
    notification_collection ,
    user_collection
)
from services.profile_fetch_service import format_notification
from services.translation import translate_message
from bson import ObjectId
from core.utils.core_enums import NotificationRecipientType


class NotificationModel:

    @staticmethod
    async def get_admin_notifications(admin_id: str, lang: str):
        try:
            notifications = await notification_collection.find(
                {
                    "recipient_id": admin_id,
                    "recipient_type": NotificationRecipientType.ADMIN.value,
                }
            ).sort("created_at", -1).to_list(length=100)

            today = []
            earlier = []
            today_date = datetime.now(timezone.utc).date()

            for n in notifications:
                created_at = n.get("created_at")

                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )

                if isinstance(created_at, datetime):
                    created_at = created_at.astimezone(timezone.utc)

                # Translate keys
                n["title"] = translate_message(n.get("title"), lang)
                n["message"] = translate_message(n.get("message"), lang)

                reference = n.get("reference", {})

                # REPORT
                if n.get("type") == "report":
                    user_id = reference.get("reported_by")

                    if user_id and ObjectId.is_valid(user_id):
                        user = await user_collection.find_one(
                            {"_id": ObjectId(user_id), "is_deleted": False},
                            {"username": 1}
                        )
                        if user:
                            reference["reported_by_name"] = user.get("username")

                # BLOCK
                if n.get("type") == "block":
                    user_id = reference.get("blocked_by")

                    if user_id and ObjectId.is_valid(user_id):
                        user = await user_collection.find_one(
                            {"_id": ObjectId(user_id), "is_deleted": False},
                            {"username": 1}
                        )
                        if user:
                            reference["blocked_by_name"] = user.get("username")

                formatted = format_notification(n)

                if created_at.date() == today_date:
                    today.append(formatted)
                else:
                    earlier.append(formatted)

            return {
                "today": today,
                "earlier": earlier
            }

        except Exception as e:
            raise RuntimeError(str(e))

    # -----------------------------------------------------

    @staticmethod
    async def mark_admin_notification_read(
        notification_id: str,
        admin_id: str
    ):
        if not ObjectId.is_valid(notification_id):
            raise ValueError("INVALID_NOTIFICATION_ID")

        result = await notification_collection.update_one(
            {
                "_id": ObjectId(notification_id),
                "recipient_id": admin_id,
                "recipient_type": NotificationRecipientType.ADMIN.value,
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": datetime.now(timezone.utc)
                }
            }
        )

        if result.matched_count == 0:
            raise ValueError("NOTIFICATION_NOT_FOUND")

        return True

    # -----------------------------------------------------

    @staticmethod
    async def mark_all_admin_notifications_read(admin_id: str):

        result = await notification_collection.update_many(
            {
                "recipient_id": admin_id,
                "recipient_type": NotificationRecipientType.ADMIN.value,
                "is_read": False
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": datetime.now(timezone.utc)
                }
            }
        )

        return result.modified_count
