import asyncio
from dataclasses import dataclass
from random import randint
import pytest
from asynchrony import NONE, RETURN, Tasks, SKIP, RAISE


async def double(x: int) -> int:
    for _ in range(4):
        if randint(0, 1):
            await asyncio.sleep(0)
    return x * 2


async def fail() -> int:
    raise ZeroDivisionError


async def freeze() -> int:
    await asyncio.sleep(10)
    raise AssertionError


@dataclass
class Mock:
    calls: int = 0

    async def entry(self) -> None:
        self.calls += 1


@pytest.mark.asyncio
async def test_basic_start_and_list() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(3))
    tasks.start(double(7))

    assert not tasks.any_done
    assert not tasks.all_done
    assert tasks.done_count == 0
    assert not tasks.any_cancelled
    assert not tasks.all_cancelled
    assert tasks.cancelled_count == 0

    results = await tasks
    assert results == [6, 14]

    assert tasks.all_done
    assert tasks.any_done
    assert tasks.done_count == 2
    assert not tasks.any_cancelled
    assert not tasks.all_cancelled
    assert tasks.cancelled_count == 0
    assert tasks.all_successful
    assert tasks.exceptions == ()


@pytest.mark.asyncio
async def test_wait() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(3))
    await tasks.wait()
    results = await tasks.list(pending=RAISE)
    assert results == [6]


@pytest.mark.asyncio
async def test_list_twice() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(3))
    results1 = await tasks.list()
    results2 = await tasks.list(pending=RAISE)
    assert results1 == results2


@pytest.mark.asyncio
async def test_list_empty() -> None:
    tasks = Tasks[int](timeout=5)
    results = await tasks.list()
    assert results == []


@pytest.mark.asyncio
async def test_context_manager() -> None:
    async with Tasks[int](timeout=5) as tasks:
        tasks.start(double(3))
    assert tasks.all_done
    results = await tasks.list(pending=RAISE)
    assert results == [6]


@pytest.mark.asyncio
async def test_map() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.map([3, 4, 5], double)
    results = await tasks
    assert results == [6, 8, 10]


@pytest.mark.asyncio
async def test_copy() -> None:
    tasks1 = Tasks[int](timeout=5)
    tasks1.start(double(3))

    tasks2 = tasks1.copy()
    tasks1.start(double(4))
    tasks2.start(double(5))

    results1 = await tasks1
    results2 = await tasks2

    assert results1 == [6, 8]
    assert results2 == [6, 10]


@pytest.mark.asyncio
async def test_merge() -> None:
    tasks1 = Tasks[int](timeout=5)
    tasks1.start(double(3))

    tasks2 = Tasks[int](timeout=5)
    tasks2.start(double(4))

    tasks3 = tasks1.merge(tasks2)
    tasks3.start(double(5))

    results1 = await tasks1
    results2 = await tasks2
    results3 = await tasks3

    assert results1 == [6]
    assert results2 == [8]
    assert results3 == [6, 8, 10]


@pytest.mark.asyncio
async def test_plus() -> None:
    tasks1 = Tasks[int](timeout=5)
    tasks1.start(double(3))

    tasks2 = Tasks[int](timeout=5)
    tasks2.start(double(4))

    tasks3 = tasks1 + tasks2
    tasks3.start(double(5))

    results1 = await tasks1
    results2 = await tasks2
    results3 = await tasks3

    assert results1 == [6]
    assert results2 == [8]
    assert results3 == [6, 8, 10]


@pytest.mark.asyncio
async def test_cancel_all() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(4))
    tasks.start(double(5))

    assert not tasks.any_cancelled
    assert not tasks.any_done
    assert tasks.cancelled_count == 0
    assert tasks.done_count == 0

    tasks.cancel_all()
    await tasks.wait(safe=True)

    assert tasks.done_count == 2
    assert tasks.cancelled_count == 2

    assert tasks.all_done
    assert tasks.all_cancelled

    assert tasks.any_cancelled
    assert tasks.any_done


@pytest.mark.asyncio
async def test_iter() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(4))
    tasks.start(double(6))

    results = set()
    async for result in tasks.iter():
        results.add(result)
    assert results == {8, 12}


@pytest.mark.asyncio
async def test_defer() -> None:
    tasks = Tasks[int](timeout=5)
    mock = Mock()
    tasks.defer(mock.entry())
    await tasks
    assert mock.calls == 1


@pytest.mark.asyncio
async def test_defer_await_twice() -> None:
    tasks = Tasks[int](timeout=5)
    mock = Mock()
    tasks.defer(mock.entry())
    await tasks
    await tasks
    assert mock.calls == 1


@pytest.mark.asyncio
async def test_defer_twice() -> None:
    tasks = Tasks[int](timeout=5)
    mock = Mock()
    tasks.defer(mock.entry())
    tasks.defer(mock.entry())
    await tasks
    assert mock.calls == 2


@pytest.mark.asyncio
async def test_defer_context_explodes() -> None:
    mock = Mock()
    with pytest.raises(ValueError):
        async with Tasks[int](timeout=5) as tasks:
            tasks.defer(mock.entry())
            raise ValueError
    assert mock.calls == 1


