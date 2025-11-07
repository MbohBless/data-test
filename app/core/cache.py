"""
Cache Manager Module

Provides Redis-based caching for:
- Database schema information
- LLM query logs
- Generated SQL statements
- Evaluation results

MCP-Ready Interface:
- Can be extended to MCP Feedback Repository pattern
- All methods support async operation
"""

from typing import Any, List, Optional

import redis.asyncio as aioredis
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class CacheManager:
    """
    Manages Redis caching operations with connection pooling.

    Handles:
    - Key-value storage with TTL
    - JSON serialization/deserialization
    - Connection lifecycle management
    - Error handling and logging
    """

    def __init__(self, redis_url: Optional[str] = None) -> None:
        """
        Initialize CacheManager with Redis connection.

        Args:
            redis_url: Redis connection URL (defaults to settings.redis_url)
        """
        self.redis_url = redis_url or str(settings.redis_url)
        self._redis: Optional[aioredis.Redis] = None
        self._connection_pool: Optional[aioredis.ConnectionPool] = None

    async def connect(self) -> None:
        """
        Establish Redis connection with connection pooling.

        Creates connection pool for efficient connection reuse.
        Should be called during application startup.

        Raises:
            redis.ConnectionError: If connection fails
        """
        logger.info("Connecting to Redis", url=self._mask_url(self.redis_url))
        try:
            self._connection_pool = aioredis.ConnectionPool.from_url(
                self.redis_url,
                decode_responses=True,
                max_connections=20,
            )
            self._redis = aioredis.Redis(connection_pool=self._connection_pool)
            # Test connection
            await self._redis.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise

    async def disconnect(self) -> None:
        """
        Close Redis connection and cleanup resources.

        Should be called during application shutdown.
        """
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed")
        if self._connection_pool:
            await self._connection_pool.disconnect()

    async def get(self, key: str) -> Optional[str]:
        """
        Get value from cache by key.

        Args:
            key: Cache key

        Returns:
            Cached value as string, or None if not found

        Raises:
            redis.RedisError: If Redis operation fails
        """
        if not self._redis:
            logger.warning("Redis not connected, skipping cache get")
            return None

        try:
            value = await self._redis.get(key)
            if value:
                logger.debug("Cache hit", key=key)
            else:
                logger.debug("Cache miss", key=key)
            return value
        except Exception as e:
            logger.error("Cache get failed", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache (as string)
            ttl: Time-to-live in seconds (defaults to settings.redis_cache_ttl)

        Returns:
            True if set successfully, False otherwise

        Raises:
            redis.RedisError: If Redis operation fails
        """
        if not self._redis:
            logger.warning("Redis not connected, skipping cache set")
            return False

        ttl = ttl or settings.redis_cache_ttl

        try:
            await self._redis.set(key, value, ex=ttl)
            logger.debug("Cache set", key=key, ttl=ttl)
            return True
        except Exception as e:
            logger.error("Cache set failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if deleted, False otherwise
        """
        if not self._redis:
            logger.warning("Redis not connected, skipping cache delete")
            return False

        try:
            result = await self._redis.delete(key)
            logger.debug("Cache delete", key=key, deleted=bool(result))
            return bool(result)
        except Exception as e:
            logger.error("Cache delete failed", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists, False otherwise
        """
        if not self._redis:
            return False

        try:
            result = await self._redis.exists(key)
            return bool(result)
        except Exception as e:
            logger.error("Cache exists check failed", key=key, error=str(e))
            return False

    async def get_many(self, keys: List[str]) -> List[Optional[str]]:
        """
        Get multiple values from cache.

        Args:
            keys: List of cache keys

        Returns:
            List of values (None for missing keys)
        """
        if not self._redis:
            return [None] * len(keys)

        try:
            values = await self._redis.mget(keys)
            logger.debug("Cache get_many", key_count=len(keys))
            return values  # type: ignore[return-value]
        except Exception as e:
            logger.error("Cache get_many failed", error=str(e))
            return [None] * len(keys)

    async def set_many(
        self,
        mapping: dict[str, str],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set multiple key-value pairs.

        Args:
            mapping: Dict of key-value pairs
            ttl: Time-to-live in seconds for all keys

        Returns:
            True if all set successfully
        """
        if not self._redis:
            return False

        try:
            # Use pipeline for efficiency
            async with self._redis.pipeline(transaction=True) as pipe:
                for key, value in mapping.items():
                    if ttl:
                        pipe.set(key, value, ex=ttl)
                    else:
                        pipe.set(key, value)
                await pipe.execute()

            logger.debug("Cache set_many", key_count=len(mapping))
            return True
        except Exception as e:
            logger.error("Cache set_many failed", error=str(e))
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Redis key pattern (e.g., "schema:*")

        Returns:
            Number of keys deleted
        """
        if not self._redis:
            return 0

        try:
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self._redis.delete(*keys)
                logger.info("Cache cleared by pattern", pattern=pattern, deleted=deleted)
                return deleted
            return 0
        except Exception as e:
            logger.error("Cache clear_pattern failed", pattern=pattern, error=str(e))
            return 0

    async def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key.

        Args:
            key: Cache key

        Returns:
            TTL in seconds, or None if key doesn't exist
        """
        if not self._redis:
            return None

        try:
            ttl = await self._redis.ttl(key)
            if ttl == -2:  # Key doesn't exist
                return None
            if ttl == -1:  # Key exists but has no TTL
                return -1
            return ttl
        except Exception as e:
            logger.error("Get TTL failed", key=key, error=str(e))
            return None

    def _mask_url(self, url: str) -> str:
        """
        Mask sensitive information in Redis URL for logging.

        Args:
            url: Redis connection URL

        Returns:
            Masked URL string
        """
        # Simple masking: hide password if present
        if "@" in url:
            parts = url.split("@")
            return f"***@{parts[-1]}"
        return url

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._redis is not None


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


async def get_cache_manager() -> CacheManager:
    """
    Get or create global cache manager instance.

    Returns:
        CacheManager: Global cache manager instance

    Usage:
        cache = await get_cache_manager()
        await cache.set("key", "value")
    """
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
        await _cache_manager.connect()
    return _cache_manager
