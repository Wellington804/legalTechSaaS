import json
import functools
import logging
from typing import Optional, Any, Callable
import redis.asyncio as aioredis
from fastapi import Request, Response
from app.core.config import settings

logger = logging.getLogger("redis_cache")

class RedisCacheManager:
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None

    async def connect(self):
        try:
            self.redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2.0
            )
            await self.redis_client.ping()
            logger.info("Conectado ao Redis com sucesso!")
        except Exception as e:
            logger.warning(f"Não foi possível conectar ao Redis: {e}. O sistema funcionará com fallback sem cache.")
            self.redis_client = None

    async def disconnect(self):
        if self.redis_client:
            await self.redis_client.close()

    async def get(self, key: str) -> Optional[Any]:
        if not self.redis_client:
            return None
        try:
            data = await self.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Erro ao buscar chave no Redis {key}: {e}")
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        if not self.redis_client:
            return False
        try:
            serialized = json.dumps(value, default=str)
            await self.redis_client.set(key, serialized, ex=ttl_seconds)
            return True
        except Exception as e:
            logger.error(f"Erro ao gravar chave no Redis {key}: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        if not self.redis_client:
            return 0
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Invalidadas {deleted} chaves com o padrão {pattern}")
                return deleted
        except Exception as e:
            logger.error(f"Erro ao invalidar chaves do Redis com padrão {pattern}: {e}")
        return 0

cache_manager = RedisCacheManager()

def cache_response(ttl_seconds: int = 300, key_prefix: str = "cache"):
    """
    Decorator para rotas do FastAPI que realiza cache L2 isolado por tenant e query parameters.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Optional[Request] = kwargs.get("req") or kwargs.get("request")
            tenant_id = "default-tenant"
            if request and hasattr(request, "state") and hasattr(request.state, "tenant_id"):
                tenant_id = request.state.tenant_id

            # Gera chave de cache única
            query_str = json.dumps(
                {k: v for k, v in kwargs.items() if k not in ["request", "req", "db"]},
                sort_keys=True,
                default=str
            )
            cache_key = f"legaltech:tenant:{tenant_id}:{key_prefix}:{func.__name__}:{hash(query_str)}"

            cached_data = await cache_manager.get(cache_key)
            if cached_data is not None:
                logger.debug(f"Cache hit para {cache_key}")
                return cached_data

            result = await func(*args, **kwargs)

            # Grava no Redis
            if result is not None:
                # Se for um modelo Pydantic ou dict
                dict_result = result.model_dump() if hasattr(result, "model_dump") else result
                await cache_manager.set(cache_key, dict_result, ttl_seconds=ttl_seconds)

            return result
        return wrapper
    return decorator
