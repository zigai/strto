import ast
import datetime
import json
import math
import os
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from typing import Any, ClassVar, Literal, Protocol

from stdl import dt
from stdl.fs import File, json_load, yaml_load

from strto.utils import fmt_parser_err

ITER_SEP = ","
SLICE_SEP = ":"
FROM_FILE_PREFIX = "@"


class Parser(Protocol):
    def __call__(self, value: str) -> Any: ...
    def clean(self, value) -> str: ...
    def parse(self, value: str) -> Any: ...


class ParserBase(ABC):
    """Abstract base class for runtime parser implementations."""

    def __call__(self, value: str) -> Any:
        value = self.clean(value)
        return self.parse(value)

    def clean(self, value) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @abstractmethod
    def parse(self, value: str) -> Any:
        raise NotImplementedError


class Cast(ParserBase):
    """Cast a value to a type."""

    def __init__(self, t: type):
        self.t = t

    def parse(self, value) -> Any:
        if isinstance(value, self.t):
            return value
        try:
            return self.t(value)
        except Exception as e:
            raise ValueError(fmt_parser_err(value, self.t)) from e


class IterableParser(ParserBase):
    """
    Convert a value to an iterable.

    Args:
        t (type): The type to of the iterable. Defaults to list.
        sep (str): The separator to split the value by.
        from_file (bool): Whether to allow the value to be a readable from a file.
    """

    def __init__(self, t: type | None = None, sep: str = ITER_SEP, from_file: bool = False):  # type: ignore
        self.t = t
        self.sep = sep
        self.from_file = from_file

    def parse(self, value) -> Iterable:
        if isinstance(value, str):
            if self.from_file and value.startswith(FROM_FILE_PREFIX):
                filepath = value[len(FROM_FILE_PREFIX) :]
                if os.path.isfile(filepath):
                    value = self.read_from_file(filepath)
                else:
                    raise FileNotFoundError(
                        fmt_parser_err(value, self.t or "iterable", "file not found")
                    )
            else:
                value = [i.strip() for i in value.split(self.sep)]
        elif isinstance(value, Iterable):
            value = [i.split(self.sep) for i in value]
        else:
            raise TypeError(
                fmt_parser_err(value, self.t or "iterable", "expected string or Iterable")
            )
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
        t: type | None = None,
        mode: Literal["cast", "unpack"] = "cast",
        sep: str = ITER_SEP,
        from_file: bool = False,
    ):
        super().__init__(t, sep, from_file)
        self.mode = mode

    def parse(self, value) -> Mapping:
        if isinstance(value, str):
            if self.from_file and value.startswith(FROM_FILE_PREFIX):
                filepath = value[len(FROM_FILE_PREFIX) :]
                if os.path.isfile(filepath):
                    value = self.read_from_file(filepath)
                else:
                    raise FileNotFoundError(
                        fmt_parser_err(value, self.t or "mapping", "file not found")
                    )
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
        raise TypeError(
            fmt_parser_err(value, self.t or "mapping", "expected JSON string or @file path")
        )

    def read_from_file(self, value: str) -> Mapping:  # type:ignore
        if value.endswith((".yaml", ".yml")):
            return yaml_load(value)  # type:ignore
        return json_load(value)  # type:ignore


class DatetimeParser(ParserBase):
    def parse(self, value) -> datetime.datetime:
        try:
            return dt.parse_datetime_str(value)
        except Exception as e:
            raise ValueError(
                fmt_parser_err(value, datetime.datetime, "use common date formats like YYYY-MM-DD")
            ) from e


class DateParser(ParserBase):
    def parse(self, value) -> datetime.date:
        try:
            return dt.parse_datetime_str(value).date()
        except Exception as e:
            raise ValueError(
                fmt_parser_err(value, datetime.date, "use common date formats like YYYY-MM-DD")
            ) from e


class SliceParser(ParserBase):
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
                fmt_parser_err(
                    value, self.t, f"use 'start{self.sep}stop[{self.sep}step]' with 1-3 parts"
                )
            )
        return self.t(*nums)


class RangeParser(SliceParser):
    t = range

    def _get_nums(self, value: str):  # type:ignore
        return [int(i) for i in value.split(self.sep) if i]


