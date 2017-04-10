"""
This module contains the views for the JASMIN Cloud API.
"""

import functools

from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.encoding import smart_text
from django.contrib.auth import login

from docutils import core

from rest_framework.utils import formatting
from rest_framework import (
    compat, decorators, permissions, response, status,
    exceptions as drf_exceptions, views as drf_views
)

from . import serializers
from .provider import errors as provider_errors


def get_view_description(view_cls, html = False):
    """
    Alternative django-rest-framework ``VIEW_DESCRIPTION_FUNCTION`` that allows
    RestructuredText to be used instead of Markdown.

    This allows docstrings to be used in the DRF-generated HTML views and in
    Sphinx-generated API views.
    """
    description = view_cls.__doc__ or ''
    description = formatting.dedent(smart_text(description))
    if html:
        # from https://wiki.python.org/moin/ReStructuredText -- we use the
        # third recipe to get just the HTML parts corresponding to the ReST
        # docstring:
        parts = core.publish_parts(source=description, writer_name='html')
        html = parts['body_pre_docinfo'] + parts['fragment']
        # have to use mark_safe so our HTML will get explicitly marked as
        # safe and will be correctly rendered
        return mark_safe(html)
    return description


def exception_handler(exc, context):
    """
    Exception handler that converts errors from :py:mod:`.provider.errors` into
    appropriate HTTP responses.
    """
    if isinstance(exc, provider_errors.UnsupportedOperationError):
        return response.Response(
            { 'detail' : str(exc), 'code' : 'unsupported_operation'},
            status = status.HTTP_501_NOT_IMPLEMENTED
        )
    if isinstance(exc, provider_errors.QuotaExceededError):
        return response.Response(
            { 'detail' : str(exc), 'code' : 'quota_exceeded'},
            status = status.HTTP_409_CONFLICT
        )
    if isinstance(exc, provider_errors.InvalidOperationError):
        return response.Response(
            { 'detail' : str(exc), 'code' : 'invalid_operation'},
            status = status.HTTP_409_CONFLICT
        )
    if isinstance(exc, provider_errors.BadInputError):
        return response.Response(
            { 'detail' : str(exc), 'code' : 'bad_input'},
            status = status.HTTP_400_BAD_REQUEST
        )
    # If we get this far, we are going to defer to the DRF exception handler
    # For provider errors that have a direct correlation with DRF exceptions,
    # convert them before deferring to DRF
    if isinstance(exc, provider_errors.AuthenticationError):
        exc = drf_exceptions.AuthenticationFailed(str(exc))
    elif isinstance(exc, provider_errors.PermissionDeniedError):
        exc = drf_exceptions.PermissionDenied(str(exc))
    elif isinstance(exc, provider_errors.ObjectNotFoundError):
        exc = drf_exceptions.NotFound(str(exc))
    return drf_views.exception_handler(exc, context)


@decorators.api_view(['POST'])
def authenticate(request):
    """
    This view attempts to authenticate the user using the given username and
    password. If authentication is successful, a session is started for the user.

    Example request payload::

        {
            "username" : "jbloggs",
            "password" : "mysecurepassword"
        }
    """
    serializer = serializers.LoginSerializer(data = request.data)
    serializer.is_valid(raise_exception = True)
    login(request, serializer.validated_data['user'])
    # Just return a 200 OK response
    return response.Response()


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
def tenancies(request):
    """
    Returns the tenancies available to the authenticated user.
    """
    session = request.user.cloudsession.session
    serializer = serializers.TenancySerializer(
        session.tenancies(),
        many = True,
        context = { 'request' : request }
    )
    return response.Response(serializer.data)


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
def quotas(request, tenant):
    """
    Returns information about the quotas available to the tenant.
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    return response.Response({
        k : serializers.QuotaSerializer(v).data for k, v in session.quotas().items()
    })


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
def images(request, tenant):
    """
    Returns the images available to the specified tenancy.

    The image attributes are:

    * ``id``: The id of the image.
    * ``name``: The human-readable name of the image.
    * ``is_public``: Indicates if the image is public or private.
    * ``nat_allowed``: Indicates if NAT is allowed for machines deployed from the image.
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    serializer = serializers.ImageSerializer(
        session.images(),
        many = True,
        context = { 'request' : request, 'tenant' : tenant }
    )
    return response.Response(serializer.data)


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
def image_details(request, tenant, image):
    """
    Returns the details for the specified image.

    The image attributes are:

    * ``id``: The id of the image.
    * ``name``: The human-readable name of the image.
    * ``is_public``: Indicates if the image is public or private.
    * ``nat_allowed``: Indicates if NAT is allowed for machines deployed from the image.
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    serializer = serializers.ImageSerializer(
        session.find_image(image),
        context = { 'request' : request, 'tenant' : tenant }
    )
    return response.Response(serializer.data)


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
def sizes(request, tenant):
    """
    Returns the machine sizes available to the specified tenancy.

    The size attributes are:

    * ``id``: The id of the size.
    * ``name``: The human-readable name of the size.
    * ``cpus``: The number of CPUs.
    * ``ram``: The amount of RAM (in MB).
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    serializer = serializers.SizeSerializer(
        session.sizes(),
        many = True,
        context = { 'request' : request, 'tenant' : tenant }
    )
    return response.Response(serializer.data)


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
def size_details(request, tenant, size):
    """
    Returns the details for the specified machine size.

    The size attributes are:

    * ``id``: The id of the size.
    * ``name``: The human-readable name of the size.
    * ``cpus``: The number of CPUs.
    * ``ram``: The amount of RAM (in MB).
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    serializer = serializers.SizeSerializer(
        session.find_size(size),
        context = { 'request' : request, 'tenant' : tenant }
    )
    return response.Response(serializer.data)


@decorators.api_view(['GET', 'POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
def machines(request, tenant):
    """
    On ``GET`` requests, return the machines deployed in the specified tenancy.

    On ``POST`` requests, create a new machine. The request body should look like::

        {
            "name" : "test-machine",
            "image_id" : "<uuid of image>",
            "size_id" : "<id of size>"
        }
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    if request.method == 'POST':
        input_serializer = serializers.MachineSerializer(data = request.data)
        input_serializer.is_valid(raise_exception = True)
        machine = session.create_machine(
            input_serializer.validated_data['name'],
            input_serializer.validated_data['image_id'],
            input_serializer.validated_data['size_id']
        )
        # REST semantics say the response should be a 201 Created with a Location
        # header pointing to the resource
        location = request.build_absolute_uri(
            reverse('jasmin_cloud:machine_details', kwargs = {
                'tenant' : tenant,
                'machine' : machine.id
            })
        )
        return response.Response(
            status = status.HTTP_201_CREATED,
            headers = { 'Location' : location }
        )
    else:
        serializer = serializers.MachineSerializer(
            session.machines(),
            many = True,
            context = { 'request' : request, 'tenant' : tenant }
        )
        return response.Response(serializer.data)


