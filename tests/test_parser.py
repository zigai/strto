import datetime
import enum
import fractions
import math
import pathlib
from fractions import Fraction

import pytest

from strto import StrToTypeParser, get_parser


class TestInt:
    def test_simple(self, parser: StrToTypeParser):
        assert parser.parse("5", int) == 5

    def test_exponent_power(self, parser: StrToTypeParser):
        assert parser.parse("2**4", int) == 16
        assert parser.parse("3**2", int) == 9

    def test_scientific_notation(self, parser: StrToTypeParser):
        assert parser.parse("2e4", int) == 20000
        assert parser.parse("1e3", int) == 1000

    def test_caret_power(self, parser: StrToTypeParser):
        assert parser.parse("2^4", int) == 16
        assert parser.parse("3^2", int) == 9

    def test_multiplication(self, parser: StrToTypeParser):
        assert parser.parse("2*4", int) == 8
        assert parser.parse("3*5", int) == 15

    def test_complex_expression(self, parser: StrToTypeParser):
        assert parser.parse("2*3**2", int) == 18
        assert parser.parse("2^3*4", int) == 32

    def test_negative_numbers(self, parser: StrToTypeParser):
        assert parser.parse("-5", int) == -5
        assert parser.parse("-2**3", int) == -8

    def test_subtraction(self, parser: StrToTypeParser):
        assert parser.parse("10-3", int) == 7
        assert parser.parse("20-5-2", int) == 13

    def test_division(self, parser: StrToTypeParser):
        assert parser.parse("10/2", int) == 5
        assert parser.parse("20/4", int) == 5

    def test_floor_division(self, parser: StrToTypeParser):
        assert parser.parse("10//3", int) == 3
        assert parser.parse("17//4", int) == 4

    def test_modulo(self, parser: StrToTypeParser):
        assert parser.parse("10%3", int) == 1
        assert parser.parse("17%4", int) == 1

    def test_addition(self, parser: StrToTypeParser):
        assert parser.parse("5+3", int) == 8
        assert parser.parse("10+5+2", int) == 17

    def test_division_by_zero(self, parser: StrToTypeParser):
        with pytest.raises(ZeroDivisionError):
            parser.parse("10/0", int)
        with pytest.raises(ZeroDivisionError):
            parser.parse("5//0", int)
        with pytest.raises(ZeroDivisionError):
            parser.parse("10%0", int)


class TestFloat:
    def test_simple(self, parser: StrToTypeParser):
        assert parser.parse("1.5", float) == 1.5

    def test_exponent_power(self, parser: StrToTypeParser):
        assert parser.parse("2**4", float) == 16.0
        assert parser.parse("3**2", float) == 9.0

    def test_scientific_notation(self, parser: StrToTypeParser):
        assert parser.parse("2e4", float) == 20000.0
        assert parser.parse("1.5e3", float) == 1500.0

    def test_caret_power(self, parser: StrToTypeParser):
        assert parser.parse("2^4", float) == 16.0
        assert parser.parse("3^2", float) == 9.0

    def test_multiplication(self, parser: StrToTypeParser):
        assert parser.parse("2*4", float) == 8.0
        assert parser.parse("3.5*2", float) == 7.0

    def test_complex_expression(self, parser: StrToTypeParser):
        assert parser.parse("2*3**2", float) == 18.0
        assert parser.parse("2^3*4", float) == 32.0

    def test_negative_numbers(self, parser: StrToTypeParser):
        assert parser.parse("-5.5", float) == -5.5
        assert parser.parse("-2**3", float) == -8.0

    def test_subtraction(self, parser: StrToTypeParser):
        assert parser.parse("10.5-3.2", float) == 7.3
        assert parser.parse("20-5-2", float) == 13.0

    def test_division(self, parser: StrToTypeParser):
        assert parser.parse("10/2", float) == 5.0
        assert parser.parse("20/4", float) == 5.0
        assert parser.parse("10.0/3.0", float) == 3.3333333333333335

    def test_floor_division(self, parser: StrToTypeParser):
        assert parser.parse("10//3", float) == 3.0
        assert parser.parse("17//4", float) == 4.0

    def test_modulo(self, parser: StrToTypeParser):
        assert parser.parse("10%3", float) == 1.0
        assert parser.parse("17.5%4", float) == 1.5

    def test_addition(self, parser: StrToTypeParser):
        assert parser.parse("5.5+3.2", float) == 8.7
        assert parser.parse("10+5+2", float) == 17.0

    def test_division_by_zero(self, parser: StrToTypeParser):
        with pytest.raises(ZeroDivisionError):
            parser.parse("10/0", float)
        with pytest.raises(ZeroDivisionError):
            parser.parse("5//0", float)
        with pytest.raises(ZeroDivisionError):
            parser.parse("10%0", float)

    def test_constants(self, parser: StrToTypeParser):
        assert parser.parse("pi", float) == math.pi
        assert parser.parse("e", float) == math.e
        assert parser.parse("tau", float) == math.tau
        assert parser.parse("phi", float) == (1 + math.sqrt(5)) / 2
        assert parser.parse("sqrt2", float) == math.sqrt(2)
        assert parser.parse("sqrt3", float) == math.sqrt(3)

    def test_constants_in_expressions(self, parser: StrToTypeParser):
        assert parser.parse("pi*2", float) == 2 * math.pi
        assert parser.parse("e+1", float) == math.e + 1
        assert parser.parse("2*pi", float) == 2 * math.pi


