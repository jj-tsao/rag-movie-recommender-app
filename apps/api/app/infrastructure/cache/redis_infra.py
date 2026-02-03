from __future__ import annotations

from dataclasses import dataclass
import redis.asyncio as redis
from redis.asyncio import Redis


@dataclass(frozen=True)
class RedisClients:
    """Pair of Redis *async* clients sharing the same URL/config.
    - bytes: decode_responses=False (bytes payloads; good for gzip blobs)
    - text:  decode_responses=True  (str payloads; good for JSON strings)
    """

    bytes: Redis
    text: Redis


def make_redis_clients(redis_url: str) -> RedisClients:
    bytes_client: Redis = redis.from_url(
        redis_url,
        decode_responses=False,
        health_check_interval=30,
        socket_keepalive=True,
        retry_on_timeout=True,
    )
    text_client: Redis = redis.from_url(
        redis_url,
        decode_responses=True,
        health_check_interval=30,
        socket_keepalive=True,
        retry_on_timeout=True,
    )
    return RedisClients(bytes=bytes_client, text=text_client)
