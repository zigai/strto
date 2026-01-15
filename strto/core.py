from __future__ import annotations

import array
import builtins
import dataclasses
import enum
import inspect
import json
import sys
import typing
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Generic, TypeVar, cast, get_type_hints

from objinspect import Class, Parameter
from objinspect.constants import EMPTY as OBJ_EMPTY
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

from strto.parsers import (
    ITER_SEP,
    LiteralParser,
    Parser,
    fmt_parser_err,
    load_data_from_file,
    load_mapping_value,
)
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
        *,
        from_file: bool = False,
        allow_class_init: bool = False,
    ) -> None:
        self.parsers: dict[Any, Parser | Callable[[str], Any]] = parsers or {}
        self.from_file = from_file
        self.allow_class_init = allow_class_init

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
            if self._is_dataclass_type(t):
                return True
            if self._is_pydantic_v2_model(t):
                return True
            if self.allow_class_init and self._is_class_init_parsable(t):
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

    def parse(self, value: Any, t: type[T] | Any) -> T:
        t = unwrap_annotated(t)
        if t in (list, dict, set, tuple, frozenset) and isinstance(value, t):
            return cast(T, value)
        if parser := self.parsers.get(t, None):
            return cast(T, parser(value))
        if self._is_dataclass_type(t):
            return cast(T, self._parse_dataclass(value, t))
        if self._is_pydantic_v2_model(t):
            return cast(T, self._parse_pydantic_v2(value, t))
        if self.allow_class_init and self._is_class_init_parsable(t):
            return cast(T, self._parse_class_init(value, t))
        if is_generic_alias(t):
            return cast(T, self._parse_alias(value, t))
        if is_union_type(t):
            return cast(T, self._parse_union(value, t))
        if value is None:
            return cast(T, None)
        return cast(T, self._parse_special(value, t))

    def _parse_alias(self, value: Any, t: type[T]) -> T:
        base_t = type_origin(t)
        sub_t = type_args(t)

        if is_mapping_type(base_t):
            key_type, value_type = sub_t
            mapping_instance = base_t()
            if isinstance(value, Mapping):
                items = value
            elif isinstance(value, str):
                try:
                    items = json.loads(value)
                except ValueError as e:
                    raise ValueError(
                        fmt_parser_err(value, t, "expected JSON string for mapping")
                    ) from e
            else:
                raise TypeError(fmt_parser_err(value, t, "expected mapping or JSON string"))
            for k, v in items.items():
                mapping_instance[self.parse(k, key_type)] = self.parse(v, value_type)
            return cast(T, mapping_instance)

        if base_t is array.array:
            from strto.parsers import ArrayParser

            item_t = sub_t[0] if sub_t else None
            type_code = ArrayParser.get_type_code(item_t)
            parser = ArrayParser(type_code=type_code)
            return cast(T, parser(value))

        if is_iterable_type(base_t):
            if isinstance(value, Mapping):
                raise TypeError(fmt_parser_err(value, t, "expected iterable or string"))
            if isinstance(value, str):
                text = value.strip()
                if text.startswith("["):
                    try:
                        parts = json.loads(text)
                    except ValueError as e:
                        raise ValueError(
                            fmt_parser_err(value, t, "expected JSON array or iterable string")
                        ) from e
                elif self.from_file and text.startswith("@"):
                    data = load_data_from_file(text[1:])
                    parts = data
                else:
                    parts = [i.strip() for i in value.split(ITER_SEP)] if value != "" else []
            elif isinstance(value, Iterable):
                parts = list(value)
            else:
                raise TypeError(fmt_parser_err(value, t, "expected iterable or string"))

            if base_t is tuple:
                if not isinstance(parts, list):
                    parts = list(parts)

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
                    T,
                    tuple(self.parse(v, st) for v, st in zip(parts, sub_t, strict=False)),
                )

            if not isinstance(parts, list):
                parts = list(parts)
            item_t = sub_t[0]  # iterables with single parameter, e.g., list[T], set[T]
            return cast(
                T,
                base_t([self.parse(i, item_t) for i in parts]),
            )

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

    def _is_dataclass_type(self, t: Any) -> bool:
        return inspect.isclass(t) and dataclasses.is_dataclass(t)

    def _is_pydantic_v2_model(self, t: Any) -> bool:
        if not inspect.isclass(t):
            return False
        try:
            import pydantic
        except Exception:
            return False
        base = getattr(pydantic, "BaseModel", None)
        if base is None:
            return False
        if not hasattr(base, "model_validate"):
            return False
        return issubclass(t, base)

    def _is_class_init_parsable(self, t: Any) -> bool:
        if not inspect.isclass(t):
            return False
        if self._is_dataclass_type(t) or self._is_pydantic_v2_model(t):
            return False
        if issubclass(t, enum.Enum):
            return False
        if t in (list, dict, set, tuple, frozenset):
            return False
        return True

    def _get_init_params(self, t: type[Any]) -> list[Parameter]:
        cls_info = Class(t)
        params = cls_info.init_args
        return params or []

    def _get_type_hints_for_class(self, t: type[Any]) -> dict[str, Any]:
        try:
            return get_type_hints(t, include_extras=True)
        except (TypeError, NameError):
            try:
                return get_type_hints(t)
            except (TypeError, NameError):
                annotations = dict(getattr(t, "__annotations__", {}) or {})
                return self._resolve_string_annotations(annotations, t)

    def _resolve_string_annotations(
        self,
        annotations: Mapping[str, Any],
        t: type[Any],
    ) -> dict[str, Any]:
        module = sys.modules.get(t.__module__)
        module_ns = vars(module) if module is not None else {}
        resolved: dict[str, Any] = {}
        for name, annotation in annotations.items():
            if isinstance(annotation, str):
                if annotation in module_ns:
                    resolved[name] = module_ns[annotation]
                    continue
                builtin = getattr(builtins, annotation, None)
                if builtin is not None:
                    resolved[name] = builtin
                    continue
            resolved[name] = annotation
        return resolved

    def _resolve_annotation(self, annotation: Any, t: type[Any]) -> Any:
        if isinstance(annotation, typing.ForwardRef):
            annotation = annotation.__forward_arg__
        if isinstance(annotation, str):
            module = sys.modules.get(t.__module__)
            module_ns = vars(module) if module is not None else {}
            if annotation in module_ns:
                return module_ns[annotation]
            builtin = getattr(builtins, annotation, None)
            if builtin is not None:
                return builtin
        return annotation

    def _parse_dataclass(self, value: Any, t: type[T]) -> T:
        mapping = load_mapping_value(value, from_file=self.from_file)
        params = self._get_init_params(t)
        hints = self._get_type_hints_for_class(t)

        parsed_kwargs: dict[str, Any] = {}
        missing: list[str] = []

        for param in params:
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            param_type = hints.get(param.name, param.type)
            if param_type is OBJ_EMPTY:
                param_type = Any
            if param.name in mapping:
                parsed_kwargs[param.name] = self._parse_model_value(
                    mapping[param.name],
                    param_type,
                )
            elif param.default is OBJ_EMPTY:
                missing.append(param.name)

        if missing:
            raise ValueError(
                fmt_parser_err(
                    value,
                    t,
                    f"missing required fields: {', '.join(missing)}",
                )
            )
        return t(**parsed_kwargs)

    def _parse_pydantic_v2(self, value: Any, t: type[T]) -> T:
        mapping = load_mapping_value(value, from_file=self.from_file)

        field_types: dict[str, Any] = {}
        model_fields = getattr(t, "model_fields", None)
        if isinstance(model_fields, Mapping):
            for name, field in model_fields.items():
                annotation = getattr(field, "annotation", Any)
                field_types[name] = annotation

        if not field_types:
            params = self._get_init_params(t)
            hints = self._get_type_hints_for_class(t)
            for param in params:
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue
                field_types[param.name] = hints.get(param.name, param.type)

        parsed: dict[str, Any] = {}
        for name, raw in mapping.items():
            if name not in field_types:
                parsed[name] = raw
                continue
            field_type = field_types.get(name, Any)
            parsed[name] = self._parse_model_value(raw, field_type)

        return t.model_validate(parsed)

    def _parse_model_value(self, raw: Any, field_type: Any) -> Any:
        field_type = unwrap_annotated(field_type)
        if field_type in (Any, OBJ_EMPTY):
            return raw
        if field_type in (list, dict, set, tuple, frozenset):
            if isinstance(raw, field_type):
                return raw
        return self.parse(raw, field_type)

    def _parse_class_init(self, value: Any, t: type[T]) -> T:
        mapping = load_mapping_value(value, from_file=self.from_file)
        params = self._get_init_params(t)
        class_hints = self._get_type_hints_for_class(t)

        accepts_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params)
        parsed_kwargs: dict[str, Any] = {}
        missing: list[str] = []

        for param in params:
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                continue
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                continue
            param_type = param.type
            if param_type is OBJ_EMPTY:
                param_type = class_hints.get(param.name, Any)
            else:
                param_type = self._resolve_annotation(param_type, t)
            if param_type is OBJ_EMPTY:
                param_type = Any
            if param.name in mapping:
                parsed_kwargs[param.name] = self._parse_model_value(
                    mapping[param.name],
                    param_type,
                )
            elif param.default is OBJ_EMPTY:
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    missing.append(param.name)
                else:
                    missing.append(param.name)

        if missing:
            raise ValueError(
                fmt_parser_err(
                    value,
                    t,
                    f"missing required fields: {', '.join(missing)}",
                )
            )

        if accepts_kwargs:
            for key, raw in mapping.items():
                if key in parsed_kwargs:
                    continue
                parsed_kwargs[key] = raw

        return t(**parsed_kwargs)


class _ParseFunc(Generic[T]):
    def __init__(self, parser: StrToTypeParser, t: type[T]) -> None:
        self._parser = parser
        self._t = t

    def __call__(self, value: str) -> T:
        return self._parser.parse(value, self._t)

    def __repr__(self) -> str:
        return f"parser[{_format_type_for_repr(self._t)}]"


def get_parser(from_file: bool = True, *, allow_class_init: bool = False) -> StrToTypeParser:
    import datetime
    import decimal
    import fractions
    import pathlib
    from collections import Counter, OrderedDict, deque

    from strto.parsers import (
        ArrayParser,
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
        TimedeltaParser,
        TimeParser,
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

    parser = StrToTypeParser(from_file=from_file, allow_class_init=allow_class_init)
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
            datetime.time: TimeParser(),
            datetime.timedelta: TimedeltaParser(),
            array.array: ArrayParser(),
        }
    )
    return parser


__all__ = ["StrToTypeParser", "get_parser"]
