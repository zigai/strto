import datetime
import enum
import fractions
import pathlib
from fractions import Fraction

import pytest

from strto import StrToTypeParser, get_parser


@pytest.fixture
def parser() -> StrToTypeParser:
    return get_parser(from_file=True)


class TestInt:
    def test_simple(self, parser: StrToTypeParser):
        assert parser.parse("5", int) == 5


class TestFloat:
    def test_simple(self, parser: StrToTypeParser):
        assert parser.parse("1.5", float) == 1.5


class TestFraction:
    def test_simple(self, parser: StrToTypeParser):
        assert parser.parse("1/3", fractions.Fraction) == fractions.Fraction("1/3")


class TestPath:
    def test_simple(self, parser: StrToTypeParser):
        assert parser.parse("./data/here.txt", pathlib.Path) == pathlib.Path("./data/here.txt")


class TestList:
    def test_simple(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", list) == ["1", "2", "3", "4", "5"]
        assert parser.parse(" 1 ,2,3   ,4   ,5", list) == ["1", "2", "3", "4", "5"]

    def test_int(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", list[int]) == [1, 2, 3, 4, 5]

    def test_float(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", list[float]) == [1.0, 2.0, 3.0, 4.0, 5.0]

    def test_str(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", list[str]) == ["1", "2", "3", "4", "5"]

    def test_fraction(self, parser: StrToTypeParser):
        assert parser.parse("1/2,2/2,3/2,4/2,5/2", list[Fraction]) == [
            Fraction(1, 2),
            Fraction(2, 2),
            Fraction(3, 2),
            Fraction(4, 2),
            Fraction(5, 2),
        ]


class TestTuple:
    def test_int(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", tuple[int]) == (1, 2, 3, 4, 5)

    def test_float(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", tuple[float]) == (1.0, 2.0, 3.0, 4.0, 5.0)

    def test_str(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", tuple[str]) == ("1", "2", "3", "4", "5")


class TestSet:
    def test_int(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", set[int]) == {1, 2, 3, 4, 5}

    def test_float(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", set[float]) == {1.0, 2.0, 3.0, 4.0, 5.0}

    def test_str(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", set[str]) == {"1", "2", "3", "4", "5"}


class TestFrozenset:
    def test_int(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", frozenset[int]) == frozenset({1, 2, 3, 4, 5})

    def test_float(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", frozenset[float]) == frozenset({1.0, 2.0, 3.0, 4.0, 5.0})

    def test_str(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3,4,5", frozenset[str]) == frozenset({"1", "2", "3", "4", "5"})


class TestDict:
    def test_simple(self, parser: StrToTypeParser):
        assert parser.parse('{"a":1,"b":2,"c":3}', dict) == {"a": 1, "b": 2, "c": 3}

    def test_str_int(self, parser: StrToTypeParser):
        assert parser.parse('{"a":1,"b":2,"c":3}', dict[str, int]) == {"a": 1, "b": 2, "c": 3}

    def test_str_float(self, parser: StrToTypeParser):
        assert parser.parse('{"a":1,"b":2,"c":3}', dict[str, float]) == {
            "a": 1.0,
            "b": 2.0,
            "c": 3.0,
        }

    def test_str_str(self, parser: StrToTypeParser):
        assert parser.parse('{"a":1,"b":2,"c":3}', dict[str, str]) == {"a": "1", "b": "2", "c": "3"}

    def test_str_union_float_int(self, parser: StrToTypeParser):
        assert parser.parse('{"a":1,"b":2.5,"c":3.1}', dict[str, float | int]) == {
            "a": 1,
            "b": 2.5,
            "c": 3.1,
        }

    def test_str_union_int_float(self, parser: StrToTypeParser):
        assert parser.parse('{"a":1,"b":2.5,"c":3.1}', dict[str, int | float]) == {
            "a": 1,
            "b": 2.5,
            "c": 3.1,
        }


class TestSlice:
    def test_slice(self, parser: StrToTypeParser):
        assert parser.parse("0:5", slice) == slice(0, 5)
        assert parser.parse(":5", slice) == slice(None, 5)
        assert parser.parse("0:", slice) == slice(0, None)
        assert parser.parse("0:5:2", slice) == slice(0, 5, 2)
        assert parser.parse("::5", slice) == slice(None, None, 5)
        with pytest.raises(ValueError):
            parser.parse("0:5:2:4", slice)


class TestRange:
    def test_range(self, parser: StrToTypeParser):
        assert parser.parse("5", range) == range(5)
        assert parser.parse("5:6", range) == range(5, 6)
        assert parser.parse("0:5", range) == range(0, 5)
        assert parser.parse(":5", range) == range(0, 5)
        assert parser.parse("5:", range) == range(5)
        assert parser.parse("0:5:2", range) == range(0, 5, 2)
        with pytest.raises(ValueError):
            parser.parse("0:5:2:4", range)


class TestDatetime:
    def test_datetime(self, parser: StrToTypeParser):
        date = datetime.datetime(year=2022, day=19, month=7)
        assert parser.parse("2022.07.19", datetime.datetime) == date
        assert parser.parse("2022/07/19", datetime.datetime) == date
        assert parser.parse("19-7-2022", datetime.datetime) == date
        assert parser.parse("July 19th 2022", datetime.datetime) == date


class TestDate:
    def test_date(self, parser: StrToTypeParser):
        date = datetime.date(year=2022, day=19, month=7)
        assert parser.parse("2022.07.19", datetime.date) == date
        assert parser.parse("2022/07/19", datetime.date) == date
        assert parser.parse("19-7-2022", datetime.date) == date
        assert parser.parse("July 19th 2022", datetime.date) == date


class TestEnum:
    def test_enum(self, parser: StrToTypeParser):
        class MyEnum(enum.Enum):
            A = 1
            B = 2
            C = 3

        assert parser.parse("A", MyEnum) == MyEnum.A
        with pytest.raises(KeyError):
            parser.parse("D", MyEnum)


class TestLiteral:
    def test_literal(self, parser: StrToTypeParser):
        from typing import Literal

        MyLiteral = Literal[1, 2, 3]
        assert parser.parse("1", MyLiteral) == 1
        assert parser.parse("False", Literal[True, False]) == False
        assert parser.parse(b"bytes", Literal[b"bytes", b"string"]) == b"bytes"

        with pytest.raises(ValueError):
            parser.parse("4", MyLiteral)
