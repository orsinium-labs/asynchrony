from __future__ import annotations

import asyncio
import dataclasses
from functools import cached_property
import time
import warnings
from typing import AsyncIterator, Callable, Coroutine, Generator, Generic, Iterable, TypeVar


T = TypeVar('T', covariant=True)
G = TypeVar('G')
C = Coroutine[object, object, T]


@dataclasses.dataclass
class Tasks(Generic[T]):
    """Manager for async tasks.

    Example::

        tasks = Tasks(timeout=5)
        for name in names:
            tasks.start(get_user(name))
        users = await tasks

    """
    timeout: float | None = None

    _started: list[asyncio.Task[T]] = dataclasses.field(default_factory=list)
    _deferred: list[C[None]] = dataclasses.field(default_factory=list)
    _awaited: bool = False

    @property
    def all_done(self) -> bool:
        """True if all the wrapped tasks are done.

        "Done" also includes failed and cancelled tasks.
        """
        return all(task.done() for task in self._started)

    @property
    def any_done(self) -> bool:
        """True if any of the wrapped tasks is done.

        "Done" also includes failed and cancelled tasks.
        """
        return any(task.done() for task in self._started)

    @property
    def done_count(self) -> int:
        """How many tasks are done.

        "Done" also includes failed and cancelled tasks.
        """
        return sum(task.done() for task in self._started)

    @property
    def all_cancelled(self) -> bool:
        """True if all the wrapped tasks are cancelled.
        """
        return all(task.cancelled() for task in self._started)

    @property
    def any_cancelled(self) -> bool:
        """True if any of the wrapped tasks is cancelled.
        """
        return any(task.cancelled() for task in self._started)

    @property
    def cancelled_count(self) -> int:
        """How many wrapped tasks are cancelled.
        """
        return sum(task.cancelled() for task in self._started)

    @cached_property
    def results(self) -> list[T]:
        """The list of results from all wrapped tasks.

        It can be used only after the `Tasks` was awaited and all tasks were successful.
        """
        assert self._awaited, 'the tasks should be awaited before you can get results'
        return [task.result() for task in self._started]

    @property
    def available_results(self) -> list[T]:
        """Get results of all done tasks.
        """
        return [task.result() for task in self._started if task.done()]

    def map(self, items: Iterable[G], f: Callable[[G], C[T]]) -> None:
        """Start `f` for each item from `items`.
        """
        self._started.extend(asyncio.create_task(f(item)) for item in items)

    def start(self, coro: C[T], name: str | None = None) -> None:
        """Schedule the coroutine.

        The coroutine may be executed the next time you call `await` anywhere in your code.
        It will be definitely executed when you await this `Tasks` instance.
        """
        task = asyncio.create_task(coro, name=name)
        self._started.append(task)

    def defer(self, coro: C[None]) -> None:
        """Execute the coroutine after all tasks are finished (or any failed).

        Use it to close resources needed for the tasks.
        See also: `contextlib.AsyncExitStack`.
        """
        self._deferred.append(coro)

    async def cancel_all(self) -> None:
        """Request cancellation for all wrapped tasks.

        It will raise `asyncio.CancelledError` from the current `await` of each task.
        The exception may be caught or suppressed by the task.
        """
        self._awaited = True
        for task in self._started:
            task.cancel()

    async def wait_all_cancelled(self) -> None:
        """Block until all tasks are cancelled.

        If timeout is reached, `TimeoutError` is raised.
        """
        start = time.monotonic()
        for task in self._started:
            while not task.cancelled():
                if self.timeout is not None:
                    spent = time.monotonic() - start
                    if spent > self.timeout:
                        raise TimeoutError
                await asyncio.sleep(0)

    def merge(self, other: Tasks[G]) -> Tasks[T | G]:
        """Merge tasks from the current and the given `Tasks` instances.
        """
        assert not self._awaited
        assert not other._awaited
        return dataclasses.replace(
            self,
            _started=self._started + other._started,  # type: ignore
            _deferred=self._deferred + other._deferred,
        )

    def copy(self) -> Tasks[T]:
        """Create a deep copy of the `Tasks` instance.
        """
        return dataclasses.replace(
            self,
            _started=self._started.copy(),
            _deferred=self._deferred.copy(),
        )

    async def wait(self) -> None:
        """Wait for all started and deferred tasks to finish.
        """
        async for _ in self.get_channel():
            pass

    async def get_list(self) -> list[T]:
        """Wait for all started and deferred tasks to finish.

        Returns the list of tasks results in the same order as tasks were started.
        """
        try:
            results = await self._list()
        finally:
            await self._run_deferred()
            self._awaited = True
        return results

    async def get_channel(self) -> AsyncIterator[T]:
        """Iterate over results of all coroutines out of order.

        Each result is returned as soon as any task completes.
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
        """Use Tasks as a context manager to automatically await on exit.

        Tasks as a context manager:
        1. Awaits for all wrapped tasks when leaving the context.
        2. Always runs deferred functions, even if the context fails.
        """
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

    def __add__(self, other: Tasks[G]) -> Tasks[T | G]:
        return self.merge(other)
