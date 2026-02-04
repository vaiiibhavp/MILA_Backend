from datetime import datetime, timedelta
from bson import ObjectId
from config.db_config import (
    user_collection ,
    daily_action_history
)
from core.utils.core_enums import MembershipType
from bson import ObjectId
from datetime import datetime
from core.utils.response_mixin import CustomResponseMixin
from services.translation import translate_message
from config.basic_config import settings

response = CustomResponseMixin()

DAILY_FREE_LIMIT = settings.DAILY_FREE_LIMIT

def today_bucket():
    return datetime.utcnow().strftime("%Y-%m-%d")


async def increment_daily_counter(user_id: str, action: str):
    today = today_bucket()

    inc_map = {
        "like": {"like_count": 1, "total_count": 1},
        "pass": {"pass_count": 1, "total_count": 1},
        "favorite": {"favourite_count": 1, "total_count": 1},
    }

    await daily_action_history.update_one(
        {
            "user_id": user_id,
            "date_bucket": today
        },
        {
            "$inc": inc_map[action],
            "$set": {"updated_at": datetime.utcnow()},
            "$setOnInsert": {
                "user_id": user_id,
                "date_bucket": today,
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )

async def check_daily_action_limit(user_id: str):
    user = await user_collection.find_one(
        {"_id": ObjectId(user_id)},
        {"membership_type": 1}
    )

    if not user:
        return False, 0, "USER_NOT_FOUND"

    # Premium users → unlimited
    if user.get("membership_type") == MembershipType.PREMIUM.value:
        return True, 0, None

    today = today_bucket()

    counter_doc = await daily_action_history.find_one(
        {"user_id": user_id, "date_bucket": today},
        {"total_count": 1}
    )

    total = counter_doc.get("total_count", 0) if counter_doc else 0

    if total >= DAILY_FREE_LIMIT:
        return False, total, "DAILY_LIMIT_REACHED"

    return True, total, None
