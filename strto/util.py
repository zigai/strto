import types
import typing

ALIAS_TYPES = [typing._SpecialGenericAlias, types.GenericAlias]  # type:ignore
UNION_TYPES = [typing._UnionGenericAlias, types.UnionType]  # type:ignore


def is_alias_type(t) -> bool:
    return type(t) in ALIAS_TYPES


def is_union_type(t) -> bool:
    return type(t) in UNION_TYPES


def type_to_str(t) -> str:
    """
    Convert a Python type to its string representation.

    Args:
        t (type): A Python type.

    Returns:
        str: The string representation of the Python type.

    Examples:
        >>> from objinspect import util
        >>> type_to_str(union_parameter.UnionParameter)
        'UnionParameter'
        >>> type_to_str(int)
        'int'
    """
    type_str = repr(t)
    if "<class '" in type_str:
        type_str = type_str.split("'")[1]
    return type_str.split(".")[-1]
