import ast
import datetime
import json
import math
import os
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from typing import Any, ClassVar, Generic, Literal, Protocol, TypeVar, overload

from stdl import dt
from stdl.fs import File, json_load, yaml_load

from strto.utils import fmt_parser_err

ParseResultType = TypeVar("ParseResultType")
ParseResultType_co = TypeVar("ParseResultType_co", covariant=True)
IterableType = TypeVar("IterableType", bound="Iterable")
MappingType = TypeVar("MappingType", bound="Mapping")
NumericType = TypeVar("NumericType", int, float)

ITER_SEP = ","
SLICE_SEP = ":"
FROM_FILE_PREFIX = "@"


class Parser(Protocol[ParseResultType_co]):
    def __call__(self, value: str) -> ParseResultType_co: ...
    def clean(self, value: Any) -> Any: ...
    def parse(self, value: str) -> ParseResultType_co: ...


class ParserBase(ABC, Generic[ParseResultType]):
    """Abstract base class for runtime parser implementations."""

    def __call__(self, value: str) -> ParseResultType:
        value = self.clean(value)
        return self.parse(value)

    def clean(self, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @abstractmethod
    def parse(self, value: str) -> ParseResultType:
        raise NotImplementedError


class Cast(ParserBase[ParseResultType]):
    """Cast a value to a type."""

    def __init__(self, t: type[ParseResultType]) -> None:
        self.t = t

    def clean(self, value: Any) -> Any:
        if self.t is str:
            return value
        return super().clean(value)

    def parse(self, value: Any) -> ParseResultType:
        if isinstance(value, self.t):
            return value
        try:
            return self.t(value)
        except Exception as e:
            raise ValueError(fmt_parser_err(value, self.t)) from e


class IterableParser(ParserBase[IterableType]):
    """
    Convert a value to an iterable.

    Args:
        t (type): The type to of the iterable. Defaults to list.
        sep (str): The separator to split the value by.
        from_file (bool): Whether to allow the value to be a readable from a file.
    """

    @overload
    def __init__(
        self,
        t: type[IterableType],
        sep: str = ...,
        from_file: bool = ...,
    ) -> None: ...

    @overload
    def __init__(
        self,
        t: None = ...,
        sep: str = ...,
        from_file: bool = ...,
    ) -> None: ...

    def __init__(
        self,
        t: type[IterableType] | None = None,
        sep: str = ITER_SEP,
        from_file: bool = False,
    ) -> None:
        self.t: type[IterableType] | None = t
        self.sep = sep
        self.from_file = from_file

    def parse(self, value: str | Iterable[str]) -> IterableType:
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
            return self.t(value)  # type: ignore[return-value]
        return value  # type: ignore[return-value]

    def read_from_file(self, value: str) -> list[str]:
        data = File(value).should_exist().splitlines()
        if len(data) == 1 and self.sep in data[0]:
            data = data[0].split(self.sep)
        return [i.strip() for i in data]


class MappingParser(IterableParser[MappingType]):  # type: ignore[type-arg]
    """
    Convert a value to a mapping.

    Args:
        t (type): The type to cast mapping values to.
        sep (str): The separator to split the value by.
        from_file (bool): Whether to allow the value to be a readable from a file.
    """

    @overload
    def __init__(
        self,
        t: type[MappingType],
        mode: Literal["cast", "unpack"] = ...,
        sep: str = ...,
        from_file: bool = ...,
    ) -> None: ...

    @overload
    def __init__(
        self,
        t: None = ...,
        mode: Literal["cast", "unpack"] = ...,
        sep: str = ...,
        from_file: bool = ...,
    ) -> None: ...

    def __init__(
        self,
        t: type[MappingType] | None = None,
        mode: Literal["cast", "unpack"] = "cast",
        sep: str = ITER_SEP,
        from_file: bool = False,
    ) -> None:
        super().__init__(t, sep, from_file)  # type: ignore[arg-type]
        self.mode = mode

    def parse(self, value: str) -> MappingType:  # type: ignore[override]
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
                    return self.t(value)  # type: ignore[return-value]
                elif self.mode == "unpack":
                    return self.t(**value)  # type: ignore[return-value]
                else:
                    raise ValueError(f"Invalid mode: {self.mode}")
            return value  # type: ignore[return-value]
        raise TypeError(
            fmt_parser_err(value, self.t or "mapping", "expected JSON string or @file path")
        )

    def read_from_file(self, value: str) -> Mapping[str, Any]:  # type: ignore[override]
        if value.endswith((".yaml", ".yml")):
            return yaml_load(value)  # type: ignore[return-value]
        return json_load(value)  # type: ignore[return-value]


class DatetimeParser(ParserBase[datetime.datetime]):
    def parse(self, value: str) -> datetime.datetime:
        try:
            return dt.parse_datetime_str(value)
        except Exception as e:
            raise ValueError(
                fmt_parser_err(value, datetime.datetime, "use common date formats like YYYY-MM-DD")
            ) from e


class DateParser(ParserBase[datetime.date]):
    def parse(self, value: str) -> datetime.date:
        try:
            return dt.parse_datetime_str(value).date()
        except Exception as e:
            raise ValueError(
                fmt_parser_err(value, datetime.date, "use common date formats like YYYY-MM-DD")
            ) from e


class TimeParser(ParserBase[datetime.time]):
    def parse(self, value: str) -> datetime.time:
        try:
            return dt.parse_datetime_str(value).time()
        except Exception as e:
            raise ValueError(
                fmt_parser_err(value, datetime.time, "use common time formats like HH:MM:SS")
            ) from e


class TimedeltaParser(ParserBase[datetime.timedelta]):
    def parse(self, value: str | int | float) -> datetime.timedelta:
        if isinstance(value, (int, float)):
            return datetime.timedelta(seconds=value)
        try:
            return datetime.timedelta(seconds=dt.hms_to_seconds(value))
        except Exception as e:
            raise ValueError(
                fmt_parser_err(value, datetime.timedelta, "use formats like HH:MM:SS or seconds")
            ) from e


class SliceParser(ParserBase[slice]):
    def __init__(self, sep: str = SLICE_SEP) -> None:
        self.sep = sep

    def _get_nums(self, value: str) -> list[float | None]:
        return [float(i) if i else None for i in value.split(self.sep)]

    def parse(self, value: str | slice) -> slice:
        if isinstance(value, slice):
            return value
        nums = self._get_nums(value)
        if len(nums) not in (1, 2, 3):
            raise ValueError(
                fmt_parser_err(
                    value,
                    slice,
                    f"use 'start{self.sep}stop[{self.sep}step]' with 1-3 parts",
                )
            )
        return slice(*nums)


class RangeParser(ParserBase[range]):
    def __init__(self, sep: str = SLICE_SEP) -> None:
        self.sep = sep

    def _get_nums(self, value: str) -> list[int]:
        return [int(i) for i in value.split(self.sep) if i]

    def parse(self, value: str | range) -> range:
        if isinstance(value, range):
            return value
        nums = self._get_nums(value)
        if len(nums) not in (1, 2, 3):
            raise ValueError(
                fmt_parser_err(
                    value,
                    range,
                    f"use 'start{self.sep}stop[{self.sep}step]' with 1-3 parts",
                )
            )
        return range(*nums)


class NumberParser(ParserBase[NumericType]):
    """Base class for numeric parsers."""

    CONSTANTS: ClassVar[dict[str, float | int]] = {}

    def __init__(self, allow_expressions: bool = True) -> None:
        self.allow_expressions = allow_expressions

    def parse(self, value: str) -> NumericType:
        """Parse a string into a numeric value. To be implemented by subclasses."""
        raise NotImplementedError

    def _basic_parse(self, value: str) -> NumericType | None:
        value = self.clean(value)

        if isinstance(value, str) and value in self.CONSTANTS:
            return self.CONSTANTS[value]  # type: ignore[return-value]

        try:
            return self._convert_value(value)
        except ValueError:
            pass

        return None

    def _convert_value(self, value: str) -> NumericType:
        """Convert value to the appropriate numeric type. To be implemented by subclasses."""
        raise NotImplementedError

    def _eval_node(self, node: ast.expr) -> NumericType:
        """Safely evaluate an AST node with limited operations."""
        match node:
            case ast.Constant():
                if isinstance(node.value, (int, float)):
                    return self._convert_constant(node.value)
                elif isinstance(node.value, str):
                    if node.value in self.CONSTANTS:
                        return self.CONSTANTS[node.value]  # type: ignore[return-value]
                    else:
                        raise TypeError(f"unsupported constant: '{node.value}'")
                else:
                    raise TypeError(f"unsupported constant type: {type(node.value)}")
            case ast.Name():
                if node.id in self.CONSTANTS:
                    return self.CONSTANTS[node.id]  # type: ignore[return-value]
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
                        return +operand  # type: ignore[return-value]
                    case ast.USub():
                        return -operand  # type: ignore[return-value]
                    case _:
                        raise TypeError(f"unsupported unary operator: {type(node.op)}")
            case _:
                raise TypeError(f"unsupported node type: {type(node)}")

    def _convert_constant(self, value: float | int) -> NumericType:
        """Convert a constant value. To be implemented by subclasses."""
        raise NotImplementedError

    def _eval_binop(self, op: ast.operator, left: NumericType, right: NumericType) -> NumericType:
        """Evaluate a binary operation. To be implemented by subclasses."""
        raise NotImplementedError


class IntParser(NumberParser[int]):
    CONSTANTS: ClassVar[dict[str, int]] = {}

    def _basic_parse(self, value: str) -> int | None:
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

    def _convert_value(self, value: str) -> int:
        return int(value)

    def _convert_constant(self, value: float | int) -> int:
        return int(value)

    def _convert_result(self, result: float | int) -> int:
        if isinstance(result, (int, float)):
            return int(result)
        else:
            raise TypeError("expression does not evaluate to a number")

    def _eval_binop(self, op: ast.operator, left: int, right: int) -> int:
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


class FloatParser(NumberParser[float]):
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

    def _convert_value(self, value: str) -> float:
        return float(value)

    def _convert_constant(self, value: float | int) -> float:
        return float(value)

    def _convert_result(self, result: float | int) -> float:
        if isinstance(result, (int, float)):
            return float(result)
        else:
            raise TypeError("expression does not evaluate to a number")

    def _eval_binop(self, op: ast.operator, left: float | int, right: float | int) -> float:
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


class BoolParser(ParserBase[bool]):
    def __init__(
        self,
        true_synonyms: set[str] | None = None,
        false_synonyms: set[str] | None = None,
        case_sensitive: bool = False,
    ) -> None:
        self._true_synonyms = true_synonyms or {"1", "true", "yes", "y", "on"}
        self._false_synonyms = false_synonyms or {"0", "false", "no", "n", "off"}
        self._case_sensitive = case_sensitive
        if case_sensitive:
            self._true_synonyms = {s.lower() for s in self._true_synonyms}
            self._false_synonyms = {s.lower() for s in self._false_synonyms}

    def parse(self, value: str | int | bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            key = value if self._case_sensitive else value.lower()
            if key in self._true_synonyms:
                return True
            if key in self._false_synonyms:
                return False
            valid_choices = sorted(self._true_synonyms | self._false_synonyms)
            raise ValueError(
                fmt_parser_err(
                    value,
                    bool,
                    "valid choices: " + ", ".join(repr(c) for c in valid_choices),
                )
            )
        raise TypeError(fmt_parser_err(value, bool, "expected bool, int, or str"))


class LiteralParser(ParserBase[ParseResultType]):
    def __init__(
        self,
        choices: tuple[ParseResultType, ...],
        *,
        target_t: Any = None,
    ) -> None:
        self._choices: list[ParseResultType] = list(choices)
        self._target_t = target_t

    def parse(self, value: Any) -> ParseResultType:
        target = self._target_t or "Literal"
        choices = self._choices

        if not choices:
            raise ValueError(fmt_parser_err(value, target, "no valid Literal choices"))

        if value in choices:
            return value

        present_types = {type(j) for j in choices}
        for t in (int, str, bytes, bool):
            if t not in present_types:
                continue
            try:
                if t is bool:
                    parsed = value.lower() == "true" if isinstance(value, str) else bool(value)
                else:
                    parsed = t(value)
                if parsed in choices:
                    return parsed  # type: ignore[return-value]
            except Exception:
                continue

        raise ValueError(fmt_parser_err(value, target, f"valid choices: {choices}"))


__all__ = [
    "Cast",
    "Parser",
    "ParserBase",
    "DateParser",
    "DatetimeParser",
    "TimeParser",
    "TimedeltaParser",
    "FloatParser",
    "IntParser",
    "IterableParser",
    "MappingParser",
    "RangeParser",
    "SliceParser",
    "BoolParser",
    "LiteralParser",
]
