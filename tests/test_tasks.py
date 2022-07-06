from dataclasses import dataclass
import pytest
from asynchrony import Tasks


async def double(x: int) -> int:
    return x * 2


@dataclass
class Mock:
    calls: int = 0

    async def entry(self) -> None:
        self.calls += 1


@pytest.mark.asyncio
async def test_basic_start_and_wait() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(3))
    tasks.start(double(7))
    results = await tasks.wait()
    assert results == [6, 14]

    assert results == tasks.results
    assert results == tasks.available_results

    assert tasks.any_done
    assert tasks.all_done
    assert not tasks.any_cancelled
    assert not tasks.all_cancelled


@pytest.mark.asyncio
async def test_await() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(3))
    results = await tasks
    assert results == [6]


@pytest.mark.asyncio
async def test_wait_twice() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(3))
    results1 = await tasks.wait()
    results2 = await tasks.wait()
    assert results1 == results2


@pytest.mark.asyncio
async def test_wait_empty() -> None:
    tasks = Tasks[int](timeout=5)
    results = await tasks.wait()
    assert results == []


@pytest.mark.asyncio
async def test_context_manager() -> None:
    async with Tasks[int](timeout=5) as tasks:
        tasks.start(double(3))
    assert tasks.all_done
    assert tasks.results == [6]


@pytest.mark.asyncio
async def test_copy() -> None:
    tasks1 = Tasks[int](timeout=5)
    tasks1.start(double(3))

    tasks2 = tasks1.copy()
    tasks2.start(double(4))

    results1 = await tasks1
    results2 = await tasks2

    assert results1 == [6]
    assert results2 == [6, 8]


@pytest.mark.asyncio
async def test_cancel_all() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(4))

    assert not tasks.any_cancelled
    assert not tasks.any_done

    await tasks.cancel_all()
    await tasks.wait_all_cancelled()

    assert tasks.any_cancelled
    assert tasks.all_cancelled
    assert tasks.any_done
    assert tasks.all_done


@pytest.mark.asyncio
async def test_wait_unordered() -> None:
    tasks = Tasks[int](timeout=5)
    tasks.start(double(4))
    tasks.start(double(6))

    results = set()
    async for result in tasks.wait_unordered():
        results.add(result)
    assert results == {8, 12}


@pytest.mark.asyncio
async def test_defer() -> None:
    tasks = Tasks[int](timeout=5)
    mock = Mock()
    tasks.defer(mock.entry())
    await tasks
    assert mock.calls == 1
