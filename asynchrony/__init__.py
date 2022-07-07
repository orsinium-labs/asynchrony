"""Collection of utilities to write safe asyncio code.
"""
from ._helpers import make_safe
from ._tasks import Tasks

__version__ = '1.0.0'
__all__ = ['Tasks', 'make_safe']
