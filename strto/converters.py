import datetime
import json
import os
from typing import Any, Iterable, Mapping

from stdl import dt
from stdl.fs import File, json_load, yaml_load

from strto.constants import ITER_SEP, SLICE_SEP


class Converter:
    """
    Base class for all converters.
    """

    def __init__(self):
        pass

    def __call__(self, value: str) -> Any:
        value = self.clean(value)
        return self.convert(value)

    def clean(self, value) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    def convert(self, value: str) -> Any:
        raise NotImplementedError


class CastTo(Converter):
    """
    Cast a value to a type.
    """

    def __init__(self, t: type):
        self.t = t

    def convert(self, value) -> Any:
        if isinstance(value, self.t):
            return value
        return self.t(value)


class IterableConverter(Converter):
    """
    Convert a value to an iterable.

    Args:
        t (type): The type to of the iterable. Defaults to list.
        sep (str): The separator to split the value by.
        from_file (bool): Whether to allow the value to be a readable from a file.
    """

    def __init__(self, t: type = None, sep: str = ITER_SEP, from_file: bool = False):  # type: ignore
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
    """
    Convert a value to a mapping.

    Args:
        t (type): The type to cast mapping values to.
        sep (str): The separator to split the value by.
        from_file (bool): Whether to allow the value to be a readable from a file.
    """

    def __init__(self, t: type = None, sep: str = ITER_SEP, from_file: bool = False):  # type: ignore
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


class DateTimeConverter(Converter):
    def convert(self, value) -> datetime.datetime:
        return dt.parse_datetime_str(value)


class DateConverter(Converter):
    def convert(self, value) -> datetime.date:
        return dt.parse_datetime_str(value).date()


class SliceConverter(Converter):
    def __init__(self, sep: str = SLICE_SEP):
        self.sep = sep

    def convert(self, value: str) -> slice:
        if isinstance(value, slice):
            return value
        nums = [float(i) if i else None for i in value.split(self.sep)]
        if len(nums) not in (1, 2, 3):
            raise ValueError(f"Slice arg must be 1-3 values separated by {self.sep}")
        return slice(*nums)


class RangeConverter(Converter):
    def __init__(self, sep: str = SLICE_SEP):
        self.sep = sep

    def convert(self, value: str) -> range:
        if isinstance(value, range):
            return value
        nums = [int(i) for i in value.split(self.sep) if i]
        if len(nums) not in (1, 2, 3):
            raise ValueError(f"Range arg must be 1-3 values separated by {self.sep}")
        return range(*nums)


__all__ = [
    "CastTo",
    "Converter",
    "DateConverter",
    "DateTimeConverter",
    "IterableConverter",
    "MappingConverter",
    "RangeConverter",
    "SliceConverter",
]
