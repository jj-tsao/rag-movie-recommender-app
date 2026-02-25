from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Type

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.asyncio.retry import Retry

# Errors that indicate a stale / broken connection and are safe to retry.
# RuntimeError covers uvloop's "TCPTransport closed" when a pooled
# connection is silently dropped by the server or a network proxy.
_RETRY_ERRORS: Sequence[Type[Exception]] = (
    RedisConnectionError,
    RedisTimeoutError,
    ConnectionResetError,
    OSError,
    RuntimeError,
)

_RETRY = Retry(ExponentialBackoff(cap=0.5, base=0.05), retries=3)


@dataclass(frozen=True)
class RedisClients:
    """Pair of Redis *async* clients sharing the same URL/config.
    - bytes: decode_responses=False (bytes payloads; good for gzip blobs)
    - text:  decode_responses=True  (str payloads; good for JSON strings)
    """

    bytes: Redis
    text: Redis


def make_redis_clients(redis_url: str) -> RedisClients:
    shared_opts = dict(
        health_check_interval=10,
        socket_keepalive=True,
        socket_connect_timeout=2,
        socket_timeout=5,
        retry_on_timeout=True,
        retry=_RETRY,
        retry_on_error=list(_RETRY_ERRORS),
    )
    bytes_client: Redis = redis.from_url(
        redis_url, decode_responses=False, **shared_opts
    )
    text_client: Redis = redis.from_url(
        redis_url, decode_responses=True, **shared_opts
    )
    return RedisClients(bytes=bytes_client, text=text_client)
