from datetime import timezone, datetime
from config.db_config import user_collection, transaction_collection
from config.models.user_models import find_expiring_subscriptions
from core.utils.core_enums import NotificationRecipientType, NotificationType, MembershipStatus, MembershipType
from services.notification_service import send_notification


async def notify_expiring_subscriptions(days_before: int):
    subs = await find_expiring_subscriptions(days_before)

    for sub in subs:
        await send_notification(
            recipient_id=str(sub['_id']),
            recipient_type=NotificationRecipientType.USER,
            notification_type=NotificationType.SUBSCRIPTION_EXPIRY,
            title="PUSH_TITLE_SUBSCRIPTION_EXPIRING_SOON",
            message="PUSH_MESSAGE_SUBSCRIPTION_EXPIRING_SOON",
        )

async def expire_and_activate_subscriptions_job():
    """
    1. Find users with expired active subscriptions
    2. Check if they have other pending subscriptions
    3. Activate next subscription OR mark as expired
    """
    today = datetime.now(tz=timezone.utc)

    # Find users with active status but expired subscriptions
    pipeline = [
        {
            "$match": {
                "membership_status": MembershipStatus.ACTIVE.value
            }
        },
        # 🔹 Convert string → ObjectId safely
        {
            "$addFields": {
                "membership_trans_id_obj": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": ["$membership_trans_id", None]},
                                {"$eq": [{"$type": "$membership_trans_id"}, "string"]}
                            ]
                        },
                        {"$toObjectId": "$membership_trans_id"},
                        None
                    ]
                }
            }
        },
        {
            "$lookup": {
                "from": "transaction",
                "localField": "membership_trans_id_obj",
                "foreignField": "_id",
                "as": "transaction"
            }
        },
        {
            "$unwind": {
                "path": "$transaction",
                "preserveNullAndEmptyArrays": False
            }
        },
        {
            "$match": {
                "transaction.trans_type": "subscription_transaction",
                "transaction.status": "success",
                "transaction.expires_at": {"$lt": today}
            }
        }
    ]

    cursor = user_collection.aggregate(pipeline)

    # Convert to list to see results
    expired_users = await cursor.to_list(length=None)

    print(f"Found {len(expired_users)} users with expired subscriptions")

    # Process each user
    for user in expired_users:
        await handle_subscription_expiry(user["_id"])


async def handle_subscription_expiry(user_id):
    """Handle expiry for a specific user"""

    # Find the next available (unused) subscription
    next_subscription = await transaction_collection.find_one(
        {
            "user_id": str(user_id),
            "trans_type": "subscription_transaction",
            "status": "success",
            "is_activated": False,  # Not yet activated
            "expires_at": {"$gte": datetime.now(tz=timezone.utc)}  # Not expired
        },
        sort=[("created_at", 1)]  # Get oldest first (FIFO)
    )

    if next_subscription:
        # Activate the next subscription
        await activate_subscription(user_id, next_subscription)
    else:
        # No more subscriptions, mark user as expired
        await mark_user_expired(user_id)


async def activate_subscription(user_id, subscription):
    """Activate a new subscription for the user"""

    # Update user with new active subscription
    await user_collection.update_one(
        {"_id": user_id},
        {
            "$set": {
                "membership_trans_id": str(subscription["_id"]),
                "membership_status": MembershipStatus.ACTIVE.value,
                "updated_at": datetime.now(tz=timezone.utc)
            }
        }
    )

    # Mark this subscription as activated
    await transaction_collection.update_one(
        {"_id": subscription["_id"]},
        {
            "$set": {
                "is_activated": True,
                "activated_at": datetime.now(tz=timezone.utc)
            }
        }
    )

    print(f"Activated subscription {subscription['_id']} for user {user_id}")


async def mark_user_expired(user_id):
    """Mark user as expired when no subscriptions remain"""

    await user_collection.update_one(
        {"_id": user_id},
        {
            "$set": {
                "membership_status": MembershipStatus.EXPIRED.value,
                "updated_at": datetime.now(tz=timezone.utc),
                "membership_type": MembershipType.FREE.value,
                "membership_trans_id": None
            }
        }
    )

    print(f"Marked user {user_id} as expired")