@pytest.mark.asyncio
async def test_await__cancel_on_failure() -> None:
    tasks = Tasks[int](timeout=5, cancel_on_failure=True)
    tasks.start(fail())
    tasks.start(freeze())
    tasks.start(freeze())
    tasks.start(freeze())
    with pytest.raises(ZeroDivisionError):
        await tasks
    await tasks.wait(safe=True)
    assert tasks.any_cancelled
    assert tasks.done_count == 4
    assert tasks.cancelled_count == 3
    with pytest.raises((asyncio.CancelledError, ZeroDivisionError)):
        await tasks.wait()
    assert len(tasks.exceptions) == 4
    results = await tasks.list(failed=SKIP, cancelled=SKIP)
    assert results == []
    assert not tasks.all_successful


@pytest.mark.asyncio
async def test_await__do_not_cancel_on_failure() -> None:
    tasks = Tasks[int](timeout=5, cancel_on_failure=False)
    tasks.start(fail())
    tasks.start(freeze())
    tasks.start(freeze())
    tasks.start(freeze())
    with pytest.raises(ZeroDivisionError):
        await tasks
    await asyncio.sleep(0)
    assert not tasks.any_cancelled
    assert not tasks.all_successful
    tasks.cancel_all()


@pytest.mark.asyncio
async def test_timeout__await__cancel_on_failure() -> None:
    tasks = Tasks[int](timeout=.01, cancel_on_failure=True)
    tasks.start(freeze())
    tasks.start(freeze())
    with pytest.raises(asyncio.TimeoutError):
        await tasks
    assert not tasks.all_successful
    await tasks.wait(safe=True)
    assert tasks.any_cancelled
    assert tasks.all_cancelled
    assert len(tasks.exceptions) == 2
    assert type(tasks.exceptions[0]) is asyncio.CancelledError
    assert type(tasks.exceptions[1]) is asyncio.CancelledError
    assert not tasks.all_successful
    results = await tasks.list(failed=SKIP, cancelled=SKIP, pending=RAISE)
    assert results == []


@pytest.mark.asyncio
async def test_wait__cancel_on_failure() -> None:
    tasks = Tasks[int](timeout=5, cancel_on_failure=True)
    tasks.start(fail())
    tasks.start(freeze())
    tasks.start(freeze())
    tasks.start(freeze())
    with pytest.raises(ZeroDivisionError):
        await tasks.wait()
    await tasks.wait(safe=True)
    assert tasks.any_cancelled
    assert tasks.done_count == 4
    assert tasks.cancelled_count == 3
    with pytest.raises((asyncio.CancelledError, ZeroDivisionError)):
        await tasks.wait()
    assert len(tasks.exceptions) == 4
    assert not tasks.all_successful
    results = await tasks.list(failed=SKIP, cancelled=SKIP, pending=RAISE)
    assert results == []


@pytest.mark.asyncio
async def test_exceptions() -> None:
    tasks = Tasks[int](timeout=5, cancel_on_failure=True)
    tasks.start(fail())
    tasks.start(fail())
    await tasks.wait(safe=True)
    assert len(tasks.exceptions) == 2
    assert type(tasks.exceptions[0]) is ZeroDivisionError
    assert type(tasks.exceptions[1]) is ZeroDivisionError
    assert not tasks.all_successful


@pytest.mark.asyncio
async def test_max_concurrency() -> None:
    online = 0

    async def f() -> None:
        nonlocal online
        online += 1
        for _ in range(20):
            assert 1 <= online <= 4
            await asyncio.sleep(0)
        online -= 1

    tasks = Tasks[None](timeout=5, max_concurrency=4)
    for _ in range(200):
        tasks.start(f())
    await tasks
    assert online == 0


@pytest.mark.asyncio
async def test_failed() -> None:
    tasks = Tasks[int](timeout=5, cancel_on_failure=True)
    tasks.start(fail())
    tasks.start(fail())

    assert await tasks.list(failed=SKIP) == []
    assert await tasks.list(failed=NONE) == [None, None]
    results = await tasks.list(failed=RETURN)
    assert len(results) == 2
    assert type(results[0]) is ZeroDivisionError
    assert type(results[1]) is ZeroDivisionError
    with pytest.raises(ZeroDivisionError):
        await tasks.list(failed=RAISE)


@pytest.mark.asyncio
async def test_cancelled() -> None:
    tasks = Tasks[int](timeout=5, cancel_on_failure=True)
    tasks.start(fail())
    tasks.start(fail())
    tasks.cancel_all()

    assert await tasks.list(cancelled=SKIP) == []
    assert await tasks.list(cancelled=NONE) == [None, None]
    results = await tasks.list(cancelled=RETURN)
    assert len(results) == 2
    assert type(results[0]) is asyncio.CancelledError
    assert type(results[1]) is asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await tasks.list(cancelled=RAISE)


@pytest.mark.asyncio
async def test_pending() -> None:
    tasks = Tasks[int](timeout=5, cancel_on_failure=True)
    tasks.start(fail())
    tasks.start(fail())

    assert await tasks.list(pending=SKIP) == []
    assert await tasks.list(pending=NONE) == [None, None]
    results = await tasks.list(pending=RETURN)
    assert len(results) == 2
    assert type(results[0]) is asyncio.InvalidStateError
    assert type(results[1]) is asyncio.InvalidStateError
    with pytest.raises(asyncio.InvalidStateError):
        await tasks.list(pending=RAISE)
