import datetime
import enum
import fractions
import pathlib

import pytest

from strto.parser import Parser, get_parser


@pytest.fixture
def parser() -> Parser:
    return get_parser()


def test_simple_types(parser: Parser):
    assert parser.parse("1.5", float) == 1.5
    assert parser.parse("5", int) == 5
    assert parser.parse("1/3", fractions.Fraction) == fractions.Fraction("1/3")
    assert parser.parse("./data/here.txt", pathlib.Path) == pathlib.Path("./data/here.txt")
    assert parser.parse('{"a":1,"b":2,"c":3}', dict) == {"a": 1, "b": 2, "c": 3}
    assert parser.parse("1,2,3,4,5", list) == ["1", "2", "3", "4", "5"]
    assert parser.parse(" 1 ,2,3   ,4   ,5", list) == ["1", "2", "3", "4", "5"]


def test_iter_alias_simple(parser: Parser):
    assert parser.parse("1,2,3,4,5", list[int]) == [1, 2, 3, 4, 5]
    assert parser.parse("1,2,3,4,5", list[float]) == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert parser.parse("1,2,3,4,5", list[str]) == ["1", "2", "3", "4", "5"]

    assert parser.parse("1,2,3,4,5", tuple[int]) == (1, 2, 3, 4, 5)
    assert parser.parse("1,2,3,4,5", tuple[float]) == (1.0, 2.0, 3.0, 4.0, 5.0)
    assert parser.parse("1,2,3,4,5", tuple[str]) == ("1", "2", "3", "4", "5")

    assert parser.parse("1,2,3,4,5", set[int]) == {1, 2, 3, 4, 5}
    assert parser.parse("1,2,3,4,5", set[float]) == {1.0, 2.0, 3.0, 4.0, 5.0}
    assert parser.parse("1,2,3,4,5", set[str]) == {"1", "2", "3", "4", "5"}

    assert parser.parse("1,2,3,4,5", frozenset[int]) == frozenset({1, 2, 3, 4, 5})
    assert parser.parse("1,2,3,4,5", frozenset[float]) == frozenset({1.0, 2.0, 3.0, 4.0, 5.0})
    assert parser.parse("1,2,3,4,5", frozenset[str]) == frozenset({"1", "2", "3", "4", "5"})


def test_mapping_alias(parser: Parser):
    assert parser.parse('{"a":1,"b":2,"c":3}', dict[str, int]) == {"a": 1, "b": 2, "c": 3}
    assert parser.parse('{"a":1,"b":2,"c":3}', dict[str, float]) == {"a": 1.0, "b": 2.0, "c": 3.0}
    assert parser.parse('{"a":1,"b":2,"c":3}', dict[str, str]) == {"a": "1", "b": "2", "c": "3"}


def test_slice(parser: Parser):
    assert parser.parse("0:5", slice) == slice(0, 5)
    assert parser.parse(":5", slice) == slice(None, 5)
    assert parser.parse("0:", slice) == slice(0, None)
    assert parser.parse("0:5:2", slice) == slice(0, 5, 2)
    assert parser.parse("::5", slice) == slice(None, None, 5)
    with pytest.raises(ValueError):
        parser.parse("0:5:2:4", slice)


def test_range(parser: Parser):
    assert parser.parse("5", range) == range(5)
    assert parser.parse("5:6", range) == range(5, 6)
    assert parser.parse("0:5", range) == range(0, 5)
    assert parser.parse(":5", range) == range(0, 5)
    assert parser.parse("5:", range) == range(5)
    assert parser.parse("0:5:2", range) == range(0, 5, 2)
    with pytest.raises(ValueError):
        parser.parse("0:5:2:4", range)


def test_datetime(parser: Parser):
    date = datetime.datetime(year=2022, day=19, month=7)
    assert parser.parse("2022.07.19", datetime.datetime) == date
    assert parser.parse("2022/07/19", datetime.datetime) == date
    assert parser.parse("19-7-2022", datetime.datetime) == date
    assert parser.parse("July 19th 2022", datetime.datetime) == date


def test_date(parser: Parser):
    date = datetime.date(year=2022, day=19, month=7)
    assert parser.parse("2022.07.19", datetime.date) == date
    assert parser.parse("2022/07/19", datetime.date) == date
    assert parser.parse("19-7-2022", datetime.date) == date
    assert parser.parse("July 19th 2022", datetime.date) == date


def test_enum(parser: Parser):
    class MyEnum(enum.Enum):
        A = 1
        B = 2
        C = 3

    assert parser.parse("A", MyEnum) == MyEnum.A
    with pytest.raises(KeyError):
        parser.parse("d", MyEnum)
