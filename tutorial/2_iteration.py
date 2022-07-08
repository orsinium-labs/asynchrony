import asyncio
from aiohttp import ClientSession
from asynchrony import Tasks

URLS = (
    'https://google.com/',
    'https://orsinium.dev/',
)


async def check_if_healthy(session: ClientSession, url: str) -> str:
    resp = await session.get(url)
    return f'{url=} {resp.ok=}'


async def main() -> None:
    tasks = Tasks[str](timeout=5)
    async with ClientSession() as session:
        # `tasks.map` is a shortcut for calling `tasks.start` in a loop for each item
        # of a sequence.
        tasks.map(URLS, lambda url: check_if_healthy(session, url))
        async for message in tasks.iter():
            print(message)


if __name__ == '__main__':
    asyncio.run(main())
