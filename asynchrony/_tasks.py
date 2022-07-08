from __future__ import annotations

import asyncio
import dataclasses
import warnings
from functools import cached_property
from typing import (
    TYPE_CHECKING, AsyncIterator, Awaitable, Callable, Coroutine, Generator,
    Generic, Iterable, List, TypeVar,
)

from ._constants import Behavior

T = TypeVar('T', covariant=True)
if TYPE_CHECKING:
    G = TypeVar('G')
    C = Coroutine[object, object, T]


@dataclasses.dataclass
class Tasks(Generic[T]):
    """Manager for async tasks.

    Args:

        timeout: how long to await for tasks to finish.
        cancel_on_failure: if a task fails, cancel all other tasks.
            It includes cases when a task was cancelled or timed out.
        max_concurrency: how many workers can be executed at the same time.

    Example::

        tasks = Tasks(timeout=5)
        for name in names:
            tasks.start(get_user(name))
        users = await tasks

    """
    timeout: float | None = None
    cancel_on_failure: bool = True
    max_concurrency: int | None = None

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

    @property
    def all_succesful(self) -> bool:
        """True if none of the tasks were failed or cancelled.
        """
        assert self._awaited, 'tasks must be awaited first'
        for task in self._started:
            if not task.done():
                return False
            if task.cancelled():
                return False
            if task.exception() is not None:
                return False
        return True

    @cached_property
    def exceptions(self) -> tuple[BaseException, ...]:
        """All exceptions raised from tasks.

        It can be used only after the `Tasks` was awaited.
        """
        assert self._awaited, 'tasks must be awaited before you can get exceptions'
        exceptions: list[BaseException] = []
        for task in self._started:
            try:
                exc = task.exception()
            except asyncio.CancelledError as err:
                exceptions.append(err)
            else:
                if exc is not None:
                    exceptions.append(exc)
        return tuple(exceptions)

    @cached_property
    def _semaphore(self) -> asyncio.Semaphore:
        assert self.max_concurrency is not None
        return asyncio.Semaphore(self.max_concurrency)

    def map(self, items: Iterable[G], f: Callable[[G], C[T]]) -> None:
        """Start `f` for each item from `items`.
        """
        assert not self._awaited, 'tasks already awaited'
        for item in items:
            coro = f(item)
            if self.max_concurrency is not None:
                coro = self._run_with_semaphore(coro)
            self._started.append(asyncio.create_task(coro))

    def start(self, coro: C[T], name: str | None = None) -> None:
        """Schedule the coroutine.

        The coroutine may be executed the next time you call `await` anywhere in your code.
        It will be definitely executed when you await this `Tasks` instance.
        """
        assert not self._awaited, 'tasks already awaited'
        if self.max_concurrency is not None:
            coro = self._run_with_semaphore(coro)
        task = asyncio.create_task(coro, name=name)
        self._started.append(task)

    async def _run_with_semaphore(self, coro: C[T]) -> T:
        async with self._semaphore:
            return await coro

    def defer(self, coro: C[None]) -> None:
        """Execute the coroutine after all tasks are finished (or any failed).

        Use it to close resources needed for the tasks.
        See also: `contextlib.AsyncExitStack`.
        """
        self._deferred.append(coro)

    def cancel_all(self) -> None:
        """Request cancellation for all wrapped tasks.

        It will raise `asyncio.CancelledError` from the current `await` of each task.
        The exception may be caught or suppressed by the task.
        """
        self._awaited = True
        for task in self._started:
            task.cancel()

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

    async def wait(self, *, safe: bool = False) -> None:
        """Wait for all started and deferred tasks to finish.

        If `safe=True`, all exceptions from tasks will be ignored.
        Otherwise, if a task raised an exception, `wait` wil re-raise it.
        """
        beh = Behavior.SKIP if safe else Behavior.RAISE
        async for _ in self.iter(failed=beh, cancelled=beh, pending=Behavior.AWAIT):
            pass

    async def list(
        self, *,
        failed: Behavior = Behavior.RAISE,
        cancelled: Behavior = Behavior.RAISE,
        pending: Behavior = Behavior.AWAIT,
    ) -> List[T | BaseException | None]:
        """Wait for all started and deferred tasks to finish.

        Returns the list of tasks results in the same order as tasks were started.
        """
        iterator = self.iter(
            failed=failed,
            cancelled=cancelled,
            pending=pending,
            ordered=True,
        )
        return [result async for result in iterator]

    async def iter(
        self, *,
        failed: Behavior = Behavior.RAISE,
        cancelled: Behavior = Behavior.RAISE,
        pending: Behavior = Behavior.AWAIT,
        ordered: bool = False,
    ) -> AsyncIterator[T | BaseException | None]:
        """Iterate over results of all coroutines.

        If `ordered=False` (default), each result is returned as soon
        as any task completes. Otherwise, it will go through all wrapped tasks
        and wait for each to finish.
        """
        results = self._iter(
            failed=failed,
            cancelled=cancelled,
            pending=pending,
            ordered=ordered,
        )
        try:
            async for result in results:
                yield result
        except (Exception, asyncio.CancelledError) as exc:
            self._handle_failure(exc)
            raise
        finally:
            await self._run_deferred()
            self._awaited = True

    async def _iter(
        self, failed: Behavior, cancelled: Behavior, pending: Behavior, ordered: bool,
    ) -> AsyncIterator[T | BaseException | None]:
        futures: Iterable[Awaitable[T]]
        if ordered:
            futures = self._started
        else:
            futures = asyncio.as_completed(self._started, timeout=self.timeout)
        for future in futures:
            try:
                if pending is Behavior.AWAIT:
                    result = await asyncio.wait_for(future, timeout=self.timeout)
                else:
                    result = future.result()
            except asyncio.CancelledError as exc:
                if cancelled is not Behavior.SKIP:
                    yield cancelled.pipe(exc)
            except asyncio.InvalidStateError as exc:
                if pending is not Behavior.SKIP:
                    yield pending.pipe(exc)
            except Exception as exc:
                if failed is not Behavior.SKIP:
                    yield failed.pipe(exc)
            else:
                yield result

    async def _run_deferred(self) -> None:
        self._awaited = True
        if not self._deferred:
            return
        future = asyncio.gather(*self._deferred)
        await asyncio.wait_for(future, timeout=self.timeout)
        self._deferred = []

    def _handle_failure(self, exc: BaseException) -> None:
        if not self.cancel_on_failure:
            return
        for task in self._started:
            task.cancel()

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
            await self.list()
        else:
            await self._run_deferred()

    def __await__(self) -> Generator[object, object, List[T]]:
        coro = self.list()
        result = yield from asyncio.ensure_future(coro)
        return result  # type: ignore[return-value]

    def __add__(self, other: Tasks[G]) -> Tasks[T | G]:
        return self.merge(other)
