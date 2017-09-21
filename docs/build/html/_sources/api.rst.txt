The JASMIN Cloud API
====================

The JASMIN Cloud API is built using the
`Django REST framework <http://www.django-rest-framework.org/>`_.

The API is intended to be largely self-documenting. As well as accepting requests
and returning responses in JSON format, the API is hyperlinked and provides
browsable HTML endpoints with documentation, allowing developers to navigate
the API, make their own requests and view the responses in the browser.

All API endpoints other than ``authenticate`` require authentication, and all
tenancy endpoints require the authenticated user to belong to the requested
tenancy. To begin browsing the API, submit a valid JASMIN username and password
that belongs to at least one tenancy using the
`authenticate endpoint <https://jasmin-ref-portal01.jc.rl.ac.uk/api/session/>`_.

Currently, the only authentication mechanism supported by the JASMIN Cloud API is
session cookies. This means that any HTTP client you use to access the API must
be able to preserve and submit cookies (e.g. a
`requests Session <http://docs.python-requests.org/en/master/user/advanced/#session-objects>`_).

All ``POST`` and ``PUT`` requests should provide data as JSON, with the
``Content-Type`` header set to ``application/json``, rather than form-encoded.
``POST``, ``PUT`` and ``DELETE`` requests must also pass a CSRF token, which is
provided as a cookie. The
`Django documentation <https://docs.djangoproject.com/en/1.11/ref/csrf/#ajax>`_
provides a good example of how to consume it.

For an example of an application consuming the JASMIN Cloud API see the
`JASMIN Cloud Portal <https://github.com/cedadev/jasmin-cloud-ui>`_, a
Javascript-based web user interface for the JASMIN Cloud.
