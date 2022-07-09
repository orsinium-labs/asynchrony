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

A simple example of starting concurrent tasks for all URLs (maximum 100 tasks at the same time) and waiting for all of them to finish:

```python
from asynchrony import Tasks

async def download_page(url: str) -> bytes:
    ...

urls = [...]
tasks = Tasks[bytes](timeout=10, max_concurrency=100)
tasks.map(urls, download_page)

try:
    pages = await tasks
except Exception:
    failed = sum(t.failed for t in tasks)
    print(f'{failed} tasks failed')
    cancelled = sum(t.cancelled for t in tasks)
    print(f'{cancelled} tasks cancelled')
else:
    print(f'finished {len(tasks)} tasks')
```

See [tutorial](./tutorial) for runnable usage examples.
