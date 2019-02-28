"""
Django views for interacting with the configured cloud provider.
"""

import logging, functools

from django.urls import reverse
from django.contrib.auth import authenticate as dj_authenticate, login, logout
from django.utils.safestring import mark_safe
from django.utils.encoding import smart_text
from django.core.exceptions import ImproperlyConfigured

from docutils import core

from rest_framework import (
    decorators, permissions, response, status, exceptions as drf_exceptions
)
from rest_framework.utils import formatting

from . import serializers
from .provider import base as provider_base, errors as provider_errors
from .settings import cloud_settings


log = logging.getLogger(__name__)


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
        # Get just the HTML parts corresponding to the docstring
        parts = core.publish_parts(source = description, writer_name = 'html')
        html = parts['body_pre_docinfo'] + parts['fragment']
        # Mark the output as safe for rendering as-is
        return mark_safe(html)
    return description


def convert_provider_exceptions(view):
    """
    Decorator that converts errors from :py:mod:`.provider.errors` into appropriate
    HTTP responses or Django REST framework errors.
    """
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        # For provider errors that don't map to authentication/not found errors,
        # return suitable responses
        except provider_errors.UnsupportedOperationError as exc:
            return response.Response(
                { 'detail': str(exc), 'code': 'unsupported_operation'},
                status = status.HTTP_501_NOT_IMPLEMENTED
            )
        except provider_errors.QuotaExceededError as exc:
            return response.Response(
                { 'detail': str(exc), 'code': 'quota_exceeded'},
                status = status.HTTP_409_CONFLICT
            )
        except provider_errors.InvalidOperationError as exc:
            return response.Response(
                { 'detail': str(exc), 'code': 'invalid_operation'},
                status = status.HTTP_409_CONFLICT
            )
        except provider_errors.BadInputError as exc:
            return response.Response(
                { 'detail': str(exc), 'code': 'bad_input'},
                status = status.HTTP_400_BAD_REQUEST
            )
        except provider_errors.OperationTimedOutError as exc:
            return response.Response(
                { 'detail': str(exc), 'code': 'operation_timed_out'},
                status = status.HTTP_504_GATEWAY_TIMEOUT
            )
        # For authentication/not found errors, raise the DRF equivalent
        except provider_errors.AuthenticationError as exc:
            raise drf_exceptions.AuthenticationFailed(str(exc))
        except provider_errors.PermissionDeniedError as exc:
            raise drf_exceptions.PermissionDenied(str(exc))
        except provider_errors.ObjectNotFoundError as exc:
            raise drf_exceptions.NotFound(str(exc))
        except provider_errors.Error as exc:
            log.exception('Unexpected provider error occurred')
            return response.Response(
                { 'detail': str(exc) },
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    return wrapper


def require_provider_session(view):
    """
    Decorator that converts credentials stored in the HTTP session into an
    :py:class:`.provider.base.UnscopedSession` for the configured provider.
    """
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        # If there is no provider session on the request, force a reauthentication
        session = getattr(request, 'auth', None)
        if session is None or not isinstance(session, provider_base.UnscopedSession):
            request.session.flush()
            raise drf_exceptions.NotAuthenticated
        return view(request, *args, **kwargs)
    return wrapper


@decorators.api_view(['POST'])
@convert_provider_exceptions
def authenticate(request):
    """
    This view attempts to authenticate the user using the given username and
    password. If authentication is successful, a session is started for the user.

    Example request payload::

        {
            "username": "jbloggs",
            "password": "mysecurepassword"
        }
    """
    serializer = serializers.LoginSerializer(data = request.data)
    serializer.is_valid(raise_exception = True)
    username = serializer.validated_data['username']
    password = serializer.validated_data['password']
    user = dj_authenticate(request, username = username, password = password)
    if user is None or not user.is_active:
        raise drf_exceptions.AuthenticationFailed('Invalid username or password.')
    # Find the token from the session
    # NOTE: The token will have been placed there in the dj_authenticate call by the
    #       provider backend - we are not relying on a persistent session
    try:
        token = request.session['provider_token']
    except KeyError:
        raise ImproperlyConfigured('Please configure the provider backend.')
    login(request, user)
    return response.Response({
        'username': user.username,
        'token': token,
        'links': {
            'tenancies': request.build_absolute_uri(reverse('jasmin_cloud:tenancies'))
        }
    })


@decorators.api_view(['GET', 'DELETE'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def session(request):
    """
    On ``GET`` requests, return information about the current session.

    On ``DELETE`` requests, destroy the current session.
    """
    if request.method == 'DELETE':
        logout(request)
        return response.Response()
    else:
        return response.Response({
            'username': request.user.username,
            'token': request.auth.token(),
            'links': {
                'tenancies': request.build_absolute_uri(reverse('jasmin_cloud:tenancies'))
            }
        })


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def tenancies(request):
    """
    Returns the tenancies available to the authenticated user.
    """
    serializer = serializers.TenancySerializer(
        request.auth.tenancies(),
        many = True,
        context = { 'request': request }
    )
    return response.Response(serializer.data)


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def quotas(request, tenant):
    """
    Returns information about the quotas available to the tenant.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.QuotaSerializer(
            session.quotas(),
            many = True,
            context = { 'request': request, 'tenant': tenant }
        )
    return response.Response(serializer.data)


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def images(request, tenant):
    """
    Returns the images available to the specified tenancy.

    The image attributes are:

    * ``id``: The id of the image.
    * ``name``: The human-readable name of the image.
    * ``is_public``: Indicates if the image is public or private.
    * ``nat_allowed``: Indicates if NAT is allowed for machines deployed from the image.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.ImageSerializer(
            session.images(),
            many = True,
            context = { 'request': request, 'tenant': tenant }
        )
    return response.Response(serializer.data)


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def image_details(request, tenant, image):
    """
    Returns the details for the specified image.

    The image attributes are:

    * ``id``: The id of the image.
    * ``name``: The human-readable name of the image.
    * ``is_public``: Indicates if the image is public or private.
    * ``nat_allowed``: Indicates if NAT is allowed for machines deployed from the image.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.ImageSerializer(
            session.find_image(image),
            context = { 'request': request, 'tenant': tenant }
        )
    return response.Response(serializer.data)


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def sizes(request, tenant):
    """
    Returns the machine sizes available to the specified tenancy.

    The size attributes are:

    * ``id``: The id of the size.
    * ``name``: The human-readable name of the size.
    * ``cpus``: The number of CPUs.
    * ``ram``: The amount of RAM (in MB).
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.SizeSerializer(
            session.sizes(),
            many = True,
            context = { 'request': request, 'tenant': tenant }
        )
    return response.Response(serializer.data)


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def size_details(request, tenant, size):
    """
    Returns the details for the specified machine size.

    The size attributes are:

    * ``id``: The id of the size.
    * ``name``: The human-readable name of the size.
    * ``cpus``: The number of CPUs.
    * ``ram``: The amount of RAM (in MB).
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.SizeSerializer(
            session.find_size(size),
            context = { 'request': request, 'tenant': tenant }
        )
    return response.Response(serializer.data)


@decorators.api_view(['GET', 'POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def machines(request, tenant):
    """
    On ``GET`` requests, return the machines deployed in the specified tenancy.

    On ``POST`` requests, create a new machine. The request body should look like::

        {
            "name": "test-machine",
            "image_id": "<uuid of image>",
            "size_id": "<id of size>"
        }
    """
    if request.method == 'POST':
        input_serializer = serializers.MachineSerializer(data = request.data)
        input_serializer.is_valid(raise_exception = True)
        with request.auth.scoped_session(tenant) as session:
            output_serializer = serializers.MachineSerializer(
                session.create_machine(
                    input_serializer.validated_data['name'],
                    input_serializer.validated_data['image_id'],
                    input_serializer.validated_data['size_id'],
                    cloud_settings.SSH_KEY_STORE.get_key(request.user.username)
                ),
                context = { 'request': request, 'tenant': tenant }
            )
        return response.Response(output_serializer.data, status = status.HTTP_201_CREATED)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.MachineSerializer(
                session.machines(),
                many = True,
                context = { 'request': request, 'tenant': tenant }
            )
        return response.Response(serializer.data)


@decorators.api_view(['GET', 'DELETE'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def machine_details(request, tenant, machine):
    """
    On ``GET`` requests, return the details for the specified machine.

    On ``DELETE`` requests, delete the specified machine.
    """
    if request.method == 'DELETE':
        with request.auth.scoped_session(tenant) as session:
            deleted = session.delete_machine(machine)
        if deleted:
            serializer = serializers.MachineSerializer(
                deleted,
                context = { 'request': request, 'tenant': tenant }
            )
            return response.Response(serializer.data)
        else:
            return response.Response()
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.MachineSerializer(
                session.find_machine(machine),
                context = { 'request': request, 'tenant': tenant }
            )
        return response.Response(serializer.data)


@decorators.api_view(['POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def machine_start(request, tenant, machine):
    """
    Start (power on) the specified machine.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.MachineSerializer(
            session.start_machine(machine),
            context = { 'request': request, 'tenant': tenant }
        )
    return response.Response(serializer.data)


@decorators.api_view(['POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def machine_stop(request, tenant, machine):
    """
    Stop (power off) the specified machine.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.MachineSerializer(
            session.stop_machine(machine),
            context = { 'request': request, 'tenant': tenant }
        )
    return response.Response(serializer.data)


@decorators.api_view(['POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def machine_restart(request, tenant, machine):
    """
    Restart (power cycle) the specified machine.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.MachineSerializer(
            session.restart_machine(machine),
            context = { 'request': request, 'tenant': tenant }
        )
    return response.Response(serializer.data)


@decorators.api_view(['GET', 'POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def external_ips(request, tenant):
    """
    On ``GET`` requests, return a list of external IP addresses that are
    allocated to the tenancy.

    On ``POST`` requests, allocate a new external IP address for the tenancy from
    a pool. This functionality is not available for all providers. The request
    body is ignored. The returned response will be the allocated IP::

        {
            "external_ip": "172.28.128.4",
            "internal_ip": null
        }
    """
    if request.method == 'POST':
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.ExternalIPSerializer(session.allocate_external_ip())
        return response.Response(serializer.data, status = status.HTTP_201_CREATED)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.ExternalIPSerializer(
                session.external_ips(),
                many = True,
                context = { 'request': request, 'tenant': tenant }
            )
        return response.Response(serializer.data)


@decorators.api_view(['GET', 'PUT'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def external_ip_details(request, tenant, ip):
    """
    On ``GET`` requests, return the details for the external IP address.

    On ``PUT`` requests, attach the specified machine to the external IP address.
    If the machine_id is ``null``, the external IP address will be detached from
    the machine it is currently attached to.
    The request body should contain the machine ID::

        { "machine_id": "<machine id>" }
    """
    if request.method == 'PUT':
        input_serializer = serializers.ExternalIPSerializer(data = request.data)
        input_serializer.is_valid(raise_exception = True)
        machine_id = input_serializer.validated_data['machine_id']
        with request.auth.scoped_session(tenant) as session:
            if machine_id:
                ip = session.attach_external_ip(ip, str(machine_id))
            else:
                ip = session.detach_external_ip(ip)
        output_serializer = serializers.ExternalIPSerializer(
            ip,
            context = { 'request': request, 'tenant': tenant }
        )
        return response.Response(output_serializer.data)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.ExternalIPSerializer(
                session.find_external_ip(ip),
                context = { 'request': request, 'tenant': tenant }
            )
        return response.Response(serializer.data)


@decorators.api_view(['GET', 'POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def volumes(request, tenant):
    """
    On ``GET`` requests, return a list of the volumes for the tenancy.

    On ``POST`` requests, create a new volume. The request body should look like::

        {
            "name": "volume-name",
            "size": 20
        }

    The size of the volume is given in GB.
    """
    if request.method == 'POST':
        input_serializer = serializers.CreateVolumeSerializer(data = request.data)
        input_serializer.is_valid(raise_exception = True)
        with request.auth.scoped_session(tenant) as session:
            output_serializer = serializers.VolumeSerializer(
                session.create_volume(
                    input_serializer.validated_data['name'],
                    input_serializer.validated_data['size']
                ),
                context = { 'request': request, 'tenant': tenant }
            )
        return response.Response(output_serializer.data, status = status.HTTP_201_CREATED)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.VolumeSerializer(
                session.volumes(),
                many = True,
                context = { 'request': request, 'tenant': tenant }
            )
        return response.Response(serializer.data)


@decorators.api_view(['GET', 'PUT', 'DELETE'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def volume_details(request, tenant, volume):
    """
    On ``GET`` requests, return the details for the specified volume.

    On ``PUT`` requests, update the attachment status of the specified volume
    depending on the given ``machine_id``.

    To attach a volume to a machine, just give the machine id::

        { "machine_id": "<uuid of machine>" }

    To detach a volume, just give ``null`` as the the machine id::

        { "machine_id": null }

    On ``DELETE`` requests, delete the specified volume.
    """
    if request.method == 'PUT':
        input_serializer = serializers.UpdateVolumeSerializer(data = request.data)
        input_serializer.is_valid(raise_exception = True)
        machine_id = input_serializer.validated_data['machine_id']
        with request.auth.scoped_session(tenant) as session:
            if machine_id:
                volume = session.attach_volume(volume, str(machine_id))
            else:
                volume = session.detach_volume(volume)
        output_serializer = serializers.VolumeSerializer(
            volume,
            context = { 'request': request, 'tenant': tenant }
        )
        return response.Response(output_serializer.data)
    elif request.method == 'DELETE':
        with request.auth.scoped_session(tenant) as session:
            deleted = session.delete_volume(volume)
        if deleted:
            serializer = serializers.VolumeSerializer(
                deleted,
                context = { 'request': request, 'tenant': tenant }
            )
            return response.Response(serializer.data)
        else:
            return response.Response()
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.VolumeSerializer(
                session.find_volume(volume),
                context = { 'request': request, 'tenant': tenant }
            )
        return response.Response(serializer.data)


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def cluster_types(request, tenant):
    """
    Returns the cluster types available to the tenancy.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.ClusterTypeSerializer(
            session.cluster_types(),
            many = True,
            context = { 'request': request, 'tenant': tenant }
        )
    return response.Response(serializer.data)


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def cluster_type_details(request, tenant, cluster_type):
    """
    Returns the requested cluster type.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.ClusterTypeSerializer(
            session.find_cluster_type(cluster_type),
            context = { 'request': request, 'tenant': tenant }
        )
    return response.Response(serializer.data)


@decorators.api_view(['GET', 'POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def clusters(request, tenant):
    """
    On ``GET`` requests, return a list of the deployed clusters.

    On ``POST`` requests, create a new cluster.
    """
    if request.method == 'POST':
        with request.auth.scoped_session(tenant) as session:
            input_serializer = serializers.CreateClusterSerializer(
                data = request.data,
                context = { 'session': session }
            )
            input_serializer.is_valid(raise_exception = True)
            cluster = session.create_cluster(
                input_serializer.validated_data['name'],
                input_serializer.validated_data['cluster_type'],
                input_serializer.validated_data['parameter_values']
            )
        output_serializer = serializers.ClusterSerializer(
            cluster,
            context = { 'request': request, 'tenant': tenant }
        )
        return response.Response(output_serializer.data)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.ClusterSerializer(
                session.clusters(),
                many = True,
                context = { 'request': request, 'tenant': tenant }
            )
        return response.Response(serializer.data)


@decorators.api_view(['GET', 'PUT', 'DELETE'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def cluster_details(request, tenant, cluster):
    """
    On ``GET`` requests, return the named cluster.

    On ``PUT`` requests, update the named cluster with the given paramters.

    On ``DELETE`` requests, delete the named cluster.
    """
    if request.method == 'PUT':
        with request.auth.scoped_session(tenant) as session:
            cluster = session.find_cluster(cluster)
            input_serializer = serializers.UpdateClusterSerializer(
                data = request.data,
                context = dict(session = session, cluster = cluster)
            )
            input_serializer.is_valid(raise_exception = True)
            updated = session.update_cluster(
                cluster,
                input_serializer.validated_data['parameter_values']
            )
        output_serializer = serializers.ClusterSerializer(
            updated,
            context = { 'request': request, 'tenant': tenant }
        )
        return response.Response(output_serializer.data)
    elif request.method == 'DELETE':
        with request.auth.scoped_session(tenant) as session:
            deleted = session.delete_cluster(cluster)
        if deleted:
            serializer = serializers.ClusterSerializer(
                deleted,
                context = { 'request': request, 'tenant': tenant }
            )
            return response.Response(serializer.data)
        else:
            return response.Response()
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.ClusterSerializer(
                session.find_cluster(cluster),
                context = { 'request': request, 'tenant': tenant }
            )
        return response.Response(serializer.data)


@decorators.api_view(['POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
@require_provider_session
@convert_provider_exceptions
def cluster_patch(request, tenant, cluster):
    """
    Patch the given cluster.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.ClusterSerializer(
            session.patch_cluster(cluster),
            context = { 'request': request, 'tenant': tenant }
        )
    return response.Response(serializer.data)
