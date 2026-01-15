# strto

[![Tests](https://github.com/zigai/strto/actions/workflows/tests.yml/badge.svg)](https://github.com/zigai/strto/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/strto.svg)](https://badge.fury.io/py/strto)
![Supported versions](https://img.shields.io/badge/python-3.10+-blue.svg)
[![Downloads](https://static.pepy.tech/badge/strto)](https://pepy.tech/project/strto)
[![license](https://img.shields.io/github/license/zigai/strto.svg)](https://github.com/zigai/strto/blob/master/LICENSE)

`strto` is a Python library for parsing strings into Python objects based on types and type annotations.

## Installation

#### From PyPi

```sh
pip install strto
```

#### From source

```sh
pip install git+https://github.com/zigai/strto.git
```

## Examples

```python
>>> from strto import get_parser
>>> parser = get_parser()

>>> parser.parse("5", int)
5
>>> parser.parse("1.5", int | float)
1.5
>>> parser.parse("1,2,3,4,5", list[int])
[1, 2, 3, 4, 5]
>>> parser.parse('{"a":1,"b":2,"c":3}', dict[str, int])
{'a': 1, 'b': 2, 'c': 3}

import datetime
>>> parser.parse("2022.07.19", datetime.date)
datetime.date(2022, 7, 19)

>>> parser.parse("0:5:1", range)
range(0, 5, 1)

>>> import enum
>>> class Color(enum.Enum):
...     RED = 1
...     GREEN = 2
...     BLUE = 3
>>> parser.parse("RED", Color)
Color.RED

```

### Automatic model parsing (dataclasses and pydantic v2)

`strto` can parse dataclasses and pydantic v2 models from JSON, files, or key/value strings:

```python
from dataclasses import dataclass
from strto import get_parser

@dataclass
class NetworkAddress:
    host: str
    port: int

parser = get_parser()

parser.parse('{"host":"localhost","port":5432}', NetworkAddress)
parser.parse("host=localhost port=5432", NetworkAddress)
parser.parse("@addr.yaml", NetworkAddress)
```

Nested models via dotted keys (or nested JSON):

```python
from dataclasses import dataclass

@dataclass
class NetworkAddress:
    host: str
    port: int

@dataclass
class ApplicationConfig:
    debug: bool = False
    network: NetworkAddress | None = None

parser.parse(
    "debug=true network.host=db network.port=5433",
    ApplicationConfig,
)
```

Notes:

- Key/value parsing supports dotted keys for nested objects.
- Use JSON arrays/objects for complex values (e.g., lists of objects).
- Pydantic support requires pydantic v2 to be installed.

Optional: enable parsing for any class by inspecting `__init__` with `objinspect`:

```python
from strto import get_parser

parser = get_parser(allow_class_init=True)
```

### Custom parser for alternative string formats

If you want a non-standard string format (e.g., `host:port`), register a custom parser
to override the default model parsing for that type.

```python
from dataclasses import dataclass
from strto import ParserBase, get_parser

@dataclass
class NetworkAddress:
    host: str
    port: int

class NetworkAddressParser(ParserBase):
    def parse(self, value: str) -> NetworkAddress:
        host, port = value.rsplit(":")
        return NetworkAddress(host=host, port=int(port))

parser = get_parser()
parser.add(NetworkAddress, NetworkAddressParser())
result = parser.parse("example.com:8080", NetworkAddress)
print(result)  # NetworkAddress(host='example.com', port=8080)

# You can also use a function
def parse_network_address(value: str) -> NetworkAddress:
    host, port = value.rsplit(":")
    return NetworkAddress(host=host, port=int(port))

parser = get_parser()
parser.add(NetworkAddress, parse_network_address)
result = parser.parse("example.com:8080", NetworkAddress)
print(result)  # NetworkAddress(host='example.com', port=8080)

```

## License

[MIT License](https://github.com/zigai/strto/blob/master/LICENSE)
