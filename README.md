# asynchrony

Python [asyncio](https://docs.python.org/3/library/asyncio.html) framework for writing safe and fast concurrent code.

Features:

+ Type annotated and type safe
+ Makes it easy to work with cancellation, errors, and scheduling.
+ Well tested and well documented.
+ Zero dependency.
+ Based on real world experience and pain.

## Installation and usage

```bash
python3 -m pip install asynchrony
```

A simple example of starting 100 tasks concurrently and waiting for all of them to finish:

```python
from asynchrony import Tasks

async def download_page(url: str) -> bytes:
    ...

tasks = Tasks[bytes](timeout=10, max_concurrency=100)
for url in URLS:
    tasks.start(download_page(url))
pages = await tasks
```

See [tutorial](./tutorial) for runnable usage examples.
