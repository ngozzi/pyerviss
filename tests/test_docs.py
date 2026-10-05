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


NOTEBOOKS = Path(__file__).parent.parent / "notebooks"


def test_notebooks_are_valid_and_link_to_themselves_on_colab():
    import json

    notebooks = sorted(NOTEBOOKS.glob("*.ipynb"))
    assert notebooks
    for path in notebooks:
        nb = json.loads(path.read_text())
        assert nb["nbformat"] == 4
        colab = f"colab.research.google.com/github/ngozzi/pyerviss/blob/main/notebooks/{path.name}"
        assert colab in "".join(nb["cells"][0]["source"]), f"{path.name}: Colab badge link"
        errors = [
            output
            for cell in nb["cells"]
            if cell["cell_type"] == "code"
            for output in cell.get("outputs", [])
            if output["output_type"] == "error"
        ]
        assert not errors, f"{path.name} was saved with errors in its outputs"
