"""Collection of utilities to write safe asyncio code.
"""
from ._constants import Behavior
from ._helpers import make_safe
from ._tasks import Tasks


__version__ = '1.0.0'
__all__ = [
    'Behavior',
    'Tasks',
    'make_safe',
    'RETURN',
    'RAISE',
    'SKIP',
    'NONE',
]


RETURN = Behavior.RETURN
RAISE = Behavior.RAISE
SKIP = Behavior.SKIP
NONE = Behavior.NONE
