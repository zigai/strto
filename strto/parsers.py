import datetime
import json
import os
import typing as T

from stdl import dt
from stdl.fs import File, json_load, yaml_load

from strto.constants import FROM_FILE_PREFIX, ITER_SEP, SLICE_SEP


class ParserBase(T.Protocol):
    """
    Base class for all converters.
    """

    def __call__(self, value: str) -> T.Any:
        value = self.clean(value)
        return self.parse(value)

    def clean(self, value) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    def parse(self, value: str) -> T.Any:
        raise NotImplementedError


class Cast(ParserBase):
    """Cast a value to a type."""

    def __init__(self, t: type):
        self.t = t

    def parse(self, value) -> T.Any:
        if isinstance(value, self.t):
            return value
        return self.t(value)


class IterableParser(ParserBase):
    """
    Convert a value to an iterable.

    Args:
        iter_t (type): The type to of the iterable. Defaults to list.
        sep (str): The separator to split the value by.
        from_file (bool): Whether to allow the value to be a readable from a file.
    """

    def __init__(self, iter_t: type = None, sep: str = ITER_SEP, from_file: bool = False):  # type: ignore
        self.sep = sep
        self.from_file = from_file
        self.iter_t = iter_t

    def parse(self, value) -> T.Iterable:
        if isinstance(value, str):
            if self.from_file and value.startswith(FROM_FILE_PREFIX):
                filepath = value[len(FROM_FILE_PREFIX) :]
                if os.path.isfile(filepath):
                    value = self.read_from_file(filepath)
                else:
                    raise FileNotFoundError(value)
            else:
                value = [i.strip() for i in value.split(self.sep)]
        elif isinstance(value, T.Iterable):
            value = [i.split(self.sep) for i in value]
        else:
            raise TypeError(f"Cannot convert '{value}' to an iterable")
        if self.iter_t is not None:
            return self.iter_t(value)  # type: ignore
        return value

    def read_from_file(self, value: str):
        data = File(value).should_exist().splitlines()
        if len(data) == 1 and self.sep in data[0]:
            data = data[0].split(self.sep)
        return [i.strip() for i in data]


class MappingParser(IterableParser):
    """
    Convert a value to a mapping.

    Args:
        mapping_t (type): The type to cast mapping values to.
        sep (str): The separator to split the value by.
        from_file (bool): Whether to allow the value to be a readable from a file.
    """

    def __init__(self, mapping_t: type = None, sep: str = ITER_SEP, from_file: bool = False):  # type: ignore
        self.sep = sep
        self.from_file = from_file
        self.mapping_t = mapping_t

    def parse(self, value) -> T.Mapping:
        if isinstance(value, str):
            if self.from_file and value.startswith(FROM_FILE_PREFIX):
                filepath = value[len(FROM_FILE_PREFIX) :]
                if os.path.isfile(filepath):
                    value = self.read_from_file(filepath)
                else:
                    raise FileNotFoundError(value)
            else:
                value = json.loads(value)
            if self.mapping_t is not None:
                return self.mapping_t(value)  # type: ignore
            return value
        raise TypeError(f"Cannot convert '{value}' to a mapping")

    def read_from_file(self, value: str) -> T.Mapping:  # type:ignore
        if value.endswith((".yaml", ".yml")):
            return yaml_load(value)  # type:ignore
        return json_load(value)  # type:ignore


class DatetimeParser(ParserBase):
    def parse(self, value) -> datetime.datetime:
        return dt.parse_datetime_str(value)


class DateParser(ParserBase):
    def parse(self, value) -> datetime.date:
        return dt.parse_datetime_str(value).date()


class SliceParser(ParserBase):
    def __init__(self, sep: str = SLICE_SEP):
        self.sep = sep

    def parse(self, value: str) -> slice:
        if isinstance(value, slice):
            return value
        nums = [float(i) if i else None for i in value.split(self.sep)]
        if len(nums) not in (1, 2, 3):
            raise ValueError(f"Slice argument must be 1-3 values separated by '{self.sep}'")
        return slice(*nums)


class RangeParser(ParserBase):
    def __init__(self, sep: str = SLICE_SEP):
        self.sep = sep

    def parse(self, value: str) -> range:
        if isinstance(value, range):
            return value
        nums = [int(i) for i in value.split(self.sep) if i]
        if len(nums) not in (1, 2, 3):
            raise ValueError(f"Range argument must be 1-3 values separated by '{self.sep}'")
        return range(*nums)


class IntFloatParser(ParserBase):
    def parse(self, value: str) -> int | float:
        value = self.clean(value)
        if isinstance(value, (int, float)):
            return value
        if "e" in value or "." in value:
            return float(value)
        return int(value)


class BoolParser(ParserBase):
    def parse(self, value: str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            value = value.lower()
            if value in ["1", "true"]:
                return True
            if value in ["0", "false"]:
                return False
            raise ValueError(value)
        raise TypeError(value)


__all__ = [
    "Cast",
    "ParserBase",
    "DateParser",
    "DatetimeParser",
    "IterableParser",
    "MappingParser",
    "RangeParser",
    "SliceParser",
    "BoolParser",
]
