import asyncio
from random import randint
import pytest
from asynchrony import make_safe


async def double(x: int) -> int:
    for _ in range(4):
        if randint(0, 1):
            await asyncio.sleep(0)
    return x * 2


async def fail() -> int:
    raise ZeroDivisionError


@pytest.mark.asyncio
async def test_make_safe__ok() -> None:
    result = await make_safe(double(3))
    assert result == 6


@pytest.mark.asyncio
async def test_make_safe__fail() -> None:
    with pytest.raises(ZeroDivisionError):
        await fail()
    result = await make_safe(fail())
    assert result is None


@pytest.mark.asyncio
async def test_make_safe__no_logger() -> None:
    result = await make_safe(fail(), logger=None)
    assert result is None


@pytest.mark.asyncio
async def test_make_safe__default() -> None:
    result = await make_safe(fail(), default=13)
    assert result == 13
