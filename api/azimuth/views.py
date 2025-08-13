"""
Django views for interacting with the configured cloud provider.
"""

import contextlib
import dataclasses
import functools
import logging
import math

from azimuth_auth.settings import auth_settings
from django.shortcuts import redirect, render
from django.template import Context, Engine
from django.urls import reverse
from django.utils.encoding import smart_str
from django.utils.safestring import mark_safe
from docutils import core
from rest_framework import decorators, permissions, response, status
from rest_framework import exceptions as drf_exceptions
from rest_framework.utils import formatting

from . import identity, scheduling, serializers
from .apps import errors as apps_errors
from .cluster_api import errors as cluster_api_errors
from .cluster_engine import errors as cluster_engine_errors
from .keystore import errors as keystore_errors
from .provider import errors as provider_errors
from .settings import cloud_settings

log = logging.getLogger(__name__)


def get_view_description(view_cls, html=False):
    """
    Alternative django-rest-framework ``VIEW_DESCRIPTION_FUNCTION`` that allows
    RestructuredText to be used instead of Markdown.

    This allows docstrings to be used in the DRF-generated HTML views and in
    Sphinx-generated API views.
    """
    description = view_cls.__doc__ or ""
    description = formatting.dedent(smart_str(description))
    if html:
        # Get just the HTML parts corresponding to the docstring
        parts = core.publish_parts(source=description, writer_name="html")
        html = parts["body_pre_docinfo"] + parts["fragment"]
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
                {"detail": str(exc), "code": "unsupported_operation"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except provider_errors.QuotaExceededError as exc:
            return response.Response(
                {"detail": str(exc), "code": "quota_exceeded"},
                status=status.HTTP_409_CONFLICT,
            )
        except provider_errors.InvalidOperationError as exc:
            return response.Response(
                {"detail": str(exc), "code": "invalid_operation"},
                status=status.HTTP_409_CONFLICT,
            )
        except provider_errors.BadInputError as exc:
            return response.Response(
                {"detail": str(exc), "code": "bad_input"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except provider_errors.OperationTimedOutError as exc:
            return response.Response(
                {"detail": str(exc), "code": "operation_timed_out"},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        # For authentication/not found errors, raise the DRF equivalent
        except provider_errors.AuthenticationError as exc:
            raise drf_exceptions.AuthenticationFailed(str(exc))
        except provider_errors.PermissionDeniedError as exc:
            raise drf_exceptions.PermissionDenied(str(exc))
        except provider_errors.ObjectNotFoundError as exc:
            raise drf_exceptions.NotFound(str(exc))
        except provider_errors.Error as exc:
            log.exception("Unexpected provider error")
            return response.Response(
                {"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return wrapper


def convert_key_store_exceptions(view):
    """
    Decorator that converts errors from :py:mod:`.keystore.errors` into appropriate
    HTTP responses or Django REST framework errors.
    """

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except keystore_errors.KeyNotFound:
            return response.Response(
                {"detail": "No SSH public key available.", "code": "ssh_key_not_set"},
                status=status.HTTP_409_CONFLICT,
            )
        except keystore_errors.UnsupportedOperation as exc:
            return response.Response(
                {"detail": str(exc), "code": "unsupported_operation"},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        except keystore_errors.Error as exc:
            log.exception("Unexpected key store error")
            return response.Response(
                {"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return wrapper


def convert_cluster_engine_exceptions(view):
    """
    Decorator that converts errors from :py:mod:`.cluster_engine.errors` into
    appropriate HTTP responses or Django REST framework errors.
    """

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        # For provider errors that don't map to authentication/not found errors,
        # return suitable responses
        except cluster_engine_errors.UnsupportedOperationError as exc:
            return response.Response(
                {"detail": str(exc), "code": "unsupported_operation"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except cluster_engine_errors.QuotaExceededError as exc:
            return response.Response(
                {"detail": str(exc), "code": "quota_exceeded"},
                status=status.HTTP_409_CONFLICT,
            )
        except cluster_engine_errors.InvalidOperationError as exc:
            return response.Response(
                {"detail": str(exc), "code": "invalid_operation"},
                status=status.HTTP_409_CONFLICT,
            )
        except cluster_engine_errors.BadInputError as exc:
            return response.Response(
                {"detail": str(exc), "code": "bad_input"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except cluster_engine_errors.ObjectNotFoundError as exc:
            raise drf_exceptions.NotFound(str(exc))
        except cluster_engine_errors.Error as exc:
            log.exception("Unexpected cluster engine error")
            return response.Response(
                {"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return wrapper


def convert_cluster_api_exceptions(view):
    """
    Decorator that converts errors from :py:mod:`.cluster_api.errors` into appropriate
    HTTP responses or Django REST framework errors.
    """

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        # For provider errors that don't map to authentication/not found errors,
        # return suitable responses
        except cluster_api_errors.UnsupportedOperationError as exc:
            return response.Response(
                {"detail": str(exc), "code": "unsupported_operation"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except cluster_api_errors.InvalidOperationError as exc:
            return response.Response(
                {"detail": str(exc), "code": "invalid_operation"},
                status=status.HTTP_409_CONFLICT,
            )
        except cluster_api_errors.BadInputError as exc:
            return response.Response(
                {"detail": str(exc), "code": "bad_input"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except cluster_api_errors.ObjectNotFoundError as exc:
            raise drf_exceptions.NotFound(str(exc))
        except cluster_api_errors.Error as exc:
            log.exception("Unexpected Cluster API provider error")
            return response.Response(
                {"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return wrapper


def convert_apps_exceptions(view):
    """
    Decorator that converts errors from :py:mod:`.apps.errors` into appropriate
    HTTP responses or Django REST framework errors.
    """

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        # For provider errors that don't map to authentication/not found errors,
        # return suitable responses
        except apps_errors.UnsupportedOperationError as exc:
            return response.Response(
                {"detail": str(exc), "code": "unsupported_operation"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except apps_errors.InvalidOperationError as exc:
            return response.Response(
                {"detail": str(exc), "code": "invalid_operation"},
                status=status.HTTP_409_CONFLICT,
            )
        except apps_errors.BadInputError as exc:
            return response.Response(
                {"detail": str(exc), "code": "bad_input"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except apps_errors.ObjectNotFoundError as exc:
            raise drf_exceptions.NotFound(str(exc))
        except apps_errors.Error as exc:
            log.exception("Unexpected apps provider error")
            return response.Response(
                {"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return wrapper


def provider_api_view(methods):
    """
    Returns a decorator for a provider API view that combines several decorators into
    one.
    """

    def decorator(view):
        view = convert_provider_exceptions(view)
        view = convert_key_store_exceptions(view)
        view = convert_cluster_api_exceptions(view)
        view = convert_cluster_engine_exceptions(view)
        view = convert_apps_exceptions(view)
        view = decorators.permission_classes([permissions.IsAuthenticated])(view)
        view = decorators.api_view(methods)(view)
        return view

    return decorator


def redirect_to_signin(view):
    """
    Decorator that redirects unauthorized requests to the sign in page instead
    of returning a 401 to the client.

    Primarily for use with views that use redirect_to_zenith_service to redirect users
    to external services.
    """

    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            return redirect(
                "{}?{}={}".format(
                    reverse("azimuth_auth:login"),
                    auth_settings.NEXT_URL_PARAM,
                    request.get_full_path(),
                )
            )
        else:
            return response

    return wrapper


def redirect_to_zenith_service(
    request,
    service_type,
    service_name,
    service_fqdn,
    service_label=None,
    readiness_path="/",
):
    """
    Redirects to a service URL if it is ready.

    If it is not ready, a holding page is rendered.
    """
    if not service_label:
        service_label = " ".join(w.capitalize() for w in service_name.split("-"))
    if not service_fqdn:
        return render(
            request,
            "azimuth/service_not_available.html",
            {"service_name": service_label},
        )
    redirect_url = cloud_settings.APPS.service_is_ready(service_fqdn, readiness_path)
    if redirect_url:
        return redirect(redirect_url)
    else:
        return render(
            request,
            "azimuth/service_not_ready.html",
            {"service_name": service_label, "service_type": service_type},
        )


@decorators.api_view(["GET"])
# The info endpoint does not require authentication
@decorators.authentication_classes([])
def cloud_info(request):
    data = {
        "available_clouds": cloud_settings.AVAILABLE_CLOUDS,
        "current_cloud": cloud_settings.CURRENT_CLOUD,
        "links": {
            "session": request.build_absolute_uri(reverse("azimuth:session")),
            "documentation": cloud_settings.DOCUMENTATION_URL,
            "support": cloud_settings.SUPPORT_URL,
        },
    }
    if cloud_settings.METRICS.CLOUD_METRICS_URL:
        data["links"]["metrics"] = cloud_settings.METRICS.CLOUD_METRICS_URL
    return response.Response(data)


@provider_api_view(["GET"])
def session(request):
    """
    Returns information about the current session.
    """
    return response.Response(
        {
            "user_id": request.auth.user_id(),
            "username": request.auth.username(),
            "token": request.auth.token(),
            "links": {
                "ssh_public_key": (
                    request.build_absolute_uri(reverse("azimuth:ssh_public_key"))
                ),
                "tenancies": request.build_absolute_uri(reverse("azimuth:tenancies")),
            },
        }
    )


@provider_api_view(["GET"])
def session_verify(request):
    """
    Verify the current session and return information about the authenticated user.

    This endpoint can be used to check for the presence of an authenticated session
    and optionally for tenancy-level authorization by specifying the configured header
    (defaults to ``X-Auth-Tenancy-Id``).

    It returns the ID, username, email (if known) and the IDs of the tenancies that the
    authenticated user belongs to in the ``X-Remote-User-Id``, ``X-Remote-User``,
    ``X-Remote-User-Email`` and ``X-Remote-Group`` headers respectively.

    It is used as an auth callout for the Dex provider. The Dex provider is used to
    sign Azimuth users into Keycloak realms that are used for Zenith OIDC.
    """
    # If we get to here, the user is already authenticated
    # If they are not, a 401 will have been returned
    content = {"authenticated": True}
    tenancies = list(request.auth.tenancies())
    # If the tenancy ID header is present, verify that the user belongs to the tenancy
    tenancy_id = request.META.get(cloud_settings.VERIFY_TENANCY_ID_HEADER)
    if tenancy_id:
        if any(t.id == tenancy_id for t in tenancies):
            content["authorized"] = True
        else:
            raise drf_exceptions.PermissionDenied()
    headers = {
        "X-Remote-User-Id": request.auth.user_id(),
        "X-Remote-User": request.auth.username(),
        "X-Remote-Group": ",".join(t.id for t in tenancies),
    }
    email = request.auth.user_email()
    if email:
        headers["X-Remote-User-Email"] = email
    return response.Response(content, headers=headers)


@provider_api_view(["GET", "PUT"])
def ssh_public_key(request):
    """
    On ``GET`` requests, return the current SSH public key for the user along with
    a hint about whether the key can be updated (i.e. the configured key store
    supports updating SSH public keys).

    On ``PUT`` requests, update the SSH public key for the user. The request body
    should look like::

        {
            "ssh_public_key": "<public key content>"
        }
    """
    if request.method == "PUT":
        serializer = serializers.SSHKeyUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ssh_public_key = cloud_settings.SSH_KEY_STORE.update_key(
            request.user.username,
            serializer.validated_data["ssh_public_key"],
            # Pass the request and the sessions as keyword options
            # so that the key store can use them if it needs to
            request=request,
            unscoped_session=request.auth,
        )
    else:
        try:
            ssh_public_key = cloud_settings.SSH_KEY_STORE.get_key(
                request.user.username,
                # Pass the request and the sessions as keyword options
                # so that the key store can use them if it needs to
                request=request,
                unscoped_session=request.auth,
            )
        except keystore_errors.KeyNotFound:
            ssh_public_key = None
    content = dict(
        ssh_public_key=ssh_public_key,
        can_update=cloud_settings.SSH_KEY_STORE.supports_key_update,
        ssh_key_is_public=cloud_settings.SSH_KEY_STORE.ssh_key_is_public,
    )
    if cloud_settings.SSH_KEY_STORE.supports_key_update:
        content.update(
            allowed_key_types=cloud_settings.SSH_ALLOWED_KEY_TYPES,
            rsa_min_bits=cloud_settings.SSH_RSA_MIN_BITS,
        )
    return response.Response(content)


@provider_api_view(["GET"])
def tenancies(request):
    """
    Returns the tenancies available to the authenticated user.
    """
    serializer = serializers.TenancySerializer(
        request.auth.tenancies(), many=True, context={"request": request}
    )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def capabilities(request, tenant):
    """
    Returns the capabilities for the tenant.
    """
    with request.auth.scoped_session(tenant) as session:
        response_data = dict(
            # Clusters are supported if a cluster engine is configured
            supports_clusters=bool(cloud_settings.CLUSTER_ENGINE),
            # Kubernetes is supported if a Cluster API provider is configured
            supports_kubernetes=bool(cloud_settings.CLUSTER_API_PROVIDER),
            # Kubernetes apps are supported if an apps provider is configured
            supports_apps=bool(cloud_settings.APPS_PROVIDER),
            # Scheduling must be specifically enabled
            supports_scheduling=bool(cloud_settings.SCHEDULING.ENABLED),
        )
        # If a capability is enabled in config, allow it to be disabled for a
        # session/tenant. If a capability is disabled in config, do not allow
        # it to be overridden by a session capability.
        for cap, value in dataclasses.asdict(session.capabilities()).items():
            # Capability is set in config
            if cap in response_data:
                # Capability is enabled (True) in config and can be set to whatever
                # we get back from our session capabilities
                if response_data[cap]:
                    response_data[cap] = value
            # Capability is a session capability and is not set in config
            else:
                response_data[cap] = value

    response_data["links"] = {"self": request.build_absolute_uri()}
    return response.Response(response_data)


@provider_api_view(["GET"])
def quotas(request, tenant):
    """
    Returns information about the quotas available to the tenant.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.QuotaSerializer(
            session.quotas(), many=True, context={"request": request, "tenant": tenant}
        )
    return response.Response(serializer.data)


@provider_api_view(["GET", "POST"])
def identity_provider(request, tenant):
    """
    On ``GET`` requests, return information about the identity provider for the tenancy.

    On ``POST`` requests, enable the identity provider for the tenancy.
    """
    with request.auth.scoped_session(tenant) as session:
        if request.method == "POST":
            realm = identity.ensure_realm(session.tenancy())
        else:
            realm = identity.get_realm(session.tenancy())
    if realm:
        response_data = dict(
            enabled=True, status=realm.status, admin_url=realm.admin_url
        )
    else:
        response_data = dict(enabled=False)
    response_data["links"] = {"self": request.build_absolute_uri()}
    return response.Response(response_data)


@provider_api_view(["GET"])
def images(request, tenant):
    """
    Returns the images available to the specified tenancy.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.ImageSerializer(
            session.images(), many=True, context={"request": request, "tenant": tenant}
        )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def image_details(request, tenant, image):
    """
    Returns the details for the specified image.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.ImageSerializer(
            session.find_image(image), context={"request": request, "tenant": tenant}
        )
    return response.Response(serializer.data)


_SIZE_UNITS = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]


def _format_size(amount, original_units):
    """
    Formats a size by increasing the units when it is possible to do so.
    """
    # If the amount is zero, then use the given units
    if amount == 0:
        return f"0{original_units}"
    # Otherwise calculate the exponent and the formatted amount
    exponent = math.floor(math.log(amount) / math.log(1024))
    new_amount = amount / math.pow(1024, exponent)
    # Make sure the new amount renders nicely for integers, e.g. 1GB vs 1.00GB
    if new_amount % 1 == 0:
        formatted_amount = int(new_amount)
    else:
        formatted_amount = f"{new_amount:.2f}"
    units_index = _SIZE_UNITS.index(original_units) + exponent
    # Return the formatted value
    return f"{formatted_amount}{_SIZE_UNITS[units_index]}"


def _curated_size(cloud_size, curated_size_spec):
    """
    Given a cloud size and the matching spec for a curated size,
    return the new size.
    """
    curated_size = cloud_size
    if "name" in curated_size_spec:
        curated_size = dataclasses.replace(curated_size, name=curated_size_spec["name"])
    if "description" in curated_size_spec:
        template = Engine.get_default().from_string(curated_size_spec["description"])
        curated_size = dataclasses.replace(
            curated_size,
            description=template.render(
                Context(
                    {
                        "cpus": cloud_size.cpus,
                        "ram": _format_size(cloud_size.ram, "MB"),
                        "disk": _format_size(cloud_size.disk, "GB"),
                        "ephemeral_disk": _format_size(cloud_size.ephemeral_disk, "GB"),
                    }
                )
            ),
        )
    if "additional_properties" in curated_size_spec:
        additional_properties = curated_size.additional_properties.copy()
        additional_properties.update(
            {
                str(key): str(value)
                for key, value in curated_size_spec["additional_properties"].items()
            }
        )
        curated_size = dataclasses.replace(
            curated_size, additional_properties=additional_properties
        )
    return dataclasses.replace(
        curated_size, sort_idx=curated_size_spec.get("sort_idx", 0)
    )


@provider_api_view(["GET"])
def sizes(request, tenant):
    """
    Returns the machine sizes available to the specified tenancy.
    """
    with request.auth.scoped_session(tenant) as session:
        sizes = session.sizes()
        if cloud_settings.CURATED_SIZES:
            # Index the curated sizes by id, maintaining the sort index
            curated_size_specs = {
                cs["id"]: dict(cs, sort_idx=idx)
                for idx, cs in enumerate(cloud_settings.CURATED_SIZES)
            }
            sizes = [
                _curated_size(size, curated_size_specs[size.id])
                for size in sizes
                if size.id in curated_size_specs
            ]
        serializer = serializers.SizeSerializer(
            sizes, many=True, context={"request": request, "tenant": tenant}
        )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def size_details(request, tenant, size):
    """
    Returns the details for the specified machine size.
    """
    with request.auth.scoped_session(tenant) as session:
        size = session.find_size(size)
        if cloud_settings.CURATED_SIZES:
            try:
                curated_size_spec = next(
                    dict(cs, sort_idx=idx)
                    for idx, cs in enumerate(cloud_settings.CURATED_SIZES)
                    if cs["id"] == size.id
                )
            except StopIteration:
                pass
            else:
                size = _curated_size(size, curated_size_spec)
        serializer = serializers.SizeSerializer(
            size, context={"request": request, "tenant": tenant}
        )
    return response.Response(serializer.data)


@provider_api_view(["GET", "POST"])
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

    with request.auth.scoped_session(tenant) as session:
        if not session.capabilities().supports_machines:
            return response.Response(
                {
                    "detail": "Machine support has been disabled by the administrator.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "POST":
            input_serializer = serializers.CreateMachineSerializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            machine = session.create_machine(
                name=input_serializer.validated_data["name"],
                image=input_serializer.validated_data["image_id"],
                size=input_serializer.validated_data["size_id"],
                ssh_key=cloud_settings.SSH_KEY_STORE.get_key(
                    request.user.username,
                    request=request,
                    unscoped_session=request.auth,
                ),
            )
            output_serializer = serializers.MachineSerializer(
                machine, context={"request": request, "tenant": tenant}
            )
            return response.Response(
                output_serializer.data, status=status.HTTP_201_CREATED
            )
        else:
            serializer = serializers.MachineSerializer(
                session.machines(),
                many=True,
                context={"request": request, "tenant": tenant},
            )
            return response.Response(serializer.data)


@provider_api_view(["GET", "DELETE"])
def machine_details(request, tenant, machine):
    """
    On ``GET`` requests, return the details for the specified machine.

    On ``DELETE`` requests, delete the specified machine.
    """
    with request.auth.scoped_session(tenant) as session:
        if not session.capabilities().supports_machines:
            return response.Response(
                {
                    "detail": "Machine support has been disabled by the administrator.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "DELETE":
            deleted = session.delete_machine(machine)
            if deleted:
                serializer = serializers.MachineSerializer(
                    deleted, context={"request": request, "tenant": tenant}
                )
                return response.Response(serializer.data)
            else:
                return response.Response()
        else:
            serializer = serializers.MachineSerializer(
                session.find_machine(machine),
                context={"request": request, "tenant": tenant},
            )
            return response.Response(serializer.data)


@provider_api_view(["GET"])
def machine_logs(request, tenant, machine):
    """
    Return the logs for the specified machine as a list of lines.
    """
    with request.auth.scoped_session(tenant) as session:
        if not session.capabilities().supports_machines:
            return response.Response(
                {
                    "detail": "Machine support has been disabled by the administrator.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        machine_logs = session.fetch_logs_for_machine(machine)
    return response.Response(dict(logs=machine_logs))


@provider_api_view(["GET", "POST"])
def machine_firewall_rules(request, tenant, machine):
    """
    On ``GET`` requests, return the firewall rules for the specified machine.

    On ``POST`` requests, create a new firewall rule for the machine. The
    request body should look like::

        {
            "direction": "INBOUND",
            "protocol": "TCP",
            "port": 22,
            "remote_cidr": "0.0.0.0/0"
        }
    """
    with request.auth.scoped_session(tenant) as session:
        if not session.capabilities().supports_machines:
            return response.Response(
                {
                    "detail": "Machine support has been disabled by the administrator.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "POST":
            input_serializer = serializers.CreateFirewallRuleSerializer(
                data=request.data
            )
            input_serializer.is_valid(raise_exception=True)
            output_serializer = serializers.FirewallGroupSerializer(
                session.add_firewall_rule_to_machine(
                    machine,
                    input_serializer.validated_data["direction"],
                    input_serializer.validated_data["protocol"],
                    input_serializer.validated_data["port"],
                    input_serializer.validated_data["remote_cidr"],
                ),
                many=True,
                context={"request": request, "tenant": tenant},
            )
            return response.Response(
                output_serializer.data, status=status.HTTP_201_CREATED
            )
        else:
            serializer = serializers.FirewallGroupSerializer(
                session.fetch_firewall_rules_for_machine(machine),
                many=True,
                context={"request": request, "tenant": tenant},
            )
            return response.Response(serializer.data)


@provider_api_view(["DELETE"])
def machine_firewall_rule_details(request, tenant, machine, rule):
    """
    Delete the specified firewall rule.
    """
    with request.auth.scoped_session(tenant) as session:
        if not session.capabilities().supports_machines:
            return response.Response(
                {
                    "detail": "Machine support has been disabled by the administrator.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        output_serializer = serializers.FirewallGroupSerializer(
            session.remove_firewall_rule_from_machine(machine, rule),
            many=True,
            context={"request": request, "tenant": tenant},
        )
        return response.Response(output_serializer.data)


@provider_api_view(["POST"])
def machine_start(request, tenant, machine):
    """
    Start (power on) the specified machine.
    """
    with request.auth.scoped_session(tenant) as session:
        if not session.capabilities().supports_machines:
            return response.Response(
                {
                    "detail": "Machine support has been disabled by the administrator.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = serializers.MachineSerializer(
            session.start_machine(machine),
            context={"request": request, "tenant": tenant},
        )
    return response.Response(serializer.data)


@provider_api_view(["POST"])
def machine_stop(request, tenant, machine):
    """
    Stop (power off) the specified machine.
    """
    with request.auth.scoped_session(tenant) as session:
        if not session.capabilities().supports_machines:
            return response.Response(
                {
                    "detail": "Machine support has been disabled by the administrator.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = serializers.MachineSerializer(
            session.stop_machine(machine),
            context={"request": request, "tenant": tenant},
        )
    return response.Response(serializer.data)


@provider_api_view(["POST"])
def machine_restart(request, tenant, machine):
    """
    Restart (power cycle) the specified machine.
    """

    with request.auth.scoped_session(tenant) as session:
        if not session.capabilities().supports_machines:
            return response.Response(
                {
                    "detail": "Machine support has been disabled by the administrator.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = serializers.MachineSerializer(
            session.restart_machine(machine),
            context={"request": request, "tenant": tenant},
        )
    return response.Response(serializer.data)


@provider_api_view(["GET", "POST"])
def external_ips(request, tenant):
    """
    On ``GET`` requests, return a list of external IP addresses that are
    allocated to the tenancy.

    On ``POST`` requests, allocate a new external IP address for the tenancy from
    a pool. This functionality is not available for all providers. The request
    body is ignored.
    """
    if request.method == "POST":
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.ExternalIPSerializer(
                session.allocate_external_ip()
            )
        return response.Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.ExternalIPSerializer(
                session.external_ips(),
                many=True,
                context={"request": request, "tenant": tenant},
            )
        return response.Response(serializer.data)


@provider_api_view(["GET", "PATCH"])
def external_ip_details(request, tenant, ip):
    """
    On ``GET`` requests, return the details for the external IP address.

    On ``PATCH`` requests, attach the specified machine to the external IP address.
    If the machine_id is ``null``, the external IP address will be detached from
    the machine it is currently attached to.
    The request body should contain the machine ID::

        { "machine_id": "<machine id>" }
    """
    with request.auth.scoped_session(tenant) as session:
        if not session.capabilities().supports_machines:
            return response.Response(
                {
                    "detail": "Machine support has been disabled by the administrator.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "PATCH":
            input_serializer = serializers.ExternalIPSerializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            machine_id = input_serializer.validated_data["machine_id"]
            if machine_id:
                # If attaching, we need to check if NAT is permitted for the machine
                machine = session.find_machine(machine_id)
                if machine.metadata.get("nat_allowed", "1") == "0":
                    return response.Response(
                        {
                            "detail": (
                                "Machine is not allowed to have an external IP address."
                            ),
                            "code": "invalid_operation",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                ip = session.attach_external_ip(ip, str(machine_id))
            else:
                ip = session.detach_external_ip(ip)
            output_serializer = serializers.ExternalIPSerializer(
                ip, context={"request": request, "tenant": tenant}
            )
            return response.Response(output_serializer.data)
        else:
            serializer = serializers.ExternalIPSerializer(
                session.find_external_ip(ip),
                context={"request": request, "tenant": tenant},
            )
            return response.Response(serializer.data)


@provider_api_view(["GET", "POST"])
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
    with request.auth.scoped_session(tenant) as session:
        if (
            not session.capabilities().supports_volumes
            or not session.capabilities().supports_machines
        ):
            return response.Response(
                {
                    "detail": (
                        "Volumes are not supported by this provider, "
                        "or support has been disabled by the administrator."
                    ),
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "POST":
            input_serializer = serializers.CreateVolumeSerializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)

            output_serializer = serializers.VolumeSerializer(
                session.create_volume(
                    input_serializer.validated_data["name"],
                    input_serializer.validated_data["size"],
                ),
                context={"request": request, "tenant": tenant},
            )
            return response.Response(
                output_serializer.data, status=status.HTTP_201_CREATED
            )
        else:
            serializer = serializers.VolumeSerializer(
                session.volumes(),
                many=True,
                context={"request": request, "tenant": tenant},
            )
            return response.Response(serializer.data)


@provider_api_view(["GET", "PATCH", "DELETE"])
def volume_details(request, tenant, volume):
    """
    On ``GET`` requests, return the details for the specified volume.

    On ``PATCH`` requests, update the attachment status of the specified volume
    depending on the given ``machine_id``.

    To attach a volume to a machine, just give the machine id::

        { "machine_id": "<uuid of machine>" }

    To detach a volume, just give ``null`` as the the machine id::

        { "machine_id": null }

    On ``DELETE`` requests, delete the specified volume.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not session.capabilities().supports_volumes
            or not session.capabilities().supports_machines
        ):
            return response.Response(
                {
                    "detail": (
                        "Volumes are not supported by this provider, "
                        "or support has been disabled by the administrator."
                    ),
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "PATCH":
            input_serializer = serializers.UpdateVolumeSerializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            machine_id = input_serializer.validated_data["machine_id"]
            if machine_id:
                volume = session.attach_volume(volume, str(machine_id))
            else:
                volume = session.detach_volume(volume)
            output_serializer = serializers.VolumeSerializer(
                volume, context={"request": request, "tenant": tenant}
            )
            return response.Response(output_serializer.data)
        elif request.method == "DELETE":
            deleted = session.delete_volume(volume)
            if deleted:
                serializer = serializers.VolumeSerializer(
                    deleted, context={"request": request, "tenant": tenant}
                )
                return response.Response(serializer.data)
            else:
                return response.Response()
        else:
            serializer = serializers.VolumeSerializer(
                session.find_volume(volume),
                context={"request": request, "tenant": tenant},
            )
            return response.Response(serializer.data)


@provider_api_view(["GET"])
def cluster_types(request, tenant):
    """
    Returns the cluster types available to the tenancy.
    """
    if not cloud_settings.CLUSTER_ENGINE:
        return response.Response(
            {"detail": "Clusters are not supported.", "code": "unsupported_operation"},
            status=status.HTTP_404_NOT_FOUND,
        )
    with request.auth.scoped_session(tenant) as session:
        with cloud_settings.CLUSTER_ENGINE.create_manager(session) as cluster_manager:
            serializer = serializers.ClusterTypeSerializer(
                cluster_manager.cluster_types(),
                many=True,
                context={"request": request, "tenant": tenant},
            )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def cluster_type_details(request, tenant, cluster_type):
    """
    Returns the requested cluster type.
    """
    if not cloud_settings.CLUSTER_ENGINE:
        return response.Response(
            {"detail": "Clusters are not supported.", "code": "unsupported_operation"},
            status=status.HTTP_404_NOT_FOUND,
        )
    with request.auth.scoped_session(tenant) as session:
        with cloud_settings.CLUSTER_ENGINE.create_manager(session) as cluster_manager:
            serializer = serializers.ClusterTypeSerializer(
                cluster_manager.find_cluster_type(cluster_type),
                context={"request": request, "tenant": tenant},
            )
    return response.Response(serializer.data)


@provider_api_view(["POST"])
def cluster_schedule_new(request, tenant):
    """
    Returns scheduling information for the creating a new CaaS cluster.
    """
    if not cloud_settings.CLUSTER_ENGINE:
        return response.Response(
            {"detail": "Clusters are not supported.", "code": "unsupported_operation"},
            status=status.HTTP_404_NOT_FOUND,
        )
    with request.auth.scoped_session(tenant) as session:
        with cloud_settings.CLUSTER_ENGINE.create_manager(session) as cluster_manager:
            input_serializer = serializers.CreateClusterSerializer(
                data=request.data,
                context={
                    "session": session,
                    "cluster_manager": cluster_manager,
                    "validate_schedule": False,
                },
            )
            input_serializer.is_valid(raise_exception=True)
            # Get the scheduling information for the cluster
            calculator = scheduling.CaaSClusterCalculator(session)
            resources = calculator.calculate(
                input_serializer.validated_data["cluster_type"],
                input_serializer.validated_data["parameter_values"],
            )
            checker = scheduling.QuotaChecker(session)
            fits, quotas = checker.check(resources)
            serializer = serializers.ProjectedQuotaSerializer(quotas, many=True)
            return response.Response(
                {"quotas": serializer.data},
                status=(status.HTTP_200_OK if fits else status.HTTP_409_CONFLICT),
            )


@provider_api_view(["POST"])
def cluster_schedule_existing(request, tenant, cluster):
    """
    Returns scheduling information for updating the specified CaaS cluster.
    """
    if not cloud_settings.CLUSTER_ENGINE:
        return response.Response(
            {"detail": "Clusters are not supported.", "code": "unsupported_operation"},
            status=status.HTTP_404_NOT_FOUND,
        )
    with request.auth.scoped_session(tenant) as session:
        with cloud_settings.CLUSTER_ENGINE.create_manager(session) as cluster_manager:
            cluster = cluster_manager.find_cluster(cluster)
            cluster_type = cluster_manager.find_cluster_type(cluster.cluster_type)
            input_serializer = serializers.UpdateClusterSerializer(
                instance=cluster,
                data=request.data,
                context=dict(
                    session=session,
                    cluster_manager=cluster_manager,
                    cluster_type=cluster_type,
                ),
            )
            input_serializer.is_valid(raise_exception=True)
            # Get the scheduling information for the cluster
            calculator = scheduling.CaaSClusterCalculator(session)
            current_resources = calculator.calculate(
                cluster_type, cluster.parameter_values
            )
            future_resources = calculator.calculate(
                cluster_type, input_serializer.validated_data["parameter_values"]
            )
            checker = scheduling.QuotaChecker(session)
            fits, quotas = checker.check(future_resources, current_resources)
            serializer = serializers.ProjectedQuotaSerializer(quotas, many=True)
            return response.Response(
                {"quotas": serializer.data},
                status=(status.HTTP_200_OK if fits else status.HTTP_409_CONFLICT),
            )


@provider_api_view(["GET", "POST"])
def clusters(request, tenant):
    """
    On ``GET`` requests, return a list of the deployed clusters.

    On ``POST`` requests, create a new cluster.
    """
    if not cloud_settings.CLUSTER_ENGINE:
        return response.Response(
            {"detail": "Clusters are not supported.", "code": "unsupported_operation"},
            status=status.HTTP_404_NOT_FOUND,
        )
    with request.auth.scoped_session(tenant) as session:
        with cloud_settings.CLUSTER_ENGINE.create_manager(session) as cluster_manager:
            if request.method == "POST":
                input_serializer = serializers.CreateClusterSerializer(
                    data=request.data,
                    context={"session": session, "cluster_manager": cluster_manager},
                )
                input_serializer.is_valid(raise_exception=True)
                # Check that the cluster fits within quota
                calculator = scheduling.CaaSClusterCalculator(session)
                resources = calculator.calculate(
                    input_serializer.validated_data["cluster_type"],
                    input_serializer.validated_data["parameter_values"],
                )
                checker = scheduling.QuotaChecker(session)
                fits, _ = checker.check(resources)
                if not fits:
                    return response.Response(
                        {
                            "detail": "Cluster exceeds at least one quota.",
                            "code": "quota_exceeded",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                # If an SSH key is available, add it to the params
                try:
                    ssh_key = cloud_settings.SSH_KEY_STORE.get_key(
                        request.user.username,
                        # Pass the request and the sessions as keyword options
                        # so that the key store can use them if it needs to
                        request=request,
                        unscoped_session=request.auth,
                        scoped_session=session,
                    )
                except (
                    keystore_errors.UnsupportedOperation,
                    keystore_errors.KeyNotFound,
                ):
                    ssh_key = None
                cluster = cluster_manager.create_cluster(
                    input_serializer.validated_data["name"],
                    input_serializer.validated_data["cluster_type"],
                    input_serializer.validated_data["parameter_values"],
                    ssh_key,
                    resources,
                    input_serializer.validated_data.get("schedule"),
                )
                # Set up the identity for the cluster services
                if cloud_settings.APPS:
                    realm = identity.ensure_realm(session.tenancy())
                    identity.ensure_platform_for_cluster(
                        session.tenancy(), realm, cluster
                    )
                output_serializer = serializers.ClusterSerializer(
                    cluster, context={"request": request, "tenant": tenant}
                )
                return response.Response(output_serializer.data)
            else:
                serializer = serializers.ClusterSerializer(
                    cluster_manager.clusters(),
                    many=True,
                    context={"request": request, "tenant": tenant},
                )
                return response.Response(serializer.data)


@provider_api_view(["GET", "PATCH", "DELETE"])
def cluster_details(request, tenant, cluster):
    """
    On ``GET`` requests, return the named cluster.

    On ``PATCH`` requests, update the named cluster with the given parameters.

    On ``DELETE`` requests, delete the named cluster.
    """
    if not cloud_settings.CLUSTER_ENGINE:
        return response.Response(
            {"detail": "Clusters are not supported.", "code": "unsupported_operation"},
            status=status.HTTP_404_NOT_FOUND,
        )
    with request.auth.scoped_session(tenant) as session:
        with cloud_settings.CLUSTER_ENGINE.create_manager(session) as cluster_manager:
            cluster = cluster_manager.find_cluster(cluster)
            if request.method == "PATCH":
                cluster_type = cluster_manager.find_cluster_type(cluster.cluster_type)
                input_serializer = serializers.UpdateClusterSerializer(
                    instance=cluster,
                    data=request.data,
                    context=dict(
                        session=session,
                        cluster_manager=cluster_manager,
                        cluster_type=cluster_type,
                    ),
                )
                input_serializer.is_valid(raise_exception=True)
                # Check that the changes to the cluster fit within quota
                calculator = scheduling.CaaSClusterCalculator(session)
                current_resources = calculator.calculate(
                    cluster_type, cluster.parameter_values
                )
                future_resources = calculator.calculate(
                    cluster_type, input_serializer.validated_data["parameter_values"]
                )
                checker = scheduling.QuotaChecker(session)
                fits, _ = checker.check(future_resources, current_resources)
                if not fits:
                    return response.Response(
                        {
                            "detail": "Cluster exceeds at least one quota.",
                            "code": "quota_exceeded",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                cluster = cluster_manager.update_cluster(
                    cluster, input_serializer.validated_data["parameter_values"]
                )
                # Ensure that the identity resources are up-to-date for the cluster
                if cloud_settings.APPS:
                    realm = identity.ensure_realm(session.tenancy())
                    identity.ensure_platform_for_cluster(
                        session.tenancy(), realm, cluster
                    )
                output_serializer = serializers.ClusterSerializer(
                    cluster, context={"request": request, "tenant": tenant}
                )
                return response.Response(output_serializer.data)
            elif request.method == "DELETE":
                deleted = cluster_manager.delete_cluster(cluster)
                if deleted:
                    serializer = serializers.ClusterSerializer(
                        deleted, context={"request": request, "tenant": tenant}
                    )
                    return response.Response(serializer.data)
                else:
                    return response.Response()
            else:
                serializer = serializers.ClusterSerializer(
                    cluster, context={"request": request, "tenant": tenant}
                )
                return response.Response(serializer.data)


@provider_api_view(["POST"])
def cluster_patch(request, tenant, cluster):
    """
    Patch the given cluster.
    """
    if not cloud_settings.CLUSTER_ENGINE:
        return response.Response(
            {"detail": "Clusters are not supported.", "code": "unsupported_operation"},
            status=status.HTTP_404_NOT_FOUND,
        )
    with request.auth.scoped_session(tenant) as session:
        with cloud_settings.CLUSTER_ENGINE.create_manager(session) as cluster_manager:
            cluster = cluster_manager.patch_cluster(cluster)
            # Ensure that the identity resources are up-to-date for the cluster
            if cloud_settings.APPS:
                realm = identity.ensure_realm(session.tenancy())
                identity.ensure_platform_for_cluster(session.tenancy(), realm, cluster)
            serializer = serializers.ClusterSerializer(
                cluster, context={"request": request, "tenant": tenant}
            )
    return response.Response(serializer.data)


@redirect_to_signin
@provider_api_view(["GET"])
def cluster_service(request, tenant, cluster, service):
    """
    Redirects the user to the specified service on the specified cluster.
    """
    if not cloud_settings.CLUSTER_ENGINE:
        return response.Response(
            {"detail": "Clusters are not supported.", "code": "unsupported_operation"},
            status=status.HTTP_404_NOT_FOUND,
        )
    service_fqdn = None
    service_label = None
    try:
        if cloud_settings.CLUSTER_ENGINE:
            with request.auth.scoped_session(tenant) as session:
                with cloud_settings.CLUSTER_ENGINE.create_manager(
                    session
                ) as cluster_manager:
                    cluster = cluster_manager.find_cluster(cluster)
        service_obj = next(s for s in cluster.services if s.name == service)
        service_fqdn = service_obj.fqdn
        service_label = service_obj.label
    except (cluster_engine_errors.ObjectNotFoundError, StopIteration):
        pass
    return redirect_to_zenith_service(
        request, "cluster", service, service_fqdn, service_label=service_label
    )


@provider_api_view(["GET"])
def kubernetes_cluster_templates(request, tenant):
    """
    Return a list of the available Kubernetes cluster templates for the tenancy.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.CLUSTER_API_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes clusters are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        with cloud_settings.CLUSTER_API_PROVIDER.session(session) as capi_session:
            serializer = serializers.KubernetesClusterTemplateSerializer(
                capi_session.cluster_templates(),
                many=True,
                context={"request": request, "tenant": tenant},
            )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def kubernetes_cluster_template_details(request, tenant, template):
    """
    Return the details for the specified Kubernetes cluster template.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.CLUSTER_API_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes clusters are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        with cloud_settings.CLUSTER_API_PROVIDER.session(session) as capi_session:
            serializer = serializers.KubernetesClusterTemplateSerializer(
                capi_session.find_cluster_template(template),
                context={"request": request, "tenant": tenant},
            )
    return response.Response(serializer.data)


def kubernetes_cluster_check_quotas(session, cluster, template, **data):
    """
    Check the quotas for a Kubernetes cluster.
    """
    calculator = scheduling.KubernetesClusterCalculator(session)
    # Calculate the resources used by the current cluster
    if cluster:
        # Index the sizes that have already been loaded so we don't have to load them
        # again
        known_sizes = {}
        if "control_plane_size" in data:
            known_sizes[data["control_plane_size"].id] = data["control_plane_size"]
        for ng in data.get("node_groups", []):
            known_sizes[ng["machine_size"].id] = ng["machine_size"]
        # Calculate the data for the current state of the cluster
        current_data = {
            "control_plane_size": (
                known_sizes[cluster.control_plane_size_id]
                if cluster.control_plane_size_id in known_sizes
                else session.find_size(cluster.control_plane_size_id)
            ),
            "node_groups": [
                {
                    "name": ng.name,
                    "machine_size": (
                        known_sizes[ng.machine_size_id]
                        if ng.machine_size_id in known_sizes
                        else session.find_size(ng.machine_size_id)
                    ),
                    "autoscale": ng.autoscale,
                    "count": ng.count,
                    "min_count": ng.min_count,
                    "max_count": ng.max_count,
                }
                for ng in cluster.node_groups
            ],
            "monitoring_enabled": cluster.monitoring_enabled,
            "monitoring_metrics_volume_size": cluster.monitoring_metrics_volume_size,
            "monitoring_logs_volume_size": cluster.monitoring_logs_volume_size,
        }
        # Calculate the resources for the current state of the cluster
        current_resources = calculator.calculate(template, **current_data)
        # Overwrite with any changes from the incoming data
        data = {**current_data, **data}
    else:
        current_resources = None
    future_resources = calculator.calculate(template, **data)
    checker = scheduling.QuotaChecker(session)
    return [future_resources, *checker.check(future_resources, current_resources)]


@provider_api_view(["POST"])
def kubernetes_cluster_schedule_new(request, tenant):
    """
    Returns scheduling information for creating a new Kubernetes cluster.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.CLUSTER_API_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes clusters are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        with cloud_settings.CLUSTER_API_PROVIDER.session(session) as capi_session:
            input_serializer = serializers.CreateKubernetesClusterSerializer(
                data=request.data,
                context={
                    "session": session,
                    "capi_session": capi_session,
                    "validate_schedule": False,
                },
            )
            input_serializer.is_valid(raise_exception=True)
            _, fits, quotas = kubernetes_cluster_check_quotas(
                session, None, **input_serializer.validated_data
            )
            serializer = serializers.ProjectedQuotaSerializer(quotas, many=True)
            return response.Response(
                {"quotas": serializer.data},
                status=(status.HTTP_200_OK if fits else status.HTTP_409_CONFLICT),
            )


@provider_api_view(["POST"])
def kubernetes_cluster_schedule_existing(request, tenant, cluster):
    """
    Returns scheduling information for updating the specified Kubernetes cluster.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.CLUSTER_API_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes clusters are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        with cloud_settings.CLUSTER_API_PROVIDER.session(session) as capi_session:
            cluster = capi_session.find_cluster(cluster)
            input_serializer = serializers.UpdateKubernetesClusterSerializer(
                instance=cluster,
                data=request.data,
                context={"session": session, "capi_session": capi_session},
            )
            input_serializer.is_valid(raise_exception=True)
            _, fits, quotas = kubernetes_cluster_check_quotas(
                session,
                cluster,
                capi_session.find_cluster_template(cluster.template_id),
                **{
                    k: v
                    for k, v in input_serializer.validated_data.items()
                    if k != "template"
                },
            )
            serializer = serializers.ProjectedQuotaSerializer(quotas, many=True)
            return response.Response(
                {"quotas": serializer.data},
                status=(status.HTTP_200_OK if fits else status.HTTP_409_CONFLICT),
            )


@provider_api_view(["GET", "POST"])
def kubernetes_clusters(request, tenant):
    """
    On ``GET`` requests, return a list of the deployed Kubernetes clusters for the
    tenancy.

    On ``POST`` requests, create a new Kubernetes cluster.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.CLUSTER_API_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes clusters are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        with cloud_settings.CLUSTER_API_PROVIDER.session(session) as capi_session:
            if request.method == "POST":
                input_serializer = serializers.CreateKubernetesClusterSerializer(
                    data=request.data,
                    context={"session": session, "capi_session": capi_session},
                )
                input_serializer.is_valid(raise_exception=True)
                # Check that the cluster fits within quota
                resources, fits, _ = kubernetes_cluster_check_quotas(
                    session, None, **input_serializer.validated_data
                )
                if not fits:
                    return response.Response(
                        {
                            "detail": "Cluster exceeds at least one quota.",
                            "code": "quota_exceeded",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                params = dict(input_serializer.validated_data)
                if cloud_settings.APPS:
                    # Make sure that the identity realm exists
                    realm = identity.ensure_realm(session.tenancy())
                    params["zenith_identity_realm_name"] = realm.name
                cluster = capi_session.create_cluster(resources=resources, **params)
                output_serializer = serializers.KubernetesClusterSerializer(
                    cluster, context={"request": request, "tenant": tenant}
                )
                return response.Response(output_serializer.data)
            else:
                serializer = serializers.KubernetesClusterSerializer(
                    capi_session.clusters(),
                    many=True,
                    context={"request": request, "tenant": tenant},
                )
                return response.Response(serializer.data)


@provider_api_view(["GET", "PATCH", "DELETE"])
def kubernetes_cluster_details(request, tenant, cluster):
    """
    On ``GET`` requests, return the specified Kubernetes cluster.

    On ``PATCH`` requests, update the specified Kubernetes cluster with the given
    data and return it. There are two distinct forms of update available - an
    "upgrade" operation that accepts only a template id and an "update" operation
    that accepts all other options.

    On ``DELETE`` requests, delete the specified Kubernetes cluster.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.CLUSTER_API_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes clusters are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        with cloud_settings.CLUSTER_API_PROVIDER.session(session) as capi_session:
            if request.method == "PATCH":
                cluster = capi_session.find_cluster(cluster)
                input_serializer = serializers.UpdateKubernetesClusterSerializer(
                    instance=cluster,
                    data=request.data,
                    context={"session": session, "capi_session": capi_session},
                )
                input_serializer.is_valid(raise_exception=True)
                template = input_serializer.validated_data.get("template")
                if template:
                    cluster = capi_session.upgrade_cluster(cluster, template)
                else:
                    data = {
                        k: v
                        for k, v in input_serializer.validated_data.items()
                        if k != "template"
                    }
                    # Check that the new size of the cluster fits within quota
                    _, fits, _ = kubernetes_cluster_check_quotas(
                        session,
                        cluster,
                        capi_session.find_cluster_template(cluster.template_id),
                        **data,
                    )
                    if not fits:
                        return response.Response(
                            {
                                "detail": "Cluster exceeds at least one quota.",
                                "code": "quota_exceeded",
                            },
                            status=status.HTTP_409_CONFLICT,
                        )
                    cluster = capi_session.update_cluster(cluster, **data)
                output_serializer = serializers.KubernetesClusterSerializer(
                    cluster, context={"request": request, "tenant": tenant}
                )
                return response.Response(output_serializer.data)
            elif request.method == "DELETE":
                deleted = capi_session.delete_cluster(cluster)
                if deleted:
                    serializer = serializers.KubernetesClusterSerializer(
                        deleted, context={"request": request, "tenant": tenant}
                    )
                    return response.Response(serializer.data)
                else:
                    return response.Response()
            else:
                serializer = serializers.KubernetesClusterSerializer(
                    capi_session.find_cluster(cluster),
                    context={"request": request, "tenant": tenant},
                )
                return response.Response(serializer.data)


@provider_api_view(["POST"])
def kubernetes_cluster_generate_kubeconfig(request, tenant, cluster):
    """
    Generate a kubeconfig file for the specified Kubernetes cluster.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.CLUSTER_API_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes clusters are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        with cloud_settings.CLUSTER_API_PROVIDER.session(session) as capi_session:
            kubeconfig = capi_session.generate_kubeconfig(cluster)
    return response.Response({"kubeconfig": kubeconfig})


@redirect_to_signin
@provider_api_view(["GET"])
def kubernetes_cluster_service(request, tenant, cluster, service):
    """
    Redirects the user to the specified service on the specified Kubernetes cluster.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.CLUSTER_API_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes clusters are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

    service_fqdn = None
    service_label = None
    try:
        if cloud_settings.CLUSTER_API_PROVIDER:
            with cloud_settings.CLUSTER_API_PROVIDER.session(session) as capi_session:
                cluster = capi_session.find_cluster(cluster)
        service_obj = next(s for s in cluster.services if s.name == service)
        service_fqdn = service_obj.fqdn
        service_label = service_obj.label
    except (cluster_api_errors.ObjectNotFoundError, StopIteration):
        pass
    return redirect_to_zenith_service(
        request, "kubernetes", service, service_fqdn, service_label=service_label
    )


@provider_api_view(["GET"])
def kubernetes_app_templates(request, tenant):
    """
    Return a list of the available Kubernetes app templates for the tenancy.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.APPS_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes clusters are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        with cloud_settings.APPS_PROVIDER.session(session) as apps_session:
            serializer = serializers.KubernetesAppTemplateSerializer(
                apps_session.app_templates(),
                many=True,
                context={"request": request, "tenant": tenant},
            )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def kubernetes_app_template_details(request, tenant, template):
    """
    Return the details for the specified Kubernetes app template.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.APPS_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes clusters are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        with cloud_settings.APPS_PROVIDER.session(session) as apps_session:
            serializer = serializers.KubernetesAppTemplateSerializer(
                apps_session.find_app_template(template),
                context={"request": request, "tenant": tenant},
            )
    return response.Response(serializer.data)


def optional_capi_session(cloud_session):
    """
    Returns a context manager that yields either a CAPI session or None.
    """
    # If a CAPI provider is available, get a session
    if (
        bool(cloud_settings.CLUSTER_API_PROVIDER)
        and cloud_session.capabilities().supports_kubernetes
    ):
        return cloud_settings.CLUSTER_API_PROVIDER.session(cloud_session)
    else:
        return contextlib.nullcontext()


@provider_api_view(["GET", "POST"])
def kubernetes_apps(request, tenant):
    """
    On ``GET`` requests, return a list of the deployed Kubernetes apps for the tenancy.

    On ``POST`` requests, create a new Kubernetes app.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.APPS_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes apps are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        with cloud_settings.APPS_PROVIDER.session(session) as apps_session:
            if request.method == "POST":
                with optional_capi_session(session) as capi_session:
                    input_serializer = serializers.CreateKubernetesAppSerializer(
                        data=request.data,
                        context={
                            "session": session,
                            "apps_session": apps_session,
                            "capi_session": capi_session,
                        },
                    )
                    input_serializer.is_valid(raise_exception=True)
                    params = dict(input_serializer.validated_data)
                    if cloud_settings.APPS:
                        # Make sure that the identity realm exists
                        realm = identity.ensure_realm(session.tenancy())
                        params["zenith_identity_realm_name"] = realm.name
                    app = apps_session.create_app(**params)
                    output_serializer = serializers.KubernetesAppSerializer(
                        app, context={"request": request, "tenant": tenant}
                    )
                    return response.Response(output_serializer.data)
            else:
                serializer = serializers.KubernetesAppSerializer(
                    apps_session.apps(),
                    many=True,
                    context={"request": request, "tenant": tenant},
                )
                return response.Response(serializer.data)


@provider_api_view(["GET", "PATCH", "DELETE"])
def kubernetes_app_details(request, tenant, app):
    """
    On ``GET`` requests, return the specified Kubernetes app.

    On ``PATCH`` requests, update the specified Kubernetes app with the given
    data and return it.

    On ``DELETE`` requests, delete the specified Kubernetes app.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.APPS_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes apps are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        with cloud_settings.APPS_PROVIDER.session(session) as apps_session:
            if request.method == "PATCH":
                app = apps_session.find_app(app)
                app_template = apps_session.find_app_template(app.template_id)
                input_serializer = serializers.UpdateKubernetesAppSerializer(
                    data=request.data,
                    context=dict(
                        session=session,
                        apps_session=apps_session,
                        app_template=app_template,
                        app=app,
                    ),
                )
                input_serializer.is_valid(raise_exception=True)
                output_serializer = serializers.KubernetesAppSerializer(
                    apps_session.update_app(
                        app, app_template, **input_serializer.validated_data
                    ),
                    context={"request": request, "tenant": tenant},
                )
                return response.Response(output_serializer.data)
            elif request.method == "DELETE":
                deleted = apps_session.delete_app(app)
                if deleted:
                    serializer = serializers.KubernetesAppSerializer(
                        deleted, context={"request": request, "tenant": tenant}
                    )
                    return response.Response(serializer.data)
                else:
                    return response.Response()
            else:
                serializer = serializers.KubernetesAppSerializer(
                    apps_session.find_app(app),
                    context={"request": request, "tenant": tenant},
                )
                return response.Response(serializer.data)


@redirect_to_signin
@provider_api_view(["GET"])
def kubernetes_app_service(request, tenant, app, service):
    """
    Redirects the user to the specified service for the specified Kubernetes app.
    """
    with request.auth.scoped_session(tenant) as session:
        if (
            not bool(cloud_settings.APPS_PROVIDER)
            or not session.capabilities().supports_kubernetes
        ):
            return response.Response(
                {
                    "detail": "Kubernetes apps are not supported.",
                    "code": "unsupported_operation",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        service_fqdn = None
        service_label = None
        try:
            with cloud_settings.APPS_PROVIDER.session(session) as apps_session:
                app = apps_session.find_app(app)
            service_obj = next(s for s in app.services if s.name == service)
            service_fqdn = service_obj.fqdn
            service_label = service_obj.label
        except (cluster_api_errors.ObjectNotFoundError, StopIteration):
            pass
        return redirect_to_zenith_service(
            request,
            "kubernetes_app",
            service,
            service_fqdn,
            service_label=service_label,
        )
