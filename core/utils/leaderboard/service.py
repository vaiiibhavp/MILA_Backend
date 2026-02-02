from core.utils.leaderboard.leaderboard_helper import LeaderboardRedisHelper
from core.utils.leaderboard.constants import TOP_N

redis_helper = LeaderboardRedisHelper()

async def build_leaderboard():
    raw = await redis_helper.get_top(TOP_N)

    leaderboard = []
    for idx, (user_id, votes) in enumerate(raw):
        leaderboard.append({
            "rank": idx + 1,
            "user_id": int(user_id),
            "votes": int(votes),
            # fetch from DB/cache if needed
            "name": f"User {user_id}",
            "photo": None
        })

    return leaderboard
