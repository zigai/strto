import pytest

from strto import StrToTypeParser, get_parser


@pytest.fixture()
def parser() -> StrToTypeParser:
    return get_parser(from_file=True)
