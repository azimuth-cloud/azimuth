from gunicorn.glogging import Logger as GLogger
from gunicorn.instrument.statsd import Statsd

from django.urls import reverse


class StatusEndpointFilterMixin:
    """
    Mixin for logger classes that allows for the filtering of the status endpoint.
    """
    def access(self, resp, req, environ, request_time):
        # If the request path starts with the status path, ignore it
        if not req.path.startswith(reverse("status")):
            super().access(resp, req, environ, request_time)


class Logger(StatusEndpointFilterMixin, GLogger):
    """
    Custom logger that allows for the filtering of the status endpoint.
    """


class StatsdLogger(StatusEndpointFilterMixin, Statsd):
    """
    Custom statsd-enabled logger that allows for the filtering of the status endpoint.
    """
