import enum
import inspect
import json
from collections.abc import Callable
from functools import partial
from typing import Any, TypeVar, Union, cast

from objinspect.typing import (
    get_literal_choices,
    is_direct_literal,
    is_generic_alias,
    is_iterable_type,
    is_mapping_type,
    is_union_type,
    type_args,
    type_origin,
)

from strto.parsers import ITER_SEP, Parser

T = TypeVar("T")


class StrToTypeParser:
    def __init__(
        self,
        parsers: dict[Any, Parser | Callable[[str], Any]] | None = None,
    ) -> None:
        self.parsers: dict[Any, Parser | Callable[[str], Any]] = parsers or {}

    def __len__(self):
        return len(self.parsers)

    def __getitem__(self, t: type[T]) -> Parser | Callable[[str], T]:
        return self.get(t)

    def add(self, t: type[T], parser: Parser | Callable[[str], T]) -> None:
        self.parsers[t] = parser

    def extend(self, parsers: dict[type[T], Parser | Callable[[str], T]]) -> None:
        self.parsers.update(parsers)

    def get(self, t: type[T]) -> Parser | Callable[[str], T]:
        return self.parsers[t]

    def get_parse_func(self, t: type[T] | Any) -> Callable[[str], T]:
        return partial(self.parse, t=t)

    def is_supported(self, t: type[T] | Any) -> bool:
        """Check if a type is supported for parsing."""
        try:
            if self.parsers.get(t, None):
                return True
            if is_generic_alias(t):
                return self._is_generic_supported(t)
            if is_union_type(t):
                return self._is_union_supported(t)
            if is_direct_literal(t):
                return True
            if inspect.isclass(t) and issubclass(t, enum.Enum):
                return True
        except Exception:
            return False
        else:
            return False

    def _is_generic_supported(self, t: type[T]) -> bool:
        base_t = type_origin(t)
        sub_t = type_args(t)

        if is_mapping_type(base_t):
            key_type, value_type = sub_t
            return self.is_supported(key_type) and self.is_supported(value_type)
        elif is_iterable_type(base_t):
            item_type = sub_t[0]
            return self.is_supported(item_type)

        return False

    def _is_union_supported(self, t: type[T]) -> bool:
        for arg in type_args(t):
            if self.is_supported(arg):
                return True
        return False

    def parse(self, value: str, t: type[T] | Any) -> T:
        if parser := self.parsers.get(t, None):
            return cast(T, parser(value))
        if is_generic_alias(t):
            return cast(T, self._parse_alias(value, t))
        if is_union_type(t):
            return cast(T, self._parse_union(value, t))
        if value is None:
            return cast(T, None)
        return cast(T, self._parse_special(value, t))

    def _parse_alias(self, value: str, t: type[T]) -> T:
        base_t = type_origin(t)
        sub_t = type_args(t)

        if is_mapping_type(base_t):
            key_type, value_type = sub_t
            mapping_instance = base_t()
            for k, v in json.loads(value).items():
                mapping_instance[self.parse(k, key_type)] = self.parse(v, value_type)
            return cast(T, mapping_instance)

        elif is_iterable_type(base_t):
            item_t = sub_t[0]
            return cast(T, base_t([self.parse(i.strip(), item_t) for i in value.split(ITER_SEP)]))

        raise NotImplementedError

    def _parse_union(self, value: str, t: type[T]) -> T:
        for i in type_args(t):
            try:
                return cast(T, self.parse(value, i))
            except Exception:
                continue
        raise ValueError(f"Could not parse '{value}' as '{t}'")

    def _parse_special(self, value: str, t: type[T]) -> T:
        """Parse enum or literal"""
        if inspect.isclass(t):
            if issubclass(t, enum.Enum):
                return cast(T, t[value])

        if is_direct_literal(t):
            choices = get_literal_choices(t)
            if not choices:
                raise ValueError("Empty literal")
            if value in choices:
                return cast(T, value)

            possible_types = [i for i in [int, str, bytes, bool] if i in {type(j) for j in choices}]
            for possible_type in possible_types:
                try:
                    if possible_type is bool:
                        parsed = value.lower() == "true"
                    else:
                        parsed = possible_type(value)
                    if parsed in choices:
                        return cast(T, parsed)
                except ValueError:
                    continue
            else:
                raise ValueError(
                    f"'{value}' is not a valid choice for {t}. Valid choices are: {choices}"
                )
        raise NotImplementedError(t)


def get_parser(from_file: bool = True) -> StrToTypeParser:
    """
    Args:
        from_file (bool): Allow iterable types to be loaded from a file.
    """
    import datetime
    import decimal
    import fractions
    import pathlib
    from collections import ChainMap, Counter, OrderedDict, defaultdict, deque

    from strto.parsers import (
        BoolParser,
        Cast,
        DateParser,
        DatetimeParser,
        FloatParser,
        IntParser,
        IterableParser,
        MappingParser,
        RangeParser,
        SliceParser,
    )

    DIRECTLY_CASTABLE_TYPES = [
        str,
        decimal.Decimal,
        fractions.Fraction,
        pathlib.Path,
        pathlib.PosixPath,
        pathlib.WindowsPath,
        pathlib.PureWindowsPath,
        pathlib.PurePosixPath,
        bytearray,
    ]

    ITERABLE_TYPES = [list, frozenset, deque, set, tuple]
    MAPPING_TYPES_CAST = [dict, OrderedDict, Counter]
    MAPPING_TYPES_UNPACK = []

    parser = StrToTypeParser()
    for t in DIRECTLY_CASTABLE_TYPES:
        parser.add(t, Cast(t))
    for t in MAPPING_TYPES_CAST:
        parser.add(t, MappingParser(t, from_file=from_file, mode="cast"))
    for t in MAPPING_TYPES_UNPACK:
        parser.add(t, MappingParser(t, from_file=from_file, mode="unpack"))
    for t in ITERABLE_TYPES:
        parser.add(t, IterableParser(t, from_file=from_file))

    parser.extend(
        {
            int: IntParser(),
            float: FloatParser(),
            bool: BoolParser(),
            range: RangeParser(),
            slice: SliceParser(),
            datetime.datetime: DatetimeParser(),
            datetime.date: DateParser(),
        }
    )
    return parser


__all__ = ["StrToTypeParser", "get_parser"]
