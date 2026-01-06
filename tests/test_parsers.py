import array
import ast
import datetime
import json
from types import SimpleNamespace

import pytest

from strto import parsers


class DummyParser(parsers.ParserBase):
    def parse(self, value: str):
        return super().parse(value)


def test_parser_base_call_and_clean() -> None:
    class Identity(parsers.ParserBase):
        def parse(self, value: str):
            return value

    parser = Identity()
    assert parser("  spaced  ") == "spaced"


def test_parser_base_not_implemented() -> None:
    parser = DummyParser()
    with pytest.raises(NotImplementedError):
        parser.parse("value")


def test_cast_success_and_error() -> None:
    caster = parsers.Cast(int)
    assert caster("5") == 5
    with pytest.raises(ValueError):
        caster("not-int")


def test_cast_str_preserves_whitespace() -> None:
    caster = parsers.Cast(str)
    assert caster("  spaced  ") == "  spaced  "
    assert parsers.Cast(int)(" 5 ") == 5


def test_iterable_parser_from_file(tmp_path) -> None:
    data_file = tmp_path / "values.txt"
    data_file.write_text("1,2,3")
    parser = parsers.IterableParser(list, from_file=True)
    assert parser(f"@{data_file}") == ["1", "2", "3"]


def test_iterable_parser_multiline_file(tmp_path) -> None:
    data_file = tmp_path / "values.txt"
    data_file.write_text("1\n2\n3\n")
    parser = parsers.IterableParser(from_file=True)
    assert parser(f"@{data_file}") == ["1", "2", "3"]


def test_iterable_parser_missing_file(tmp_path) -> None:
    parser = parsers.IterableParser(list, from_file=True)
    with pytest.raises(FileNotFoundError):
        parser(f"@{tmp_path / 'missing.txt'}")


def test_iterable_parser_from_iterable() -> None:
    parser = parsers.IterableParser(tuple)
    assert parser(["a,b", "c,d"]) == (["a", "b"], ["c", "d"])


def test_iterable_parser_invalid_type() -> None:
    parser = parsers.IterableParser()
    with pytest.raises(TypeError):
        parser(42)  # type: ignore[arg-type]


def test_mapping_parser_from_json() -> None:
    parser = parsers.MappingParser(dict)
    assert parser(json.dumps({"a": 1})) == {"a": 1}


def test_mapping_parser_without_target() -> None:
    parser = parsers.MappingParser()
    assert parser(json.dumps({"a": 1})) == {"a": 1}


def test_mapping_parser_from_file_yaml(tmp_path) -> None:
    yaml_file = tmp_path / "data.yaml"
    yaml_file.write_text("a: 1\n")
    parser = parsers.MappingParser(dict, from_file=True)
    assert parser(f"@{yaml_file}") == {"a": 1}


def test_mapping_parser_from_file_json(tmp_path) -> None:
    json_file = tmp_path / "data.json"
    json_file.write_text(json.dumps({"a": 1}))
    parser = parsers.MappingParser(dict, from_file=True)
    assert parser(f"@{json_file}") == {"a": 1}


def test_mapping_parser_unpacked_mode() -> None:
    class Container(SimpleNamespace):
        pass

    parser = parsers.MappingParser(Container, mode="unpack")
    result = parser(json.dumps({"a": 1}))
    assert isinstance(result, Container)
    assert result.a == 1


def test_mapping_parser_invalid_mode() -> None:
    parser = parsers.MappingParser(dict, mode="invalid")
    with pytest.raises(ValueError):
        parser(json.dumps({"a": 1}))


def test_mapping_parser_invalid_type() -> None:
    parser = parsers.MappingParser(dict)
    with pytest.raises(TypeError):
        parser({"a": 1})  # type: ignore[arg-type]


def test_mapping_parser_missing_file(tmp_path) -> None:
    parser = parsers.MappingParser(dict, from_file=True)
    with pytest.raises(FileNotFoundError):
        parser(f"@{tmp_path / 'missing.json'}")


