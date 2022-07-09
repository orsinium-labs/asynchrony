from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import cached_property
from types import FrameType
from typing import Generic, TypeVar

T = TypeVar('T')


@dataclass
class Task(Generic[T]):
    """Task is a concurrent worker.

    It holds information about the worker and allows to cancel it.

    1. Create a new task: `Tasks.start`.
    1. Iterate over tasks: `for task in tasks`.
    """
    _task: asyncio.Task[T]

    @property
    def cancelled(self) -> bool:
        """True if the task is cancelled.

        You can cancel the task by calling `Task.cancel`.
        """
        return self._task.cancelled()

    @property
    def done(self) -> bool:
        """True if the task is done.

        "Done" means on of:

        1. The task finished successfully (returned a result).
        1. The task raised an exception.
        1. The task was cancelled.

        In other words, it's NOT done only if it still has work to do.
        """
        return self._task.done()

    @property
    def failed(self) -> bool:
        """True if the task failed with an exception.

        False if:

        1. The task isn't finished yet
        1. The task was cancelled
        1. The task finished successfully (returned a result).
        """
        if self._task.cancelled():
            return False
        if not self._task.done():
            return False
        return self._task.exception() is not None

    @property
    def ok(self) -> bool:
        """Check if the task finished successfully.

        It will return False if:

        1. The task is still pending.
        1. The task failed.
        1. The task was cancelled.
        """
        try:
            self._task.result()
        except (Exception, asyncio.CancelledError):
            return False
        else:
            return True

    @property
    def exception(self) -> BaseException | None:
        """If the task failed with an exception, get this exception.
        """
        if not self._task.done():
            return None
        try:
            return self._task.exception()
        except asyncio.CancelledError as exc:
            return exc

    @cached_property
    def result(self) -> T:
        """
        Return the result this future represents.

        1. If the task has been cancelled, raises `asyncio.CancelledError`.
        1. If the task result isn't yet available, raises `asyncio.InvalidStateError`.
        1. If the task failed with an exception, this exception is raised.
        """
        return self._task.result()

    @property
    def name(self) -> str:
        """Get the name of the task as passed into `Tasks.start`.
        """
        return self._task.get_name()

    @property
    def stack(self) -> list[FrameType]:
        """Return the list of stack frames for this task's coroutine.

        If the coroutine is not done, this returns the stack where it is
        suspended.  If the coroutine has completed successfully or was
        cancelled, this returns an empty list.  If the coroutine was
        terminated by an exception, this returns the list of traceback
        frames.
        """
        return self._task.get_stack()

    def cancel(self) -> None:
        """Request that this task cancel itself.

        This arranges for a CancelledError to be thrown into the
        wrapped coroutine on the next cycle through the event loop.
        The coroutine then has a chance to clean up or even deny
        the request using try/except/finally.

        This does not guarantee that the task will be cancelled:
        the exception might be caught and acted upon, delaying
        cancellation of the task or preventing cancellation completely.
        The task may also return a value or raise a different exception.

        Immediately after this method is called, `Task.cancelled` will
        not return True (unless the task was already cancelled). A
        task will be marked as cancelled when the wrapped coroutine
        terminates with a CancelledError exception (even if cancel()
        was not called).
        """
        self._task.cancel()
