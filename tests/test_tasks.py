import asyncio
from dataclasses import dataclass
from random import randint
import pytest
from asynchrony import Tasks


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
    results = await tasks.get_list()
    assert results == [6, 14]

    assert results == tasks.results
    assert results == tasks.available_results

    assert tasks.any_done
    assert tasks.all_done
    assert tasks.done_count == 2
    assert not tasks.any_cancelled
    assert not tasks.all_cancelled
    assert tasks.cancelled_count == 0


@pytest.mark.asyncio
async def test_await() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(3))
    results = await tasks
    assert results == [6]


@pytest.mark.asyncio
async def test_wait() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(3))
    await tasks.wait()
    assert tasks.results == [6]
    assert tasks.available_results == [6]


@pytest.mark.asyncio
async def test_list_twice() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(3))
    results1 = await tasks.get_list()
    results2 = await tasks.get_list()
    assert results1 == results2


@pytest.mark.asyncio
async def test_list_empty() -> None:
    tasks = Tasks[int](timeout=5)
    results = await tasks.get_list()
    assert results == []


@pytest.mark.asyncio
async def test_context_manager() -> None:
    async with Tasks[int](timeout=5) as tasks:
        tasks.start(double(3))
    assert tasks.all_done
    assert tasks.results == [6]


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

    await tasks.cancel_all()
    await tasks.wait_all_cancelled()

    assert tasks.any_cancelled
    assert tasks.all_cancelled
    assert tasks.cancelled_count == 2
    assert tasks.any_done
    assert tasks.all_done
    assert tasks.done_count == 2


@pytest.mark.asyncio
async def test_get_channel() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(4))
    tasks.start(double(6))

    results = set()
    async for result in tasks.get_channel():
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
async def test_cancel_on_failure() -> None:
    tasks = Tasks[int](timeout=5, cancel_on_failure=True)
    tasks.start(fail())
    tasks.start(freeze())
    tasks.start(freeze())
    tasks.start(freeze())
    with pytest.raises(ZeroDivisionError):
        await tasks
    while not tasks.all_done:
        asyncio.sleep(0)
    assert tasks.any_cancelled
    assert tasks.done_count == 4
    assert tasks.cancelled_count == 3
