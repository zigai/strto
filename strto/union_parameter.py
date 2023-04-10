import types
import typing
from types import FunctionType
from typing import Any

from strto.util import is_union_type, type_args, type_to_str


class UnionParameter:
    """
    UnionParameter is used to store the parameters of Union type.
    It can store multiple parameters in a tuple and can convert the Union type to its parameters using the `from_type` classmethod.

    Attributes:
    params (tuple): A tuple of parameters of Union type.

    Example:
    >>> UnionParameter((float, int))
    UnionParameter(float | int)
    >>> UnionParameter.from_type(float | int)
    UnionParameter(float | int)
    """

    def __init__(self, params: tuple) -> None:
        self.params = params

    def __iter__(self):
        for i in self.params:
            yield i

    def __repr__(self) -> str:
        params = [type_to_str(i) for i in self.params]
        params = " | ".join(params)
        return f"{self.__class__.__name__}({params})"

    @classmethod
    def from_type(cls, t):
        if not is_union_type(t):
            return cls(type_args(t))
        raise TypeError(t)
