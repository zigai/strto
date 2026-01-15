from __future__ import annotations

from dataclasses import dataclass, field
import pathlib

import pytest

from strto import get_parser


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    username: str | None = None
    password: str | None = None


@dataclass
class ApplicationConfig:
    debug: bool = False
    log_level: str = "INFO"
    database: DatabaseConfig | None = None
    allowed_hosts: list[str] = field(default_factory=list)


def test_dataclass_json() -> None:
    parser = get_parser()
    config = parser.parse(
        '{"host":"db","port":5433,"username":"u","password":"p"}',
        DatabaseConfig,
    )
    assert config == DatabaseConfig(host="db", port=5433, username="u", password="p")


def test_dataclass_kv() -> None:
    parser = get_parser()
    config = parser.parse("host=db port=5433 username=u password=p", DatabaseConfig)
    assert config == DatabaseConfig(host="db", port=5433, username="u", password="p")


def test_dataclass_nested_kv() -> None:
    parser = get_parser()
    config = parser.parse(
        "debug=true log_level=WARNING database.host=db database.port=5433 "
        "allowed_hosts=example.com,localhost",
        ApplicationConfig,
    )
    assert config.debug is True
    assert config.log_level == "WARNING"
    assert config.database == DatabaseConfig(host="db", port=5433)
    assert config.allowed_hosts == ["example.com", "localhost"]


def test_dataclass_list_json() -> None:
    parser = get_parser()
    result = parser.parse(
        '[{"host":"a","port":1},{"host":"b","port":2}]',
        list[DatabaseConfig],
    )
    assert result == [DatabaseConfig(host="a", port=1), DatabaseConfig(host="b", port=2)]


def test_dataclass_file(tmp_path: pathlib.Path) -> None:
    parser = get_parser()
    path = tmp_path / "db.json"
    path.write_text('{"host":"file","port":6000}')
    config = parser.parse(f"@{path}", DatabaseConfig)
    assert config == DatabaseConfig(host="file", port=6000)


def test_pydantic_v2_json() -> None:
    pydantic = pytest.importorskip("pydantic")
    if not hasattr(pydantic.BaseModel, "model_validate"):
        pytest.skip("pydantic v2 required")

    class PDatabase(pydantic.BaseModel):
        host: str = "localhost"
        port: int = 5432
        username: str | None = None
        password: str | None = None

    parser = get_parser()
    config = parser.parse('{"host":"db","port":5433}', PDatabase)
    assert config.host == "db"
    assert config.port == 5433


def test_pydantic_v2_nested_kv() -> None:
    pydantic = pytest.importorskip("pydantic")
    if not hasattr(pydantic.BaseModel, "model_validate"):
        pytest.skip("pydantic v2 required")

    class PDatabase(pydantic.BaseModel):
        host: str = "localhost"
        port: int = 5432

    class PApplication(pydantic.BaseModel):
        debug: bool = False
        database: PDatabase
        allowed_hosts: list[str] = []

    parser = get_parser()
    config = parser.parse(
        "debug=true database.host=db database.port=5433 allowed_hosts=example.com,localhost",
        PApplication,
    )
    assert config.debug is True
    assert config.database.host == "db"
    assert config.database.port == 5433
    assert config.allowed_hosts == ["example.com", "localhost"]


def test_pydantic_v2_extra_fields_ignored() -> None:
    pydantic = pytest.importorskip("pydantic")
    if not hasattr(pydantic.BaseModel, "model_validate"):
        pytest.skip("pydantic v2 required")

    class PConfig(pydantic.BaseModel):
        model_config = pydantic.ConfigDict(extra="ignore")
        host: str
        port: int

    parser = get_parser()
    config = parser.parse('{"host":"db","port":5432,"extra":"ignored"}', PConfig)
    assert config.host == "db"
    assert config.port == 5432


def test_dataclass_bare_list_dict_json() -> None:
    @dataclass
    class PayloadConfig:
        payload: dict
        tags: list

    parser = get_parser()
    config = parser.parse('{"payload":{"a":1},"tags":["a","b"]}', PayloadConfig)
    assert config.payload == {"a": 1}
    assert config.tags == ["a", "b"]


class PlainConfig:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port


class PlainAppConfig:
    def __init__(self, debug: bool, database: PlainConfig) -> None:
        self.debug = debug
        self.database = database


def test_plain_class_parsing_disabled_by_default() -> None:
    parser = get_parser()
    with pytest.raises(TypeError):
        parser.parse("host=localhost port=5432", PlainConfig)


def test_plain_class_parsing_enabled() -> None:
    parser = get_parser(allow_class_init=True)
    config = parser.parse(
        "debug=true database.host=db database.port=5433",
        PlainAppConfig,
    )
    assert config.debug is True
    assert isinstance(config.database, PlainConfig)
    assert config.database.host == "db"
    assert config.database.port == 5433
