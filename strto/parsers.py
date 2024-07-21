import datetime
import json
import os
import typing as T

from stdl import dt
from stdl.fs import File, json_load, yaml_load

from strto.constants import FROM_FILE_PREFIX, ITER_SEP, SLICE_SEP


class Parser(T.Protocol):
    """
    Base class for all parsers.
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


class Cast(Parser):
    """Cast a value to a type."""

    def __init__(self, t: type):
        self.t = t

    def parse(self, value) -> T.Any:
        if isinstance(value, self.t):
            return value
        return self.t(value)


class IterableParser(Parser):
    """
    Convert a value to an iterable.

    Args:
        t (type): The type to of the iterable. Defaults to list.
        sep (str): The separator to split the value by.
        from_file (bool): Whether to allow the value to be a readable from a file.
    """

    def __init__(self, t: type = None, sep: str = ITER_SEP, from_file: bool = False):  # type: ignore
        self.t = t
        self.sep = sep
        self.from_file = from_file

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
        if self.t is not None:
            return self.t(value)  # type: ignore
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
        t (type): The type to cast mapping values to.
        sep (str): The separator to split the value by.
        from_file (bool): Whether to allow the value to be a readable from a file.
    """

    def __init__(
        self,
        t: type = None,
        mode: T.Literal["cast", "unpack"] = "cast",
        sep: str = ITER_SEP,
        from_file: bool = False,
    ):
        super().__init__(t, sep, from_file)
        self.mode = mode

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
            if self.t is not None:
                if self.mode == "cast":
                    return self.t(value)
                elif self.mode == "unpack":
                    return self.t(**value)  # type: ignore
                else:
                    raise ValueError(f"Invalid mode: {self.mode}")
            return value
        raise TypeError(f"Cannot convert '{value}' to a mapping")

    def read_from_file(self, value: str) -> T.Mapping:  # type:ignore
        if value.endswith((".yaml", ".yml")):
            return yaml_load(value)  # type:ignore
        return json_load(value)  # type:ignore


class DatetimeParser(Parser):
    def parse(self, value) -> datetime.datetime:
        return dt.parse_datetime_str(value)


class DateParser(Parser):
    def parse(self, value) -> datetime.date:
        return dt.parse_datetime_str(value).date()


class SliceParser(Parser):
    t = slice

    def __init__(self, sep: str = SLICE_SEP):
        self.sep = sep

    def _get_nums(self, value: str):
        return [float(i) if i else None for i in value.split(self.sep)]

    def parse(self, value: str):
        if isinstance(value, self.t):
            return value
        nums = self._get_nums(value)
        if len(nums) not in (1, 2, 3):
            raise ValueError(
                f"{self.t.__name__} argument must be 1-3 values separated by '{self.sep}'"
            )
        return self.t(*nums)


class RangeParser(SliceParser):
    t = range

    def _get_nums(self, value: str):  # type:ignore
        return [int(i) for i in value.split(self.sep) if i]


class IntFloatParser(Parser):
    def parse(self, value: str) -> int | float:
        value = self.clean(value)
        if isinstance(value, (int, float)):
            return value
        if "e" in value or "." in value:
            return float(value)
        return int(value)


class BoolParser(Parser):
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
    "Parser",
    "DateParser",
    "DatetimeParser",
    "IterableParser",
    "MappingParser",
    "RangeParser",
    "SliceParser",
    "BoolParser",
]