def test_datetime_parser_error() -> None:
    parser = parsers.DatetimeParser()
    with pytest.raises(ValueError):
        parser("not-a-date")


def test_date_parser_error() -> None:
    parser = parsers.DateParser()
    with pytest.raises(ValueError):
        parser("not-a-date")


def test_time_parser_success() -> None:
    parser = parsers.TimeParser()
    t = parser("12:34:56")
    assert t.hour == 12
    assert t.minute == 34
    assert t.second == 56


def test_time_parser_error() -> None:
    parser = parsers.TimeParser()
    with pytest.raises(ValueError):
        parser("not-a-time")


def test_timedelta_parser_numeric() -> None:
    parser = parsers.TimedeltaParser()
    assert parser("3600") == datetime.timedelta(hours=1)
    assert parser(1800) == datetime.timedelta(minutes=30)
    assert parser(90.5) == datetime.timedelta(seconds=90.5)


def test_timedelta_parser_string_hms() -> None:
    parser = parsers.TimedeltaParser()
    assert parser("01:00:00") == datetime.timedelta(hours=1)
    assert parser("00:30:00") == datetime.timedelta(minutes=30)


def test_timedelta_parser_error() -> None:
    parser = parsers.TimedeltaParser()
    with pytest.raises(ValueError):
        parser("invalid")


def test_slice_parser_existing_slice() -> None:
    parser = parsers.SliceParser()
    existing = slice(1, 5, 2)
    assert parser(existing) is existing


def test_slice_parser_invalid_length() -> None:
    parser = parsers.SliceParser()
    with pytest.raises(ValueError):
        parser("1:2:3:4")


def test_range_parser_success() -> None:
    parser = parsers.RangeParser()
    assert parser("1:4:1") == range(1, 4, 1)


def test_int_parser_rejects_float_like() -> None:
    parser = parsers.IntParser()
    with pytest.raises(ValueError):
        parser.parse("3.5")


def test_int_parser_invalid_expression() -> None:
    parser = parsers.IntParser()
    with pytest.raises(ValueError):
        parser.parse("(1,2)")


def test_int_parser_no_expressions() -> None:
    parser = parsers.IntParser(allow_expressions=False)
    with pytest.raises(ValueError):
        parser.parse("abc")


def test_int_parser_convert_result_error() -> None:
    parser = parsers.IntParser()
    with pytest.raises(TypeError):
        parser._convert_result("oops")  # type: ignore[arg-type]


def test_int_parser_eval_binop_error() -> None:
    parser = parsers.IntParser()
    with pytest.raises(TypeError):
        parser._eval_binop(ast.BitAnd(), 1, 2)


def test_float_parser_invalid_expression() -> None:
    parser = parsers.FloatParser()
    with pytest.raises(ValueError):
        parser.parse("unknown_name")


def test_float_parser_no_expressions() -> None:
    parser = parsers.FloatParser(allow_expressions=False)
    with pytest.raises(ValueError):
        parser.parse("1+2")


def test_float_parser_convert_result_error() -> None:
    parser = parsers.FloatParser()
    with pytest.raises(TypeError):
        parser._convert_result("oops")  # type: ignore[arg-type]


def test_float_parser_eval_binop_error() -> None:
    parser = parsers.FloatParser()
    with pytest.raises(TypeError):
        parser._eval_binop(ast.BitAnd(), 1.0, 2.0)


def test_bool_parser_synonyms_and_errors() -> None:
    parser = parsers.BoolParser(case_sensitive=True)
    assert parser("true") is True
    assert parser("false") is False
    assert parser(1) is True
    assert parser(False) is False
    with pytest.raises(ValueError):
        parser("maybe")
    with pytest.raises(TypeError):
        parser(3.14)  # type: ignore[arg-type]


