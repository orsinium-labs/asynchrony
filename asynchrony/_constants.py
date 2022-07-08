from __future__ import annotations
import enum


class Behavior(enum.Enum):
    RETURN = enum.auto()
    RAISE = enum.auto()
    SKIP = enum.auto()
    NONE = enum.auto()
    AWAIT = enum.auto()

    def pipe(self, exc: BaseException) -> BaseException | None:
        if self is Behavior.RETURN:
            return exc
        if self is Behavior.RAISE:
            raise exc
        if self is Behavior.NONE:
            return None
        raise RuntimeError('invalid state')  # pragma: no cover
