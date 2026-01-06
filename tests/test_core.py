import enum
import typing

import pytest

from strto import StrToTypeParser
from strto import core


class Choice(enum.Enum):
    RED = 1
    BLUE = 2


def test_len_and_getitem(parser: StrToTypeParser) -> None:
    assert len(parser) > 0
    int_parser = parser[int]
    assert callable(int_parser)
    assert callable(parser.get(int))
    parse_int = parser.get_parse_func(int)
    assert parse_int("7") == 7
    assert repr(parse_int) == "parser[int]"
    parser.extend({complex: complex})
    assert parser.parse("1+2j", complex) == complex(1, 2)


def test_parse_none_returns_none(parser: StrToTypeParser) -> None:
    assert parser.parse(None, type(None)) is None


def test_is_supported_variants(parser: StrToTypeParser) -> None:
    assert parser.is_supported(list[int])
    assert parser.is_supported(tuple[int])
    assert parser.is_supported(tuple[int, ...])
    assert parser.is_supported(tuple[int, str])
    assert parser.is_supported(int | str)
    assert not parser.is_supported(tuple[()])
    assert not parser.is_supported(set[()])
    assert not parser.is_supported(typing.Type[int])


def test_is_supported_handles_error(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()

    def boom(t: typing.Any) -> bool:
        if t is sentinel:
            raise TypeError
        return False

    parser = core.StrToTypeParser()
    monkeypatch.setattr(core, "is_generic_alias", boom)
    assert parser.is_supported(sentinel) is False


def test_parse_alias_mapping_error() -> None:
    parser = core.StrToTypeParser({int: int, str: str, dict: dict})
    with pytest.raises(ValueError):
        parser.parse("{", dict[str, int])


def test_parse_alias_tuple_length_mismatch(parser: StrToTypeParser) -> None:
    with pytest.raises(ValueError):
        parser.parse("1,2", tuple[int, int, int])


def test_parse_alias_unsupported_origin() -> None:
    parser = core.StrToTypeParser({int: int})
    with pytest.raises(TypeError):
        parser.parse("value", typing.Type[int])


def test_parse_union_error(parser: StrToTypeParser) -> None:
    with pytest.raises(ValueError) as exc:
        parser.parse("not-a-number", int | float)
    assert "tried types" in str(exc.value)


def test_parse_enum_success_and_error() -> None:
    parser = core.StrToTypeParser()
    parser.add(str, lambda v: v)
    assert parser.parse("RED", Choice) is Choice.RED
    with pytest.raises(KeyError):
        parser.parse("MISSING", Choice)


def test_parse_literal_success_and_error() -> None:
    parser = core.StrToTypeParser()
    parser.add(int, int)
    assert parser.parse("1", typing.Literal[1, 2]) == 1
    with pytest.raises(ValueError):
        parser.parse("nope", typing.Literal[1, 2])


def test_parse_special_type_error(parser: StrToTypeParser) -> None:
    with pytest.raises(TypeError):
        parser.parse("some-bytes", bytes)


def test_parse_array_with_int_annotation(parser: StrToTypeParser) -> None:
    import array
    import sys

    if sys.version_info < (3, 12):
        pytest.skip("array.array[T] not subscriptable before Python 3.12")

    result = parser.parse("1,2,3", array.array[int])
    assert result.typecode == "l"
    assert list(result) == [1, 2, 3]


def test_parse_array_with_float_annotation(parser: StrToTypeParser) -> None:
    import array
    import sys

    if sys.version_info < (3, 12):
        pytest.skip("array.array[T] not subscriptable before Python 3.12")

    result = parser.parse("1.5,2.5,3.5", array.array[float])
    assert result.typecode == "d"
    assert list(result) == [1.5, 2.5, 3.5]


def test_parse_array_with_ctypes_annotation(parser: StrToTypeParser) -> None:
    import array
    import ctypes
    import sys

    if sys.version_info < (3, 12):
        pytest.skip("array.array[T] not subscriptable before Python 3.12")

    result = parser.parse("1,2,3", array.array[ctypes.c_short])
    assert result.typecode == "h"
    assert list(result) == [1, 2, 3]


def test_parse_bare_array_infers_from_values(parser: StrToTypeParser) -> None:
    import array

    result = parser.parse("1,2,3", array.array)
    assert result.typecode == "l"
    assert list(result) == [1, 2, 3]
