from __future__ import annotations

import asyncio
from logging import getLogger
from typing import Coroutine, TypeVar


logger = getLogger(__package__)
T = TypeVar('T')
C = Coroutine[object, object, T]


async def make_safe(coro: C[T], *, default: T | None = None) -> T | None:
    try:
        return await coro
    except Exception:
        logger.exception("suppressed exception")
    return default


async def chain(*coros: C[None]) -> None:
    for coro in coros:
        await coro


async def finalize(first: C[None], second: C[T]) -> T:
    first_task = asyncio.create_task(first)
    while not first_task.done():
        await asyncio.sleep(0)
    return await second
