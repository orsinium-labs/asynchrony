from __future__ import annotations

import asyncio
import dataclasses
import warnings
from typing import Coroutine, Generic, TypeVar


T = TypeVar('T')
G = TypeVar('G')
C = Coroutine[object, object, T]


@dataclasses.dataclass
class Tasks(Generic[T]):
    timeout: int

    _started: list[asyncio.Task[T]] = dataclasses.field(default_factory=list)
    _deferred: list[C[None]] = dataclasses.field(default_factory=list)
    _awaited: bool = False  # indicates if Tasks were awaited to finish.

    def start(self, coro: C[T]) -> None:
        """Immediately start coroutine.
        """
        task = asyncio.create_task(coro)
        self._started.append(task)

    def defer(self, coro: C[None]) -> None:
        self._deferred.append(coro)

    def merge(self, other: Tasks[G]) -> Tasks[T | G]:
        assert not self._awaited
        assert not other._awaited
        return dataclasses.replace(
            self,  # type: ignore
            _started=self._started + other._started,    # type: ignore
            _deferred=self._deferred + other._deferred,
        )

    def copy(self) -> Tasks[T]:
        return dataclasses.replace(self)

    async def wait(self) -> None:
        """Wait for all started and deferred coroutines to finish.
        """
        await self.run()

    async def run(self) -> list[T]:
        """Wait for all started and deferred coroutines to finish.
        """
        try:
            results = await self._wait()
        finally:
            await self._run_deferred()
        return results

    async def _wait(self) -> list[T]:
        self._awaited = True
        if not self._started:
            return []
        future = asyncio.gather(*self._started)
        results = await asyncio.wait_for(future, timeout=self.timeout)
        return results

    async def _run_deferred(self) -> None:
        await asyncio.gather(*self._deferred)

    def __del__(self) -> None:
        if not self._awaited:
            warnings.warn("Tasks.run was never called")