class TestFraction:
    def test_simple(self, parser: StrToTypeParser):
        assert parser.parse("1/3", fractions.Fraction) == fractions.Fraction("1/3")


class TestPath:
    def test_simple(self, parser: StrToTypeParser):
        assert parser.parse("./data/here.txt", pathlib.Path) == pathlib.Path("./data/here.txt")


class TestStr:
    def test_preserves_whitespace(self, parser: StrToTypeParser):
        assert parser.parse("  spaced  ", str) == "  spaced  "

    def test_list_trims_items(self, parser: StrToTypeParser):
        assert parser.parse(" a , b  ,c ", list[str]) == ["a", "b", "c"]


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

    def test_variadic_with_ellipsis_int(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3", tuple[int, ...]) == (1, 2, 3)

    def test_variadic_with_ellipsis_float(self, parser: StrToTypeParser):
        assert parser.parse("1,2,3.5", tuple[float, ...]) == (1.0, 2.0, 3.5)

    def test_fixed_length_two(self, parser: StrToTypeParser):
        assert parser.parse("1,hello", tuple[int, str]) == (1, "hello")

    def test_fixed_length_three(self, parser: StrToTypeParser):
        assert parser.parse("1,2.5,True", tuple[int, float, bool]) == (1, 2.5, True)

    def test_fixed_length_mismatch_raises(self, parser: StrToTypeParser):
        with pytest.raises(ValueError):
            parser.parse("1,2", tuple[int, str, int])


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


class TestBool:
    def test_bool_synonyms_default(self, parser: StrToTypeParser):
        for v in ["1", "true", "True", "TRUE", "yes", "YeS", "y", "Y", "on", "On"]:
            assert parser.parse(v, bool) is True

        for v in ["0", "false", "False", "FALSE", "no", "No", "n", "N", "off", "OFF"]:
            assert parser.parse(v, bool) is False

    def test_bool_case_sensitive_override(self):
        parser = get_parser()
        from strto.parsers import BoolParser

        parser.add(bool, BoolParser(case_sensitive=True))

        for v in ["true", "yes", "y", "on", "1"]:
            assert parser.parse(v, bool) is True
        for v in ["false", "no", "n", "off", "0"]:
            assert parser.parse(v, bool) is False

        with pytest.raises(ValueError):
            parser.parse("True", bool)
        with pytest.raises(ValueError):
            parser.parse("False", bool)


class TestAnnotated:
    def test_direct(self, parser: StrToTypeParser):
        from typing import Annotated

        assert parser.parse("5", Annotated[int, "meta"]) == 5

    def test_list_item(self, parser: StrToTypeParser):
        from typing import Annotated

        assert parser.parse("1,2,3", list[Annotated[int, "meta"]]) == [1, 2, 3]

    def test_union(self, parser: StrToTypeParser):
        from typing import Annotated

        assert parser.parse("1.5", Annotated[int | float, "meta"]) == 1.5


class TestIsSupported:
    class UnsupportedType:
        pass

    def test_basic_types(self, parser: StrToTypeParser):
        assert parser.is_supported(int) == True
        assert parser.is_supported(float) == True
        assert parser.is_supported(str) == True
        assert parser.is_supported(bool) == True

        assert parser.is_supported(self.UnsupportedType) == False
        assert parser.is_supported(bytes) == False

    def test_generic_types(self, parser: StrToTypeParser):
        assert parser.is_supported(list[int]) == True
        assert parser.is_supported(list[float]) == True
        assert parser.is_supported(list[str]) == True
        assert parser.is_supported(dict[str, int]) == True
        assert parser.is_supported(dict[str, float]) == True
        assert parser.is_supported(set[int]) == True

        assert parser.is_supported(list[self.UnsupportedType]) == False
        assert parser.is_supported(dict[self.UnsupportedType, int]) == False

        assert parser.is_supported(tuple[int, ...]) == True
        assert parser.is_supported(tuple[int, str]) == True
        assert parser.is_supported(tuple[self.UnsupportedType, ...]) == False
        assert parser.is_supported(tuple[int, self.UnsupportedType]) == False

    def test_union_types(self, parser: StrToTypeParser):
        assert parser.is_supported(int | float) == True
        assert parser.is_supported(str | int) == True
        assert parser.is_supported(float | str) == True

        assert parser.is_supported(int | self.UnsupportedType) == True  # int is supported
        assert parser.is_supported(self.UnsupportedType | bytes) == False

    def test_literal_types(self, parser: StrToTypeParser):
        from typing import Literal

        assert parser.is_supported(Literal[1, 2, 3]) == True
        assert parser.is_supported(Literal["a", "b", "c"]) == True
        assert parser.is_supported(Literal[True, False]) == True

    def test_enum_types(self, parser: StrToTypeParser):
        import enum

        class Color(enum.Enum):
            RED = 1
            GREEN = 2
            BLUE = 3

        assert parser.is_supported(Color) == True

    def test_unsupported_types(self, parser: StrToTypeParser):
        assert parser.is_supported(type) == False
        assert parser.is_supported(object) == False
        assert parser.is_supported(None) == False
