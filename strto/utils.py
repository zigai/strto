import typing
from typing import Any


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


def unwrap_annotated(t: Any) -> Any:
    while typing.get_origin(t) is typing.Annotated:
        args = typing.get_args(t)
        if not args:
            break
        t = args[0]
    return t
