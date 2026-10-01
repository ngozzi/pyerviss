"""Sphinx configuration for the pyerviss documentation."""

from importlib.metadata import version as package_version

project = "pyerviss"
author = "Nicolo Gozzi"
copyright = "2026, Nicolo Gozzi"
release = package_version("pyerviss")
version = ".".join(release.split(".")[:2])

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
]

source_suffix = {".md": "markdown"}
exclude_patterns = ["_build"]

# MyST: allow ::: fences for admonitions and generate anchors for headings
myst_enable_extensions = ["colon_fence"]
myst_heading_anchors = 3

autodoc_member_order = "bysource"
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pandas": ("https://pandas.pydata.org/docs", None),
}

html_theme = "furo"
html_title = f"pyerviss {release}"
html_theme_options = {
    "source_repository": "https://github.com/ngozzi/pyerviss",
    "source_branch": "main",
    "source_directory": "docs/",
}
