"""Retry helper with exponential backoff."""

from __future__ import annotations

import functools
import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry(
    max_attempts: int = 3,
    backoff_seconds: int = 20,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry a function up to ``max_attempts`` times, sleeping longer each time."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:  # type: ignore[no-untyped-def]
            attempt = 0
            wait = backoff_seconds
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as err:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func.__name__,
                            attempt,
                            err,
                        )
                        raise
                    logger.warning(
                        "%s attempt %d/%d failed (%s); retrying in %ds",
                        func.__name__,
                        attempt,
                        max_attempts,
                        err,
                        wait,
                    )
                    time.sleep(wait)
                    wait += backoff_seconds

        return wrapper

    return decorator