@decorators.api_view(['GET', 'DELETE'])
@decorators.permission_classes([permissions.IsAuthenticated])
def machine_details(request, tenant, machine):
    """
    On ``GET`` requests, return the details for the specified machine.

    On ``DELETE`` requests, delete the specified machine.
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    if request.method == 'DELETE':
        session.delete_machine(machine)
        return response.Response()
    else:
        serializer = serializers.MachineSerializer(
            session.find_machine(machine),
            context = { 'request' : request, 'tenant' : tenant }
        )
        return response.Response(serializer.data)


@decorators.api_view(['POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
def machine_start(request, tenant, machine):
    """
    Start (power on) the specified machine.
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    session.start_machine(machine)
    return response.Response()


@decorators.api_view(['POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
def machine_stop(request, tenant, machine):
    """
    Stop (power off) the specified machine.
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    session.stop_machine(machine)
    return response.Response()


@decorators.api_view(['POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
def machine_restart(request, tenant, machine):
    """
    Restart (power cycle) the specified machine.
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    session.restart_machine(machine)
    return response.Response()


@decorators.api_view(['GET', 'POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
def external_ips(request, tenant):
    """
    On ``GET`` requests, return a list of external IP addresses that are
    allocated to the tenancy.

    On ``POST`` requests, allocate a new external IP address for the tenancy from
    a pool. This functionality is not available for all providers. The request
    body is ignored. The returned response will be the allocated IP::

        {
            "external_ip" : "172.28.128.4",
            "internal_ip" : null
        }
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    if request.method == 'POST':
        serializer = serializers.ExternalIPSerializer(session.allocate_external_ip())
        return response.Response(serializer.data, status = status.HTTP_201_CREATED)
    else:
        serializer = serializers.ExternalIPSerializer(
            session.external_ips(),
            many = True
        )
        return response.Response(serializer.data)


@decorators.api_view(['POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
def machine_attach_external_ip(request, tenant, machine):
    """
    Attaches the given external IP to the specified machine.

    The request body should look like::

        { "external_ip" : "172.28.128.3" }

    where ``external_ip`` should be one of the available IPs returned by
    ``/tenancies/<tenant>/external_ips/``.
    """
    serializer = serializers.ExternalIPSerializer(data = request.data)
    serializer.is_valid(raise_exception = True)
    session = request.user.cloudsession.session.scoped_session(tenant)
    session.attach_external_ip(machine, serializer.validated_data['external_ip'])
    return response.Response()


@decorators.api_view(['POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
def machine_detach_external_ips(request, tenant, machine):
    """
    Detaches all external IPs from the specified machine.

    The request body should be empty.
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    session.detach_external_ips(machine)
    return response.Response()


@decorators.api_view(['GET', 'POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
def machine_volumes(request, tenant, machine):
    """
    On ``GET`` requests, return a list of the volumes attached to the specified
    machine.

    On ``POST`` requests, attach a new volume to the machine. The request body
    should contain the size of the volume to attach in GB::

        { "size" : 20 }
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    if request.method == 'POST':
        input_serializer = serializers.VolumeSerializer(data = request.data)
        input_serializer.is_valid(raise_exception = True)
        volume = session.attach_volume(
            machine, input_serializer.validated_data['size']
        )
        # REST semantics say the response should be a 201 Created with a Location
        # header pointing to the resource
        location = request.build_absolute_uri(
            reverse('jasmin_cloud:machine_volume_details', kwargs = {
                'tenant' : tenant,
                'machine' : machine,
                'volume' : volume.id,
            })
        )
        return response.Response(
            status = status.HTTP_201_CREATED,
            headers = { 'Location' : location }
        )
    else:
        serializer = serializers.VolumeSerializer(
            session.volumes(machine),
            many = True,
            context = { 'request' : request, 'tenant' : tenant, 'machine' : machine }
        )
        return response.Response(serializer.data)


@decorators.api_view(['GET', 'DELETE'])
@decorators.permission_classes([permissions.IsAuthenticated])
def machine_volume_details(request, tenant, machine, volume):
    """
    On ``GET`` requests, return the details for the specified volume.

    On ``DELETE`` requests, delete the specified volume.
    """
    session = request.user.cloudsession.session.scoped_session(tenant)
    if request.method == 'DELETE':
        session.detach_volume(machine, volume)
        return response.Response()
    else:
        serializer = serializers.VolumeSerializer(
            session.find_volume(machine, volume),
            context = { 'request' : request, 'tenant' : tenant, 'machine' : machine }
        )
        return response.Response(serializer.data)