def test_literal_parser_behaviour() -> None:
    parser = parsers.LiteralParser((1, "two", b"three", True), target_t="Choice")
    assert parser("1") == 1
    assert parser("two") == "two"
    assert parser("true") is True
    with pytest.raises(ValueError):
        parser("missing")


def test_literal_parser_empty_choices() -> None:
    parser = parsers.LiteralParser((), target_t="Choice")
    with pytest.raises(ValueError):
        parser("anything")


def test_number_parser_not_implemented() -> None:
    number_parser = parsers.NumberParser()
    with pytest.raises(NotImplementedError):
        number_parser.parse("1")
    with pytest.raises(NotImplementedError):
        number_parser._convert_value("1")
    with pytest.raises(NotImplementedError):
        number_parser._convert_constant(1)
    with pytest.raises(NotImplementedError):
        number_parser._eval_binop(ast.Add(), 1, 2)


def test_number_parser_eval_node_behaviour() -> None:
    parser = parsers.FloatParser()
    assert parser._eval_node(ast.Constant("pi")) == pytest.approx(
        parsers.FloatParser.CONSTANTS["pi"]
    )
    assert parser._eval_node(ast.UnaryOp(op=ast.UAdd(), operand=ast.Constant(2))) == 2.0
    with pytest.raises(TypeError):
        parser._eval_node(ast.Constant("not_const"))
    with pytest.raises(TypeError):
        parser._eval_node(ast.Constant(None))
    with pytest.raises(TypeError):
        parser._eval_node(ast.UnaryOp(op=ast.Not(), operand=ast.Constant(1)))
    with pytest.raises(TypeError):
        parser._eval_node(ast.List(elts=[], ctx=ast.Load()))


def test_int_parser_constant_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(parsers.IntParser.CONSTANTS, "ten", 10)
    parser = parsers.IntParser()
    assert parser.parse("ten") == 10


def test_array_parser_with_explicit_type_code() -> None:
    parser = parsers.ArrayParser(type_code="i")
    result = parser("1,2,3")
    assert result == array.array("i", [1, 2, 3])


def test_array_parser_with_float_type_code() -> None:
    parser = parsers.ArrayParser(type_code="d")
    result = parser("1.5,2.5,3.5")
    assert result == array.array("d", [1.5, 2.5, 3.5])


def test_array_parser_infer_float_from_values() -> None:
    parser = parsers.ArrayParser()
    result = parser("1.5,2.5")
    assert result.typecode == "d"
    assert list(result) == [1.5, 2.5]


def test_array_parser_infer_int_from_values() -> None:
    parser = parsers.ArrayParser()
    result = parser("1,2,3")
    assert result.typecode == "l"
    assert list(result) == [1, 2, 3]


def test_array_parser_passthrough_existing_array() -> None:
    parser = parsers.ArrayParser(type_code="i")
    arr = array.array("i", [1, 2])
    assert parser(arr) is arr


def test_array_parser_invalid_value() -> None:
    parser = parsers.ArrayParser(type_code="i")
    with pytest.raises(ValueError):
        parser("1,abc,3")


def test_array_parser_custom_separator() -> None:
    parser = parsers.ArrayParser(type_code="i", sep=";")
    result = parser("1;2;3")
    assert result == array.array("i", [1, 2, 3])


def test_array_parser_ctypes_short() -> None:
    import ctypes

    type_code = parsers.ArrayParser.get_type_code(ctypes.c_short)
    assert type_code == "h"
    parser = parsers.ArrayParser(type_code=type_code)
    result = parser("1,2,3")
    assert result.typecode == "h"


def test_array_parser_ctypes_ulonglong() -> None:
    import ctypes

    type_code = parsers.ArrayParser.get_type_code(ctypes.c_ulonglong)
    assert type_code == "Q"


def test_array_parser_get_type_code_none() -> None:
    assert parsers.ArrayParser.get_type_code(None) is None


def test_array_parser_get_type_code_unknown() -> None:
    assert parsers.ArrayParser.get_type_code(str) is None
