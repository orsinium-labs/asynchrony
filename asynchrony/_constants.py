from __future__ import annotations
import enum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from typing import Final


class Behavior(enum.Enum):
    RETURN = enum.auto()    # return exceptions as values
    RAISE = enum.auto()     # raise exceptions
    SKIP = enum.auto()      # skip invalid values
    NONE = enum.auto()      # return None instead of the invalid value
    AWAIT = enum.auto()     # (only for pending) block and await for the result

    def pipe(self, exc: BaseException) -> BaseException | None:
        if self is Behavior.RETURN:
            return exc
        if self is Behavior.RAISE:
            raise exc
        if self is Behavior.NONE:
            return None
        raise RuntimeError('invalid state')  # pragma: no cover


RETURN: Literal[Behavior.RETURN] = Behavior.RETURN
RAISE: Literal[Behavior.RAISE] = Behavior.RAISE
SKIP: Final = Behavior.SKIP
NONE: Final = Behavior.NONE
AWAIT: Final = Behavior.AWAIT  # not exported, only used as default