class NumberParser(ParserBase):
    """Base class for numeric parsers."""

    CONSTANTS: ClassVar[dict[str, float]] = {}

    def __init__(self, allow_expressions: bool = True):
        self.allow_expressions = allow_expressions

    def parse(self, value: str):
        """Parse a string into a numeric value. To be implemented by subclasses."""
        raise NotImplementedError

    def _basic_parse(self, value: str):
        value = self.clean(value)

        if isinstance(value, str) and value in self.CONSTANTS:
            return self.CONSTANTS[value]

        try:
            return self._convert_value(value)
        except ValueError:
            pass

        return None

    def _convert_value(self, value):
        """Convert value to the appropriate numeric type. To be implemented by subclasses."""
        raise NotImplementedError

    def _eval_node(self, node: ast.expr):
        """Safely evaluate an AST node with limited operations."""
        match node:
            case ast.Constant():
                if isinstance(node.value, (int, float)):
                    return self._convert_constant(node.value)
                elif isinstance(node.value, str):
                    if node.value in self.CONSTANTS:
                        return self.CONSTANTS[node.value]
                    else:
                        raise TypeError(f"unsupported constant: '{node.value}'")
                else:
                    raise TypeError(f"unsupported constant type: {type(node.value)}")
            case ast.Name():
                if node.id in self.CONSTANTS:
                    return self.CONSTANTS[node.id]
                else:
                    raise NameError(f"undefined name: '{node.id}'")
            case ast.BinOp():
                left = self._eval_node(node.left)
                right = self._eval_node(node.right)
                return self._eval_binop(node.op, left, right)
            case ast.UnaryOp():
                operand = self._eval_node(node.operand)
                match node.op:
                    case ast.UAdd():
                        return +operand
                    case ast.USub():
                        return -operand
                    case _:
                        raise TypeError(f"unsupported unary operator: {type(node.op)}")
            case _:
                raise TypeError(f"unsupported node type: {type(node)}")

    def _convert_constant(self, value):
        """Convert a constant value. To be implemented by subclasses."""
        raise NotImplementedError

    def _eval_binop(self, op, left, right):
        """Evaluate a binary operation. To be implemented by subclasses."""
        raise NotImplementedError


class IntParser(NumberParser):
    def _basic_parse(self, value: str):
        """Override to reject float-like strings for union parsing"""
        value = self.clean(value)

        if isinstance(value, int):
            return value
        if isinstance(value, str) and value in self.CONSTANTS:
            return self.CONSTANTS[value]
        if "." in value:
            raise ValueError(fmt_parser_err(value, int, "looks like a float"))

        try:
            return self._convert_value(value)
        except ValueError:
            pass

        return None

    def parse(self, value: str) -> int:
        result = self._basic_parse(value)
        if result is not None:
            return self._convert_result(result)

        if self.allow_expressions:
            value = value.replace("^", "**")

            try:
                node = ast.parse(value, mode="eval")
                result = self._eval_node(node.body)
            except (SyntaxError, TypeError, NameError):
                raise ValueError(fmt_parser_err(value, int, "invalid expression or name"))
            except ZeroDivisionError:
                raise ZeroDivisionError(fmt_parser_err(value, int, "division by zero"))

            return self._convert_result(result)
        else:
            raise ValueError(fmt_parser_err(value, int, "invalid integer value"))

    def _convert_value(self, value):
        return int(value)

    def _convert_constant(self, value):
        return int(value)

    def _convert_result(self, result):
        if isinstance(result, (int, float)):
            return int(result)
        else:
            raise TypeError("expression does not evaluate to a number")

    def _eval_binop(self, op, left, right):
        match op:
            case ast.Add():
                return left + right
            case ast.Sub():
                return left - right
            case ast.Mult():
                return left * right
            case ast.Div():
                return left // right
            case ast.FloorDiv():
                return left // right
            case ast.Mod():
                return left % right
            case ast.Pow():
                return left**right
            case _:
                raise TypeError(f"unsupported binary operator: {type(op)}")


class FloatParser(NumberParser):
    CONSTANTS: ClassVar[dict[str, float]] = {
        "pi": math.pi,
        "e": math.e,
        "tau": math.tau,
        "phi": (1 + math.sqrt(5)) / 2,
        "sqrt2": math.sqrt(2),
        "sqrt3": math.sqrt(3),
    }

    def parse(self, value: str) -> float:
        result = self._basic_parse(value)
        if result is not None:
            return self._convert_result(result)

        if self.allow_expressions:
            value = value.replace("^", "**")

            try:
                node = ast.parse(value, mode="eval")
                result = self._eval_node(node.body)
            except (SyntaxError, TypeError, NameError):
                raise ValueError(fmt_parser_err(value, float, "invalid expression or name"))
            except ZeroDivisionError:
                raise ZeroDivisionError(fmt_parser_err(value, float, "division by zero"))

            return self._convert_result(result)
        else:
            raise ValueError(fmt_parser_err(value, float, "invalid float value"))

    def _convert_value(self, value):
        return float(value)

    def _convert_constant(self, value):
        return float(value)

    def _convert_result(self, result):
        if isinstance(result, (int, float)):
            return float(result)
        else:
            raise TypeError("expression does not evaluate to a number")

    def _eval_binop(self, op, left, right):
        match op:
            case ast.Add():
                return left + right
            case ast.Sub():
                return left - right
            case ast.Mult():
                return left * right
            case ast.Div():
                return left / right
            case ast.FloorDiv():
                return left // right
            case ast.Mod():
                return left % right
            case ast.Pow():
                return left**right
            case _:
                raise TypeError(f"unsupported binary operator: {type(op)}")


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
            raise ValueError(fmt_parser_err(value, bool, "valid choices: '1','0','true','false'"))
        raise TypeError(fmt_parser_err(value, bool, "expected bool, int, or str"))


__all__ = [
    "Cast",
    "Parser",
    "ParserBase",
    "DateParser",
    "DatetimeParser",
    "FloatParser",
    "IntParser",
    "IterableParser",
    "MappingParser",
    "RangeParser",
    "SliceParser",
    "BoolParser",
]
