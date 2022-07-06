from __future__ import annotations

import asyncio
import dataclasses
import math
import time
import warnings
from typing import AsyncIterator, Coroutine, Generator, Generic, TypeVar


T = TypeVar('T', covariant=True)
G = TypeVar('G')
C = Coroutine[object, object, T]


@dataclasses.dataclass
class Tasks(Generic[T]):
    timeout: float | None = None

    _started: list[asyncio.Task[T]] = dataclasses.field(default_factory=list)
    _deferred: list[C[None]] = dataclasses.field(default_factory=list)
    _awaited: bool = False  # indicates if Tasks were awaited to finish.

    @property
    def all_done(self) -> bool:
        return all(task.done() for task in self._started)

    @property
    def any_done(self) -> bool:
        return any(task.done() for task in self._started)

    @property
    def all_cancelled(self) -> bool:
        return all(task.cancelled() for task in self._started)

    @property
    def any_cancelled(self) -> bool:
        return any(task.cancelled() for task in self._started)

    @property
    def results(self) -> list[T]:
        return [task.result() for task in self._started]

    @property
    def available_results(self) -> list[T]:
        return [task.result() for task in self._started if task.done()]

    def start(self, coro: C[T]) -> None:
        """Immediately start coroutine.
        """
        task = asyncio.create_task(coro)
        self._started.append(task)

    def defer(self, coro: C[None]) -> None:
        self._deferred.append(coro)

    async def cancel_all(self) -> None:
        self._awaited = True
        for task in self._started:
            task.cancel()

    async def wait_all_cancelled(self, duration: float = 5, pause: float = 0) -> None:
        assert math.isfinite(pause)
        start = time.monotonic()
        for task in self._started:
            while not task.cancelled():
                if not math.isinf(duration):
                    spent = time.monotonic() - start
                    if spent > duration:
                        raise TimeoutError
                await asyncio.sleep(pause)

    def merge(self, other: Tasks[G]) -> Tasks[T | G]:
        assert not self._awaited
        assert not other._awaited
        return dataclasses.replace(
            self,
            _started=self._started + other._started,  # type: ignore
            _deferred=self._deferred + other._deferred,
        )

    def copy(self) -> Tasks[T]:
        return dataclasses.replace(
            self,
            _started=self._started.copy(),
            _deferred=self._deferred.copy(),
        )

    async def wait(self) -> list[T]:
        """Wait for all started and deferred coroutines to finish.
        """
        try:
            results = await self._wait()
        finally:
            await self._run_deferred()
        return results

    async def wait_unordered(self, pause: float = 0) -> AsyncIterator[T]:
        """Wait for all started and deferred coroutines to finish.
        """
        try:
            async for result in self._wait_unordered(pause=pause):
                yield result
        finally:
            await self._run_deferred()

    async def _wait(self) -> list[T]:
        self._awaited = True
        if not self._started:
            return []
        future = asyncio.gather(*self._started)
        results = await asyncio.wait_for(future, timeout=self.timeout)
        return results

    async def _wait_unordered(self, pause: float) -> AsyncIterator[T]:
        self._awaited = True
        pending = self._started
        while pending:
            new_pending = []
            for task in pending:
                if task.done():
                    yield task.result()
                else:
                    new_pending.append(task)
            pending = new_pending
            if pending:
                await asyncio.sleep(pause)

    async def _run_deferred(self) -> None:
        future = asyncio.gather(*self._deferred)
        await asyncio.wait_for(future, timeout=self.timeout)

    def __del__(self) -> None:
        if not self._awaited:
            cls = type(self)
            warnings.warn(f'{cls.__name__}.wait was never called')

    async def __aenter__(self: G) -> G:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            await self.wait()
        else:
            await self._run_deferred()

    def __await__(self) -> Generator[object, object, list[T]]:
        coro = self.wait()
        result = yield from asyncio.ensure_future(coro)
        return result
