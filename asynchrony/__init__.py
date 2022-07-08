"""Collection of utilities to write safe asyncio code.
"""
from ._constants import Behavior, RETURN, RAISE, SKIP, NONE
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
