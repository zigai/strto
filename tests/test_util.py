import typing
from collections import OrderedDict, defaultdict

from strto.util import *


def test_is_iterable_type_simple():
    assert not is_iterable_type(int)
    assert is_iterable_type(list)
    assert is_iterable_type(str)
    assert is_iterable_type(dict)
    assert is_iterable_type(set)
    assert is_iterable_type(tuple)


def test_is_mapping_type_simple():
    assert not is_mapping_type(int)
    assert not is_mapping_type(list)
    assert not is_mapping_type(str)
    assert is_mapping_type(dict)


def test_is_iterable_type_alias():
    assert is_iterable_type(list[int])
    assert is_iterable_type(list[int | float])
    assert is_iterable_type(tuple[int])


def test_is_mapping_type_alias():
    assert is_mapping_type(dict[str, int])
    assert is_mapping_type(dict[str, int | float])


def test_is_iterable_type_typing():
    assert is_iterable_type(typing.List)
    assert is_iterable_type(typing.Dict)
    assert is_iterable_type(typing.Sequence)
    assert is_iterable_type(typing.Set)
    assert is_iterable_type(typing.Deque)


def test_is_mapping_type_typing():
    assert is_mapping_type(OrderedDict)
    assert is_mapping_type(defaultdict)
    assert is_mapping_type(typing.Dict)
    assert is_mapping_type(typing.Mapping)
    assert is_mapping_type(typing.OrderedDict)
    assert is_mapping_type(typing.DefaultDict)
