"""
This tutorial shows how to not fail the main loop if one or more tasks fail.
"""
import asyncio
from aiohttp import ClientSession
from asynchrony import Tasks, RETURN

URLS = (
    'https://i-hope-some-non-existent-website/',
    'https://google.com/',
    'https://orsinium.dev/',
)


async def check_if_healthy(session: ClientSession, url: str) -> str:
    resp = await session.get(url)
    return f'{url=} {resp.ok=}'


async def main() -> None:
    tasks = Tasks[str](timeout=5)
    async with ClientSession() as session:
        tasks.map(URLS, lambda url: check_if_healthy(session, url))
        # By default, if a task fails, `Tasks.iter` will cancel all remaining tasks
        # and then re-raise the exception. We can pass `failed=RETURN` to make it
        # return exceptions as values instead of raising them.
        async for result in tasks.iter(failed=RETURN):
            print(result)
        # `Tasks.all_successful` will return False if there is any unfinished,
        # cancelled, or failed task.
        if not tasks.all_successful:
            # `Tasks.exceptions` holds all exceptions from all tasks.
            print(f'finished with {len(tasks.exceptions)} failure(s)')


if __name__ == '__main__':
    asyncio.run(main())
