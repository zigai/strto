import functools
import operator
import sys
import types
import typing
from typing import Any

if sys.version_info >= (3, 12):
    from typing import TypeAliasType
else:
    TypeAliasType = None  # type: ignore[misc,assignment]


def _type_display(t: Any) -> str:
    try:
        return t.__name__
    except Exception:
        return str(t)


def fmt_parser_err(value: Any, target: Any, hint: str | None = None) -> str:
    msg = f"could not parse {value!r} as {_type_display(target)}."
    if hint:
        msg += f" {hint}"
    return msg


def is_type_alias(t: Any) -> bool:
    if TypeAliasType is None:
        return False
    return isinstance(t, TypeAliasType)


def _unwrap_type_alias(t: Any) -> Any:
    while is_type_alias(t):
        t = t.__value__  # type: ignore[union-attr]
    return t


def _resolve_generic_type_args(t: Any) -> Any:
    origin = typing.get_origin(t)
    if origin is None or origin is typing.Annotated:
        return t

    args = typing.get_args(t)
    if not args:
        return t

    resolved_args: list[Any] = []
    changed = False
    for arg in args:
        if arg is Ellipsis:
            resolved_args.append(arg)
            continue
        resolved = unwrap_type(arg)
        if resolved is not arg:
            changed = True
        resolved_args.append(resolved)

    if not changed:
        return t

    if origin is types.UnionType:
        return functools.reduce(operator.or_, resolved_args)

    return origin[tuple(resolved_args)]


def unwrap_type(t: Any) -> Any:
    t = _unwrap_type_alias(t)

    while typing.get_origin(t) is typing.Annotated:
        args = typing.get_args(t)
        if not args:
            break
        t = args[0]

    t = _unwrap_type_alias(t)
    t = _resolve_generic_type_args(t)
    return t


unwrap_annotated = unwrap_type
