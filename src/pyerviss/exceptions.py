"""Custom exceptions for PyERVISS."""


class PyERVISSError(Exception):
    """Base exception for PyERVISS."""

    pass


class DataNotFoundError(PyERVISSError):
    """Raised when requested data is not available."""

    pass


class DataFetchError(PyERVISSError):
    """Raised when data fetching from remote source fails."""

    pass


class InvalidParameterError(PyERVISSError):
    """Raised when invalid parameters are provided."""

    pass


class CacheError(PyERVISSError):
    """Raised when cache operations fail."""

    pass
