"""
This is the first tutorial.
It will show you the basics of using `Tasks` to wait for multiple tasks to finish.
"""
import asyncio
from aiohttp import ClientSession
from asynchrony import Tasks

URLS = (
    'https://google.com/',
    'https://orsinium.dev/',
)


async def check_if_healthy(session: ClientSession, url: str) -> bool:
    resp = await session.get(url)
    return resp.ok


async def main() -> None:
    # * `[bool]` specifies the return type of all tasks that you're going to schedule.
    #   It makes your code type-safe.
    # * `timeout` is how long (in seconds) to wait for all tasks to finish before
    #   raising `TimeoutError`. You should always specify a timeout.
    tasks = Tasks[bool](timeout=5)
    async with ClientSession() as session:
        for url in URLS:
            tasks.start(check_if_healthy(session, url))
        states = await tasks
    # `await tasks` always returns results in the same order as the corresponding
    # tasks are started. So, we can safely `zip` it to match URLs to results.
    for url, is_healthy in zip(URLS, states):
        print(f'{url=}, {is_healthy=}')


if __name__ == '__main__':
    asyncio.run(main())
