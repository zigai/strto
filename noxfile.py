import re
import sys
from pathlib import Path

import nox

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def get_python_versions() -> list[str]:
    with open(Path("pyproject.toml"), "rb") as f:
        data = tomllib.load(f)

    classifiers = data.get("project", {}).get("classifiers", [])
    versions = []

    for classifier in classifiers:
        if classifier.startswith("Programming Language :: Python :: 3."):
            match = re.search(r"3\.\d+", classifier)
            if match:
                versions.append(match.group())
    return sorted(versions)


PYTHON_VERSIONS = get_python_versions()
nox.options.default_venv_backend = "uv|virtualenv"

@nox.session(python=PYTHON_VERSIONS)
def tests(session):
    """Run tests with pytest for all supported Python versions."""
    session.install(".[test]")
    session.run("pytest", "-v")
