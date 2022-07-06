from __future__ import annotations

import asyncio
import dataclasses
from functools import cached_property
import math
import time
import warnings
from typing import AsyncIterator, Callable, Coroutine, Generator, Generic, Iterable, TypeVar


T = TypeVar('T', covariant=True)
G = TypeVar('G')
C = Coroutine[object, object, T]


@dataclasses.dataclass
class Tasks(Generic[T]):
    timeout: float | None = None

    _started: list[asyncio.Task[T]] = dataclasses.field(default_factory=list)
    _deferred: list[C[None]] = dataclasses.field(default_factory=list)
    _awaited: bool = False

    @classmethod
    def map(
        cls,
        f: Callable[[G], C[T]],
        items: Iterable[G],
        timeout: float = None,
    ) -> Tasks[T]:
        tasks = cls(timeout=timeout)
        for item in items:
            tasks.start(f(item))
        return tasks

    @property
    def all_done(self) -> bool:
        return all(task.done() for task in self._started)

    @property
    def any_done(self) -> bool:
        return any(task.done() for task in self._started)

    @property
    def done_count(self) -> int:
        return sum(task.done() for task in self._started)

    @property
    def all_cancelled(self) -> bool:
        return all(task.cancelled() for task in self._started)

    @property
    def any_cancelled(self) -> bool:
        return any(task.cancelled() for task in self._started)

    @property
    def cancelled_count(self) -> int:
        return sum(task.cancelled() for task in self._started)

    @cached_property
    def results(self) -> list[T]:
        assert self._awaited, 'the tasks should be awaited before you can get results'
        return [task.result() for task in self._started]

    @property
    def available_results(self) -> list[T]:
        return [task.result() for task in self._started if task.done()]

    def start(self, coro: C[T], name: str | None = None) -> None:
        """Immediately schedule the coroutine.
        """
        task = asyncio.create_task(coro, name=name)
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

    async def wait(self) -> None:
        """Wait for all started and deferred coroutines to finish.
        """
        async for _ in self.get_channel():
            pass

    async def get_list(self) -> list[T]:
        """Wait for all started and deferred coroutines to finish.
        """
        try:
            results = await self._list()
        finally:
            await self._run_deferred()
            self._awaited = True
        return results

    async def get_channel(self) -> AsyncIterator[T]:
        """Wait for all started and deferred coroutines to finish.
        """
        try:
            futures = asyncio.as_completed(self._started, timeout=self.timeout)
            for future in futures:
                yield await future
        finally:
            await self._run_deferred()
            self._awaited = True

    async def _list(self) -> list[T]:
        if not self._started:
            return []
        future = asyncio.gather(*self._started)
        results = await asyncio.wait_for(future, timeout=self.timeout)
        return results

    async def _run_deferred(self) -> None:
        self._awaited = True
        if not self._deferred:
            return
        future = asyncio.gather(*self._deferred)
        await asyncio.wait_for(future, timeout=self.timeout)
        self._deferred = []

    def __del__(self) -> None:
        if not self._awaited:
            warnings.warn('Tasks instance was never awaited')

    async def __aenter__(self: G) -> G:
        return self

    async def __aexit__(self, exc_type: Exception | None, exc, tb) -> None:
        if exc_type is None:
            await self.get_list()
        else:
            await self._run_deferred()

    def __await__(self) -> Generator[object, object, list[T]]:
        coro = self.get_list()
        result = yield from asyncio.ensure_future(coro)
        return result
