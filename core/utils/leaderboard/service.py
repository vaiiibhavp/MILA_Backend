from bson import ObjectId

from config.models.contest_model import resolve_user_avatar
from config.models.user_models import get_user_details
from core.utils.leaderboard.leaderboard_helper import LeaderboardRedisHelper
from core.utils.leaderboard.constants import TOP_N

redis_helper = LeaderboardRedisHelper()

async def build_leaderboard():
    raw = await redis_helper.get_top(TOP_N)

    leaderboard = []
    for idx, (user_id, votes) in enumerate(raw):
        avatar = await resolve_user_avatar(user_id)

        user = await get_user_details(
            {"_id": ObjectId(user_id), "is_deleted": {"$ne": True}},
            fields=["username"]
        )
        leaderboard.append({
            "rank": idx + 1,
            "user_id": str(user_id),
            "total_votes": int(votes),
            "username": user.get("username") if user else None,
            "avatar": avatar
        })

    return leaderboard
