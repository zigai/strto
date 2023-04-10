import json
import os
from typing import Any, Iterable, Mapping

from stdl.fs import File, json_load, yaml_load


class Converter:
    def __init__(self):
        pass

    def __call__(self, value: str) -> Any:
        value = self.clean(value)
        return self.convert(value)

    def clean(self, value) -> str:
        return value.strip()

    def convert(self, value: str) -> Any:
        raise NotImplementedError


class CastTo(Converter):
    def __init__(self, t: type):
        self.t = t

    def convert(self, value) -> Any:
        if isinstance(value, self.t):
            return value
        return self.t(value)


class IterableConverter(Converter):
    def __init__(self, t: type = None, sep: str = ",", from_file: bool = False):  # type: ignore
        self.sep = sep
        self.from_file = from_file
        self.t = t

    def convert(self, value) -> Iterable:
        if isinstance(value, str):
            if self.from_file and os.path.isfile(value):
                value = self.read_from_file(value)
            else:
                value = [i.strip() for i in value.split(self.sep)]
        elif isinstance(value, Iterable):
            value = [i.split(self.sep) for i in value]
        else:
            raise TypeError(f"Cannot convert '{value}' to an iterable")

        if self.t is not None:
            return self.t(value)  # type: ignore
        return value

    def read_from_file(self, value: str):
        data = File(value).splitlines()
        if len(data) == 1 and self.sep in data[0]:
            data = data[0].split(self.sep)
        return [i.strip() for i in data]


class MappingConverter(IterableConverter):
    def __init__(self, t: type = None, sep: str = ",", from_file: bool = False):  # type: ignore
        self.sep = sep
        self.from_file = from_file
        self.t = t

    def convert(self, value) -> Mapping:
        if isinstance(value, str):
            if self.from_file and os.path.isfile(value):
                value = self.read_from_file(value)
            else:
                value = json.loads(value)
            if self.t is not None:
                return self.t(value)  # type: ignore
            return value
        raise TypeError(f"Cannot convert '{value}' to a mapping")

    def read_from_file(self, value: str) -> Mapping:
        if value.endswith((".yaml", ".yml")):
            return yaml_load(value)  # type:ignore
        return json_load(value)  # type:ignore
