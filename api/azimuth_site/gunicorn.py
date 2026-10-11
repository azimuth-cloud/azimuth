import http

from django.urls import reverse
from gunicorn.glogging import Logger as GLogger
from gunicorn.instrument.statsd import Statsd


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

    def __init__(self, cfg):
        super().__init__(cfg)

        # Initialise as many counters as possible to zero
        # https://www.section.io/blog/beware-prometheus-counters-that-do-not-begin-at-zero/
        self.increment("gunicorn.log.critical", 0)
        self.increment("gunicorn.log.error", 0)
        self.increment("gunicorn.log.warning", 0)
        self.increment("gunicorn.log.exception", 0)
        self.increment("gunicorn.requests", 0)
        for status in http.HTTPStatus:
            # Ignore the 1xx statuses as we will never serve them
            if status.value >= 200:
                self.increment(f"gunicorn.request.status.{status.value}", 0)
