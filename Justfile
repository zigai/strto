@_:
    just --list

lint:
    ruff check

fix:
    ruff check --fix

format:
    ruff format

test:
    hatch run test:test

clean:
    rm -rf .venv .pytest_cache .mypy_cache .ruff_cache
    find . -type d -name "__pycache__" -exec rm -r {} +
