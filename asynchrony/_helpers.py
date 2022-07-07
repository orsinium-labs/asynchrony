from __future__ import annotations

from logging import getLogger, Logger, LoggerAdapter
from typing import Coroutine, TypeVar


default_logger = getLogger(__package__)
T = TypeVar('T')
D = TypeVar('D')
C = Coroutine[object, object, T]


async def make_safe(
    coro: C[T], *,
    default: D | None = None,
    logger: Logger | LoggerAdapter | None = default_logger,
    message: str = "suppressed exception in a coroutine",
    exception: type[BaseException] | tuple[type[BaseException], ...] = Exception,
) -> T | D | None:
    """
    Args:
        coro : the coroutine to run.
        default: the default value to return if `coro` fails.
        logger: the logger to use to log the failure.
        message: the error message to log.
        exception: the exception type(s) to catch.
    """
    try:
        return await coro
    except exception:
        if logger is not None:
            logger.exception(message)
    return default
