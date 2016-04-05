"""
This module provides functionality for persisting and retrieving cloud sessions
across multiple requests.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import logging

from .cloudservices import CloudServiceError


_log = logging.getLogger(__name__)


def includeme(config):
    """
    Configures the Pyramid application for persisting and retrieving cloud sessions.

    :param config: Pyramid configurator
    """
    config.add_request_method(cloud_sessions, reify = True)
    config.add_request_method(active_cloud_session, reify = True)


_SESSION_KEY = 'cloud'
def cloud_sessions(request):
    """
    Returns the dictionary of cloud sessions for the request.

    .. note::

        This function should be accessed as a property of the Pyramid request object,
        i.e. ``sessions = request.cloud_sessions``.

        This property is reified, so it is only evaluated once per request.
    """
    if _SESSION_KEY not in request.session:
        request.session[_SESSION_KEY] = {}
    return CloudSessionManager(request.session[_SESSION_KEY])


def active_cloud_session(request):
    """
    Returns the cloud session for the current org, or raises an error if there is not one.

    .. note::

        This function should be accessed as a property of the Pyramid request object,
        i.e. ``sessions = request.active_cloud_session``.

        This property is reified, so it is only evaluated once per request.
    """
    return request.cloud_sessions.get_session(request.current_org)


class CloudSessionManager:
    """
    Manages the available cloud sessions.
    """
    def __init__(self, sessions):
        self.sessions = sessions

    def has_sessions_for(self):
        """
        Returns the orgs for which the cloud session manager has a session.
        """
        return self.sessions.keys()

    def start_session(self, org, provider, *args, **kwargs):
        """
        Starts a session using the given provider, catching any cloud service errors
        and storing them for later.
        """
        try:
            self.sessions[org] = provider(*args, **kwargs)
        except CloudServiceError as e:
            self.sessions[org] = e
            _log.exception('Error opening session for {}'.format(org))

    def get_session(self, org):
        """
        If there is a session available for the org, return it.

        If there was a problem opening the session, raise the exception that was
        stored when the session was opened.

        If there is no session for the org, raise a key error.
        """
        session = self.sessions[org]
        if isinstance(session, CloudServiceError):
            raise session
        return session

    def clear(self):
        """
        Clears all the session information.
        """
        self.sessions.clear()
