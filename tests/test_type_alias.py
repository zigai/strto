from typing import Annotated

from strto import StrToTypeParser


class TestTypeAlias:
    def test_simple_type_alias(self, parser: StrToTypeParser) -> None:
        type IntAlias = int
        assert parser.parse("42", IntAlias) == 42

    def test_type_alias_to_list(self, parser: StrToTypeParser) -> None:
        type IntList = list[int]
        assert parser.parse("1,2,3", IntList) == [1, 2, 3]

    def test_nested_type_alias(self, parser: StrToTypeParser) -> None:
        type MyInt = int
        type MyIntList = list[MyInt]
        assert parser.parse("1,2,3", MyIntList) == [1, 2, 3]

    def test_type_alias_dict(self, parser: StrToTypeParser) -> None:
        type StrIntDict = dict[str, int]
        assert parser.parse('{"a":1,"b":2}', StrIntDict) == {"a": 1, "b": 2}

    def test_type_alias_tuple(self, parser: StrToTypeParser) -> None:
        type IntStrTuple = tuple[int, str]
        assert parser.parse("42,hello", IntStrTuple) == (42, "hello")

    def test_is_supported_type_alias(self, parser: StrToTypeParser) -> None:
        type IntAlias = int
        type IntList = list[int]
        assert parser.is_supported(IntAlias) is True
        assert parser.is_supported(IntList) is True

    def test_chained_type_alias(self, parser: StrToTypeParser) -> None:
        type A = int
        type B = A
        type C = B
        assert parser.parse("42", C) == 42

    def test_annotated_type_alias(self, parser: StrToTypeParser) -> None:
        type MyInt = int
        assert parser.parse("42", Annotated[MyInt, "meta"]) == 42

    def test_type_alias_of_annotated(self, parser: StrToTypeParser) -> None:
        type AnnotatedInt = Annotated[int, "metadata"]
        assert parser.parse("42", AnnotatedInt) == 42

    def test_type_alias_in_union(self, parser: StrToTypeParser) -> None:
        type MyInt = int
        assert parser.parse("42", MyInt | str) == 42
        assert parser.parse("hello", MyInt | str) == "hello"
