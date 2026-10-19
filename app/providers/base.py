class RouteProviderError(Exception):
    """Base class for route provider failures that are safe to show to the user."""

    status_code = 502


class ProviderNotConfiguredError(RouteProviderError):
    status_code = 400


class ProviderRequestError(RouteProviderError):
    status_code = 400
