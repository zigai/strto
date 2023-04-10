import json
import os
from typing import Any, Iterable, Mapping

from converters import *
from stdl.fs import File, json_load, yaml_load

from .util import is_alias_type, is_union_type, type_to_str


class Parser:
    def __init__(self, converters: dict[Any, Converter] | None = None) -> None:
        self.converters: dict[Any, Converter] = converters or {}

    def __len__(self):
        return len(self.converters)

    def __getitem__(self, t: Any):
        return self.get(t)

    def add_converter(self, t: Any, func: Converter):
        self.converters[t] = func

    def extend(self, parsers: dict[Any, Converter]):
        self.converters = self.converters | parsers

    def get(self, t: Any):
        return self.converters[t]

    def parse(self, value: str, t: Any) -> Any:
        if parser := self.converters.get(t, None):
            return parser(value)
        if value is None:
            return None


def get_parser() -> Parser:
    converters = {
        str: CastTo(str),
        int: CastTo(int),
        float: CastTo(float),
        bool: CastTo(bool),
        list: IterableConverter(),
        tuple: IterableConverter(tuple),
        dict: MappingConverter(),
        set: IterableConverter(set),
        frozenset: IterableConverter(frozenset),
    }
    return Parser(converters)
