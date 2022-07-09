"""
This tutorial shows how to cancel tasks, and rollback changes
"""
import asyncio
from dataclasses import dataclass
from random import randint, seed
from asynchrony import Tasks

URLS = (
    'https://i-hope-some-non-existent-website/',
    'https://google.com/',
    'https://orsinium.dev/',
)

SALARY = 5
seed(1)


@dataclass
class Employee:
    name: str
    account: int = 0

    async def send_money(self, amount: int) -> None:
        if self.name == 'Ericsson':
            raise RuntimeError('I am a company, duh')
        if randint(0, 1):
            await asyncio.sleep(.1)
        self.account += amount

    async def request_money(self, amount: int) -> None:
        if randint(0, 1):
            await asyncio.sleep(.1)
        self.account -= amount


async def main() -> None:
    employees = [
        Employee('Ericsson'),
        Employee('Joe Armstrong'),
        Employee('Robert Virding'),
        Employee('Mike Williams'),
    ]

    # `cancel_on_failure` is already `True` by default, but let's set it explicitly.
    # It indicates that if a task fails, all other unfinished tasks should be cancelled.
    tasks = Tasks[None](timeout=5, cancel_on_failure=True)
    for employee in employees:
        tasks.start(employee.send_money(SALARY))

    try:
        await tasks
    except Exception as exc:
        # Oh no! Sending money to employees failed.
        # Now, we need to stop all pending transactions
        # and rollback all finished ones.
        print(f'failed to send money: {exc}')

        # Count finished tasks.
        # It includes successful tasks, failed tasks, and already cancelled tasks.
        print(f'finished tasks: {sum(t.done for t in tasks)}')

        # Since `cancel_on_failure` is True, cancellation for all remaining tasks
        # is already requested. But if you want to make it double sure,
        # you can request cancellation explicitly:
        tasks.cancel_all()

        # At this point, `Tasks` requested cancellation of remaining tasks,
        # but some of them may still need time to actually get cancelled.
        # So, let's wait until all tasks will be "done"
        # (which includes cancelled tasks).
        # `safe=True` says to not raise exceptions for failed or cancelled tasks.
        await tasks.wait(safe=True)

        # Now, all tasks that haven't finished sending money should be cancelled:
        print(f'cancelled tasks: {sum(t.cancelled for t in tasks)}')

        print('\nbefore rollback:')
        for e in employees:
            print(f'  {e.name} has {e.account} money')

        print('\nrolling back...')
        rollback = Tasks[None](timeout=5)
        # You can iterate over tasks. It will emit `Task` instances in the order
        # as you called `Tasks.start` on each of them.
        for e, task in zip(employees, tasks):
            # `Task.ok` will be `True` for each successful task
            # and `False` for each failed or cancelled one.
            if task.ok:
                print(f'  salary of {e.name} will be rolled back')
                rollback.start(e.request_money(SALARY))
        await rollback

        print('\nafter rollback:')
        for e in employees:
            print(f'  {e.name} has {e.account} money')


if __name__ == '__main__':
    asyncio.run(main())
