from __future__ import annotations

import enum
import inspect
import json
from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

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

from strto.parsers import ITER_SEP, LiteralParser, Parser, fmt_parser_err
from strto.utils import unwrap_annotated

T = TypeVar("T")


def _format_type_for_repr(t: Any) -> str:
    name = getattr(t, "__name__", None)
    if name:
        return name
    return str(t)


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

    def get_parse_func(self, t: type[T]) -> _ParseFunc[T]:
        return _ParseFunc(self, t)

    def is_supported(self, t: type[T] | Any) -> bool:
        """Check if a type is supported for parsing."""
        t = unwrap_annotated(t)
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
        except (TypeError, ValueError):
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
            if base_t is tuple:  # tuple[T] or tuple[T, ...] or fixed-length tuple[T1, T2, ...]
                if not sub_t:
                    return False
                if len(sub_t) == 1:
                    return self.is_supported(sub_t[0])
                if len(sub_t) == 2 and sub_t[1] is Ellipsis:
                    return self.is_supported(sub_t[0])
                return all(self.is_supported(i) for i in sub_t)

            if not sub_t:
                return False
            item_type = sub_t[0]
            return self.is_supported(item_type)

        return False

    def _is_union_supported(self, t: type[T]) -> bool:
        for arg in type_args(t):
            if self.is_supported(arg):
                return True
        return False

    def parse(self, value: str, t: type[T] | Any) -> T:
        t = unwrap_annotated(t)
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
            try:
                items = json.loads(value)
            except ValueError as e:
                raise ValueError(
                    fmt_parser_err(value, t, "expected JSON string for mapping")
                ) from e
            for k, v in items.items():
                mapping_instance[self.parse(k, key_type)] = self.parse(v, value_type)
            return cast(T, mapping_instance)

        elif is_iterable_type(base_t):
            if base_t is tuple:
                parts = [i.strip() for i in value.split(ITER_SEP)] if value != "" else []

                if len(sub_t) == 1:  # tuple[T]
                    item_t = sub_t[0]
                    return cast(T, tuple(self.parse(i, item_t) for i in parts))

                if len(sub_t) == 2 and sub_t[1] is Ellipsis:  # tuple[T, ...]
                    item_t = sub_t[0]
                    return cast(T, tuple(self.parse(i, item_t) for i in parts))

                # fixed-length tuple
                expected_len = len(sub_t)
                if len(parts) != expected_len:
                    raise ValueError(fmt_parser_err(value, t, f"expected {expected_len} items"))
                return cast(
                    T, tuple(self.parse(v, st) for v, st in zip(parts, sub_t, strict=False))
                )

            item_t = sub_t[0]  # iterables with single parameter, e.g., list[T], set[T]
            return cast(T, base_t([self.parse(i.strip(), item_t) for i in value.split(ITER_SEP)]))

        raise TypeError(fmt_parser_err(value, t, "unsupported generic alias"))

    def _parse_union(self, value: str, t: type[T]) -> T:
        for i in type_args(t):
            try:
                return cast(T, self.parse(value, i))
            except (ValueError, TypeError, KeyError):
                continue
        tried = ", ".join([getattr(x, "__name__", str(x)) for x in type_args(t)])
        raise ValueError(fmt_parser_err(value, t, f"tried types: {tried}"))

    def _parse_special(self, value: str, t: type[T]) -> T:
        """Parse enum or literal"""
        if inspect.isclass(t):
            if issubclass(t, enum.Enum):
                try:
                    return cast(T, t[value])
                except KeyError as e:
                    choices = list(t.__members__.keys())
                    raise KeyError(fmt_parser_err(value, t, f"valid choices: {choices}")) from e

        if is_direct_literal(t):
            parser = LiteralParser(
                get_literal_choices(t),
                target_t=t,
            )
            return cast(T, parser(value))

        raise TypeError(
            fmt_parser_err(
                value,
                t,
                "unsupported type; add a custom parser via parser.add(T, ...).",
            )
        )


class _ParseFunc(Generic[T]):
    def __init__(self, parser: StrToTypeParser, t: type[T]) -> None:
        self._parser = parser
        self._t = t

    def __call__(self, value: str) -> T:
        return self._parser.parse(value, self._t)

    def __repr__(self) -> str:
        return f"parser[{_format_type_for_repr(self._t)}]"


def get_parser(from_file: bool = True) -> StrToTypeParser:
    import datetime
    import decimal
    import fractions
    import pathlib
    from collections import Counter, OrderedDict, deque

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
