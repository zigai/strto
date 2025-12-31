import sys

import pytest

from strto import StrToTypeParser, get_parser

collect_ignore: list[str] = []
if sys.version_info < (3, 12):
    collect_ignore.append("test_type_alias.py")


@pytest.fixture()
def parser() -> StrToTypeParser:
    return get_parser(from_file=True)
