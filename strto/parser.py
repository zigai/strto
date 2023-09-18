import enum
import inspect
import json
from functools import partial, partialmethod
from typing import Any, Callable

from strto.constants import ITER_SEP
from strto.converters import (
    CastTo,
    Converter,
    DateConverter,
    DateTimeConverter,
    IterableConverter,
    MappingConverter,
    RangeConverter,
    SliceConverter,
)
from strto.util import (
    is_alias_type,
    is_iterable_type,
    is_mapping_type,
    is_union_type,
    type_args,
    type_origin,
)


class Parser:
    def __init__(self, converters: dict[Any, Converter] | None = None) -> None:
        self.converters: dict[Any, Converter] = converters or {}

    def __len__(self):
        return len(self.converters)

    def __getitem__(self, t: Any):
        return self.get(t)

    def add(self, t: Any, func: Converter):
        self.converters[t] = func

    def extend(self, parsers: dict[Any, Converter]):
        self.converters.update(parsers)

    def get(self, t: Any):
        return self.converters[t]

    def parse(self, value: str, t: Any) -> Any:
        if parser := self.converters.get(t, None):
            return parser(value)
        if is_alias_type(t):
            return self.parse_alias(value, t)
        if is_union_type(t):
            return self.parse_union(value, t)
        if value is None:
            return None
        return self.parse_special(value, t)

    def get_parse_fn(self, t: Any) -> Callable[[str], Any]:
        return partial(self.parse, t=t)

    def parse_alias(self, value: str, t: Any):
        """
        Alias example: list[int]
        """
        base_type = type_origin(t)
        sub_types = type_args(t)

        if is_mapping_type(base_type):
            key_type, value_type = sub_types
            mapping_instance = base_type()
            for k, v in json.loads(value).items():
                mapping_instance[self.parse(k, key_type)] = self.parse(v, value_type)
            return mapping_instance

        elif is_iterable_type(base_type):
            item_type = sub_types[0]
            return base_type([self.parse(i.strip(), item_type) for i in value.split(ITER_SEP)])

        raise NotImplementedError

    def parse_union(self, value: str, t: Any) -> Any:
        """
        Union example: int | float
        """
        for i in type_args(t):
            try:
                return self.parse(value, i)
            except Exception:
                continue
        raise ValueError(f"Could not parse {value} as {t}")

    def parse_special(self, value: str, t: Any) -> Any:
        """
        Currently supports:
        - enum.Enum

        """
        if inspect.isclass(t):
            if issubclass(t, enum.Enum):
                return t[value]
        raise NotImplementedError


def get_parser(from_file=True) -> Parser:
    import datetime
    import decimal
    import fractions
    import pathlib
    from collections import ChainMap, Counter, OrderedDict, defaultdict, deque

    DIRECTLY_CASTABLE_TYPES = [
        bool,
        str,
        int,
        float,
        decimal.Decimal,
        fractions.Fraction,
        pathlib.Path,
        pathlib.PosixPath,
        pathlib.WindowsPath,
        pathlib.PureWindowsPath,
        pathlib.PurePosixPath,
        bytearray,
    ]

    ITER_CONTAINER_TYPES = [frozenset, deque, set, tuple]
    MAPPING_CONTAINER_TYPES = [dict, OrderedDict, defaultdict, ChainMap, Counter]

    parser = Parser(
        {
            range: RangeConverter(),
            slice: SliceConverter(),
            list: IterableConverter(),
            datetime.datetime: DateTimeConverter(),
            datetime.date: DateConverter(),
        }
    )

    for t in DIRECTLY_CASTABLE_TYPES:
        parser.add(t, CastTo(t))

    for t in MAPPING_CONTAINER_TYPES:
        parser.add(t, MappingConverter(t, from_file=from_file))

    for t in ITER_CONTAINER_TYPES:
        parser.add(t, IterableConverter(t, from_file=from_file))

    return parser


__all__ = ["Parser", "get_parser"]
