# Caching and offline use

The first query downloads the data files (a few MB) and stores them in a local cache.
After that:

- queries read from the cache and from memory, so they take a fraction of a second;
- each file is checked for updates **at most once an hour**, and only downloaded again if
  it changed;
- without a connection, the cached copy is used with a warning.

## Where the cache is

The cache uses your platform's user cache directory, for example:

| Platform | Location |
|---|---|
| Linux | `~/.cache/pyerviss` |
| macOS | `~/Library/Caches/pyerviss` |
| Windows | `C:\Users\<you>\AppData\Local\pyerviss\pyerviss\Cache` |

Set the `PYERVISS_CACHE_DIR` environment variable to use another directory.

## Updating and clearing

```python
import pyerviss as pv

pv.update_data()  # check for new data now, regardless of the hourly interval
pv.clear_cache()  # delete the cache; the next query downloads everything again
```

The mirror itself is updated once a day (see {doc}`data`), so checking more often than
that rarely finds anything new.

## Offline use

Once the data has been downloaded, queries work without a connection. If an update check
fails, pyerviss warns and uses the cached copy:

```text
UserWarning: Could not check https://raw.githubusercontent.com/ngozzi/pyerviss/main/data/ILIARIRates.csv for updates (...); using cached copy.
```

If there is no cached copy, the query raises {class}`~pyerviss.exceptions.DataFetchError`.

## Using another data location

Set `PYERVISS_DATA_URL` to download the data files from another location with the same
layout, for example an internal mirror:

```bash
export PYERVISS_DATA_URL=https://example.org/pyerviss-data/
```
