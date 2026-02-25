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
from typing import Any, Generic, TypeVar, cast, get_type_hints, overload

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
_PARSE_MISSING = object()
_BUILTIN_COLLECTION_TYPES = (list, dict, set, tuple, frozenset)


def _format_type_for_repr(t: object) -> str:
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

    def __len__(self) -> int:
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

    def is_supported(self, t: object) -> bool:
        """Check if a type is supported for parsing."""
        t = unwrap_annotated(t)
        try:
            if self._is_directly_supported(t):
                return True
            if is_generic_alias(t):
                return self._is_generic_supported(t)
            if is_union_type(t):
                return self._is_union_supported(t)
        except (TypeError, ValueError):
            return False
        return False

    def _is_directly_supported(self, t: object) -> bool:
        if self.parsers.get(t, None):
            return True
        if self._is_dataclass_type(t) or self._is_pydantic_v2_model(t):
            return True
        if self.allow_class_init and self._is_class_init_parsable(t):
            return True
        if is_direct_literal(t):
            return True
        return inspect.isclass(t) and issubclass(t, enum.Enum)

    def _is_generic_supported(self, t: object) -> bool:
        base_t = type_origin(t)
        sub_t = type_args(t)

        if is_mapping_type(base_t):
            key_type, value_type = sub_t
            return self.is_supported(key_type) and self.is_supported(value_type)
        if is_iterable_type(base_t):
            return self._is_iterable_alias_supported(base_t, sub_t)

        return False

    def _is_iterable_alias_supported(self, base_t: object, sub_t: tuple[object, ...]) -> bool:
        if base_t is tuple:  # tuple[T] or tuple[T, ...] or fixed-length tuple[T1, T2, ...]
            return self._is_tuple_alias_supported(sub_t)
        if not sub_t:
            return False
        return self.is_supported(sub_t[0])

    def _is_tuple_alias_supported(self, sub_t: tuple[object, ...]) -> bool:
        if not sub_t:
            return False
        if len(sub_t) == 1:
            return self.is_supported(sub_t[0])
        if len(sub_t) == 2 and sub_t[1] is Ellipsis:
            return self.is_supported(sub_t[0])
        return all(self.is_supported(item_t) for item_t in sub_t)

    def _is_union_supported(self, t: object) -> bool:
        return any(self.is_supported(arg) for arg in type_args(t))

    @overload
    def parse(self, value: object, t: type[T]) -> T: ...

    @overload
    def parse(self, value: object, t: object) -> object: ...

    def parse(self, value: object, t: object) -> object:
        t = unwrap_annotated(t)
        if self._is_passthrough_collection_instance(value, t):
            return value

        parsed = self._parse_known_type(value, t)
        if parsed is not _PARSE_MISSING:
            return parsed
        if value is None:
            return None
        return self._parse_special(value, t)

    def _is_passthrough_collection_instance(self, value: object, t: object) -> bool:
        return t in _BUILTIN_COLLECTION_TYPES and isinstance(value, t)

    def _parse_known_type(self, value: object, t: object) -> object:
        if parser := self.parsers.get(t, None):
            return parser(value)
        if self._is_dataclass_type(t):
            return self._parse_dataclass(value, t)
        if self._is_pydantic_v2_model(t):
            return self._parse_pydantic_v2(value, t)
        if self.allow_class_init and self._is_class_init_parsable(t):
            return self._parse_class_init(value, t)
        return self._parse_alias_or_union(value, t)

    def _parse_alias_or_union(self, value: object, t: object) -> object:
        if is_generic_alias(t):
            return self._parse_alias(value, t)
        if is_union_type(t):
            return self._parse_union(value, t)
        return _PARSE_MISSING

    def _parse_alias(self, value: object, t: type[T]) -> T:
        base_t = type_origin(t)
        sub_t = type_args(t)

        if is_mapping_type(base_t):
            key_type, value_type = sub_t
            return cast(
                T,
                self._parse_mapping_alias(value, t, base_t, key_type, value_type),
            )

        if base_t is array.array:
            from strto.parsers import ArrayParser

            item_t = sub_t[0] if sub_t else None
            type_code = ArrayParser.get_type_code(item_t)
            parser = ArrayParser(type_code=type_code)
            return cast(T, parser(value))

        if is_iterable_type(base_t):
            return cast(T, self._parse_iterable_alias(value, t, base_t, sub_t))

        raise TypeError(fmt_parser_err(value, t, "unsupported generic alias"))

    def _parse_mapping_alias(
        self,
        value: object,
        t: type[T],
        base_t: object,
        key_type: object,
        value_type: object,
    ) -> object:
        mapping_instance = base_t()
        items = cast(Mapping[object, object], self._load_mapping_alias_items(value, t))
        for key, item_value in items.items():
            mapping_instance[self.parse(key, key_type)] = self.parse(item_value, value_type)
        return mapping_instance

    def _load_mapping_alias_items(self, value: object, t: type[T]) -> object:
        if isinstance(value, Mapping):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except ValueError as e:
                raise ValueError(
                    fmt_parser_err(value, t, "expected JSON string for mapping")
                ) from e
        raise TypeError(fmt_parser_err(value, t, "expected mapping or JSON string"))

    def _parse_iterable_alias(
        self,
        value: object,
        t: type[T],
        base_t: object,
        sub_t: tuple[object, ...],
    ) -> object:
        parts = self._load_iterable_alias_parts(value, t)

        if base_t is tuple:
            return self._parse_tuple_alias(parts, value, t, sub_t)

        item_t = sub_t[0]  # iterables with single parameter, e.g., list[T], set[T]
        return base_t([self.parse(item, item_t) for item in parts])

    def _load_iterable_alias_parts(self, value: object, t: type[T]) -> list[object]:
        if isinstance(value, Mapping):
            raise TypeError(fmt_parser_err(value, t, "expected iterable or string"))
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                try:
                    loaded = json.loads(text)
                except ValueError as e:
                    raise ValueError(
                        fmt_parser_err(value, t, "expected JSON array or iterable string")
                    ) from e
                return loaded if isinstance(loaded, list) else list(loaded)
            if self.from_file and text.startswith("@"):
                loaded = load_data_from_file(text[1:])
                return loaded if isinstance(loaded, list) else list(loaded)
            return [item.strip() for item in value.split(ITER_SEP)] if value != "" else []
        if isinstance(value, Iterable):
            return list(value)
        raise TypeError(fmt_parser_err(value, t, "expected iterable or string"))

    def _parse_tuple_alias(
        self,
        parts: list[object],
        value: object,
        t: type[T],
        sub_t: tuple[object, ...],
    ) -> tuple[object, ...]:
        if len(sub_t) == 1:  # tuple[T]
            item_t = sub_t[0]
            return tuple(self.parse(item, item_t) for item in parts)

        if len(sub_t) == 2 and sub_t[1] is Ellipsis:  # tuple[T, ...]
            item_t = sub_t[0]
            return tuple(self.parse(item, item_t) for item in parts)

        expected_len = len(sub_t)  # fixed-length tuple
        if len(parts) != expected_len:
            raise ValueError(fmt_parser_err(value, t, f"expected {expected_len} items"))
        return tuple(self.parse(item, item_t) for item, item_t in zip(parts, sub_t, strict=False))

    def _parse_union(self, value: object, t: type[T]) -> T:
        for member_t in type_args(t):
            parsed = self._try_parse_union_value(value, member_t)
            if parsed is not _PARSE_MISSING:
                return cast(T, parsed)
        tried = ", ".join(getattr(item_t, "__name__", str(item_t)) for item_t in type_args(t))
        raise ValueError(fmt_parser_err(value, t, f"tried types: {tried}"))

    def _try_parse_union_value(self, value: object, t: object) -> object:
        try:
            return self.parse(value, t)
        except (ValueError, TypeError, KeyError):
            return _PARSE_MISSING

    def _parse_special(self, value: object, t: object) -> object:
        """Parse enum or literal."""
        if inspect.isclass(t) and issubclass(t, enum.Enum):
            return self._parse_enum(value, t)

        if is_direct_literal(t):
            parser = LiteralParser(
                get_literal_choices(t),
                target_t=t,
            )
            return parser(value)

        raise TypeError(
            fmt_parser_err(
                value,
                t,
                "unsupported type; add a custom parser via parser.add(T, ...).",
            )
        )

    def _parse_enum(self, value: object, t: type[enum.Enum]) -> enum.Enum:
        if isinstance(value, t):
            return value
        if issubclass(t, str):
            return self._parse_string_enum(value, t)
        return self._parse_non_string_enum(value, t)

    def _parse_string_enum(self, value: object, t: type[enum.Enum]) -> enum.Enum:
        try:
            return t(value)
        except (TypeError, ValueError):
            try:
                return t[value]
            except KeyError as e:
                self._raise_enum_parse_err(value, t, e)
                raise

    def _parse_non_string_enum(self, value: object, t: type[enum.Enum]) -> enum.Enum:
        try:
            return t[value]
        except KeyError:
            try:
                return t(value)
            except (TypeError, ValueError) as e:
                self._raise_enum_parse_err(value, t, e)
                raise

    def _raise_enum_parse_err(self, value: object, t: type[enum.Enum], exc: Exception) -> None:
        name_choices = list(t.__members__.keys())
        if issubclass(t, str):
            value_choices = [member.value for member in t]
            detail = f"valid values: {value_choices}; valid names: {name_choices}"
        else:
            detail = f"valid choices: {name_choices}"
        raise KeyError(fmt_parser_err(value, t, detail)) from exc

    def _is_dataclass_type(self, t: object) -> bool:
        return inspect.isclass(t) and dataclasses.is_dataclass(t)

    def _is_pydantic_v2_model(self, t: object) -> bool:
        if not inspect.isclass(t):
            return False
        try:
            import pydantic
        except ImportError:
            return False
        base = getattr(pydantic, "BaseModel", None)
        if base is None:
            return False
        if not hasattr(base, "model_validate"):
            return False
        return issubclass(t, base)

    def _is_class_init_parsable(self, t: object) -> bool:
        if not inspect.isclass(t):
            return False
        if self._is_dataclass_type(t) or self._is_pydantic_v2_model(t):
            return False
        if issubclass(t, enum.Enum):
            return False
        return t not in _BUILTIN_COLLECTION_TYPES

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

    def _resolve_annotation(self, annotation: object, t: type[Any]) -> object:
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

    def _parse_dataclass(self, value: object, t: type[T]) -> T:
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

    def _parse_pydantic_v2(self, value: object, t: type[T]) -> T:
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

    def _parse_model_value(self, raw: object, field_type: object) -> object:
        field_type = unwrap_annotated(field_type)
        if field_type in (Any, OBJ_EMPTY):
            return raw
        if field_type in _BUILTIN_COLLECTION_TYPES and isinstance(raw, field_type):
            return raw
        return self.parse(raw, field_type)

    def _parse_class_init(self, value: object, t: type[T]) -> T:
        mapping = load_mapping_value(value, from_file=self.from_file)
        params = self._get_init_params(t)
        class_hints = self._get_type_hints_for_class(t)

        accepts_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params)
        parsed_kwargs: dict[str, Any] = {}
        missing: list[str] = []

        for param in params:
            if self._should_skip_init_param(param):
                continue
            param_type = self._resolve_class_init_param_type(param, class_hints, t)
            if param.name in mapping:
                parsed_kwargs[param.name] = self._parse_model_value(
                    mapping[param.name],
                    param_type,
                )
                continue
            if param.default is OBJ_EMPTY:
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

    def _should_skip_init_param(self, param: Parameter) -> bool:
        return param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)

    def _resolve_class_init_param_type(
        self,
        param: Parameter,
        class_hints: Mapping[str, object],
        t: type[T],
    ) -> object:
        param_type = param.type
        if param_type is OBJ_EMPTY:
            param_type = class_hints.get(param.name, Any)
        else:
            param_type = self._resolve_annotation(param_type, t)
        return Any if param_type is OBJ_EMPTY else param_type


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
