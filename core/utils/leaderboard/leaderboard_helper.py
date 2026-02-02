from core.utils.baseRedisHelper import BaseRedisHelper
from core.utils.leaderboard.constants import LEADERBOARD_KEY, EVENT_CHANNEL
from config.basic_config import settings

class LeaderboardRedisHelper(BaseRedisHelper):

    def __init__(self):
        self.redis = self.get_client(settings.LEADERBOARD_REDIS_DB)

    async def add_vote(self, user_id: str, amount: int = 1):
        await self.redis.zincrby(LEADERBOARD_KEY, amount, user_id)
        await self.redis.publish(EVENT_CHANNEL, "updated")

    async def get_top(self, limit: int):
        return await self.redis.zrevrange(
            LEADERBOARD_KEY,
            0,
            limit - 1,
            withscores=True
        )

    async def reset_contest(self):
        await self.redis.delete(LEADERBOARD_KEY)
        await self.redis.publish(EVENT_CHANNEL, "contest_reset")
