from __future__ import annotations
import enum


class Behavior(enum.Enum):
    RETURN = enum.auto()
    RAISE = enum.auto()
    SKIP = enum.auto()
    NONE = enum.auto()

    def pipe(self, exc: BaseException) -> BaseException | None:
        if self is Behavior.RETURN:
            return exc
        if self is Behavior.RAISE:
            raise exc
        return None
