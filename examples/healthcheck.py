import asyncio
from aiohttp import ClientSession
from asynchrony import Tasks

URLS = (
    'https://google.com/',
    'https://orsinium.dev/',
)


async def check_is_healthy(session: ClientSession, url: str) -> bool:
    resp = await session.get(url)
    return resp.ok


async def main() -> None:
    tasks = Tasks[bool](timeout=5, cancel_on_failure=False)
    async with ClientSession() as session:
        for url in URLS:
            tasks.start(check_is_healthy(session, url))
        states = await tasks
    for url, is_healthy in zip(URLS, states):
        print(f'{url=}, {is_healthy=}')


if __name__ == '__main__':
    asyncio.run(main())
