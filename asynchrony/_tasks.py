from __future__ import annotations

import asyncio
import dataclasses
from functools import cached_property
import warnings
from typing import AsyncIterator, Callable, Coroutine, Generator, Generic, Iterable, TypeVar


T = TypeVar('T', covariant=True)
G = TypeVar('G')
C = Coroutine[object, object, T]


@dataclasses.dataclass
class Tasks(Generic[T]):
    """Manager for async tasks.

    Args:

        timeout: how long to await for tasks to finish.
        cancel_on_failure: if a task fails, cancel all other tasks.
            It includes cases when a task was cancelled or timed out.

    Example::

        tasks = Tasks(timeout=5)
        for name in names:
            tasks.start(get_user(name))
        users = await tasks

    """
    timeout: float | None = None
    cancel_on_failure: bool = False

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
    def results(self) -> tuple[T, ...]:
        """Results from all wrapped tasks, except failed ones.

        It can be used only after the `Tasks` was awaited.
        Doesn't raise any exceptions, assuming that all error handling was done before,
        when awaiting for tasks to finish.
        """
        assert self._awaited, 'tasks must be awaited before you can get results'
        results = []
        for task in self._started:
            assert task.done()
            if task.cancelled():
                continue
            try:
                result = task.result()
            except Exception:
                pass
            else:
                results.append(result)
        return tuple(results)

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

    @property
    def available_results(self) -> tuple[T, ...]:
        """Results of all succesfully finished tasks so far.
        """
        results = []
        for task in self._started:
            if not task.done():
                continue
            if task.cancelled():
                continue
            try:
                results.append(task.result())
            except Exception:
                pass
        return tuple(results)

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
        async for _ in self.get_channel(safe=safe):
            pass

    async def get_list(self) -> list[T]:
        """Wait for all started and deferred tasks to finish.

        Returns the list of tasks results in the same order as tasks were started.
        """
        try:
            results = await self._list()
        except (Exception, asyncio.CancelledError) as exc:
            self._handle_failure(exc)
            raise
        finally:
            await self._run_deferred()
            self._awaited = True
        return results

    async def get_channel(self, *, safe: bool = False) -> AsyncIterator[T]:
        """Iterate over results of all coroutines out of order.

        Each result is returned as soon as any task completes.

        If `safe=True`, all exceptions from tasks will be ignored.
        Otherwise, the first encountered exception will be raised.
        """
        try:
            async for result in self._channel(safe=safe):
                yield result
        except (Exception, asyncio.CancelledError) as exc:
            self._handle_failure(exc)
            raise
        finally:
            await self._run_deferred()
            self._awaited = True

    async def _channel(self, safe: bool) -> AsyncIterator[T]:
        futures = asyncio.as_completed(self._started, timeout=self.timeout)
        for future in futures:
            try:
                result = await future
            except asyncio.CancelledError:
                if not safe:
                    raise
                curr_task = asyncio.current_task()
                if curr_task and curr_task.cancelled():
                    raise
            except Exception:
                if not safe:
                    raise
            else:
                yield result

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
            await self.get_list()
        else:
            await self._run_deferred()

    def __await__(self) -> Generator[object, object, list[T]]:
        coro = self.get_list()
        result = yield from asyncio.ensure_future(coro)
        return result

    def __add__(self, other: Tasks[G]) -> Tasks[T | G]:
        return self.merge(other)
