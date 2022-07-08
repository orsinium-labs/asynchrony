from asynchrony import Tasks, NONE, RETURN


async def double(x: int) -> int:
    return x * 2


async def default_await() -> None:
    tasks = Tasks[int](timeout=5)
    results = await tasks
    reveal_type(results)  # R: builtins.list[builtins.int*]


class ListTypes:
    @staticmethod
    async def default_list() -> None:
        tasks = Tasks[int](timeout=5)
        results = await tasks.list()
        reveal_type(results)  # R: builtins.list*[builtins.int*]

    @staticmethod
    async def list_with_mix() -> None:
        tasks = Tasks[int](timeout=5)
        results = await tasks.list(failed=NONE, cancelled=RETURN)
        reveal_type(results[0])  # R: Union[builtins.int*, builtins.BaseException, None]


class IterTypes:
    @staticmethod
    async def default_iter() -> None:
        tasks = Tasks[int](timeout=5)
        async for val in tasks.iter():
            reveal_type(val)  # R: builtins.int*

    @staticmethod
    async def iter_with_failed_none() -> None:
        tasks = Tasks[int](timeout=5)
        async for val in tasks.iter(failed=NONE):
            reveal_type(val)  # R: Union[builtins.int*, None]

    @staticmethod
    async def iter_with_all_none() -> None:
        tasks = Tasks[int](timeout=5)
        async for val in tasks.iter(failed=NONE, cancelled=NONE, pending=NONE):
            reveal_type(val)  # R: Union[builtins.int*, None]

    @staticmethod
    async def iter_with_failed_return() -> None:
        tasks = Tasks[int](timeout=5)
        async for val in tasks.iter(failed=RETURN):
            reveal_type(val)  # R: Union[builtins.int*, builtins.BaseException]

    @staticmethod
    async def iter_with_all_return() -> None:
        tasks = Tasks[int](timeout=5)
        async for val in tasks.iter(failed=RETURN, cancelled=RETURN, pending=RETURN):
            reveal_type(val)  # R: Union[builtins.int*, builtins.BaseException]

    @staticmethod
    async def iter_with_mix() -> None:
        tasks = Tasks[int](timeout=5)
        async for val in tasks.iter(failed=RETURN, cancelled=NONE):
            reveal_type(val)  # R: Union[builtins.int*, builtins.BaseException, None]
