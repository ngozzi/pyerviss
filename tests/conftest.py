"""Pytest configuration and fixtures."""

import pytest

from pyerviss import data_loader
from pyerviss.cache import CACHE_DIR_ENV


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Give every test an empty cache directory and no parsed-file memory."""
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv(CACHE_DIR_ENV, str(cache_dir))
    monkeypatch.delenv(data_loader.DATA_URL_ENV, raising=False)
    data_loader._frames.clear()
    yield cache_dir
    data_loader._frames.clear()
