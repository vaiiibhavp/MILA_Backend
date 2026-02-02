from core.utils.leaderboard.leaderboard_helper import LeaderboardRedisHelper
from core.utils.leaderboard.service import build_leaderboard
from core.utils.leaderboard.websocket import manager
from core.utils.leaderboard.constants import EVENT_CHANNEL

redis_helper = LeaderboardRedisHelper()

async def leaderboard_listener():
    pubsub = redis_helper.redis.pubsub()
    await pubsub.subscribe(EVENT_CHANNEL)

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue

        event = message["data"]

        if event == "updated":
            leaderboard = await build_leaderboard()
            await manager.broadcast({
                "type": "leaderboard_update",
                "data": leaderboard
            })

        elif event == "contest_reset":
            await manager.broadcast({
                "type": "contest_reset",
                "data": []
            })
