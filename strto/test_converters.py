from .converters import *


def test_iterable_converter():
    assert IterableConverter()("a,b,c") == ["a", "b", "c"]
    assert IterableConverter()("a  ,b,c  ") == ["a", "b", "c"]
    assert IterableConverter(t=tuple)("a,b,c") == ("a", "b", "c")
    assert IterableConverter(t=set)("a,b,c") == set(["a", "b", "c"])
