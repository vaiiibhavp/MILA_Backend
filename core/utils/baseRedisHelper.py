# app/redis/base.py
import redis.asyncio as redis
from config.basic_config import settings

class BaseRedisHelper:
    _clients = {}

    @classmethod
    def get_client(cls, db: int) -> redis.Redis:
        if db not in cls._clients:
            pool = redis.ConnectionPool(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=db,
                decode_responses=True,
                max_connections=50,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=10,
                health_check_interval=30,
            )
            cls._clients[db] = redis.Redis(connection_pool=pool)

        return cls._clients[db]
