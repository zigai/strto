@_:
    just --list

_require-uv:
    @uv --version > /dev/null || (echo "Please install uv: https://docs.astral.sh/uv/" && exit 1)

_require-hatch:
   @hatch --version > /dev/null || (echo "Please install hatch: uv tool install hatch" && exit 1)

lint:
    ruff check

fix:
    ruff check --fix

format:
    ruff format

test: _require-hatch
    hatch run test:test

check: format lint test

build: _require-uv
    uv build

dev: _require-uv
    uv sync --extra dev
    uv run pre-commit install

clean:
    rm -rf .venv .pytest_cache .mypy_cache .ruff_cache
    find . -type d -name "__pycache__" -exec rm -r {} +
