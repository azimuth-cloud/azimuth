"""
Django views for interacting with the configured cloud provider.
"""

import dataclasses
import functools
import logging
import random
import string

from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.encoding import smart_text

from docutils import core

from rest_framework import decorators, permissions, response, status, exceptions as drf_exceptions
from rest_framework.utils import formatting

import requests

from . import serializers
from .keystore import errors as keystore_errors
from .provider import errors as provider_errors
from .settings import cloud_settings


log = logging.getLogger(__name__)


def get_view_description(view_cls, html = False):
    """
    Alternative django-rest-framework ``VIEW_DESCRIPTION_FUNCTION`` that allows
    RestructuredText to be used instead of Markdown.

    This allows docstrings to be used in the DRF-generated HTML views and in
    Sphinx-generated API views.
    """
    description = view_cls.__doc__ or ""
    description = formatting.dedent(smart_text(description))
    if html:
        # Get just the HTML parts corresponding to the docstring
        parts = core.publish_parts(source = description, writer_name = "html")
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
                { "detail": str(exc), "code": "unsupported_operation"},
                status = status.HTTP_404_NOT_FOUND
            )
        except provider_errors.QuotaExceededError as exc:
            return response.Response(
                { "detail": str(exc), "code": "quota_exceeded"},
                status = status.HTTP_409_CONFLICT
            )
        except provider_errors.InvalidOperationError as exc:
            return response.Response(
                { "detail": str(exc), "code": "invalid_operation"},
                status = status.HTTP_409_CONFLICT
            )
        except provider_errors.BadInputError as exc:
            return response.Response(
                { "detail": str(exc), "code": "bad_input"},
                status = status.HTTP_400_BAD_REQUEST
            )
        except provider_errors.OperationTimedOutError as exc:
            return response.Response(
                { "detail": str(exc), "code": "operation_timed_out"},
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
            log.exception("Unexpected provider error occurred")
            return response.Response(
                { "detail": str(exc) },
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
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
                { "detail": "No SSH public key available.", "code": "ssh_key_not_set" },
                status = status.HTTP_409_CONFLICT
            )
        except keystore_errors.UnsupportedOperation as exc:
            return response.Response(
                { "detail": str(exc), "code": "unsupported_operation"},
                status = status.HTTP_405_METHOD_NOT_ALLOWED
            )
        except keystore_errors.Error as exc:
            log.exception("Unexpected key store error occurred")
            return response.Response(
                { "detail": str(exc) },
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    return wrapper


def provider_api_view(methods):
    """
    Returns a decorator for a provider API view that combines several decorators into one.
    """
    def decorator(view):
        view = convert_provider_exceptions(view)
        view = convert_key_store_exceptions(view)
        view = decorators.permission_classes([permissions.IsAuthenticated])(view)
        view = decorators.api_view(methods)(view)
        return view
    return decorator


@decorators.api_view(["GET"])
# The info endpoint does not require authentication
@decorators.authentication_classes([])
def cloud_info(request):
    return response.Response({
        "available_clouds": cloud_settings.AVAILABLE_CLOUDS,
        "current_cloud": cloud_settings.CURRENT_CLOUD,
        "links": {
            "session": request.build_absolute_uri(reverse("azimuth:session"))
        }
    })


@provider_api_view(["GET"])
def session(request):
    """
    Returns information about the current session.
    """
    return response.Response({
        "username": request.auth.username(),
        "token": request.auth.token(),
        # The capability to host apps is determined by the presence of an
        # app proxy for the portal, not the cloud itself
        "capabilities": dict(
            dataclasses.asdict(request.auth.capabilities()),
            supports_apps = bool(cloud_settings.APPS.ENABLED),
        ),
        "links": {
            "ssh_public_key": request.build_absolute_uri(reverse("azimuth:ssh_public_key")),
            "tenancies": request.build_absolute_uri(reverse("azimuth:tenancies")),
        }
    })


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
        serializer = serializers.SSHKeyUpdateSerializer(data = request.data)
        serializer.is_valid(raise_exception = True)
        ssh_public_key = cloud_settings.SSH_KEY_STORE.update_key(
            request.user.username,
            serializer.validated_data["ssh_public_key"],
            # Pass the request and the sessions as keyword options
            # so that the key store can use them if it needs to
            request = request,
            unscoped_session = request.auth
        )
    else:
        try:
            ssh_public_key = cloud_settings.SSH_KEY_STORE.get_key(
                request.user.username,
                # Pass the request and the sessions as keyword options
                # so that the key store can use them if it needs to
                request = request,
                unscoped_session = request.auth
            )
        except keystore_errors.KeyNotFound:
            ssh_public_key = None
    content = dict(
        ssh_public_key = ssh_public_key,
        can_update = cloud_settings.SSH_KEY_STORE.supports_key_update
    )
    if cloud_settings.SSH_KEY_STORE.supports_key_update:
        content.update(
            allowed_key_types = cloud_settings.SSH_ALLOWED_KEY_TYPES,
            rsa_min_bits = cloud_settings.SSH_RSA_MIN_BITS
        )
    return response.Response(content)


@provider_api_view(["GET"])
def tenancies(request):
    """
    Returns the tenancies available to the authenticated user.
    """
    serializer = serializers.TenancySerializer(
        request.auth.tenancies(),
        many = True,
        context = { "request": request }
    )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def quotas(request, tenant):
    """
    Returns information about the quotas available to the tenant.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.QuotaSerializer(
            session.quotas(),
            many = True,
            context = { "request": request, "tenant": tenant }
        )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def images(request, tenant):
    """
    Returns the images available to the specified tenancy.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.ImageSerializer(
            session.images(),
            many = True,
            context = { "request": request, "tenant": tenant }
        )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def image_details(request, tenant, image):
    """
    Returns the details for the specified image.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.ImageSerializer(
            session.find_image(image),
            context = { "request": request, "tenant": tenant }
        )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def sizes(request, tenant):
    """
    Returns the machine sizes available to the specified tenancy.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.SizeSerializer(
            session.sizes(),
            many = True,
            context = { "request": request, "tenant": tenant }
        )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def size_details(request, tenant, size):
    """
    Returns the details for the specified machine size.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.SizeSerializer(
            session.find_size(size),
            context = { "request": request, "tenant": tenant }
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
    if request.method == "POST":
        input_serializer = serializers.CreateMachineSerializer(data = request.data)
        input_serializer.is_valid(raise_exception = True)
        # Start building the parameters for the machine
        params = dict(
            name = input_serializer.validated_data["name"],
            image = input_serializer.validated_data["image_id"],
            size = input_serializer.validated_data["size_id"]
        )
        # The web console is not permitted if there is no app proxy
        web_console_enabled = input_serializer.validated_data["web_console_enabled"]
        if web_console_enabled and not cloud_settings.APPS.ENABLED:
            return response.Response(
                {
                    "detail": "Web console is not available.",
                    "code": "invalid_operation"
                },
                status = status.HTTP_409_CONFLICT
            )
        # If an SSH key is available, add it to the params
        try:
            params.update(
                ssh_key = cloud_settings.SSH_KEY_STORE.get_key(
                    request.user.username,
                    request = request,
                    unscoped_session = request.auth,
                )
            )
        except keystore_errors.KeyNotFound:
            # An SSH key is required unless the web console is enabled
            if not web_console_enabled:
                raise
        # If the web console is enabled, use the machine metadata and userdata to configure it
        if web_console_enabled:
            desktop_enabled = input_serializer.validated_data["desktop_enabled"]
            # Generate a Zenith subdomain to use
            subdomain_chars = [random.choice(string.ascii_lowercase)]
            subdomain_chars.extend(random.choices(string.ascii_lowercase + string.digits, k = 39))
            params.update(
                metadata = dict(
                    web_console_enabled = 1,
                    desktop_enabled = 1 if desktop_enabled else 0,
                    apps_sshd_host = cloud_settings.APPS.SSHD_HOST,
                    apps_sshd_port = cloud_settings.APPS.SSHD_PORT,
                    apps_console_subdomain = "".join(subdomain_chars)
                ),
                userdata = "\n".join([
                    "#!/usr/bin/env bash",
                    "set -eo pipefail",
                    "curl -fsSL {} | bash -s console".format(cloud_settings.APPS.POST_DEPLOY_SCRIPT_URL)
                ])
            )
        with request.auth.scoped_session(tenant) as session:
            machine = session.create_machine(**params)
        output_serializer = serializers.MachineSerializer(
            machine,
            context = { "request": request, "tenant": tenant }
        )
        return response.Response(output_serializer.data, status = status.HTTP_201_CREATED)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.MachineSerializer(
                session.machines(),
                many = True,
                context = { "request": request, "tenant": tenant }
            )
        return response.Response(serializer.data)


@provider_api_view(["GET", "DELETE"])
def machine_details(request, tenant, machine):
    """
    On ``GET`` requests, return the details for the specified machine.

    On ``DELETE`` requests, delete the specified machine.
    """
    if request.method == "DELETE":
        with request.auth.scoped_session(tenant) as session:
            deleted = session.delete_machine(machine)
        if deleted:
            serializer = serializers.MachineSerializer(
                deleted,
                context = { "request": request, "tenant": tenant }
            )
            return response.Response(serializer.data)
        else:
            return response.Response()
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.MachineSerializer(
                session.find_machine(machine),
                context = { "request": request, "tenant": tenant }
            )
        return response.Response(serializer.data)


@provider_api_view(["GET"])
def machine_logs(request, tenant, machine):
    """
    Return the logs for the specified machine as a list of lines.
    """
    with request.auth.scoped_session(tenant) as session:
        machine_logs = session.fetch_logs_for_machine(machine)
    return response.Response(dict(logs = machine_logs))


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
    if request.method == "POST":
        input_serializer = serializers.CreateFirewallRuleSerializer(data = request.data)
        input_serializer.is_valid(raise_exception = True)
        with request.auth.scoped_session(tenant) as session:
            output_serializer = serializers.FirewallGroupSerializer(
                session.add_firewall_rule_to_machine(
                    machine,
                    input_serializer.validated_data["direction"],
                    input_serializer.validated_data["protocol"],
                    input_serializer.validated_data["port"],
                    input_serializer.validated_data["remote_cidr"],
                ),
                many = True,
                context = { "request": request, "tenant": tenant }
            )
        return response.Response(output_serializer.data, status = status.HTTP_201_CREATED)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.FirewallGroupSerializer(
                session.fetch_firewall_rules_for_machine(machine),
                many = True,
                context = { "request": request, "tenant": tenant }
            )
        return response.Response(serializer.data)


@provider_api_view(["DELETE"])
def machine_firewall_rule_details(request, tenant, machine, rule):
    """
    Delete the specified firewall rule.
    """
    with request.auth.scoped_session(tenant) as session:
        output_serializer = serializers.FirewallGroupSerializer(
            session.remove_firewall_rule_from_machine(machine, rule),
            many = True,
            context = { "request": request, "tenant": tenant }
        )
        return response.Response(output_serializer.data)


@provider_api_view(["POST"])
def machine_start(request, tenant, machine):
    """
    Start (power on) the specified machine.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.MachineSerializer(
            session.start_machine(machine),
            context = { "request": request, "tenant": tenant }
        )
    return response.Response(serializer.data)


@provider_api_view(["POST"])
def machine_stop(request, tenant, machine):
    """
    Stop (power off) the specified machine.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.MachineSerializer(
            session.stop_machine(machine),
            context = { "request": request, "tenant": tenant }
        )
    return response.Response(serializer.data)


@provider_api_view(["POST"])
def machine_restart(request, tenant, machine):
    """
    Restart (power cycle) the specified machine.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.MachineSerializer(
            session.restart_machine(machine),
            context = { "request": request, "tenant": tenant }
        )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def machine_console(request, tenant, machine):
    """
    Redirects the user to the web console for the specified machine.
    """
    # Make sure that the user has permission to access the machine
    with request.auth.scoped_session(tenant) as session:
        machine = session.find_machine(machine)
    # Check if the machine has the web console enabled
    # If not, render an error page
    if machine.metadata.get("web_console_enabled", "0") != "1":
        return render(request, "portal/console_not_available.html")
    # The subdomain is in the metadata of the machine
    subdomain = machine.metadata["apps_console_subdomain"]
    console_url = "http://{}.{}".format(subdomain, cloud_settings.APPS.BASE_DOMAIN)
    # Try to fetch the console URL without redirects
    # While it returns a 404, the console is not ready
    resp = requests.get(console_url, allow_redirects = False)
    if resp.status_code == status.HTTP_404_NOT_FOUND:
        return render(request, "portal/console_not_ready.html")
    else:
        return redirect(console_url)


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
            serializer = serializers.ExternalIPSerializer(session.allocate_external_ip())
        return response.Response(serializer.data, status = status.HTTP_201_CREATED)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.ExternalIPSerializer(
                session.external_ips(),
                many = True,
                context = { "request": request, "tenant": tenant }
            )
        return response.Response(serializer.data)


@provider_api_view(["GET", "PUT"])
def external_ip_details(request, tenant, ip):
    """
    On ``GET`` requests, return the details for the external IP address.

    On ``PUT`` requests, attach the specified machine to the external IP address.
    If the machine_id is ``null``, the external IP address will be detached from
    the machine it is currently attached to.
    The request body should contain the machine ID::

        { "machine_id": "<machine id>" }
    """
    if request.method == "PUT":
        input_serializer = serializers.ExternalIPSerializer(data = request.data)
        input_serializer.is_valid(raise_exception = True)
        machine_id = input_serializer.validated_data["machine_id"]
        with request.auth.scoped_session(tenant) as session:
            if machine_id:
                # If attaching, we need to check if NAT is permitted for the machine
                machine = session.find_machine(machine_id)
                if machine.metadata.get("nat_allowed", "1") == "0":
                    return response.Response(
                        {
                            "detail": "Machine is not allowed to have an external IP address.",
                            "code": "invalid_operation"
                        },
                        status = status.HTTP_409_CONFLICT
                    )
                ip = session.attach_external_ip(ip, str(machine_id))
            else:
                ip = session.detach_external_ip(ip)
        output_serializer = serializers.ExternalIPSerializer(
            ip,
            context = { "request": request, "tenant": tenant }
        )
        return response.Response(output_serializer.data)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.ExternalIPSerializer(
                session.find_external_ip(ip),
                context = { "request": request, "tenant": tenant }
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
    if request.method == "POST":
        input_serializer = serializers.CreateVolumeSerializer(data = request.data)
        input_serializer.is_valid(raise_exception = True)
        with request.auth.scoped_session(tenant) as session:
            output_serializer = serializers.VolumeSerializer(
                session.create_volume(
                    input_serializer.validated_data["name"],
                    input_serializer.validated_data["size"]
                ),
                context = { "request": request, "tenant": tenant }
            )
        return response.Response(output_serializer.data, status = status.HTTP_201_CREATED)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.VolumeSerializer(
                session.volumes(),
                many = True,
                context = { "request": request, "tenant": tenant }
            )
        return response.Response(serializer.data)


@provider_api_view(["GET", "PUT", "DELETE"])
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
    if request.method == "PUT":
        input_serializer = serializers.UpdateVolumeSerializer(data = request.data)
        input_serializer.is_valid(raise_exception = True)
        machine_id = input_serializer.validated_data["machine_id"]
        with request.auth.scoped_session(tenant) as session:
            if machine_id:
                volume = session.attach_volume(volume, str(machine_id))
            else:
                volume = session.detach_volume(volume)
        output_serializer = serializers.VolumeSerializer(
            volume,
            context = { "request": request, "tenant": tenant }
        )
        return response.Response(output_serializer.data)
    elif request.method == "DELETE":
        with request.auth.scoped_session(tenant) as session:
            deleted = session.delete_volume(volume)
        if deleted:
            serializer = serializers.VolumeSerializer(
                deleted,
                context = { "request": request, "tenant": tenant }
            )
            return response.Response(serializer.data)
        else:
            return response.Response()
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.VolumeSerializer(
                session.find_volume(volume),
                context = { "request": request, "tenant": tenant }
            )
        return response.Response(serializer.data)


@provider_api_view(["GET"])
def kubernetes_cluster_templates(request, tenant):
    """
    Return a list of the available Kubernetes cluster templates for the tenancy.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.KubernetesClusterTemplateSerializer(
            session.kubernetes_cluster_templates(),
            many = True,
            context = { "request": request, "tenant": tenant }
        )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def kubernetes_cluster_template_details(request, tenant, template):
    """
    Return the details for the specified Kubernetes cluster template.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.KubernetesClusterTemplateSerializer(
            session.find_kubernetes_cluster_template(template),
            context = { "request": request, "tenant": tenant }
        )
    return response.Response(serializer.data)


@provider_api_view(["GET", "POST"])
def kubernetes_clusters(request, tenant):
    """
    On ``GET`` requests, return a list of the deployed Kubernetes clusters for the tenancy.

    On ``POST`` requests, create a new Kubernetes cluster.
    """
    if request.method == "POST":
        with request.auth.scoped_session(tenant) as session:
            input_serializer = serializers.CreateKubernetesClusterSerializer(
                data = request.data,
                context = { "session": session }
            )
            input_serializer.is_valid(raise_exception = True)
            cluster = session.create_kubernetes_cluster(
                **input_serializer.validated_data,
                ssh_key = cloud_settings.SSH_KEY_STORE.get_key(
                    request.user.username,
                    # Pass the request and the sessions as keyword options
                    # so that the key store can use them if it needs to
                    request = request,
                    unscoped_session = request.auth,
                    scoped_session = session
                )
            )
        output_serializer = serializers.KubernetesClusterSerializer(
            cluster,
            context = { "request": request, "tenant": tenant }
        )
        return response.Response(output_serializer.data)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.KubernetesClusterSerializer(
                session.kubernetes_clusters(),
                many = True,
                context = { "request": request, "tenant": tenant }
            )
        return response.Response(serializer.data)


@provider_api_view(["GET", "DELETE"])
def kubernetes_cluster_details(request, tenant, cluster):
    """
    On ``GET`` requests, return the specified Kubernetes cluster.

    On ``DELETE`` requests, delete the specified Kubernetes cluster.
    """
    if request.method == "DELETE":
        with request.auth.scoped_session(tenant) as session:
            deleted = session.delete_kubernetes_cluster(cluster)
        if deleted:
            serializer = serializers.KubernetesClusterSerializer(
                deleted,
                context = { "request": request, "tenant": tenant }
            )
            return response.Response(serializer.data)
        else:
            return response.Response()
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.KubernetesClusterSerializer(
                session.find_kubernetes_cluster(cluster),
                context = { "request": request, "tenant": tenant }
            )
        return response.Response(serializer.data)


@provider_api_view(["POST"])
def kubernetes_cluster_generate_kubeconfig(request, tenant, cluster):
    """
    Generate a kubeconfig file for the specified cluster.
    """
    with request.auth.scoped_session(tenant) as session:
        kubeconfig = session.generate_kubeconfig_for_kubernetes_cluster(cluster)
    return response.Response({ "kubeconfig": kubeconfig })


@provider_api_view(["GET"])
def cluster_types(request, tenant):
    """
    Returns the cluster types available to the tenancy.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.ClusterTypeSerializer(
            session.cluster_types(),
            many = True,
            context = { "request": request, "tenant": tenant }
        )
    return response.Response(serializer.data)


@provider_api_view(["GET"])
def cluster_type_details(request, tenant, cluster_type):
    """
    Returns the requested cluster type.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.ClusterTypeSerializer(
            session.find_cluster_type(cluster_type),
            context = { "request": request, "tenant": tenant }
        )
    return response.Response(serializer.data)


@provider_api_view(["GET", "POST"])
def clusters(request, tenant):
    """
    On ``GET`` requests, return a list of the deployed clusters.

    On ``POST`` requests, create a new cluster.
    """
    if request.method == "POST":
        with request.auth.scoped_session(tenant) as session:
            input_serializer = serializers.CreateClusterSerializer(
                data = request.data,
                context = { "session": session }
            )
            input_serializer.is_valid(raise_exception = True)
            cluster = session.create_cluster(
                input_serializer.validated_data["name"],
                input_serializer.validated_data["cluster_type"],
                input_serializer.validated_data["parameter_values"],
                cloud_settings.SSH_KEY_STORE.get_key(
                    request.user.username,
                    # Pass the request and the sessions as keyword options
                    # so that the key store can use them if it needs to
                    request = request,
                    unscoped_session = request.auth,
                    scoped_session = session
                )
            )
        output_serializer = serializers.ClusterSerializer(
            cluster,
            context = { "request": request, "tenant": tenant }
        )
        return response.Response(output_serializer.data)
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.ClusterSerializer(
                session.clusters(),
                many = True,
                context = { "request": request, "tenant": tenant }
            )
        return response.Response(serializer.data)


@provider_api_view(["GET", "PUT", "DELETE"])
def cluster_details(request, tenant, cluster):
    """
    On ``GET`` requests, return the named cluster.

    On ``PUT`` requests, update the named cluster with the given paramters.

    On ``DELETE`` requests, delete the named cluster.
    """
    if request.method == "PUT":
        with request.auth.scoped_session(tenant) as session:
            cluster = session.find_cluster(cluster)
            input_serializer = serializers.UpdateClusterSerializer(
                data = request.data,
                context = dict(session = session, cluster = cluster)
            )
            input_serializer.is_valid(raise_exception = True)
            updated = session.update_cluster(
                cluster,
                input_serializer.validated_data["parameter_values"]
            )
        output_serializer = serializers.ClusterSerializer(
            updated,
            context = { "request": request, "tenant": tenant }
        )
        return response.Response(output_serializer.data)
    elif request.method == "DELETE":
        with request.auth.scoped_session(tenant) as session:
            deleted = session.delete_cluster(cluster)
        if deleted:
            serializer = serializers.ClusterSerializer(
                deleted,
                context = { "request": request, "tenant": tenant }
            )
            return response.Response(serializer.data)
        else:
            return response.Response()
    else:
        with request.auth.scoped_session(tenant) as session:
            serializer = serializers.ClusterSerializer(
                session.find_cluster(cluster),
                context = { "request": request, "tenant": tenant }
            )
        return response.Response(serializer.data)


@provider_api_view(["POST"])
def cluster_patch(request, tenant, cluster):
    """
    Patch the given cluster.
    """
    with request.auth.scoped_session(tenant) as session:
        serializer = serializers.ClusterSerializer(
            session.patch_cluster(cluster),
            context = { "request": request, "tenant": tenant }
        )
    return response.Response(serializer.data)
