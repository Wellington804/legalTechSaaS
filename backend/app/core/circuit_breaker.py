import time
import functools
import logging
from typing import Callable, Any

logger = logging.getLogger("circuit_breaker")

class CircuitBreakerOpenException(Exception):
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "CLOSED" # CLOSED, OPEN, HALF-OPEN
        self.last_failure_time = 0.0

    def __call__(self, func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            now = time.time()

            if self.state == "OPEN":
                if now - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF-OPEN"
                    logger.info(f"[Circuit Breaker] Transicionando para HALF-OPEN para a função {func.__name__}")
                else:
                    logger.warning(f"[Circuit Breaker] Chamada bloqueada em estado OPEN para {func.__name__}")
                    raise CircuitBreakerOpenException(f"Serviço temporariamente indisponível (Circuit Breaker OPEN para {func.__name__})")

            try:
                result = await func(*args, **kwargs)
                if self.state == "HALF-OPEN":
                    self.state = "CLOSED"
                    self.failure_count = 0
                    logger.info(f"[Circuit Breaker] Serviço recuperado com sucesso. Estado: CLOSED ({func.__name__})")
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = now
                logger.error(f"[Circuit Breaker] Falha capturada ({self.failure_count}/{self.failure_threshold}) em {func.__name__}: {e}")
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                    logger.critical(f"[Circuit Breaker] Limiar de falhas atingido! Estado alterado para OPEN para {func.__name__}")
                raise e
        return wrapper
