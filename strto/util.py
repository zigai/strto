import types
import typing
from collections.abc import Iterable, Mapping
from typing import Any

ALIAS_TYPES = [typing._SpecialGenericAlias, types.GenericAlias]  # type:ignore
UNION_TYPES = [typing._UnionGenericAlias, types.UnionType]  # type:ignore


def is_alias_type(t) -> bool:
    """
    Check if a type is an alias type (list[str], dict[str, int], etc...])
    """
    return type(t) in ALIAS_TYPES


def is_union_type(t) -> bool:
    """
    Check if a type is a union type (float | int, str | None, etc...)
    """
    return type(t) in UNION_TYPES


def is_iterable_type(t) -> bool:
    """
    Check if a type is an iterable type (list, tuple, etc...)
    """
    if is_alias_type(t):
        t = type_origin(t)
    return issubclass(t, Iterable)


def is_mapping_type(t) -> bool:
    """
    Check if a type is a mapping type (dict, defaultdict, etc...)
    """
    if is_alias_type(t):
        t = type_origin(t)
    return issubclass(t, Mapping)


def type_to_str(t) -> str:
    """
    Convert a Python type to its string representation.

    Args:
        t (type): A Python type.

    Returns:
        str: The string representation of the Python type.

    Examples:
        >>> type_to_str(union_parameter.UnionParameter)
        'UnionParameter'
        >>> type_to_str(int)
        'int'
    """
    type_str = repr(t)
    if "<class '" in type_str:
        type_str = type_str.split("'")[1]
    return type_str.split(".")[-1]


def type_origin(t: Any) -> Any:
    """
    typing.get_origin wrapper

    Example:
        >>> type_args(list[list[str]])
        <class 'list'>
        >>> type_origin(float | int)
        <class 'types.UnionType'>
    """
    return typing.get_origin(t)


def type_args(t: Any) -> tuple[Any, ...]:
    """
    typing.get_args wrapper

    Example:
        >>> type_args(list[str])
        (<class 'str'>,)
        >>> type_args(dict[str, int])
        (<class 'str'>, <class 'int'>)
        >>> type_args(list[list[str]])
        (list[str],)
    """
    return typing.get_args(t)


def type_simplify(t: Any) -> Any:
    """
    Examples:
    >>> type_simplify(list[str])
    <class 'list'>
    >>> type_simplify(float | list[str])
    (<class 'float'>, <class 'list'>)
    """
    origin = type_origin(t)
    if type(origin) is types.NoneType or origin is None:
        return t

    if is_union_type(t):
        args = type_args(t)
        return tuple([type_simplify(i) for i in args])

    return origin


__all__ = [
    "is_alias_type",
    "is_union_type",
    "is_iterable_type",
    "is_mapping_type",
    "type_to_str",
    "type_origin",
    "type_args",
    "type_simplify",
]
