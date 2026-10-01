# API reference

All public functions are available from the top-level package:

```python
import pyerviss as pv
```

## Querying

```{eval-rst}
.. autofunction:: pyerviss.get_ili
.. autofunction:: pyerviss.get_ari
.. autofunction:: pyerviss.get_sari
.. autofunction:: pyerviss.get_data
```

## Discovering data

```{eval-rst}
.. autofunction:: pyerviss.coverage
.. autofunction:: pyerviss.list_countries
.. autofunction:: pyerviss.list_seasons
.. autofunction:: pyerviss.latest_week
```

## Cache

```{eval-rst}
.. autofunction:: pyerviss.update_data
.. autofunction:: pyerviss.clear_cache
```

## Exceptions

All exceptions derive from {class}`~pyerviss.exceptions.PyERVISSError`.

```{eval-rst}
.. automodule:: pyerviss.exceptions
   :members:
   :show-inheritance:
```

## Lower level

These are not needed for normal use.

```{eval-rst}
.. autofunction:: pyerviss.data_loader.get_metadata
.. autofunction:: pyerviss.data_loader.load_csv
.. autofunction:: pyerviss.data_loader.fetch_file
.. autofunction:: pyerviss.cache.get_cache_dir
```

### Weeks and seasons

```{eval-rst}
.. automodule:: pyerviss.utils
   :members:
```
