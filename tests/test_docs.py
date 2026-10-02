"""Checks that keep the documentation and metadata in step with the code."""

import re
from pathlib import Path

import pyerviss

API_PAGE = Path(__file__).parent.parent / "docs" / "api.md"


def test_every_public_function_is_in_the_api_reference():
    documented = set(
        re.findall(r"\.\. autofunction:: pyerviss\.(\w+)$", API_PAGE.read_text(), re.M)
    )
    public = {name for name in pyerviss.__all__ if not name.startswith("__")}
    missing = sorted(public - documented)
    assert not missing, f"Add to docs/api.md: {', '.join(f'pyerviss.{n}' for n in missing)}"


def test_version_comes_from_pyproject():
    pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text()
    declared = re.search(r'^version = "([^"]+)"$', pyproject, re.M)
    assert declared is not None
    assert pyerviss.__version__ == declared[1]
